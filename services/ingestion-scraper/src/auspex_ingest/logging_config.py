import os
from collections.abc import MutableMapping
from typing import Any

import structlog

_SENSITIVE_EXACT: frozenset[str] = frozenset({"raw_content", "api_key", "access_key", "secret_key"})
_SENSITIVE_CONTAINS: tuple[str, ...] = ("password", "secret")


class SensitiveFieldDrop:
    def __call__(self, logger: Any, method: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
        return {
            k: v for k, v in event_dict.items()
            if k not in _SENSITIVE_EXACT
            and not any(p in k for p in _SENSITIVE_CONTAINS)
        }


def configure_logging() -> None:
    log_format = os.getenv("LOG_FORMAT", "json")
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="@timestamp"),
        SensitiveFieldDrop(),
    ]
    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
