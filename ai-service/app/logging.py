import hashlib
import sys
import structlog
from typing import Any, Dict


def _hash_value(value: Any) -> str:
    """Hash arbitrary value using SHA256 for privacy-preserving logs."""
    try:
        s = str(value)
    except Exception:
        s = repr(value)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def privacy_scrub(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Scrub sensitive fields by hashing. Avoid logging raw user data.

    Structlog processors receive (logger, method_name, event_dict). We only need
    event_dict here; the other args are ignored.
    """
    sensitive_keys = {"text", "content", "input", "transcript", "prompt"}
    for key in list(event_dict.keys()):
        if key.lower() in sensitive_keys:
            event_dict[key] = {"hash": _hash_value(event_dict[key])}
    return event_dict


def configure_logging(level: str = "info") -> None:
    """Configure structlog for JSON output with timestamps and levels."""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            privacy_scrub,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(_level_to_int(level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    )


def _level_to_int(level: str) -> int:
    level = level.lower()
    return {
        "debug": 10,
        "info": 20,
        "warning": 30,
        "error": 40,
        "critical": 50,
    }.get(level, 20)


log = structlog.get_logger()
