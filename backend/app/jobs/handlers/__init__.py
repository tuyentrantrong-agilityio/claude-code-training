"""Job handlers. Importing this package registers them in the registry."""

from app.jobs.handlers import decode, transcribe

__all__ = ["decode", "transcribe"]
