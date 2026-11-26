"""Job handlers. Importing this package registers them in the registry."""

from app.jobs.handlers import decode, index, recap, transcribe

__all__ = ["decode", "index", "recap", "transcribe"]
