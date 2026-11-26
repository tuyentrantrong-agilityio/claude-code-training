import json
import uuid
import wave
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.providers.fakes import FakeBatchStt, FakeLlm
from app.providers.types import RECAP_MARKER, ChatMessage
from app.services.recap import (
    Member,
    PromptLine,
    Recap,
    RecapParseError,
    build_messages,
    key_point_title,
    match_owner,
    parse_recap,
    snap_at_ms,
    validate_recap,
)
from app.services.reports import ParticipantPatch, format_mmss, slugify

LINES = [PromptLine(0, "Speaker 1", "Hello all."), PromptLine(4000, "Speaker 2", "I will ship it.")]


def test_build_messages_has_marker_lines_and_language() -> None:
    system, user = build_messages(LINES, "vi")
    assert system.role == "system" and user.role == "user"
    assert user.content.startswith(RECAP_MARKER)
    assert "[at_ms=0] Speaker 1: Hello all." in user.content
    assert "[at_ms=4000] Speaker 2: I will ship it." in user.content
    assert "Vietnamese" in user.content and '"follow_ups"' in user.content
    assert "English" in build_messages(LINES, "en")[1].content


def test_parse_full_recap_and_defaults() -> None:
    raw = json.dumps(
        {
            "summary": "  Done.  ",
            "follow_ups": [{"text": "Send it", "owner": "Ann", "at_ms": 10}],
            "key_points": [{"text": "Point", "at_ms": 5}],
            "chapters": [{"title": "Intro", "at_ms": 0}],
            "highlights": [{"text": "Wow", "at_ms": 1}],
            "questions": [{"text": "Why?", "at_ms": 2}],
        }
    )
    recap = parse_recap(raw)
    assert recap.summary == "Done."
    assert (recap.follow_ups[0].owner, recap.follow_ups[0].at_ms) == ("Ann", 10)
    assert recap.key_points[0].title is None
    assert len(recap.chapters) == len(recap.highlights) == len(recap.questions) == 1


def test_parse_missing_lists_are_empty_and_bad_items_skipped() -> None:
    recap = parse_recap(json.dumps({"summary": "S", "follow_ups": [{"owner": "x"}, "oops", {}]}))
    assert recap.follow_ups == [] and recap.key_points == [] and recap.questions == []
    blank = parse_recap(json.dumps({"highlights": [{"text": "  "}, {"text": "ok"}]}))
    assert [h.text for h in blank.highlights] == ["ok"]
    assert parse_recap('{"summary": null}').summary == ""


def test_parse_accepts_code_fence() -> None:
    assert parse_recap('```json\n{"summary": "S"}\n```').summary == "S"


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", '{"summary": 5}', ""])
def test_parse_rejects_unusable_replies(raw: str) -> None:
    with pytest.raises(RecapParseError):
        parse_recap(raw)


def test_snap_at_ms() -> None:
    starts = [0, 1000, 4000]
    assert [snap_at_ms(v, starts) for v in (0, 999, 1000, 3999, 4000, 9000)] == [
        0,
        0,
        1000,
        1000,
        4000,
        4000,
    ]
    assert snap_at_ms(50, [100, 200]) == 100  # before the first segment


def test_validate_drops_out_of_range_and_snaps() -> None:
    recap = parse_recap(
        json.dumps(
            {
                "follow_ups": [
                    {"text": "ok", "at_ms": 2500},
                    {"text": "negative", "at_ms": -1},
                    {"text": "too late", "at_ms": 10001},
                    {"text": "no time"},
                ],
                "chapters": [{"title": "End", "at_ms": 10000}],
            }
        )
    )
    checked = validate_recap(recap, [0, 2000, 6000], 10000)
    assert [(f.text, f.at_ms) for f in checked.follow_ups] == [("ok", 2000), ("no time", None)]
    assert [(c.title, c.at_ms) for c in checked.chapters] == [("End", 6000)]
    # Without a known duration only negative times are dropped.
    assert len(validate_recap(recap, [0], None).follow_ups) == 3


def test_key_point_title_uses_first_words() -> None:
    assert key_point_title("Given", "ignored") == "Given"
    assert key_point_title(None, "one two three four five six seven eight") == (
        "one two three four five six"
    )
    assert key_point_title("  ", "short text") == "short text"


def test_match_owner() -> None:
    ann, bob = uuid.uuid4(), uuid.uuid4()
    members = [Member(ann, "Ann Lee", "alee@example.com"), Member(bob, "Bob", "bob.x@example.com")]
    assert match_owner("ann lee", members) == ann
    assert match_owner(" ALEE ", members) == ann
    assert match_owner("Bob.X", members) == bob
    assert match_owner("Ann", members) is None
    assert match_owner("", members) is None and match_owner(None, members) is None
    twins = [*members, Member(uuid.uuid4(), "BOB", "other@example.com")]
    assert match_owner("bob", twins) is None  # ambiguous


def test_format_mmss() -> None:
    assert [format_mmss(v) for v in (0, 999, 1000, 65_000, 3_600_000, None)] == [
        "00:00",
        "00:00",
        "00:01",
        "01:05",
        "60:00",
        "00:00",
    ]


def test_slugify() -> None:
    assert slugify("Weekly Product Sync!") == "weekly-product-sync"
    assert slugify("Cu\u1ed9c h\u1ecdp \u0110\u00e0 N\u1eb5ng") == "cuoc-hop-da-nang"
    assert slugify("  ---  ") == "meeting" and slugify("") == "meeting"
    assert len(slugify("a" * 200)) == 60


def test_participant_patch_trims_and_limits() -> None:
    assert ParticipantPatch(display_name="  Ann  ").display_name == "Ann"
    for bad in ("", "   ", "x" * 81):
        with pytest.raises(ValidationError):
            ParticipantPatch(display_name=bad)
    assert len(ParticipantPatch(display_name="x" * 80).display_name) == 80


async def test_fake_llm_derives_recap_from_prompt_lines() -> None:
    user = build_messages(
        [
            PromptLine(0, "Speaker 1", "Welcome to the sync."),
            PromptLine(2000, "Speaker 2", "I will send the report today."),
            PromptLine(4000, "Speaker 1", "Can we ship it?"),
        ],
        "en",
    )
    result = await FakeLlm().complete(user, max_tokens=100, json_mode=True)
    recap = validate_recap(parse_recap(result.text), [0, 2000, 4000], 6000)
    assert [(f.owner, f.text, f.at_ms) for f in recap.follow_ups] == [
        ("Speaker 2", "I will send the report today.", 2000)
    ]
    assert [q.text for q in recap.questions] == ["Can we ship it?"]
    assert recap.summary and recap.chapters and recap.key_points and recap.highlights
    plain = await FakeLlm().complete([ChatMessage("user", "x")], max_tokens=1, json_mode=True)
    assert "text" in json.loads(plain.text)


def test_recap_default_is_empty() -> None:
    assert Recap().follow_ups == [] and Recap().summary == ""


async def test_fake_stt_demo_script_follows_audio_duration_and_language(tmp_path: Path) -> None:
    audio = tmp_path / "standup.wav"
    with wave.open(str(audio), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 8000 * 16)
    result = await FakeBatchStt().transcribe(audio, "vi")
    assert result.duration_ms == 16_000 and len(result.segments) == 8
    assert result.segments[-1].end_ms <= 16_000
    assert [s.start_ms for s in result.segments] == sorted(s.start_ms for s in result.segments)
    assert "T\u00f4i s\u1ebd" in result.segments[3].text
    english = await FakeBatchStt().transcribe(audio, "en")
    assert "I will send the release note today." in [s.text for s in english.segments]
