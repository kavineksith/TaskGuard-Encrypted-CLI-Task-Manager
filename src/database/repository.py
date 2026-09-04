"""
TaskGuard - Async SQLite Repository
Full CRUD with AES-256-GCM encryption, FTS5 search, and async generators.
All I/O is non-blocking via aiosqlite.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncGenerator, Optional

import aiosqlite

from src.constants import PRIORITY_ORDER, DUE_SOON_THRESHOLD
from src.core.exceptions import (
    DatabaseConnectionError, DatabaseQueryError,
    DatabaseTransactionError, DatabaseSchemaError,
    RecordNotFoundError, DuplicateRecordError, SearchIndexError,
)
from src.core.models import Task, Priority, Status
from src.crypto.vault import Vault
from src.database import schema as S


class TaskRepository:
    """
    Async repository for Task persistence.

    Responsibilities:
    - Schema initialisation
    - CRUD operations (all async)
    - AES-256-GCM encrypt/decrypt via Vault
    - FTS5 full-text search index maintenance
    - Async generators for memory-efficient batch reads
    - Audit log writes
    """

    def __init__(self, db_path: str | Path, vault: Vault) -> None:
        self._db_path = Path(db_path)
        self._vault   = vault
        self._sem     = asyncio.Semaphore(8)   # max concurrent DB ops

    # ── initialisation ────────────────────────────────────────────────────────

    async def init_schema(self) -> None:
        """Create all tables, indices, and FTS virtual table."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                for ddl in S.ALL_SCHEMA_DDL:
                    await db.execute(ddl)
                await db.commit()
        except aiosqlite.Error as exc:
            raise DatabaseSchemaError(str(exc)) from exc

    # ── CRUD: create ──────────────────────────────────────────────────────────

    async def create(self, task: Task) -> Task:
        """Persist a new Task. Raises DuplicateRecordError if id exists."""
        async with self._sem:
            try:
                enc_data, nonce = self._vault.encrypt_json(task.encrypted_payload())
                async with aiosqlite.connect(self._db_path) as db:
                    try:
                        await db.execute(S.INSERT_TASK, (
                            task.id,
                            task.priority.value,
                            task.status.value,
                            task.created_at.isoformat(),
                            task.updated_at.isoformat(),
                            task.due_date.isoformat() if task.due_date else None,
                            enc_data,
                            nonce,
                        ))
                        await db.execute(S.INSERT_FTS, (
                            task.id,
                            task.title,
                            " ".join(task.tags),
                        ))
                        await self._audit(db, "TASK_CREATED", task.id,
                                          {"title_len": len(task.title),
                                           "priority": task.priority.value})
                        await db.commit()
                    except aiosqlite.IntegrityError as exc:
                        raise DuplicateRecordError("Task", "id", task.id) from exc
            except (DuplicateRecordError, Exception) as exc:
                if isinstance(exc, DuplicateRecordError):
                    raise
                raise DatabaseQueryError("INSERT tasks", str(exc)) from exc
        return task

    # ── CRUD: read ────────────────────────────────────────────────────────────

    async def get_by_id(self, task_id: str) -> Task:
        """Fetch and decrypt a single Task by id."""
        async with self._sem:
            try:
                async with aiosqlite.connect(self._db_path) as db:
                    db.row_factory = aiosqlite.Row
                    async with db.execute(S.SELECT_TASK_BY_ID, (task_id,)) as cur:
                        row = await cur.fetchone()
            except aiosqlite.Error as exc:
                raise DatabaseQueryError("SELECT tasks", str(exc)) from exc

        if row is None:
            raise RecordNotFoundError("Task", task_id)
        return self._row_to_task(row)

    async def get_all(self) -> list[Task]:
        """Return all tasks sorted by priority desc, due_date asc."""
        return [t async for t in self.stream_all()]

    async def stream_all(self) -> AsyncGenerator[Task, None]:
        """Async generator — yields Tasks one at a time for memory efficiency."""
        async with self._sem:
            try:
                async with aiosqlite.connect(self._db_path) as db:
                    db.row_factory = aiosqlite.Row
                    async with db.execute(S.SELECT_ALL_TASKS) as cur:
                        async for row in cur:
                            yield self._row_to_task(row)
            except aiosqlite.Error as exc:
                raise DatabaseQueryError("SELECT tasks", str(exc)) from exc

    async def stream_by_status(self, status: Status) -> AsyncGenerator[Task, None]:
        async with self._sem:
            try:
                async with aiosqlite.connect(self._db_path) as db:
                    db.row_factory = aiosqlite.Row
                    async with db.execute(
                        S.SELECT_TASKS_BY_STATUS, (status.value,)
                    ) as cur:
                        async for row in cur:
                            yield self._row_to_task(row)
            except aiosqlite.Error as exc:
                raise DatabaseQueryError("SELECT tasks by status", str(exc)) from exc

    async def stream_by_priority(self, priority: Priority) -> AsyncGenerator[Task, None]:
        async with self._sem:
            try:
                async with aiosqlite.connect(self._db_path) as db:
                    db.row_factory = aiosqlite.Row
                    async with db.execute(
                        S.SELECT_TASKS_BY_PRIORITY, (priority.value,)
                    ) as cur:
                        async for row in cur:
                            yield self._row_to_task(row)
            except aiosqlite.Error as exc:
                raise DatabaseQueryError("SELECT tasks by priority", str(exc)) from exc

    async def get_due_soon(self, within_seconds: float = DUE_SOON_THRESHOLD
                           ) -> list[Task]:
        """Return active tasks due within *within_seconds* from now."""
        cutoff = (datetime.utcnow() + timedelta(seconds=within_seconds)).isoformat()
        async with self._sem:
            try:
                async with aiosqlite.connect(self._db_path) as db:
                    db.row_factory = aiosqlite.Row
                    async with db.execute(S.SELECT_TASKS_DUE_BEFORE, (cutoff,)) as cur:
                        rows = await cur.fetchall()
            except aiosqlite.Error as exc:
                raise DatabaseQueryError("SELECT tasks due soon", str(exc)) from exc
        return [self._row_to_task(r) for r in rows]

    async def get_overdue(self) -> list[Task]:
        """Return active tasks whose due_date has already passed."""
        now = datetime.utcnow().isoformat()
        async with self._sem:
            try:
                async with aiosqlite.connect(self._db_path) as db:
                    db.row_factory = aiosqlite.Row
                    async with db.execute(S.SELECT_TASKS_OVERDUE, (now,)) as cur:
                        rows = await cur.fetchall()
            except aiosqlite.Error as exc:
                raise DatabaseQueryError("SELECT overdue tasks", str(exc)) from exc
        return [self._row_to_task(r) for r in rows]

    # ── CRUD: update ──────────────────────────────────────────────────────────

    async def update(self, task: Task) -> Task:
        """Re-encrypt and persist updated Task fields."""
        async with self._sem:
            try:
                task.touch()
                enc_data, nonce = self._vault.encrypt_json(task.encrypted_payload())
                async with aiosqlite.connect(self._db_path) as db:
                    await db.execute(S.UPDATE_TASK, (
                        task.priority.value,
                        task.status.value,
                        task.updated_at.isoformat(),
                        task.due_date.isoformat() if task.due_date else None,
                        enc_data,
                        nonce,
                        task.id,
                    ))
                    # rebuild FTS entry
                    await db.execute(S.DELETE_FTS, (task.id,))
                    await db.execute(S.INSERT_FTS, (
                        task.id, task.title, " ".join(task.tags)
                    ))
                    await self._audit(db, "TASK_UPDATED", task.id,
                                      {"status": task.status.value,
                                       "priority": task.priority.value})
                    await db.commit()
            except aiosqlite.Error as exc:
                raise DatabaseQueryError("UPDATE tasks", str(exc)) from exc
        return task

    # ── CRUD: delete ──────────────────────────────────────────────────────────

    async def delete(self, task_id: str) -> None:
        """Hard-delete a task and its FTS entry."""
        async with self._sem:
            try:
                async with aiosqlite.connect(self._db_path) as db:
                    result = await db.execute(S.DELETE_TASK, (task_id,))
                    if result.rowcount == 0:
                        raise RecordNotFoundError("Task", task_id)
                    await db.execute(S.DELETE_FTS, (task_id,))
                    await self._audit(db, "TASK_DELETED", task_id, {})
                    await db.commit()
            except RecordNotFoundError:
                raise
            except aiosqlite.Error as exc:
                raise DatabaseQueryError("DELETE tasks", str(exc)) from exc

    # ── full-text search ──────────────────────────────────────────────────────

    async def search(self, query: str) -> list[Task]:
        """FTS5 search over title and tags; returns tasks ordered by relevance."""
        if not query or not query.strip():
            return await self.get_all()

        fts_query = self._sanitise_fts_query(query)
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(S.SEARCH_FTS, (fts_query,)) as cur:
                    fts_rows = await cur.fetchall()

                if not fts_rows:
                    return []

                ids_in_order = [r["task_id"] for r in fts_rows]
                placeholders = ",".join("?" * len(ids_in_order))
                sql = S.SELECT_TASKS_BY_IDS.format(placeholders=placeholders)

                async with db.execute(sql, ids_in_order) as cur:
                    task_rows = await cur.fetchall()

        except aiosqlite.OperationalError as exc:
            raise SearchIndexError(str(exc)) from exc
        except aiosqlite.Error as exc:
            raise DatabaseQueryError("FTS search", str(exc)) from exc

        # Preserve FTS rank order
        task_map = {r["id"]: self._row_to_task(r) for r in task_rows}
        return [task_map[tid] for tid in ids_in_order if tid in task_map]

    # ── filters (combined) ────────────────────────────────────────────────────

    async def filter_tasks(
        self,
        status:   Optional[Status]   = None,
        priority: Optional[Priority] = None,
        overdue:  bool               = False,
    ) -> list[Task]:
        """Return tasks matching all supplied filters."""
        tasks = await self.get_all()
        result: list[Task] = []
        for t in tasks:
            if status   is not None and t.status   != status:   continue
            if priority is not None and t.priority != priority: continue
            if overdue  and not t.is_overdue():     continue
            result.append(t)
        return result

    # ── statistics ────────────────────────────────────────────────────────────

    async def count(self) -> int:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(S.COUNT_TASKS) as cur:
                row = await cur.fetchone()
        return row[0] if row else 0

    async def count_by_status(self) -> dict[str, int]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(S.COUNT_BY_STATUS) as cur:
                rows = await cur.fetchall()
        return {r[0]: r[1] for r in rows}

    async def count_by_priority(self) -> dict[str, int]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(S.COUNT_BY_PRIORITY) as cur:
                rows = await cur.fetchall()
        return {r[0]: r[1] for r in rows}

    # ── private helpers ───────────────────────────────────────────────────────

    def _row_to_task(self, row) -> Task:
        """Decrypt row and reconstruct a Task domain object."""
        nonce      = bytes(row["nonce"])
        enc_data   = bytes(row["encrypted_data"])
        payload    = self._vault.decrypt_json(enc_data, nonce, record_id=row["id"])

        due = row["due_date"]
        return Task(
            id          = row["id"],
            title       = payload["title"],
            description = payload.get("description", ""),
            priority    = Priority.from_string(row["priority"]),
            status      = Status.from_string(row["status"]),
            tags        = payload.get("tags", []),
            notes       = payload.get("notes", ""),
            due_date    = datetime.fromisoformat(due) if due else None,
            created_at  = datetime.fromisoformat(row["created_at"]),
            updated_at  = datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _sanitise_fts_query(query: str) -> str:
        """
        Escape special FTS5 characters and append wildcard for prefix matching.
        Keeps AND/OR/NOT operators if explicitly provided.
        """
        # Remove characters that break FTS5 syntax
        safe = query.replace('"', '""').strip()
        # If user supplied boolean operators, use as-is; otherwise prefix match
        if not any(op in safe.upper() for op in (" AND ", " OR ", " NOT ")):
            # Wrap each word in prefix match
            words = [f'"{w}"*' for w in safe.split() if w]
            return " OR ".join(words) if words else safe
        return safe

    @staticmethod
    async def _audit(db, event: str, task_id: str, detail: dict) -> None:
        """Write an audit record inside an already-open DB transaction."""
        await db.execute(S.INSERT_AUDIT, (
            datetime.utcnow().isoformat(),
            event,
            task_id,
            "cli",
            json.dumps(detail),
        ))
