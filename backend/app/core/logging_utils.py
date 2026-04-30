"""Structured logging helpers for pipeline observability."""

from __future__ import annotations

import json


def log_structured(logger, event: str, **fields) -> None:
    """Emit a single JSON log line with a stable event name."""
    logger.info(json.dumps({"event": event, **fields}, default=str, sort_keys=True))
