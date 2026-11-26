import pytest

from app.services.ranges import ByteRange, RangeNotSatisfiableError, parse_range


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("bytes=0-99", ByteRange(0, 99)),
        ("bytes=10-", ByteRange(10, 999)),
        ("bytes=-100", ByteRange(900, 999)),
        ("bytes=900-5000", ByteRange(900, 999)),
        ("bytes=-5000", ByteRange(0, 999)),
        ("bytes=5-5", ByteRange(5, 5)),
        (None, None),
        ("", None),
        ("bytes=-", None),
        ("bytes=9-3", None),
        ("bytes=0-1,5-6", None),
        ("items=0-1", None),
        ("garbage", None),
    ],
)
def test_parse_range(header: str | None, expected: ByteRange | None) -> None:
    assert parse_range(header, 1000) == expected


@pytest.mark.parametrize("header", ["bytes=1000-", "bytes=2000-3000", "bytes=-0"])
def test_unsatisfiable(header: str) -> None:
    with pytest.raises(RangeNotSatisfiableError):
        parse_range(header, 1000)


def test_length() -> None:
    assert ByteRange(10, 19).length == 10
