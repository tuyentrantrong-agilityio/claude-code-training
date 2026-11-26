"""Chunking, rank fusion, prompt and citation helpers for search and Ask."""

import asyncio
import uuid
from typing import Any

import pytest

from app.providers.base import ProviderError, ProviderTimeout
from app.providers.fakes import FakeLlm
from app.providers.metering import MeteredLlm
from app.providers.types import ASK_MARKER, ChatMessage
from app.services import ask
from app.services.indexing import IndexLine, build_chunks, vector_literal


def line(start: int, end: int, text: str = "hello", speaker: str = "Speaker 1") -> IndexLine:
    return IndexLine(start, end, speaker, text)


# ---- chunking ----


def test_no_lines_no_chunks() -> None:
    assert build_chunks([]) == []


def test_lines_are_grouped_with_speaker_prefix() -> None:
    chunks = build_chunks([line(0, 900, "Hi"), line(1000, 1900, "Yes", "Speaker 2")])
    assert len(chunks) == 1
    assert chunks[0].text == "Speaker 1: Hi\nSpeaker 2: Yes"
    assert (chunks[0].seq, chunks[0].start_ms, chunks[0].end_ms) == (0, 0, 1900)


def test_chunk_breaks_after_about_60_seconds() -> None:
    lines = [line(i * 10_000, i * 10_000 + 9_000) for i in range(8)]
    chunks = build_chunks(lines)
    # 0-59 s fits (a line ending at exactly 60 s is allowed); the 7th line ends at 69 s.
    assert [(c.seq, c.start_ms, c.end_ms) for c in chunks] == [(0, 0, 59_000), (1, 60_000, 79_000)]
    assert chunks[0].text.count("\n") == 5


def test_chunk_breaks_at_800_characters() -> None:
    text = "x" * 190  # rendered line is 190 + len("Speaker 1: ") = 201 characters
    chunks = build_chunks([line(i * 1000, i * 1000 + 500, text) for i in range(5)])
    assert [c.text.count("\n") + 1 for c in chunks] == [3, 2]
    assert all(len(c.text) <= 800 for c in chunks)
    assert chunks[1].start_ms == 3000


def test_long_segment_is_never_split() -> None:
    chunks = build_chunks([line(0, 100, "short"), line(200, 300, "y" * 2000), line(400, 500)])
    assert len(chunks) == 3
    assert len(chunks[1].text) > 800
    assert [c.seq for c in chunks] == [0, 1, 2]


# ---- rank fusion ----


def test_rrf_scores_and_order() -> None:
    merged = ask.rrf_merge([["a", "b", "c"], ["c", "a", "d"]], k=60)
    # a: 1/61 + 1/62, c: 1/63 + 1/61, b: 1/62, d: 1/63
    assert merged == ["a", "c", "b", "d"]


def test_rrf_item_in_both_lists_beats_single_list_leader() -> None:
    assert ask.rrf_merge([["x", "y"], ["z", "y"]])[0] == "y"


def test_rrf_limit_and_empty() -> None:
    assert ask.rrf_merge([["a", "b", "c"], ["d"]], limit=2) == ["a", "d"]
    assert ask.rrf_merge([[], []]) == []


# ---- prompt and citations ----


def chunk(n: int, title: str = "Weekly sync", start_ms: int = 75_000) -> ask.RetrievedChunk:
    return ask.RetrievedChunk(
        uuid.uuid4(), uuid.uuid4(), title, start_ms, f"Speaker 1: line {n}\nSpeaker 2: more {n}"
    )


def test_prompt_has_marker_labels_titles_and_question() -> None:
    messages = ask.build_messages("What was decided?", [chunk(1), chunk(2, "Other\nmeeting", 0)])
    assert messages[0].role == "system" and messages[1].role == "user"
    user = messages[1].content
    assert ASK_MARKER in user
    assert "[c1] Weekly sync, 01:15\nSpeaker 1: line 1" in user
    assert "[c2] Other meeting, 00:00\nSpeaker 1: line 2" in user
    assert user.rstrip().endswith("Question: What was decided?")
    assert "only" in user and "[c1]" in user


def test_cited_indexes_keep_known_labels_once_in_order() -> None:
    text = "A [c2]. B [c1][c2]. C [c9] [c0] [c3]."
    assert ask.cited_indexes(text, 3) == [1, 0, 2]
    assert ask.cited_indexes("no labels here", 3) == []
    assert ask.cited_indexes("[c1]", 0) == []


def test_strip_labels() -> None:
    assert ask.strip_labels("The team agreed [c1]. Also this [c2][c3].") == (
        "The team agreed. Also this."
    )
    assert ask.strip_labels("[c1] starts here") == "starts here"
    assert ask.strip_labels("keep [text] and c1") == "keep [text] and c1"


def test_vector_literal() -> None:
    assert vector_literal([1, 0.5, -0.25]) == "[1.0,0.5,-0.25]"


def test_not_found_wording() -> None:
    assert "your meetings" in ask.not_found_text(False)
    assert "this meeting" in ask.not_found_text(True)


# ---- fake LLM and metered stream ----


async def test_fake_llm_answers_from_ask_prompt_and_cites() -> None:
    messages = ask.build_messages("q?", [chunk(1), chunk(2), chunk(3)])
    text = "".join([p async for p in FakeLlm().stream(messages, max_tokens=50)])
    assert text.startswith("According to the meeting, line 1 [c1]. Also, line 2 [c2].")
    assert "[c3]" not in text


async def test_fake_llm_stream_without_marker_is_canned() -> None:
    parts = [p async for p in FakeLlm().stream([ChatMessage("user", "x")], max_tokens=5)]
    assert "".join(parts).strip() == FakeLlm.canned


class _Session:
    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        return None


def metered(llm: Any, timeout: float = 5) -> tuple[MeteredLlm, _Session]:
    session = _Session()
    return MeteredLlm(llm, session, None, timeout=timeout), session  # type: ignore[arg-type]


async def test_metered_stream_records_usage_after_the_stream() -> None:
    wrapper, session = metered(FakeLlm())
    stream = wrapper.stream([ChatMessage("user", "one two three")], max_tokens=10)
    first = await anext(stream)
    assert first and session.added == []  # nothing recorded while streaming
    rest = [p async for p in stream]
    assert (first + "".join(rest)).strip() == FakeLlm.canned
    usage = {(r.unit_kind): int(r.units) for r in session.added}
    assert usage == {"input_tokens": 3, "output_tokens": len(FakeLlm.canned.split())}
    assert all(r.meeting_id is None and r.function == "llm" for r in session.added)


async def test_metered_stream_provider_error_records_nothing() -> None:
    wrapper, session = metered(FakeLlm(fail_times=1, retryable=True))
    with pytest.raises(ProviderError):
        _ = [p async for p in wrapper.stream([ChatMessage("user", "x")], max_tokens=5)]
    assert session.added == []


class _SlowStream(FakeLlm):
    async def stream(self, messages: list[ChatMessage], *, max_tokens: int) -> Any:
        for _ in range(100):
            await asyncio.sleep(0.02)
            yield "w "


async def test_metered_stream_timeout_covers_the_whole_stream() -> None:
    wrapper, session = metered(_SlowStream(), timeout=0.1)
    seen: list[str] = []
    with pytest.raises(ProviderTimeout):
        async for piece in wrapper.stream([ChatMessage("user", "x")], max_tokens=5):
            seen.append(piece)
    assert 0 < len(seen) < 100  # each piece was quick, the total was too long
    assert session.added == []
