"""Tests for ExportService: CSV and JSON export, streaming generator."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.core.exceptions import InvalidExportFormatError


@pytest.mark.asyncio
class TestCSVExport:
    async def test_export_csv_creates_file(self, export_svc, multiple_tasks):
        path = await export_svc.export("csv")
        assert path.exists()
        assert path.suffix == ".csv"

    async def test_export_csv_has_header(self, export_svc, multiple_tasks):
        path = await export_svc.export("csv")
        with path.open() as f:
            reader = csv.DictReader(f)
            assert "title" in reader.fieldnames
            assert "priority" in reader.fieldnames
            assert "status" in reader.fieldnames

    async def test_export_csv_row_count(self, export_svc, multiple_tasks):
        path = await export_svc.export("csv")
        with path.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == len(multiple_tasks)

    async def test_export_csv_custom_filename(self, export_svc, created_task):
        path = await export_svc.export("csv", filename="my_export.csv")
        assert path.name == "my_export.csv"

    async def test_export_csv_tags_pipe_joined(self, export_svc):
        from src.services.task_service import TaskService
        task = await export_svc._svc.create_task(
            title="Tagged", priority="LOW", status="NOT_STARTED",
            tags=["alpha", "beta"],
        )
        path = await export_svc.export("csv")
        with path.open() as f:
            rows = {r["id"]: r for r in csv.DictReader(f)}
        assert "alpha|beta" == rows[task.id]["tags"]


@pytest.mark.asyncio
class TestJSONExport:
    async def test_export_json_creates_file(self, export_svc, multiple_tasks):
        path = await export_svc.export("json")
        assert path.exists()
        assert path.suffix == ".json"

    async def test_export_json_valid_structure(self, export_svc, multiple_tasks):
        path = await export_svc.export("json")
        with path.open() as f:
            data = json.load(f)
        assert "tasks" in data
        assert "exported_at" in data
        assert data["count"] == len(multiple_tasks)

    async def test_export_json_task_fields(self, export_svc, created_task):
        path = await export_svc.export("json")
        with path.open() as f:
            data = json.load(f)
        titles = [t["title"] for t in data["tasks"]]
        assert created_task.title in titles

    async def test_export_json_custom_filename(self, export_svc, created_task):
        path = await export_svc.export("json", filename="out.json")
        assert path.name == "out.json"


@pytest.mark.asyncio
class TestExportErrors:
    async def test_invalid_format_raises(self, export_svc):
        with pytest.raises(InvalidExportFormatError):
            await export_svc.export("xlsx")

    async def test_invalid_format_case_insensitive(self, export_svc):
        # CSV and JSON in any case are valid
        path = await export_svc.export("CSV")
        assert path.exists()


@pytest.mark.asyncio
class TestStreamExport:
    async def test_stream_json(self, export_svc, multiple_tasks):
        lines = []
        async for line in export_svc.stream_export_lines("json"):
            lines.append(line)
        combined = "".join(lines)
        data = json.loads(combined)
        assert "tasks" in data

    async def test_stream_csv(self, export_svc, multiple_tasks):
        lines = []
        async for line in export_svc.stream_export_lines("csv"):
            lines.append(line)
        assert len(lines) > 1    # at least header + 1 row
        assert "title" in lines[0]
