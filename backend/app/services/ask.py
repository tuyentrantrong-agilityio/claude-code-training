"""Ask: hybrid retrieval over meeting chunks, prompt building and citation handling."""

import re
import uuid
from collections.abc import Hashable
from dataclasses import dataclass

from sqlalchemy import Float, Select, Text, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.org import Meeting, SearchChunk, Vector
from app.providers.metering import MeteredEmbedding
from app.providers.registry import get_embedding
from app.providers.types import ASK_MARKER, ChatMessage
from app.services.indexing import vector_literal
from app.services.reports import format_mmss

CANDIDATES = 20
RRF_K = 60
DEFAULT_LIMIT = 8

NOT_FOUND_ALL = (
    "I could not find that in your meetings. Try different words, or ask across all meetings."
)
NOT_FOUND_SCOPED = (
    "I could not find that in this meeting. Try different words, or ask across all meetings."
)
SYSTEM_PROMPT = (
    "You answer questions about the user's meetings. Use only the excerpts you are given. "
    "If they do not contain the answer, say so."
)
INSTRUCTIONS = """\
{marker}
Answer the question using only the numbered excerpts below. After each statement, cite the
excerpts that support it with their labels in square brackets, for example [c1]. Do not
cite a label that is not listed. Answer in the language of the question.

Excerpts:
{excerpts}

Question: {question}
"""
_LABEL_RE = re.compile(r"\[c(\d+)\]")
_LABEL_WITH_SPACE_RE = re.compile(r"[ \t]*\[c\d+\]")


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    meeting_id: uuid.UUID
    meeting_title: str
    start_ms: int
    text: str


def not_found_text(scoped: bool) -> str:
    return NOT_FOUND_SCOPED if scoped else NOT_FOUND_ALL


# ---- ranking ----


def rrf_merge[K: Hashable](
    rankings: list[list[K]], k: int = RRF_K, limit: int | None = None
) -> list[K]:
    """Reciprocal rank fusion: score(item) = sum of 1 / (k + rank), rank starting at 1.

    Ties keep the order of first appearance (earlier lists first).
    """
    scores: dict[K, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores, key=lambda item: -scores[item])  # stable sort
    return ordered if limit is None else ordered[:limit]


# ---- retrieval ----


def _base_query(scope_meeting_id: uuid.UUID | None) -> Select[uuid.UUID]:
    stmt = (
        select(SearchChunk.id)
        .join(Meeting, Meeting.id == SearchChunk.meeting_id)
        .where(Meeting.status == "ready", Meeting.deleted_at.is_(None))
    )
    if scope_meeting_id is not None:
        stmt = stmt.where(SearchChunk.meeting_id == scope_meeting_id)
    return stmt


async def search(
    session: AsyncSession,
    question: str,
    scope_meeting_id: uuid.UUID | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[RetrievedChunk]:
    """Best chunks for a question: full text and vector rankings merged with RRF."""
    ts_query = func.plainto_tsquery("simple", question)
    full_text = list(
        await session.scalars(
            _base_query(scope_meeting_id)
            .where(SearchChunk.tsv.op("@@")(ts_query))
            .order_by(func.ts_rank(SearchChunk.tsv, ts_query).desc(), SearchChunk.id)
            .limit(CANDIDATES)
        )
    )
    embedder = MeteredEmbedding(get_embedding(), session, None)
    query_vector = (await embedder.embed([question])).vectors[0]
    literal = cast(cast(vector_literal(query_vector), Text), Vector())
    distance = SearchChunk.embedding.op("<=>", return_type=Float)(literal)
    by_vector = list(
        await session.scalars(
            _base_query(scope_meeting_id)
            .where(
                SearchChunk.embedding.is_not(None),
                func.vector_dims(SearchChunk.embedding) == len(query_vector),
            )
            .order_by(distance, SearchChunk.id)
            .limit(CANDIDATES)
        )
    )
    top = rrf_merge([full_text, by_vector], limit=limit)
    if not top:
        return []
    rows = (
        await session.execute(
            select(
                SearchChunk.id,
                SearchChunk.meeting_id,
                Meeting.title,
                SearchChunk.start_ms,
                SearchChunk.text,
            )
            .join(Meeting, Meeting.id == SearchChunk.meeting_id)
            .where(SearchChunk.id.in_(top))
        )
    ).all()
    found = {r[0]: RetrievedChunk(r[0], r[1], r[2], r[3], r[4]) for r in rows}
    return [found[i] for i in top]


# ---- prompt and citations ----


def chunk_label(index: int) -> str:
    """Label of the chunk at a 0-based position: c1, c2, ..."""
    return f"c{index + 1}"


def build_messages(question: str, chunks: list[RetrievedChunk]) -> list[ChatMessage]:
    excerpts = "\n\n".join(
        f"[{chunk_label(i)}] {' '.join(c.meeting_title.split())}, {format_mmss(c.start_ms)}\n"
        f"{c.text}"
        for i, c in enumerate(chunks)
    )
    user = INSTRUCTIONS.format(marker=ASK_MARKER, excerpts=excerpts, question=question)
    return [ChatMessage("system", SYSTEM_PROMPT), ChatMessage("user", user)]


def cited_indexes(text: str, count: int) -> list[int]:
    """0-based chunk positions cited as [cN]: only labels that exist, once, in order."""
    found: list[int] = []
    for match in _LABEL_RE.finditer(text):
        index = int(match.group(1)) - 1
        if 0 <= index < count and index not in found:
            found.append(index)
    return found


def strip_labels(text: str) -> str:
    """Remove every [cN] label (with the space before it)."""
    return _LABEL_WITH_SPACE_RE.sub("", text).strip()
