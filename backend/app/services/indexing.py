"""Search index: turn transcript lines into chunks and store them with their embeddings."""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.org import SearchChunk

CHUNK_MAX_MS = 60_000
CHUNK_MAX_CHARS = 800


@dataclass(frozen=True)
class IndexLine:
    """One transcript segment with its speaker name."""

    start_ms: int
    end_ms: int
    speaker: str
    text: str


@dataclass(frozen=True)
class Chunk:
    seq: int
    start_ms: int
    end_ms: int
    text: str


def build_chunks(
    lines: list[IndexLine], max_ms: int = CHUNK_MAX_MS, max_chars: int = CHUNK_MAX_CHARS
) -> list[Chunk]:
    """Group consecutive lines until a chunk would pass max_ms or max_chars.

    A chunk spans from its first line start to its last line end and holds one
    "Speaker: text" line per segment. A segment is never split, so a single long segment
    can make a chunk longer than max_chars.
    """
    chunks: list[Chunk] = []
    texts: list[str] = []
    start = end = size = 0

    def flush() -> None:
        if texts:
            chunks.append(Chunk(len(chunks), start, end, "\n".join(texts)))
            texts.clear()

    for line in lines:
        rendered = f"{line.speaker}: {line.text}"
        if texts and (
            line.end_ms - start > max_ms or size + 1 + len(rendered) > max_chars  # +1: newline
        ):
            flush()
        if not texts:
            start, size = line.start_ms, 0
        else:
            size += 1
        texts.append(rendered)
        size += len(rendered)
        end = max(line.end_ms, line.start_ms)
    flush()
    return chunks


def vector_literal(vector: list[float]) -> str:
    """pgvector text form, for example "[0.1,0.2]"."""
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


async def delete_chunks(session: AsyncSession, meeting_id: uuid.UUID) -> None:
    await session.execute(delete(SearchChunk).where(SearchChunk.meeting_id == meeting_id))


async def replace_chunks(
    session: AsyncSession, meeting_id: uuid.UUID, chunks: list[Chunk], vectors: list[list[float]]
) -> None:
    """Replace the meeting's chunks in the caller's transaction."""
    if len(chunks) != len(vectors):
        raise ValueError("one embedding is needed for each chunk")
    await delete_chunks(session, meeting_id)
    if not chunks:
        return
    # The vector goes in as text and is cast on the server (no vector codec needed).
    await session.execute(
        text(
            "INSERT INTO search_chunks (meeting_id, seq, start_ms, end_ms, text, embedding) "
            "VALUES (:meeting_id, :seq, :start_ms, :end_ms, :text, "
            "CAST(CAST(:embedding AS text) AS vector))"
        ),
        [
            {
                "meeting_id": meeting_id,
                "seq": c.seq,
                "start_ms": c.start_ms,
                "end_ms": c.end_ms,
                "text": c.text,
                "embedding": vector_literal(v),
            }
            for c, v in zip(chunks, vectors, strict=True)
        ],
    )
