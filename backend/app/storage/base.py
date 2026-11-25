"""File storage for recordings. Keys look like "<schema>/<meeting_id>/<name>"."""

import asyncio
import contextlib
import os
import re
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

from app.core.settings import get_settings

SEGMENT_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
KEY_PARTS = 3
CHUNK_SIZE = 1024 * 1024


class InvalidStorageKeyError(ValueError):
    pass


def validate_key(key: str) -> list[str]:
    """Return the key segments, or raise when the key could leave the storage root."""
    parts = key.split("/")
    if len(parts) != KEY_PARTS:
        raise InvalidStorageKeyError(f"storage key must have {KEY_PARTS} parts: {key!r}")
    for part in parts:
        if not SEGMENT_RE.fullmatch(part) or part in (".", ".."):
            raise InvalidStorageKeyError(f"invalid storage key segment: {part!r}")
    return parts


def meeting_key(schema_name: str, meeting_id: uuid.UUID, name: str) -> str:
    key = f"{schema_name}/{meeting_id}/{name}"
    validate_key(key)
    return key


class Storage(Protocol):
    async def save(self, stream: AsyncIterator[bytes], key: str) -> int:
        """Write the stream under key and return the size in bytes."""
        ...

    def open(self, key: str) -> Path:
        """Return a readable local path for the key."""
        ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def _path(self, key: str) -> Path:
        path = self.root.joinpath(*validate_key(key)).resolve()
        if not path.is_relative_to(self.root):
            raise InvalidStorageKeyError(f"key escapes the storage root: {key!r}")
        return path

    async def save(self, stream: AsyncIterator[bytes], key: str) -> int:
        path = self._path(key)
        tmp = path.with_name(path.name + ".part")
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        size = 0
        try:
            with tmp.open("wb") as out:
                async for chunk in stream:
                    await asyncio.to_thread(out.write, chunk)
                    size += len(chunk)
            await asyncio.to_thread(os.replace, tmp, path)
        except BaseException:
            with contextlib.suppress(OSError):
                tmp.unlink()
            raise
        return size

    def open(self, key: str) -> Path:
        return self._path(key)

    async def delete(self, key: str) -> None:
        path = self._path(key)

        def _remove() -> None:
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
            with contextlib.suppress(OSError):  # only removes empty directories
                path.parent.rmdir()

        await asyncio.to_thread(_remove)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._path(key).is_file)


def get_storage() -> Storage:
    return LocalStorage(get_settings().storage_dir)


async def iter_file(path: Path, start: int = 0, end: int | None = None) -> AsyncIterator[bytes]:
    """Yield the bytes of path from start up to end (inclusive) in chunks."""
    remaining = None if end is None else end - start + 1
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining is None or remaining > 0:
            size = CHUNK_SIZE if remaining is None else min(CHUNK_SIZE, remaining)
            chunk = await asyncio.to_thread(handle.read, size)
            if not chunk:
                return
            if remaining is not None:
                remaining -= len(chunk)
            yield chunk
