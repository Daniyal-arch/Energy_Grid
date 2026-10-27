"""JSON logs (one object per line, CloudWatch-friendly) with the request and trace ids."""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time

request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)

_STD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if rid := request_id.get():
            out["request_id"] = rid
        if tid := trace_id.get():
            out["trace_id"] = tid
        for k, v in record.__dict__.items():
            if k not in _STD and not k.startswith("_"):
                out[k] = v
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root.handlers = [h]
    root.setLevel(level)
    for noisy in ("httpx", "httpcore", "botocore", "urllib3", "mcp"):
        logging.getLogger(noisy).setLevel("WARNING")
