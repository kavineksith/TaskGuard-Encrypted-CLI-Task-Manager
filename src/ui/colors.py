"""
TaskGuard - ANSI Color Constants
No external libraries required. All terminal coloring is pure Python escape codes.
"""

from __future__ import annotations
import os
import sys


def _supports_color() -> bool:
    """Return True when the terminal appears to support ANSI escape codes."""
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    term = os.environ.get("TERM", "")
    if term == "dumb":
        return False
    return True


_COLOR_ENABLED = _supports_color()


class Colors:
    """ANSI escape code constants. Strings are empty when color is disabled."""

    # ── text color ────────────────────────────────────────────────────────────
    BLACK   = "\033[30m" if _COLOR_ENABLED else ""
    RED     = "\033[31m" if _COLOR_ENABLED else ""
    GREEN   = "\033[32m" if _COLOR_ENABLED else ""
    YELLOW  = "\033[33m" if _COLOR_ENABLED else ""
    BLUE    = "\033[34m" if _COLOR_ENABLED else ""
    MAGENTA = "\033[35m" if _COLOR_ENABLED else ""
    CYAN    = "\033[36m" if _COLOR_ENABLED else ""
    WHITE   = "\033[37m" if _COLOR_ENABLED else ""

    # ── bright variants ───────────────────────────────────────────────────────
    BRIGHT_RED    = "\033[91m" if _COLOR_ENABLED else ""
    BRIGHT_GREEN  = "\033[92m" if _COLOR_ENABLED else ""
    BRIGHT_YELLOW = "\033[93m" if _COLOR_ENABLED else ""
    BRIGHT_BLUE   = "\033[94m" if _COLOR_ENABLED else ""
    BRIGHT_CYAN   = "\033[96m" if _COLOR_ENABLED else ""
    BRIGHT_WHITE  = "\033[97m" if _COLOR_ENABLED else ""

    # ── modifiers ─────────────────────────────────────────────────────────────
    BOLD      = "\033[1m"  if _COLOR_ENABLED else ""
    DIM       = "\033[2m"  if _COLOR_ENABLED else ""
    UNDERLINE = "\033[4m"  if _COLOR_ENABLED else ""
    BLINK     = "\033[5m"  if _COLOR_ENABLED else ""
    REVERSE   = "\033[7m"  if _COLOR_ENABLED else ""

    RESET     = "\033[0m"  if _COLOR_ENABLED else ""

    # ── convenience combiners ─────────────────────────────────────────────────
    @classmethod
    def bold(cls, text: str) -> str:
        return f"{cls.BOLD}{text}{cls.RESET}"

    @classmethod
    def dim(cls, text: str) -> str:
        return f"{cls.DIM}{text}{cls.RESET}"

    @classmethod
    def colorize(cls, text: str, *codes: str) -> str:
        prefix = "".join(codes)
        return f"{prefix}{text}{cls.RESET}" if prefix else text

    @classmethod
    def success(cls, text: str) -> str:
        return cls.colorize(text, cls.BOLD, cls.GREEN)

    @classmethod
    def error(cls, text: str) -> str:
        return cls.colorize(text, cls.BOLD, cls.RED)

    @classmethod
    def warning(cls, text: str) -> str:
        return cls.colorize(text, cls.BOLD, cls.YELLOW)

    @classmethod
    def info(cls, text: str) -> str:
        return cls.colorize(text, cls.CYAN)

    @classmethod
    def highlight(cls, text: str) -> str:
        return cls.colorize(text, cls.BOLD, cls.BRIGHT_WHITE)


# ─── Priority colour mapping ──────────────────────────────────────────────────

PRIORITY_COLORS: dict[str, str] = {
    "CRITICAL": Colors.BRIGHT_RED,
    "HIGH":     Colors.RED,
    "MEDIUM":   Colors.YELLOW,
    "LOW":      Colors.GREEN,
}

STATUS_COLORS: dict[str, str] = {
    "NOT_STARTED":   Colors.DIM,
    "PENDING":       Colors.CYAN,
    "ONGOING":       Colors.BRIGHT_GREEN,
    "ON_HOLD":       Colors.YELLOW,
    "COMPLETED":     Colors.GREEN,
    "NOT_COMPLETED": Colors.RED,
}


def priority_colored(priority_value: str) -> str:
    c = PRIORITY_COLORS.get(priority_value, "")
    label = priority_value.replace("_", " ").title()
    return f"{Colors.BOLD}{c}{label}{Colors.RESET}"


def status_colored(status_value: str) -> str:
    c = STATUS_COLORS.get(status_value, "")
    label = status_value.replace("_", " ").title()
    return f"{c}{label}{Colors.RESET}"
