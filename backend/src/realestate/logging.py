from __future__ import annotations

import json
import logging
import sys
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
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler._realestate_structured = True  # type: ignore[attr-defined]
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)

    app_logger = logging.getLogger("realestate")
    app_logger.setLevel(logging.INFO)
    app_logger.disabled = False
    app_logger.propagate = True
