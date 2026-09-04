"""
TaskGuard - Test Fixtures
Shared async fixtures: in-memory Vault, temp SQLite DB, service stack.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

# ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crypto.vault import Vault
from src.core.models import Task, Priority, Status
from src.database.repository import TaskRepository
from src.services.task_service import TaskService
from src.services.export_service import ExportService
from src.services.notification_service import NotificationService


# ── vault ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def test_key() -> bytes:
    return b"\x42" * 32   # deterministic 256-bit key for tests


@pytest.fixture
def vault(test_key) -> Vault:
    return Vault.from_key(test_key)


# ── database + repository ─────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def tmp_db(vault) -> TaskRepository:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    repo = TaskRepository(db_path, vault)
    await repo.init_schema()
    yield repo
    os.unlink(db_path)


# ── service stack ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def task_svc(tmp_db) -> TaskService:
    return TaskService(tmp_db)


@pytest_asyncio.fixture
async def export_dir(tmp_path) -> Path:
    d = tmp_path / "exports"
    d.mkdir()
    return d


@pytest_asyncio.fixture
async def export_svc(task_svc, export_dir) -> ExportService:
    return ExportService(task_svc, export_dir)


@pytest_asyncio.fixture
async def notify_svc(task_svc) -> NotificationService:
    return NotificationService(task_svc, poll_interval=9999)


# ── sample tasks ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_task_data() -> dict:
    return {
        "title":       "Write unit tests",
        "priority":    Priority.HIGH,
        "status":      Status.PENDING,
        "description": "Cover all modules with pytest",
        "tags":        ["testing", "quality"],
        "notes":       "Use pytest-asyncio",
        "due_date":    datetime.utcnow() + timedelta(days=3),
    }


@pytest_asyncio.fixture
async def created_task(task_svc, sample_task_data) -> Task:
    return await task_svc.create_task(**sample_task_data)


@pytest_asyncio.fixture
async def multiple_tasks(task_svc) -> list[Task]:
    data = [
        {"title": "Alpha task",   "priority": "CRITICAL", "status": "ONGOING"},
        {"title": "Beta task",    "priority": "HIGH",     "status": "PENDING"},
        {"title": "Gamma task",   "priority": "MEDIUM",   "status": "NOT_STARTED"},
        {"title": "Delta task",   "priority": "LOW",      "status": "COMPLETED"},
        {"title": "Epsilon task", "priority": "HIGH",     "status": "ON_HOLD",
         "tags": ["urgent", "review"], "due_date": datetime.utcnow() + timedelta(hours=2)},
    ]
    tasks = []
    for d in data:
        tasks.append(await task_svc.create_task(**d))
    return tasks
