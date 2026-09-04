"""
TaskGuard - Notification Service
Terminal-based notifications for overdue and due-soon tasks.
Runs a background asyncio task during interactive mode that polls every N seconds.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from src.constants import NOTIFY_POLL_INTERVAL, DUE_SOON_THRESHOLD
from src.core.exceptions import NotificationInitError
from src.core.models import Task
from src.services.task_service import TaskService
from src.ui.colors import Colors
from src.logging_setup.logger import get_logger

logger = get_logger(__name__)


class NotificationService:
    """
    Checks for overdue and due-soon tasks and prints colored terminal banners.
    Optionally runs as a background asyncio task.
    """

    def __init__(
        self,
        task_service: TaskService,
        poll_interval: int = NOTIFY_POLL_INTERVAL,
        due_soon_secs: float = DUE_SOON_THRESHOLD,
    ) -> None:
        self._svc          = task_service
        self._poll_interval= poll_interval
        self._due_soon_secs= due_soon_secs
        self._task: Optional[asyncio.Task] = None
        self._seen_ids: set[str] = set()   # avoid repeat-notifying same task

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start background notification polling (safe to call multiple times)."""
        if self._task and not self._task.done():
            return
        try:
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._poll_loop())
        except RuntimeError as exc:
            raise NotificationInitError(str(exc)) from exc

    def stop(self) -> None:
        """Cancel the background polling task."""
        if self._task and not self._task.done():
            self._task.cancel()

    # ── immediate check ───────────────────────────────────────────────────────

    async def check_and_notify(self, *, force: bool = False) -> int:
        """
        Check for overdue and due-soon tasks right now.
        Prints banners to the terminal and returns the number of notifications shown.
        If *force* is True, notify even for already-seen task ids.
        """
        overdue  , due_soon = await asyncio.gather(
            self._svc.get_overdue(),
            self._svc.get_due_soon(self._due_soon_secs),
        )

        # Remove tasks already in overdue from due_soon to avoid duplicate notify
        overdue_ids = {t.id for t in overdue}
        due_soon    = [t for t in due_soon if t.id not in overdue_ids]

        count = 0
        if overdue:
            count += self._print_overdue_banner(overdue, force=force)
        if due_soon:
            count += self._print_due_soon_banner(due_soon, force=force)

        return count

    # ── banners ───────────────────────────────────────────────────────────────

    def _print_overdue_banner(self, tasks: list[Task], *, force: bool) -> int:
        new_tasks = [t for t in tasks if force or t.id not in self._seen_ids]
        if not new_tasks:
            return 0

        w = 72
        border  = Colors.RED + "=" * w + Colors.RESET
        header  = Colors.RED + Colors.BOLD + "  OVERDUE TASKS".center(w) + Colors.RESET
        print(f"\n{border}\n{header}\n{border}")
        for t in new_tasks:
            days = abs(t.days_until_due() or 0)
            line = f"  [{t.priority.value:8}] {t.title[:45]:<45}  overdue {days:.1f}d"
            print(Colors.RED + line + Colors.RESET)
            self._seen_ids.add(t.id)
        print(border + "\n")
        logger.warning("overdue_notified",
                        extra={"event": "NOTIFY_OVERDUE", "count": len(new_tasks)})
        return len(new_tasks)

    def _print_due_soon_banner(self, tasks: list[Task], *, force: bool) -> int:
        new_tasks = [t for t in tasks if force or t.id not in self._seen_ids]
        if not new_tasks:
            return 0

        w = 72
        border = Colors.YELLOW + "-" * w + Colors.RESET
        header = Colors.YELLOW + Colors.BOLD + "  DUE SOON".center(w) + Colors.RESET
        print(f"\n{border}\n{header}\n{border}")
        for t in new_tasks:
            hours = (t.days_until_due() or 0) * 24
            line  = f"  [{t.priority.value:8}] {t.title[:45]:<45}  in {hours:.1f}h"
            print(Colors.YELLOW + line + Colors.RESET)
            self._seen_ids.add(t.id)
        print(border + "\n")
        logger.info("due_soon_notified",
                     extra={"event": "NOTIFY_DUE_SOON", "count": len(new_tasks)})
        return len(new_tasks)

    # ── background loop ───────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        """Runs indefinitely, checking for notifications every N seconds."""
        while True:
            try:
                await asyncio.sleep(self._poll_interval)
                await self.check_and_notify()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("notify_poll_error", extra={"error": str(exc)})

    # ── helpers ───────────────────────────────────────────────────────────────

    def reset_seen(self) -> None:
        """Clear the set of already-notified task ids."""
        self._seen_ids.clear()

    def __repr__(self) -> str:
        running = self._task and not self._task.done()
        return f"NotificationService(running={running}, poll={self._poll_interval}s)"

    def __bool__(self) -> bool:
        return bool(self._task and not self._task.done())

    def __len__(self) -> int:
        return len(self._seen_ids)

    def __contains__(self, task_id: str) -> bool:
        return task_id in self._seen_ids
