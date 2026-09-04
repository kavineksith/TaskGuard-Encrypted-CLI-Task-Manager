"""Tests for the exception hierarchy."""

from __future__ import annotations

import pytest
from src.core.exceptions import (
    TaskGuardError, Severity,
    DatabaseConnectionError, DatabaseQueryError, RecordNotFoundError,
    DuplicateRecordError, EncryptionError, DecryptionError, TamperedDataError,
    KeyDerivationError, InvalidKeyError, TaskNotFoundError, TaskValidationError,
    EmptyTitleError, InvalidStatusTransitionError, InvalidPriorityError,
    CSVExportError, JSONExportError, InvalidExportFormatError,
    NotificationInitError, InvalidCommandError, AuthenticationError,
    InvalidSearchQueryError,
)


class TestSeverity:
    def test_ordering(self):
        assert Severity.DEBUG < Severity.INFO < Severity.WARNING < Severity.ERROR < Severity.CRITICAL

    def test_ge_le(self):
        assert Severity.ERROR >= Severity.ERROR
        assert Severity.DEBUG <= Severity.WARNING

    def test_str_repr(self):
        assert str(Severity.ERROR) == "ERROR"
        assert "Severity" in repr(Severity.INFO)


class TestBaseException:
    def test_str_includes_code(self):
        exc = TaskGuardError("bad thing", code="TGS-0001")
        assert "TGS-0001" in str(exc)

    def test_repr(self):
        exc = TaskGuardError("bad thing")
        r   = repr(exc)
        assert "TaskGuardError" in r and "message" in r

    def test_eq(self):
        a = TaskGuardError("msg", code="TGS-0001")
        b = TaskGuardError("msg", code="TGS-0001")
        assert a == b

    def test_hash(self):
        a = TaskGuardError("msg", code="TGS-0001")
        b = TaskGuardError("msg", code="TGS-0001")
        assert hash(a) == hash(b)

    def test_bool(self):
        assert bool(TaskGuardError("x")) is True

    def test_len(self):
        exc = TaskGuardError("hello")
        assert len(exc) == 5

    def test_contains(self):
        exc = TaskGuardError("connection refused")
        assert "refused" in exc

    def test_iter(self):
        exc = TaskGuardError("x", code="TGS-0001")
        d   = dict(exc)
        assert "code" in d and "message" in d and "timestamp" in d

    def test_to_dict(self):
        exc = TaskGuardError("x")
        assert isinstance(exc.to_dict(), dict)

    def test_context_stored(self):
        exc = TaskGuardError("x", context={"key": "val"})
        assert exc.context["key"] == "val"


class TestDatabaseExceptions:
    def test_connection_error_message(self):
        exc = DatabaseConnectionError("/path/to.db", "locked")
        assert "/path/to.db" in str(exc)
        assert "locked" in str(exc)

    def test_record_not_found_bool(self):
        exc = RecordNotFoundError("Task", "abc-123")
        assert bool(exc) is False

    def test_duplicate_record_context(self):
        exc = DuplicateRecordError("Task", "title", "My Task")
        assert exc.context["field"] == "title"


class TestCryptoExceptions:
    def test_encryption_error(self):
        exc = EncryptionError("cipher failure")
        assert exc.severity == Severity.CRITICAL

    def test_tampered_data_with_id(self):
        exc = TamperedDataError("task-001")
        assert "task-001" in str(exc)

    def test_invalid_key_default_length(self):
        exc = InvalidKeyError()
        assert "32" in str(exc)


class TestTaskExceptions:
    def test_task_not_found_bool(self):
        exc = TaskNotFoundError("abc-123")
        assert bool(exc) is False

    def test_task_not_found_context(self):
        exc = TaskNotFoundError("abc-123")
        assert exc.context["task_id"] == "abc-123"

    def test_empty_title(self):
        exc = EmptyTitleError()
        assert "empty" in str(exc).lower()

    def test_invalid_status_transition(self):
        exc = InvalidStatusTransitionError("COMPLETED", "PENDING")
        assert "COMPLETED" in str(exc) and "PENDING" in str(exc)

    def test_invalid_priority(self):
        exc = InvalidPriorityError("ULTRA")
        assert "ULTRA" in str(exc)


class TestExportExceptions:
    def test_csv_export_error_path(self):
        exc = CSVExportError("/output/file.csv", "disk full")
        assert "/output/file.csv" in str(exc)

    def test_invalid_format(self):
        exc = InvalidExportFormatError("xlsx")
        assert "xlsx" in str(exc)


class TestNotifyExceptions:
    def test_notify_init(self):
        exc = NotificationInitError("no event loop")
        assert "no event loop" in str(exc)


class TestCLIExceptions:
    def test_invalid_command(self):
        exc = InvalidCommandError("flibble")
        assert "flibble" in str(exc)

    def test_auth_bool(self):
        exc = AuthenticationError()
        assert bool(exc) is False


class TestSearchExceptions:
    def test_invalid_query(self):
        exc = InvalidSearchQueryError("(((", "unmatched parens")
        assert "(((" in str(exc)
