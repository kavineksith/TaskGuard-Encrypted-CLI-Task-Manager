"""Tests for TaskService: create, update, delete, status transitions, bulk ops."""

from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timedelta

from src.core.models import Priority, Status
from src.core.exceptions import (
    TaskNotFoundError, EmptyTitleError, InvalidStatusTransitionError,
)


@pytest.mark.asyncio
class TestTaskServiceCreate:
    async def test_create_basic(self, task_svc):
        task = await task_svc.create_task(title="Basic task")
        assert task.title == "Basic task"
        assert task.status  == Status.NOT_STARTED
        assert task.priority == Priority.MEDIUM

    async def test_create_with_all_fields(self, task_svc):
        due = datetime.utcnow() + timedelta(days=5)
        task = await task_svc.create_task(
            title="Full task", priority="HIGH", status="PENDING",
            description="Complete description", tags=["tag1", "tag2"],
            notes="Some notes", due_date=due,
        )
        assert task.priority.value == "HIGH"
        assert task.status.value   == "PENDING"
        assert "tag1" in task.tags
        assert task.description    == "Complete description"

    async def test_create_empty_title_raises(self, task_svc):
        with pytest.raises(EmptyTitleError):
            await task_svc.create_task(title="")

    async def test_create_invalid_priority(self, task_svc):
        from src.core.exceptions import InvalidPriorityError
        with pytest.raises(InvalidPriorityError):
            await task_svc.create_task(title="x", priority="SUPER")

    async def test_create_assigns_uuid(self, task_svc):
        t1 = await task_svc.create_task(title="Task 1")
        t2 = await task_svc.create_task(title="Task 2")
        assert t1.id != t2.id


@pytest.mark.asyncio
class TestTaskServiceRead:
    async def test_get_task_found(self, task_svc, created_task):
        fetched = await task_svc.get_task(created_task.id)
        assert fetched.id == created_task.id

    async def test_get_task_not_found(self, task_svc):
        with pytest.raises(TaskNotFoundError):
            await task_svc.get_task("nonexistent-id")

    async def test_list_all(self, task_svc, multiple_tasks):
        tasks = await task_svc.list_tasks()
        assert len(tasks) == len(multiple_tasks)

    async def test_list_by_status(self, task_svc, multiple_tasks):
        pending = await task_svc.list_tasks(status=Status.PENDING)
        assert all(t.status == Status.PENDING for t in pending)

    async def test_list_by_priority(self, task_svc, multiple_tasks):
        crits = await task_svc.list_tasks(priority=Priority.CRITICAL)
        assert all(t.priority == Priority.CRITICAL for t in crits)

    async def test_list_overdue(self, task_svc):
        t = await task_svc.create_task(title="Overdue", priority="HIGH", status="ONGOING")
        t.due_date = datetime(2020, 1, 1)
        from src.database.repository import TaskRepository
        await task_svc._repo.update(t)
        overdue = await task_svc.list_tasks(overdue=True)
        assert any(x.id == t.id for x in overdue)

    async def test_stream_tasks(self, task_svc, multiple_tasks):
        ids = [t.id async for t in task_svc.stream_tasks()]
        assert len(ids) == len(multiple_tasks)

    async def test_stream_tasks_by_status(self, task_svc, multiple_tasks):
        async for task in task_svc.stream_tasks(status=Status.PENDING):
            assert task.status == Status.PENDING

    async def test_get_stats(self, task_svc, multiple_tasks):
        stats = await task_svc.get_stats()
        assert stats["total"] == len(multiple_tasks)
        assert "by_status" in stats and "by_priority" in stats


@pytest.mark.asyncio
class TestTaskServiceUpdate:
    async def test_update_title(self, task_svc, created_task):
        updated = await task_svc.update_task(created_task.id, title="New title")
        assert updated.title == "New title"

    async def test_update_status_valid_transition(self, task_svc, created_task):
        # PENDING -> ONGOING is valid
        updated = await task_svc.change_status(created_task.id, "ONGOING")
        assert updated.status == Status.ONGOING

    async def test_update_status_invalid_transition(self, task_svc, created_task):
        # PENDING -> COMPLETED is invalid per transitions map
        with pytest.raises(InvalidStatusTransitionError):
            await task_svc.change_status(created_task.id, "COMPLETED")

    async def test_update_empty_title_raises(self, task_svc, created_task):
        with pytest.raises(EmptyTitleError):
            await task_svc.update_task(created_task.id, title="")

    async def test_update_priority(self, task_svc, created_task):
        updated = await task_svc.change_priority(created_task.id, "CRITICAL")
        assert updated.priority == Priority.CRITICAL

    async def test_update_clear_due_date(self, task_svc):
        due = datetime.utcnow() + timedelta(days=2)
        t   = await task_svc.create_task(title="Has due", priority="LOW",
                                          status="NOT_STARTED", due_date=due)
        updated = await task_svc.update_task(t.id, clear_due=True)
        assert updated.due_date is None

    async def test_update_not_found_raises(self, task_svc):
        with pytest.raises(TaskNotFoundError):
            await task_svc.update_task("bad-id", title="x")


@pytest.mark.asyncio
class TestTaskServiceDelete:
    async def test_delete_task(self, task_svc, created_task):
        await task_svc.delete_task(created_task.id)
        with pytest.raises(TaskNotFoundError):
            await task_svc.get_task(created_task.id)

    async def test_delete_not_found(self, task_svc):
        with pytest.raises(TaskNotFoundError):
            await task_svc.delete_task("no-such-id")


@pytest.mark.asyncio
class TestTaskServiceBulk:
    async def test_bulk_delete(self, task_svc, multiple_tasks):
        ids     = [t.id for t in multiple_tasks[:2]]
        results = await task_svc.bulk_delete(ids)
        assert all(v == "deleted" for v in results.values())
        remaining = await task_svc.list_tasks()
        remaining_ids = {t.id for t in remaining}
        assert not any(tid in remaining_ids for tid in ids)

    async def test_bulk_delete_missing_id_reported(self, task_svc):
        results = await task_svc.bulk_delete(["nonexistent-id"])
        assert "error" in results["nonexistent-id"]

    async def test_bulk_status_change(self, task_svc, multiple_tasks):
        # Use tasks in ONGOING status for -> COMPLETED transition
        ongoing = [t for t in multiple_tasks if t.status == Status.ONGOING]
        if not ongoing:
            t = await task_svc.create_task(title="Going", priority="LOW",
                                            status="ONGOING")
            ongoing = [t]
        ids     = [t.id for t in ongoing]
        results = await task_svc.bulk_status_change(ids, "COMPLETED")
        assert all(v == "updated" for v in results.values())
