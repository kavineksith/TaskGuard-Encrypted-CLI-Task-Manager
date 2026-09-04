"""
TaskGuard - Logging Setup
Memory-safe non-blocking logging via QueueHandler / QueueListener.
Dual sinks: ANSI-coloured console + JSON-lines audit file.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

_QUEUE_CAPACITY  = 10_000
_FMT_CONSOLE     = "%(levelname)s  %(name)s  %(message)s"
_LOG_LEVEL_MAP   = {
    "DEBUG":    logging.DEBUG,
    "INFO":     logging.INFO,
    "WARNING":  logging.WARNING,
    "ERROR":    logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# ANSI colour codes used in the console handler
_LEVEL_COLORS = {
    "DEBUG":    "\033[36m",
    "INFO":     "\033[32m",
    "WARNING":  "\033[33m",
    "ERROR":    "\033[31m",
    "CRITICAL": "\033[35m",
}
_RESET = "\033[0m"

# Module-level state — only one listener per process
_listener: Optional[logging.handlers.QueueListener] = None
_queue:    Optional[logging.handlers.MemoryHandler] = None


# ─── coloured console handler ─────────────────────────────────────────────────

class AnsiConsoleHandler(logging.StreamHandler):
    """Emits log records with ANSI colour prefixes."""

    def emit(self, record: logging.LogRecord) -> None:
        colour  = _LEVEL_COLORS.get(record.levelname, "")
        record.levelname = (
            colour + f"[{record.levelname:8}]" + _RESET
        )
        super().emit(record)


# ─── JSON-lines audit handler ─────────────────────────────────────────────────

class JSONLinesHandler(logging.FileHandler):
    """Writes one JSON object per log record to an audit file."""

    def __init__(self, filename: str | Path, **kwargs) -> None:
        super().__init__(str(filename), encoding="utf-8", **kwargs)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "timestamp":  datetime.utcnow().isoformat(),
                "level":      record.levelname,
                "logger":     record.name,
                "message":    record.getMessage(),
                "event":      getattr(record, "event", None),
                "task_id":    getattr(record, "task_id", None),
                "extra":      {
                    k: v for k, v in record.__dict__.items()
                    if k not in logging.LogRecord.__dict__
                    and k not in ("message", "asctime", "args", "exc_info",
                                  "exc_text", "stack_info", "msg", "levelno",
                                  "levelname", "name", "pathname", "filename",
                                  "module", "funcName", "lineno", "created",
                                  "msecs", "relativeCreated", "thread",
                                  "threadName", "processName", "process")
                },
            }
            self.stream.write(json.dumps(entry, default=str) + "\n")
            self.stream.flush()
        except Exception:
            self.handleError(record)


# ─── public API ───────────────────────────────────────────────────────────────

def configure_logging(
    log_dir:     Path,
    log_file:    str     = "taskguard_audit.jsonl",
    level:       str     = "INFO",
    console:     bool    = True,
    quiet:       bool    = False,
) -> None:
    """
    Configure the root TaskGuard logger with QueueHandler + QueueListener.
    Call once at application startup.
    """
    global _listener

    if _listener is not None:
        return   # already configured

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path    = log_dir / log_file
    log_level   = _LOG_LEVEL_MAP.get(level.upper(), logging.INFO)

    # Build handlers for the listener
    handlers: list[logging.Handler] = [
        JSONLinesHandler(log_path),
    ]
    if console and not quiet:
        ch = AnsiConsoleHandler(sys.stderr)
        ch.setFormatter(logging.Formatter(_FMT_CONSOLE))
        handlers.append(ch)

    # Queue-based async dispatch
    import queue as q_mod
    log_queue = q_mod.Queue(maxsize=_QUEUE_CAPACITY)
    _listener = logging.handlers.QueueListener(log_queue, *handlers,
                                                respect_handler_level=True)
    _listener.start()

    # Attach QueueHandler to the taskguard root logger
    root = logging.getLogger("taskguard")
    root.setLevel(log_level)
    root.addHandler(logging.handlers.QueueHandler(log_queue))
    root.propagate = False


def shutdown_logging() -> None:
    """Gracefully stop the QueueListener (flush + join)."""
    global _listener
    if _listener:
        _listener.stop()
        _listener = None


def get_logger(name: str) -> logging.Logger:
    """Return a child of the taskguard root logger."""
    # Ensure name is scoped under 'taskguard'
    if not name.startswith("taskguard") and not name.startswith("src"):
        name = f"taskguard.{name}"
    logger = logging.getLogger(name)
    # Fallback: if configure_logging has never been called, add a NullHandler
    if not logger.handlers and not logger.parent.handlers:
        logger.addHandler(logging.NullHandler())
    return logger
