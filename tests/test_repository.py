"""Tests for the async TaskRepository: CRUD, search, streams, error paths."""

from __future__ import annotations

import pytest
import pytest_asyncio
from datetime import datetime, timedelta

from src.core.models import Task, Priority, Status
from src.core.exceptions import RecordNotFoundError, DuplicateRecordError


@pytest.mark.asyncio
class TestRepositoryCreate:
    async def test_create_returns_task(self, tmp_db):
        task = Task(title="Test", priority=Priority.HIGH, status=Status.PENDING)
        result = await tmp_db.create(task)
        assert result.id == task.id

    async def test_create_and_retrieve(self, tmp_db):
        task = Task(title="Persist me", priority=Priority.MEDIUM, status=Status.NOT_STARTED,
                    description="desc", tags=["a", "b"])
        await tmp_db.create(task)
        fetched = await tmp_db.get_by_id(task.id)
        assert fetched.title       == "Persist me"
        assert fetched.description == "desc"
        assert "a" in fetched.tags

    async def test_create_duplicate_id_raises(self, tmp_db):
        task = Task(title="Unique", priority=Priority.LOW, status=Status.PENDING)
        await tmp_db.create(task)
        dup  = Task(title="Copy", priority=Priority.LOW, status=Status.PENDING, id=task.id)
        with pytest.raises(DuplicateRecordError):
            await tmp_db.create(dup)

    async def test_create_with_due_date(self, tmp_db):
        due  = datetime.utcnow() + timedelta(days=7)
        task = Task(title="Due task", priority=Priority.HIGH, status=Status.PENDING,
                    due_date=due)
        await tmp_db.create(task)
        fetched = await tmp_db.get_by_id(task.id)
        assert abs((fetched.due_date - due).total_seconds()) < 1

    async def test_create_encrypts_data(self, tmp_db):
        """Verify title is NOT stored as plaintext in the DB blob."""
        import aiosqlite
        task = Task(title="TOP_SECRET_TITLE", priority=Priority.HIGH, status=Status.PENDING)
        await tmp_db.create(task)
        async with aiosqlite.connect(tmp_db._db_path) as db:
            async with db.execute("SELECT encrypted_data FROM tasks WHERE id=?",
                                  (task.id,)) as cur:
                row = await cur.fetchone()
        assert b"TOP_SECRET_TITLE" not in bytes(row[0])


@pytest.mark.asyncio
class TestRepositoryRead:
    async def test_get_by_id_not_found(self, tmp_db):
        with pytest.raises(RecordNotFoundError):
            await tmp_db.get_by_id("non-existent-id")

    async def test_get_all_empty(self, tmp_db):
        tasks = await tmp_db.get_all()
        assert tasks == []

    async def test_get_all_returns_all(self, tmp_db, multiple_tasks):
        tasks = await tmp_db.get_all()
        assert len(tasks) == len(multiple_tasks)

    async def test_stream_all(self, tmp_db, multiple_tasks):
        count = 0
        async for _ in tmp_db.stream_all():
            count += 1
        assert count == len(multiple_tasks)

    async def test_stream_by_status(self, tmp_db, multiple_tasks):
        pending = [t async for t in tmp_db.stream_by_status(Status.PENDING)]
        assert all(t.status == Status.PENDING for t in pending)

    async def test_stream_by_priority(self, tmp_db, multiple_tasks):
        high = [t async for t in tmp_db.stream_by_priority(Priority.HIGH)]
        assert all(t.priority == Priority.HIGH for t in high)

    async def test_get_overdue(self, tmp_db):
        task = Task(title="Overdue", priority=Priority.HIGH, status=Status.PENDING)
        await tmp_db.create(task)
        task.due_date = datetime(2020, 1, 1)
        await tmp_db.update(task)
        overdue = await tmp_db.get_overdue()
        assert any(t.id == task.id for t in overdue)

    async def test_get_due_soon(self, tmp_db):
        soon = datetime.utcnow() + timedelta(hours=1)
        task = Task(title="Due soon", priority=Priority.HIGH, status=Status.ONGOING,
                    due_date=soon)
        await tmp_db.create(task)
        result = await tmp_db.get_due_soon(within_seconds=7200)
        assert any(t.id == task.id for t in result)

    async def test_count(self, tmp_db, multiple_tasks):
        n = await tmp_db.count()
        assert n == len(multiple_tasks)

    async def test_count_by_status(self, tmp_db, multiple_tasks):
        stats = await tmp_db.count_by_status()
        assert isinstance(stats, dict)
        assert sum(stats.values()) == len(multiple_tasks)

    async def test_count_by_priority(self, tmp_db, multiple_tasks):
        stats = await tmp_db.count_by_priority()
        assert isinstance(stats, dict)


