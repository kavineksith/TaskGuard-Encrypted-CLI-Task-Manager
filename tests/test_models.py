"""Tests for domain models: Priority, Status, Task."""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timedelta

from src.core.models import Priority, Status, Task
from src.core.exceptions import (
    EmptyTitleError, TaskValidationError, InvalidPriorityError,
    InvalidStatusTransitionError, InvalidDueDateError,
)


# ─── Priority ─────────────────────────────────────────────────────────────────

class TestPriority:
    def test_values_exist(self):
        assert Priority.LOW and Priority.MEDIUM and Priority.HIGH and Priority.CRITICAL

    def test_from_string_valid(self):
        assert Priority.from_string("high") == Priority.HIGH
        assert Priority.from_string("CRITICAL") == Priority.CRITICAL

    def test_from_string_invalid(self):
        with pytest.raises(InvalidPriorityError):
            Priority.from_string("EXTREME")

    def test_ordering(self):
        assert Priority.LOW < Priority.MEDIUM < Priority.HIGH < Priority.CRITICAL

    def test_ge_le(self):
        assert Priority.HIGH >= Priority.HIGH
        assert Priority.LOW  <= Priority.MEDIUM

    def test_str_repr(self):
        assert "High" in str(Priority.HIGH)
        assert "Priority.HIGH" == repr(Priority.HIGH)

    def test_int_conversion(self):
        assert int(Priority.LOW) == 1
        assert int(Priority.CRITICAL) == 4

    def test_bool(self):
        assert bool(Priority.LOW) is True

    def test_hash(self):
        s = {Priority.HIGH, Priority.MEDIUM}
        assert len(s) == 2

    def test_eq_string(self):
        assert Priority.HIGH == "HIGH"

    def test_iter(self):
        d = dict(Priority.MEDIUM)
        assert "value" in d and "weight" in d

    def test_getitem(self):
        assert Priority.HIGH["value"] == "HIGH"

    def test_weight_property(self):
        assert Priority.CRITICAL.weight == 4


# ─── Status ───────────────────────────────────────────────────────────────────

class TestStatus:
    def test_all_values(self):
        for s in ("NOT_STARTED","PENDING","ONGOING","ON_HOLD","COMPLETED","NOT_COMPLETED"):
            assert Status.from_string(s) is not None

    def test_from_string_invalid(self):
        with pytest.raises(TaskValidationError):
            Status.from_string("UNKNOWN_STATUS")

    def test_bool_active(self):
        assert bool(Status.PENDING) is True
        assert bool(Status.ONGOING) is True

    def test_bool_terminal(self):
        assert bool(Status.COMPLETED)     is False
        assert bool(Status.NOT_COMPLETED) is False

    def test_transition_valid(self):
        Status.PENDING.validate_transition(Status.ONGOING)   # should not raise

    def test_transition_invalid(self):
        with pytest.raises(InvalidStatusTransitionError):
            Status.COMPLETED.validate_transition(Status.PENDING)

    def test_can_transition_to(self):
        assert Status.PENDING.can_transition_to(Status.ONGOING) is True
        assert Status.ONGOING.can_transition_to(Status.NOT_STARTED) is False

    def test_contains(self):
        assert "ONGOING" in Status.PENDING
        assert "NOT_STARTED" not in Status.PENDING

    def test_is_terminal(self):
        assert Status.COMPLETED.is_terminal is True
        assert Status.PENDING.is_terminal   is False

    def test_allowed_next(self):
        nxt = Status.ONGOING.allowed_next
        assert "COMPLETED" in nxt and "ON_HOLD" in nxt

    def test_str(self):
        assert "Ongoing" in str(Status.ONGOING)

    def test_repr(self):
        assert repr(Status.PENDING) == "Status.PENDING"


# ─── Task ─────────────────────────────────────────────────────────────────────

