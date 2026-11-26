"""HTTP Range header parsing for a single byte range."""

import re
from dataclasses import dataclass

RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


class RangeNotSatisfiableError(Exception):
    pass


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int  # inclusive

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_range(header: str | None, size: int) -> ByteRange | None:
    """Return the requested range, None to serve the whole file.

    Malformed or multi-range headers are ignored (whole file). A range that starts past
    the end raises RangeNotSatisfiableError.
    """
    if not header:
        return None
    match = RANGE_RE.fullmatch(header.strip())
    if match is None:
        return None
    first, last = match.groups()
    if not first and not last:
        return None
    if not first:  # suffix: the last N bytes
        count = int(last)
        if count == 0 or size == 0:
            raise RangeNotSatisfiableError
        return ByteRange(max(size - count, 0), size - 1)
    start = int(first)
    if start >= size:
        raise RangeNotSatisfiableError
    end = int(last) if last else size - 1
    if end < start:
        return None
    return ByteRange(start, min(end, size - 1))
