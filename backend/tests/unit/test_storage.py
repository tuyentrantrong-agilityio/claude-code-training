import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.storage import InvalidStorageKeyError, LocalStorage, meeting_key, validate_key

KEY = "org_0123456789ab/11111111-1111-1111-1111-111111111111/audio.wav"


@pytest.mark.parametrize(
    "key",
    [
        "../x/y/z",
        "a/b/../c",
        "a/b/..",
        "/etc/passwd",
        "a/b",
        "a/b/c/d",
        "a//c",
        "a/b/c d",
        "a/b/.hidden",
        "a/b/c\\d",
        "a/b/",
        "",
    ],
)
def test_bad_keys_rejected(key: str) -> None:
    with pytest.raises(InvalidStorageKeyError):
        validate_key(key)


def test_good_key() -> None:
    assert validate_key(KEY)[2] == "audio.wav"
    assert meeting_key("org_0123456789ab", uuid.UUID(int=1), "original.mp3").endswith(
        "/original.mp3"
    )


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


async def test_local_storage_roundtrip(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "rec")
    assert not await storage.exists(KEY)
    assert await storage.save(_stream(b"abc", b"de"), KEY) == 5
    assert await storage.exists(KEY)
    assert storage.open(KEY).read_bytes() == b"abcde"
    await storage.delete(KEY)
    await storage.delete(KEY)  # deleting twice is fine
    assert not await storage.exists(KEY)
    assert not (tmp_path / "rec" / KEY.split("/")[0] / KEY.split("/")[1]).exists()


async def test_failed_save_leaves_no_file(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    async def broken() -> AsyncIterator[bytes]:
        yield b"abc"
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await storage.save(broken(), KEY)
    assert not await storage.exists(KEY)
    assert list(tmp_path.rglob("*.part")) == []


def test_traversal_rejected_by_storage(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    with pytest.raises(InvalidStorageKeyError):
        storage.open("a/../../etc")


def test_root_is_absolute() -> None:
    assert LocalStorage("./data/recordings").root.is_absolute()
