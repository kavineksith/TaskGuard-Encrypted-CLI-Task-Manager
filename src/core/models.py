"""
TaskGuard - Domain Models
Task dataclass and Priority/Status enums with complete dunder method suites.
All comparisons, hashing, iteration, and rich representation are supported.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Generator, Optional

from src.constants import (
    PRIORITY_ORDER, STATUS_LABELS, PRIORITY_LABELS, STATUS_TRANSITIONS
)
from src.core.exceptions import (
    InvalidPriorityError, InvalidStatusTransitionError,
    TaskValidationError, EmptyTitleError, InvalidDueDateError,
)


# ─── Priority enum ────────────────────────────────────────────────────────────

class Priority(Enum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"

    # ── dunders ──────────────────────────────────────────────────────────────
    def __str__(self)  -> str: return PRIORITY_LABELS[self.value]
    def __repr__(self) -> str: return f"Priority.{self.value}"
    def __int__(self)  -> int: return PRIORITY_ORDER[self.value]
    def __hash__(self) -> int: return hash(self.value)
    def __bool__(self) -> bool: return True
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Priority): return self.value == other.value
        if isinstance(other, str):      return self.value == other.upper()
        return NotImplemented
    def __lt__(self, other: "Priority") -> bool:
        return PRIORITY_ORDER[self.value] < PRIORITY_ORDER[other.value]
    def __le__(self, other: "Priority") -> bool:
        return PRIORITY_ORDER[self.value] <= PRIORITY_ORDER[other.value]
    def __gt__(self, other: "Priority") -> bool:
        return PRIORITY_ORDER[self.value] > PRIORITY_ORDER[other.value]
    def __ge__(self, other: "Priority") -> bool:
        return PRIORITY_ORDER[self.value] >= PRIORITY_ORDER[other.value]
    def __iter__(self) -> Generator:
        yield "value",  self.value
        yield "label",  PRIORITY_LABELS[self.value]
        yield "weight", PRIORITY_ORDER[self.value]
    def __getitem__(self, key: str) -> Any:
        return dict(self)[key]

    @classmethod
    def from_string(cls, value: str) -> "Priority":
        try:
            return cls[value.upper()]
        except KeyError:
            raise InvalidPriorityError(value)

    @property
    def weight(self) -> int:
        return PRIORITY_ORDER[self.value]

    @property
    def label(self) -> str:
        return PRIORITY_LABELS[self.value]


# ─── Status enum ─────────────────────────────────────────────────────────────

class Status(Enum):
    NOT_STARTED   = "NOT_STARTED"
    PENDING       = "PENDING"
    ONGOING       = "ONGOING"
    ON_HOLD       = "ON_HOLD"
    COMPLETED     = "COMPLETED"
    NOT_COMPLETED = "NOT_COMPLETED"

    # ── dunders ──────────────────────────────────────────────────────────────
    def __str__(self)  -> str: return STATUS_LABELS[self.value]
    def __repr__(self) -> str: return f"Status.{self.value}"
    def __hash__(self) -> int: return hash(self.value)
    def __bool__(self) -> bool:
        return self not in (Status.COMPLETED, Status.NOT_COMPLETED)
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Status): return self.value == other.value
        if isinstance(other, str):    return self.value == other.upper()
        return NotImplemented
    def __iter__(self) -> Generator:
        yield "value",            self.value
        yield "label",            STATUS_LABELS[self.value]
        yield "is_terminal",      not bool(self)
        yield "allowed_next",     list(STATUS_TRANSITIONS.get(self.value, set()))
    def __getitem__(self, key: str) -> Any:
        return dict(self)[key]
    def __contains__(self, next_status: str) -> bool:
        return next_status in STATUS_TRANSITIONS.get(self.value, set())

    @classmethod
    def from_string(cls, value: str) -> "Status":
        try:
            return cls[value.upper()]
        except KeyError:
            valid = ", ".join(s.value for s in cls)
            raise TaskValidationError("status", f"'{value}' invalid. Valid: {valid}")

    def can_transition_to(self, next_status: "Status") -> bool:
        return next_status.value in STATUS_TRANSITIONS.get(self.value, set())

    def validate_transition(self, next_status: "Status") -> None:
        if not self.can_transition_to(next_status):
            raise InvalidStatusTransitionError(self.value, next_status.value)

    @property
    def label(self) -> str:
        return STATUS_LABELS[self.value]

    @property
    def is_terminal(self) -> bool:
        return not bool(self)

    @property
    def allowed_next(self) -> set[str]:
        return STATUS_TRANSITIONS.get(self.value, set())


# ─── Task dataclass ───────────────────────────────────────────────────────────

@dataclass
class Task:
    """
    Core task domain object.
    Full dunder suite: __str__, __repr__, __eq__, __hash__, __len__,
    __iter__, __contains__, __getitem__, __add__, __lt__, __le__,
    __gt__, __ge__, __bool__.
    """
    title:       str
    priority:    Priority
    status:      Status
    description: str                   = ""
    tags:        list[str]             = field(default_factory=list)
    notes:       str                   = ""
    due_date:    Optional[datetime]    = None
    id:          str                   = field(default_factory=lambda: str(uuid.uuid4()))
    created_at:  datetime              = field(default_factory=datetime.utcnow)
    updated_at:  datetime              = field(default_factory=datetime.utcnow)

    # ── post-init validation ──────────────────────────────────────────────────
    def __post_init__(self) -> None:
        if not isinstance(self.priority, Priority):
            self.priority = Priority.from_string(str(self.priority))
        if not isinstance(self.status, Status):
            self.status = Status.from_string(str(self.status))
        self._validate()

    def _validate(self) -> None:
        if not self.title or not self.title.strip():
            raise EmptyTitleError()
        self.title = self.title.strip()
        if len(self.title) > 200:
            raise TaskValidationError("title", "Must be 200 characters or fewer.")
        # Note: due_date range checks live in the service layer so that DB
        # reconstruction works correctly for historical/overdue tasks.
        self.tags = [t.strip().lower() for t in self.tags if t.strip()]

    # ── dunders ──────────────────────────────────────────────────────────────
    def __str__(self) -> str:
        due = self.due_date.strftime("%Y-%m-%d %H:%M") if self.due_date else "None"
        return (
            f"Task({self.id[:8]}...) [{self.priority.value}] "
            f"[{self.status.value}] '{self.title}' due:{due}"
        )

    def __repr__(self) -> str:
        return (
            f"Task(id={self.id!r}, title={self.title!r}, "
            f"priority={self.priority!r}, status={self.status!r})"
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Task): return self.id == other.id
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)

    def __len__(self) -> int:
        """Return the character length of the title."""
        return len(self.title)

    def __bool__(self) -> bool:
        """True when the task is still active (not completed/not_completed)."""
        return bool(self.status)

    def __contains__(self, item: str) -> bool:
        """True if item appears in title, description, notes, or tags."""
        item_lower = item.lower()
        return (
            item_lower in self.title.lower()
            or item_lower in self.description.lower()
            or item_lower in self.notes.lower()
            or any(item_lower in tag for tag in self.tags)
        )

    def __iter__(self) -> Generator:
        """Yield (field_name, value) pairs for serialisation."""
        yield "id",          self.id
        yield "title",       self.title
        yield "description", self.description
        yield "priority",    self.priority.value
        yield "status",      self.status.value
        yield "tags",        self.tags
        yield "notes",       self.notes
        yield "due_date",    self.due_date.isoformat() if self.due_date else None
        yield "created_at",  self.created_at.isoformat()
        yield "updated_at",  self.updated_at.isoformat()

    def __getitem__(self, key: str) -> Any:
        return dict(self)[key]

    def __add__(self, other: "Task") -> list["Task"]:
        """Combine two tasks into a list (convenience for batch ops)."""
        if not isinstance(other, Task):
            return NotImplemented
        return [self, other]

    def __lt__(self, other: "Task") -> bool:
        """Sort by priority descending, then due_date ascending (most urgent first)."""
        if self.priority != other.priority:
            return self.priority > other.priority   # higher priority = "less" in list
        if self.due_date and other.due_date:
            return self.due_date < other.due_date
        return self.due_date is not None            # tasks with due dates first

    def __le__(self, other: "Task") -> bool: return self == other or self < other
    def __gt__(self, other: "Task") -> bool: return not self <= other
    def __ge__(self, other: "Task") -> bool: return not self < other

    # ── helpers ───────────────────────────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        return dict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        due = data.get("due_date")
        created = data.get("created_at")
        updated = data.get("updated_at")
        return cls(
            id          = data["id"],
            title       = data["title"],
            description = data.get("description", ""),
            priority    = Priority.from_string(data["priority"]),
            status      = Status.from_string(data["status"]),
            tags        = data.get("tags", []),
            notes       = data.get("notes", ""),
            due_date    = datetime.fromisoformat(due)     if due     else None,
            created_at  = datetime.fromisoformat(created) if created else datetime.utcnow(),
            updated_at  = datetime.fromisoformat(updated) if updated else datetime.utcnow(),
        )

    def touch(self) -> None:
        """Update the updated_at timestamp to now."""
        self.updated_at = datetime.utcnow()

    def is_overdue(self) -> bool:
        return bool(self.due_date) and self.due_date < datetime.utcnow() and bool(self)

    def days_until_due(self) -> Optional[float]:
        if not self.due_date:
            return None
        delta = (self.due_date - datetime.utcnow()).total_seconds()
        return delta / 86_400

    def encrypted_payload(self) -> dict[str, Any]:
        """Fields that are AES-256-GCM encrypted at rest."""
        return {
            "title":       self.title,
            "description": self.description,
            "tags":        self.tags,
            "notes":       self.notes,
        }
