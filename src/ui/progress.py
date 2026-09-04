"""
TaskGuard - Progress Bar
Custom ANSI progress bar with elapsed time, ETA, and percentage.
Zero external dependencies. Async-friendly using asyncio.
"""

from __future__ import annotations

import asyncio
import sys
import time
from typing import Optional

from src.ui.colors import Colors


class ProgressBar:
    """
    Unicode progress bar rendered to stderr.

    Example:
        async with ProgressBar(total=50, label="Exporting") as bar:
            for item in items:
                await process(item)
                bar.advance()
    """

    _FILL  = "\u2588"
    _EMPTY = "\u2591"
    _L     = "\u2502"
    _R     = "\u2502"

    def __init__(
        self,
        total:    int,
        label:    str  = "Processing",
        width:    int  = 30,
        stream          = sys.stderr,
    ) -> None:
        self._total    = max(1, total)
        self._current  = 0
        self._label    = label
        self._width    = width
        self._stream   = stream
        self._start_ts: Optional[float] = None
        self._finished = False

    # ── async context manager ─────────────────────────────────────────────────

    async def __aenter__(self) -> "ProgressBar":
        self.start()
        return self

    async def __aexit__(self, *args) -> None:
        self.finish()

    # ── sync context manager ──────────────────────────────────────────────────

    def __enter__(self) -> "ProgressBar":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.finish()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._start_ts = time.monotonic()
        self._current  = 0
        self._render()

    def advance(self, step: int = 1) -> None:
        self._current = min(self._current + step, self._total)
        self._render()

    def set_progress(self, n: int) -> None:
        self._current = min(max(0, n), self._total)
        self._render()

    def finish(self) -> None:
        if not self._finished:
            self._current  = self._total
            self._finished = True
            self._render()
            print("", file=self._stream)   # newline after bar

    # ── rendering ─────────────────────────────────────────────────────────────

    def _render(self) -> None:
        pct     = self._current / self._total
        filled  = int(pct * self._width)
        empty   = self._width - filled
        bar     = (Colors.GREEN + self._FILL * filled
                   + Colors.DIM  + self._EMPTY * empty
                   + Colors.RESET)

        elapsed = time.monotonic() - (self._start_ts or time.monotonic())
        eta_str = self._eta(elapsed, pct)
        pct_str = f"{pct * 100:5.1f}%"
        el_str  = self._fmt_time(elapsed)

        label_c = Colors.BOLD + Colors.CYAN + f"{self._label:<18}" + Colors.RESET
        line = (
            f"\r  {label_c} "
            f"{Colors.BLUE}{self._L}{Colors.RESET}"
            f"{bar}"
            f"{Colors.BLUE}{self._R}{Colors.RESET} "
            f"{Colors.BOLD}{pct_str}{Colors.RESET}  "
            f"{Colors.DIM}elapsed:{el_str} eta:{eta_str}{Colors.RESET}  "
            f"{Colors.DIM}{self._current}/{self._total}{Colors.RESET}"
        )
        self._stream.write(line)
        self._stream.flush()

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.1f}s"
        m, s = divmod(int(seconds), 60)
        return f"{m}m{s:02d}s"

    @staticmethod
    def _eta(elapsed: float, pct: float) -> str:
        if pct <= 0:
            return "?"
        total_est = elapsed / pct
        remaining = total_est - elapsed
        if remaining < 0:
            return "done"
        m, s = divmod(int(remaining), 60)
        if m:
            return f"{m}m{s:02d}s"
        return f"{remaining:.1f}s"

    # ── dunders ───────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (f"ProgressBar(label={self._label!r}, "
                f"{self._current}/{self._total})")

    def __len__(self) -> int:
        return self._total

    def __bool__(self) -> bool:
        return not self._finished

    def __iter__(self):
        yield "label",   self._label
        yield "current", self._current
        yield "total",   self._total
        yield "pct",     self._current / self._total


class SpinnerBar:
    """
    Lightweight indeterminate spinner for operations of unknown duration.

    Usage (async):
        async with SpinnerBar("Loading") as sp:
            await some_long_op()
    """

    _FRAMES = ["|", "/", "-", "\\"]

    def __init__(self, label: str = "Working", stream=sys.stderr) -> None:
        self._label   = label
        self._stream  = stream
        self._frame   = 0
        self._task: Optional[asyncio.Task] = None

    async def __aenter__(self) -> "SpinnerBar":
        self._task = asyncio.get_event_loop().create_task(self._spin())
        return self

    async def __aexit__(self, *args) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._stream.write(f"\r{' ' * 40}\r")
        self._stream.flush()

    async def _spin(self) -> None:
        frames = self._FRAMES
        while True:
            f = frames[self._frame % len(frames)]
            self._stream.write(
                f"\r  {Colors.CYAN}{f}{Colors.RESET} "
                f"{Colors.BOLD}{self._label}...{Colors.RESET}  "
            )
            self._stream.flush()
            self._frame += 1
            await asyncio.sleep(0.12)