@pytest.mark.asyncio
class TestRepositoryUpdate:
    async def test_update_title(self, tmp_db, created_task):
        created_task.title = "Updated title"
        updated = await tmp_db.update(created_task)
        fetched = await tmp_db.get_by_id(created_task.id)
        assert fetched.title == "Updated title"

    async def test_update_status(self, tmp_db, created_task):
        created_task.status = Status.ONGOING
        await tmp_db.update(created_task)
        fetched = await tmp_db.get_by_id(created_task.id)
        assert fetched.status == Status.ONGOING

    async def test_update_priority(self, tmp_db, created_task):
        created_task.priority = Priority.CRITICAL
        await tmp_db.update(created_task)
        fetched = await tmp_db.get_by_id(created_task.id)
        assert fetched.priority == Priority.CRITICAL

    async def test_update_touches_updated_at(self, tmp_db, created_task):
        before = created_task.updated_at
        import time; time.sleep(0.01)
        created_task.title = "changed"
        await tmp_db.update(created_task)
        fetched = await tmp_db.get_by_id(created_task.id)
        assert fetched.updated_at > before


@pytest.mark.asyncio
class TestRepositoryDelete:
    async def test_delete_removes_task(self, tmp_db, created_task):
        await tmp_db.delete(created_task.id)
        with pytest.raises(RecordNotFoundError):
            await tmp_db.get_by_id(created_task.id)

    async def test_delete_not_found_raises(self, tmp_db):
        with pytest.raises(RecordNotFoundError):
            await tmp_db.delete("does-not-exist")


@pytest.mark.asyncio
class TestRepositorySearch:
    async def test_search_by_title_word(self, tmp_db):
        task = Task(title="Deploy backend service", priority=Priority.HIGH,
                    status=Status.PENDING)
        await tmp_db.create(task)
        results = await tmp_db.search("backend")
        assert any(r.id == task.id for r in results)

    async def test_search_by_tag(self, tmp_db):
        task = Task(title="Refactor module", priority=Priority.MEDIUM,
                    status=Status.NOT_STARTED, tags=["refactor", "cleanup"])
        await tmp_db.create(task)
        results = await tmp_db.search("refactor")
        assert any(r.id == task.id for r in results)

    async def test_search_empty_query_returns_all(self, tmp_db, multiple_tasks):
        results = await tmp_db.search("")
        assert len(results) == len(multiple_tasks)

    async def test_search_no_match_returns_empty(self, tmp_db, created_task):
        results = await tmp_db.search("zzznomatchzzz")
        assert results == []

    async def test_filter_tasks_by_status(self, tmp_db, multiple_tasks):
        result = await tmp_db.filter_tasks(status=Status.COMPLETED)
        assert all(t.status == Status.COMPLETED for t in result)

    async def test_filter_tasks_by_priority(self, tmp_db, multiple_tasks):
        result = await tmp_db.filter_tasks(priority=Priority.CRITICAL)
        assert all(t.priority == Priority.CRITICAL for t in result)
