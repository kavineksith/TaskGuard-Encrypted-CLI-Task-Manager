"""
TaskGuard - Task Service
Business logic layer: validation, status transitions, bulk operations,
async generators for streaming results.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import AsyncGenerator, Optional

from src.core.exceptions import (
    EmptyTitleError, TaskValidationError, TaskNotFoundError,
    InvalidStatusTransitionError,
)
from src.core.models import Task, Priority, Status
from src.database.repository import TaskRepository
from src.logging_setup.logger import get_logger

logger = get_logger(__name__)


class TaskService:
    """
    Orchestrates CRUD operations with domain-level validation.
    All public methods are async.
    """

    def __init__(self, repo: TaskRepository) -> None:
        self._repo = repo

    # ── create ────────────────────────────────────────────────────────────────

    async def create_task(
        self,
        title:       str,
        priority:    str | Priority = Priority.MEDIUM,
        status:      str | Status   = Status.NOT_STARTED,
        description: str            = "",
        tags:        list[str]      | None = None,
        notes:       str            = "",
        due_date:    datetime       | None = None,
    ) -> Task:
        pri = Priority.from_string(str(priority)) if isinstance(priority, str) else priority
        sts = Status.from_string(str(status))     if isinstance(status, str)   else status

        task = Task(
            title       = title,
            priority    = pri,
            status      = sts,
            description = description,
            tags        = tags or [],
            notes       = notes,
            due_date    = due_date,
        )

        result = await self._repo.create(task)
        logger.info("task_created", extra={
            "event": "TASK_CREATED",
            "task_id": result.id,
            "title_len": len(result.title),
            "priority": result.priority.value,
        })
        return result

    # ── read ──────────────────────────────────────────────────────────────────

    async def get_task(self, task_id: str) -> Task:
        try:
            return await self._repo.get_by_id(task_id)
        except Exception:
            raise TaskNotFoundError(task_id)

    async def list_tasks(
        self,
        status:   Optional[Status]   = None,
        priority: Optional[Priority] = None,
        overdue:  bool               = False,
    ) -> list[Task]:
        if status is None and priority is None and not overdue:
            return await self._repo.get_all()
        return await self._repo.filter_tasks(status, priority, overdue)
    async def stream_tasks(
        self, status: Optional[Status] = None
    ) -> AsyncGenerator[Task, None]:
        """Async generator for memory-efficient iteration."""
        if status:
            async for task in self._repo.stream_by_status(status):
                yield task
        else:
            async for task in self._repo.stream_all():
                yield task

    async def get_stats(self) -> dict:
        total, by_status, by_priority = await asyncio.gather(
            self._repo.count(),
            self._repo.count_by_status(),
            self._repo.count_by_priority(),
        )
        return {
            "total":       total,
            "by_status":   by_status,
            "by_priority": by_priority,
        }

    # ── update ────────────────────────────────────────────────────────────────

    async def update_task(
        self,
        task_id:     str,
        title:       Optional[str]      = None,
        priority:    Optional[str]      = None,
        status:      Optional[str]      = None,
        description: Optional[str]      = None,
        tags:        Optional[list[str]]= None,
        notes:       Optional[str]      = None,
        due_date:    Optional[datetime] = None,
        clear_due:   bool               = False,
    ) -> Task:
        task = await self.get_task(task_id)

        if title is not None:
            if not title.strip():
                raise EmptyTitleError()
            task.title = title.strip()

        if priority is not None:
            task.priority = Priority.from_string(priority)

        if status is not None:
            new_status = Status.from_string(status)
            task.status.validate_transition(new_status)
            task.status = new_status

        if description is not None:
            task.description = description

        if tags is not None:
            task.tags = [t.strip().lower() for t in tags if t.strip()]

        if notes is not None:
            task.notes = notes

        if clear_due:
            task.due_date = None
        elif due_date is not None:
            task.due_date = due_date

        result = await self._repo.update(task)
        logger.info("task_updated", extra={
            "event": "TASK_UPDATED",
            "task_id": task_id,
        })
        return result

    async def change_status(self, task_id: str, new_status: str) -> Task:
        return await self.update_task(task_id, status=new_status)

    async def change_priority(self, task_id: str, new_priority: str) -> Task:
        return await self.update_task(task_id, priority=new_priority)

    # ── delete ────────────────────────────────────────────────────────────────

    async def delete_task(self, task_id: str) -> None:
        await self.get_task(task_id)   # raises TaskNotFoundError if missing
        await self._repo.delete(task_id)
        logger.info("task_deleted", extra={
            "event": "TASK_DELETED",
            "task_id": task_id,
        })

    # ── bulk operations ───────────────────────────────────────────────────────

    async def bulk_delete(self, task_ids: list[str]) -> dict[str, str]:
        """
        Delete multiple tasks in parallel (bounded by Semaphore in repo).
        Returns {task_id: "deleted" | "error: <msg>"}.
        """
        sem = asyncio.Semaphore(4)

        async def _delete_one(tid: str) -> tuple[str, str]:
            async with sem:
                try:
                    await self.delete_task(tid)
                    return tid, "deleted"
                except Exception as exc:
                    return tid, f"error: {exc}"

        results = await asyncio.gather(*[_delete_one(tid) for tid in task_ids])
        return dict(results)

    async def bulk_status_change(
        self, task_ids: list[str], new_status: str
    ) -> dict[str, str]:
        """Change status for multiple tasks in parallel."""
        sem = asyncio.Semaphore(4)

        async def _update_one(tid: str) -> tuple[str, str]:
            async with sem:
                try:
                    await self.change_status(tid, new_status)
                    return tid, "updated"
                except Exception as exc:
                    return tid, f"error: {exc}"

        results = await asyncio.gather(*[_update_one(tid) for tid in task_ids])
        return dict(results)

    # ── search ────────────────────────────────────────────────────────────────

    async def search(self, query: str) -> list[Task]:
        return await self._repo.search(query)

    # ── notification helpers ──────────────────────────────────────────────────

    async def get_overdue(self) -> list[Task]:
        return await self._repo.get_overdue()

    async def get_due_soon(self, within_seconds: float = 86_400) -> list[Task]:
        return await self._repo.get_due_soon(within_seconds)
