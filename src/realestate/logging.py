from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

_RESERVED_ATTRS = set(logging.makeLogRecord({}).__dict__)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(*, structured: bool) -> None:
    if not structured:
        return
    root = logging.getLogger()
    if any(getattr(handler, "_realestate_structured", False) for handler in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler._realestate_structured = True  # type: ignore[attr-defined]
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