class TestTask:
    def make_task(self, **kwargs):
        defaults = {"title": "Test task", "priority": Priority.MEDIUM,
                    "status": Status.PENDING}
        defaults.update(kwargs)
        return Task(**defaults)

    def test_creation(self):
        t = self.make_task()
        assert t.title == "Test task"
        assert t.priority == Priority.MEDIUM

    def test_empty_title_raises(self):
        with pytest.raises(EmptyTitleError):
            self.make_task(title="")

    def test_whitespace_title_raises(self):
        with pytest.raises(EmptyTitleError):
            self.make_task(title="   ")

    def test_title_strip(self):
        t = self.make_task(title="  hello  ")
        assert t.title == "hello"

    def test_title_too_long(self):
        with pytest.raises(TaskValidationError):
            self.make_task(title="x" * 201)

    def test_tag_normalisation(self):
        t = self.make_task(tags=["  UPPER  ", "lower", ""])
        assert "upper" in t.tags
        assert "" not in t.tags

    def test_eq_by_id(self):
        t1 = self.make_task()
        t2 = self.make_task()
        assert t1 != t2
        t2_copy = Task(title=t1.title, priority=t1.priority,
                       status=t1.status, id=t1.id,
                       created_at=t1.created_at)
        assert t1 == t2_copy

    def test_hash(self):
        t = self.make_task()
        assert hash(t) == hash(t)

    def test_len(self):
        t = self.make_task(title="Hello")
        assert len(t) == 5

    def test_bool_active(self):
        t = self.make_task(status=Status.PENDING)
        assert bool(t) is True

    def test_bool_terminal(self):
        t = self.make_task(status=Status.COMPLETED)
        assert bool(t) is False

    def test_contains_title(self):
        t = self.make_task(title="Fix the bug")
        assert "bug" in t
        assert "missing" not in t

    def test_contains_tags(self):
        t = self.make_task(tags=["backend", "api"])
        assert "api" in t

    def test_iter_fields(self):
        t  = self.make_task()
        d  = dict(t)
        assert "id" in d and "title" in d and "priority" in d

    def test_getitem(self):
        t = self.make_task()
        assert t["title"] == "Test task"

    def test_add(self):
        t1 = self.make_task(title="A")
        t2 = self.make_task(title="B")
        result = t1 + t2
        assert isinstance(result, list) and len(result) == 2

    def test_ordering_priority(self):
        high = self.make_task(title="H", priority=Priority.HIGH)
        low  = self.make_task(title="L", priority=Priority.LOW)
        # high priority task sorts "less" (appears first in sorted())
        assert high < low

    def test_to_dict(self):
        t = self.make_task()
        d = t.to_dict()
        assert isinstance(d, dict)
        assert d["title"] == "Test task"

    def test_from_dict(self):
        t  = self.make_task()
        d  = t.to_dict()
        t2 = Task.from_dict(d)
        assert t2.title == t.title
        assert t2.id    == t.id

    def test_to_json(self):
        t = self.make_task()
        j = t.to_json()
        parsed = json.loads(j)
        assert parsed["title"] == "Test task"

    def test_is_overdue_false(self):
        t = self.make_task(due_date=datetime.utcnow() + timedelta(days=1))
        assert t.is_overdue() is False

    def test_is_overdue_true(self):
        t = self.make_task()
        # Patch due_date directly (bypass constructor validation)
        t.due_date = datetime(2000, 1, 1)
        assert t.is_overdue() is True

    def test_days_until_due_none(self):
        t = self.make_task()
        assert t.days_until_due() is None

    def test_touch_updates_updated_at(self):
        import time
        t = self.make_task()
        before = t.updated_at
        time.sleep(0.01)
        t.touch()
        assert t.updated_at > before

    def test_encrypted_payload_keys(self):
        t = self.make_task(description="desc", tags=["x"], notes="note")
        p = t.encrypted_payload()
        assert all(k in p for k in ("title", "description", "tags", "notes"))
