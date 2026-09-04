"""Tests for NotificationService: overdue detection, due-soon, seen-id tracking."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest

from src.core.models import Status


@pytest.mark.asyncio
class TestNotificationCheck:
    async def test_no_notifications_when_empty(self, notify_svc):
        count = await notify_svc.check_and_notify()
        assert count == 0

    async def test_overdue_task_notifies(self, task_svc, notify_svc):
        task = await task_svc.create_task(
            title="Overdue", priority="HIGH", status="ONGOING"
        )
        # Force due date into the past
        task.due_date = datetime(2020, 6, 1)
        await task_svc._repo.update(task)

        count = await notify_svc.check_and_notify()
        assert count >= 1

    async def test_due_soon_task_notifies(self, task_svc, notify_svc):
        due = datetime.utcnow() + timedelta(hours=1)
        await task_svc.create_task(
            title="Due soon", priority="MEDIUM", status="PENDING", due_date=due
        )
        svc = type(notify_svc)(task_svc, poll_interval=9999,
                                due_soon_secs=7200)   # 2hr window
        count = await svc.check_and_notify()
        assert count >= 1

    async def test_completed_task_not_notified(self, task_svc, notify_svc):
        task = await task_svc.create_task(
            title="Done task", priority="HIGH", status="ONGOING"
        )
        task.status   = Status.COMPLETED
        task.due_date = datetime(2020, 1, 1)
        await task_svc._repo.update(task)

        count = await notify_svc.check_and_notify()
        assert count == 0


@pytest.mark.asyncio
class TestNotificationSeenTracking:
    async def test_seen_ids_not_repeated(self, task_svc, notify_svc):
        task = await task_svc.create_task(
            title="Track me", priority="HIGH", status="ONGOING"
        )
        task.due_date = datetime(2020, 1, 1)
        await task_svc._repo.update(task)

        first  = await notify_svc.check_and_notify()
        second = await notify_svc.check_and_notify()
        assert first >= 1
        assert second == 0   # already seen

    async def test_force_re_notify(self, task_svc, notify_svc):
        task = await task_svc.create_task(
            title="Force notify", priority="HIGH", status="ONGOING"
        )
        task.due_date = datetime(2020, 1, 1)
        await task_svc._repo.update(task)

        await notify_svc.check_and_notify()
        count = await notify_svc.check_and_notify(force=True)
        assert count >= 1

    async def test_reset_seen(self, task_svc, notify_svc):
        task = await task_svc.create_task(
            title="Reset test", priority="HIGH", status="ONGOING"
        )
        task.due_date = datetime(2020, 1, 1)
        await task_svc._repo.update(task)

        await notify_svc.check_and_notify()
        assert len(notify_svc) > 0
        notify_svc.reset_seen()
        assert len(notify_svc) == 0


@pytest.mark.asyncio
class TestNotificationServiceDunders:
    async def test_contains(self, task_svc, notify_svc):
        task = await task_svc.create_task(
            title="Contains test", priority="HIGH", status="ONGOING"
        )
        task.due_date = datetime(2020, 1, 1)
        await task_svc._repo.update(task)
        await notify_svc.check_and_notify()
        assert task.id in notify_svc

    def test_repr(self, notify_svc):
        assert "NotificationService" in repr(notify_svc)

    def test_bool_not_started(self, notify_svc):
        assert bool(notify_svc) is False   # not started yet

    def test_len(self, notify_svc):
        assert len(notify_svc) == 0
