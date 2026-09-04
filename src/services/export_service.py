"""
TaskGuard - Export Service
Async CSV and JSON export with streaming async generators.
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from src.core.exceptions import (
    CSVExportError, JSONExportError, ExportFileIOError,
    InvalidExportFormatError,
)
from src.core.models import Task
from src.services.task_service import TaskService
from src.logging_setup.logger import get_logger

logger = get_logger(__name__)

CSV_FIELDS = [
    "id", "title", "description", "priority", "status",
    "tags", "notes", "due_date", "created_at", "updated_at",
]


class ExportService:
    """Exports tasks to CSV or JSON files asynchronously."""

    def __init__(self, task_service: TaskService, export_dir: Path) -> None:
        self._svc       = task_service
        self._export_dir = export_dir
        self._export_dir.mkdir(parents=True, exist_ok=True)

    # ── public API ────────────────────────────────────────────────────────────

    async def export(
        self,
        fmt:      str,
        filename: str | None = None,
        filters:  dict | None = None,
    ) -> Path:
        """Export tasks in *fmt* (csv|json). Returns the output file path."""
        fmt = fmt.lower()
        if fmt not in ("csv", "json"):
            raise InvalidExportFormatError(fmt)

        tasks = await self._load_tasks(filters or {})
        ts    = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        fname = filename or f"taskguard_export_{ts}.{fmt}"
        out   = self._export_dir / fname

        if fmt == "csv":
            return await self._export_csv(tasks, out)
        return await self._export_json(tasks, out)

    # ── CSV ───────────────────────────────────────────────────────────────────

    async def _export_csv(self, tasks: list[Task], path: Path) -> Path:
        """Write tasks to a UTF-8 CSV file."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._write_csv, tasks, path)
        except CSVExportError:
            raise
        except Exception as exc:
            raise CSVExportError(str(path), str(exc)) from exc
        logger.info("csv_export", extra={"path": str(path), "count": len(tasks)})
        return path

    def _write_csv(self, tasks: list[Task], path: Path) -> None:
        try:
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()
                for task in tasks:
                    row = dict(task)
                    row["tags"]    = "|".join(row["tags"])
                    row["due_date"]   = row["due_date"]   or ""
                    writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})
        except OSError as exc:
            raise CSVExportError(str(path), str(exc)) from exc

    # ── JSON ──────────────────────────────────────────────────────────────────

    async def _export_json(self, tasks: list[Task], path: Path) -> Path:
        """Write tasks to a pretty-printed JSON file."""
        try:
            data = {
                "exported_at": datetime.utcnow().isoformat(),
                "count":       len(tasks),
                "tasks":       [dict(t) for t in tasks],
            }
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._write_json, data, path)
        except JSONExportError:
            raise
        except Exception as exc:
            raise JSONExportError(str(path), str(exc)) from exc
        logger.info("json_export", extra={"path": str(path), "count": len(tasks)})
        return path

    def _write_json(self, data: dict, path: Path) -> None:
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except OSError as exc:
            raise JSONExportError(str(path), str(exc)) from exc

    # ── streaming generator ───────────────────────────────────────────────────

    async def stream_export_lines(
        self, fmt: str = "json"
    ) -> AsyncGenerator[str, None]:
        """
        Async generator that yields one line/record at a time.
        Useful for piping large exports without loading everything into memory.
        """
        if fmt == "json":
            yield '{"tasks":[\n'
            first = True
            async for task in self._svc.stream_tasks():
                prefix = "" if first else ",\n"
                first  = False
                yield prefix + json.dumps(dict(task), default=str)
            yield "\n]}\n"
        elif fmt == "csv":
            yield ",".join(CSV_FIELDS) + "\n"
            async for task in self._svc.stream_tasks():
                row = dict(task)
                row["tags"] = "|".join(row["tags"])
                yield ",".join(str(row.get(k, "")) for k in CSV_FIELDS) + "\n"

    # ── helpers ───────────────────────────────────────────────────────────────

    async def _load_tasks(self, filters: dict) -> list[Task]:
        from src.core.models import Status, Priority
        status   = Status.from_string(filters["status"])     if filters.get("status")   else None
        priority = Priority.from_string(filters["priority"]) if filters.get("priority") else None
        return await self._svc.list_tasks(status=status, priority=priority)
