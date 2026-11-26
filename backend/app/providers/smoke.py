"""Smoke check for the configured providers: one tiny real call per function.

Usage: uv run python -m app.providers.smoke [--stt path.wav] [--llm] [--embedding]
"""

import argparse
import asyncio
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.providers.registry import get_batch_stt, get_embedding, get_llm
from app.providers.types import ChatMessage

Out = Callable[[str], None]


async def _timed[T](call: Awaitable[T]) -> tuple[T, int]:
    started = time.perf_counter()
    result = await call
    return result, round((time.perf_counter() - started) * 1000)


async def _stt(path: Path, out: Out) -> bool:
    provider = get_batch_stt()
    if provider.name == "fake":
        out("stt: provider is fake (set PROVIDER_STT_BATCH), skipped")
        return False
    language = "vi"
    result, ms = await _timed(provider.transcribe(path, language))
    out(
        f"stt: {provider.name} {ms} ms, duration {result.duration_ms} ms, "
        f"{len(result.segments)} segments"
    )
    return True


async def _llm(out: Out) -> bool:
    provider = get_llm()
    if provider.name == "fake":
        out("llm: provider is fake (set PROVIDER_LLM), skipped")
        return False
    messages = [ChatMessage("user", "Reply with OK")]
    result, ms = await _timed(provider.complete(messages, max_tokens=16))
    out(
        f"llm: {provider.name} {ms} ms, {len(result.text)} chars, "
        f"tokens in/out {result.input_tokens}/{result.output_tokens}"
    )
    return True


async def _embedding(out: Out) -> bool:
    provider = get_embedding()
    if provider.name == "fake":
        out("embedding: provider is fake (set PROVIDER_EMBEDDING), skipped")
        return False
    result, ms = await _timed(provider.embed(["hello"]))
    out(
        f"embedding: {provider.name} {ms} ms, {len(result.vectors)} vector(s) of "
        f"{len(result.vectors[0]) if result.vectors else 0} dims, tokens {result.input_tokens}"
    )
    return True


async def run(args: argparse.Namespace, out: Out = print) -> int:
    """Run the requested checks; exit code 0 only if every requested one ran for real."""
    ok = True
    if args.stt is not None:
        ok = await _stt(args.stt, out) and ok
    if args.llm:
        ok = await _llm(out) and ok
    if args.embedding:
        ok = await _embedding(out) and ok
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.providers.smoke")
    parser.add_argument("--stt", type=Path, metavar="WAV", help="transcribe this wav file")
    parser.add_argument("--llm", action="store_true", help="one tiny LLM call")
    parser.add_argument("--embedding", action="store_true", help="embed one word")
    args = parser.parse_args(argv)
    if args.stt is None and not args.llm and not args.embedding:
        parser.error("choose at least one of --stt, --llm, --embedding")
    try:
        return asyncio.run(run(args))
    except Exception as exc:  # report the class and message only, never keys or payloads
        print(f"smoke failed: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
