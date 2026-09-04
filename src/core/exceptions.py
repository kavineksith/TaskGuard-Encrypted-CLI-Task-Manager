"""
TaskGuard - Exception Hierarchy
25+ custom exception classes with structured error codes, severity levels,
and context payload dicts. All exceptions carry TGS-XXXX codes.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any

from src.constants import ErrorCode


# ─── severity enum ────────────────────────────────────────────────────────────

class Severity(Enum):
    DEBUG    = "DEBUG"
    INFO     = "INFO"
    WARNING  = "WARNING"
    ERROR    = "ERROR"
    CRITICAL = "CRITICAL"

    def __str__(self)  -> str: return self.value
    def __repr__(self) -> str: return f"Severity.{self.value}"
    def __lt__(self, other: "Severity") -> bool:
        order = [s.value for s in Severity]
        return order.index(self.value) < order.index(other.value)
    def __le__(self, other: "Severity") -> bool: return self == other or self < other
    def __gt__(self, other: "Severity") -> bool: return not self <= other
    def __ge__(self, other: "Severity") -> bool: return not self < other


# ─── base exception ───────────────────────────────────────────────────────────

class TaskGuardError(Exception):
    """Root exception for all TaskGuard errors."""

    def __init__(
        self,
        message: str,
        code: str = ErrorCode.UNKNOWN,
        severity: Severity = Severity.ERROR,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message   = message
        self.code      = code
        self.severity  = severity
        self.context   = context or {}
        self.timestamp = datetime.utcnow().isoformat()

    def __str__(self)  -> str: return f"[{self.code}] {self.message}"
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(code={self.code!r}, "
            f"severity={self.severity!r}, message={self.message!r})"
        )
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TaskGuardError): return NotImplemented
        return self.code == other.code and self.message == other.message
    def __hash__(self) -> int: return hash((self.code, self.message))
    def __bool__(self)  -> bool: return True
    def __len__(self)   -> int: return len(self.message)
    def __contains__(self, item: str) -> bool: return item in self.message
    def __iter__(self):
        yield "code",      self.code
        yield "severity",  str(self.severity)
        yield "message",   self.message
        yield "timestamp", self.timestamp
        yield "context",   self.context

    def to_dict(self) -> dict[str, Any]:
        return dict(self)


# ─── database exceptions ─────────────────────────────────────────────────────

class DatabaseError(TaskGuardError):
    """Base class for all database-related errors."""
    def __init__(self, message: str, code: str = ErrorCode.DB_CONNECTION,
                 context: dict | None = None) -> None:
        super().__init__(message, code, Severity.ERROR, context)


class DatabaseConnectionError(DatabaseError):
    """Raised when the SQLite connection cannot be established."""
    def __init__(self, db_path: str, cause: str = "") -> None:
        super().__init__(
            f"Cannot connect to database at '{db_path}': {cause}",
            ErrorCode.DB_CONNECTION,
            {"db_path": db_path, "cause": cause},
        )


class DatabaseQueryError(DatabaseError):
    """Raised when a SQL query fails at execution time."""
    def __init__(self, query: str, cause: str = "") -> None:
        safe = query[:120] + "..." if len(query) > 120 else query
        super().__init__(
            f"Query execution failed: {cause}",
            ErrorCode.DB_QUERY,
            {"query": safe, "cause": cause},
        )


class DatabaseTransactionError(DatabaseError):
    """Raised when a transaction cannot be committed or rolled back."""
    def __init__(self, operation: str, cause: str = "") -> None:
        super().__init__(
            f"Transaction '{operation}' failed: {cause}",
            ErrorCode.DB_TRANSACTION,
            {"operation": operation, "cause": cause},
        )


class DatabaseSchemaError(DatabaseError):
    """Raised when schema creation or migration fails."""
    def __init__(self, cause: str = "") -> None:
        super().__init__(
            f"Schema initialisation failed: {cause}",
            ErrorCode.DB_SCHEMA,
            {"cause": cause},
        )


class DatabaseIntegrityError(DatabaseError):
    """Raised on constraint violations (FK, UNIQUE, NOT NULL)."""
    def __init__(self, constraint: str, cause: str = "") -> None:
        super().__init__(
            f"Integrity constraint '{constraint}' violated: {cause}",
            ErrorCode.DB_INTEGRITY,
            {"constraint": constraint, "cause": cause},
        )


class RecordNotFoundError(DatabaseError):
    """Raised when a requested record does not exist."""
    def __init__(self, entity: str, identifier: str) -> None:
        super().__init__(
            f"{entity} with id '{identifier}' not found.",
            ErrorCode.DB_NOT_FOUND,
            {"entity": entity, "identifier": identifier},
        )
    def __bool__(self) -> bool: return False


class DuplicateRecordError(DatabaseError):
    """Raised when an insert would violate a uniqueness constraint."""
    def __init__(self, entity: str, field: str, value: str) -> None:
        super().__init__(
            f"{entity} already exists with {field}='{value}'.",
            ErrorCode.DB_DUPLICATE,
            {"entity": entity, "field": field, "value": value},
        )


# ─── crypto exceptions ───────────────────────────────────────────────────────

class CryptoError(TaskGuardError):
    """Base class for all cryptographic errors."""
    def __init__(self, message: str, code: str = ErrorCode.CRYPTO_ENCRYPT,
                 context: dict | None = None) -> None:
        super().__init__(message, code, Severity.CRITICAL, context)


class EncryptionError(CryptoError):
    """Raised when AES-256-GCM encryption fails."""
    def __init__(self, cause: str = "") -> None:
        super().__init__(f"Encryption failed: {cause}", ErrorCode.CRYPTO_ENCRYPT,
                         {"cause": cause})


class DecryptionError(CryptoError):
    """Raised when AES-256-GCM decryption or authentication fails."""
    def __init__(self, cause: str = "") -> None:
        super().__init__(f"Decryption failed (data may be tampered): {cause}",
                         ErrorCode.CRYPTO_DECRYPT, {"cause": cause})


class KeyDerivationError(CryptoError):
    """Raised when Argon2id key derivation fails."""
    def __init__(self, cause: str = "") -> None:
        super().__init__(f"Key derivation failed: {cause}",
                         ErrorCode.CRYPTO_KEY_DERIVE, {"cause": cause})


class InvalidKeyError(CryptoError):
    """Raised when the provided key is invalid or wrong length."""
    def __init__(self, expected_len: int = 32) -> None:
        super().__init__(
            f"Invalid key: expected {expected_len}-byte key.",
            ErrorCode.CRYPTO_INVALID, {"expected_length": expected_len},
        )


class TamperedDataError(CryptoError):
    """Raised when GCM authentication tag verification fails (data tampered)."""
    def __init__(self, record_id: str = "") -> None:
        super().__init__(
            f"Authentication tag mismatch — data may be corrupted or tampered"
            + (f" (record: {record_id})" if record_id else "."),
            ErrorCode.CRYPTO_TAMPERED, {"record_id": record_id},
        )


class KeyStoreError(CryptoError):
    """Raised when reading/writing the key config file fails."""
    def __init__(self, path: str, cause: str = "") -> None:
        super().__init__(f"Key store I/O error at '{path}': {cause}",
                         ErrorCode.CRYPTO_STORE, {"path": path, "cause": cause})


class NonceGenerationError(CryptoError):
    """Raised when nonce (IV) generation fails."""
    def __init__(self, cause: str = "") -> None:
        super().__init__(f"Nonce generation failed: {cause}",
                         ErrorCode.CRYPTO_NONCE, {"cause": cause})


# ─── task domain exceptions ───────────────────────────────────────────────────

class TaskError(TaskGuardError):
    """Base class for task domain errors."""
    def __init__(self, message: str, code: str = ErrorCode.TASK_VALIDATION,
                 context: dict | None = None) -> None:
        super().__init__(message, code, Severity.WARNING, context)


class TaskNotFoundError(TaskError):
    """Raised when a task with the given id does not exist."""
    def __init__(self, task_id: str) -> None:
        super().__init__(
            f"Task '{task_id}' not found.",
            ErrorCode.TASK_NOT_FOUND, {"task_id": task_id},
        )
    def __bool__(self) -> bool: return False


class TaskValidationError(TaskError):
    """Raised when task field validation fails."""
    def __init__(self, field: str, reason: str) -> None:
        super().__init__(
            f"Validation failed for field '{field}': {reason}",
            ErrorCode.TASK_VALIDATION, {"field": field, "reason": reason},
        )


class DuplicateTaskError(TaskError):
    """Raised when a task with the same title already exists."""
    def __init__(self, title: str) -> None:
        super().__init__(
            f"A task titled '{title}' already exists.",
            ErrorCode.TASK_DUPLICATE, {"title": title},
        )


class TaskConstraintError(TaskError):
    """Raised when a business constraint is violated."""
    def __init__(self, constraint: str, detail: str = "") -> None:
        super().__init__(
            f"Constraint violated: {constraint}" + (f" — {detail}" if detail else ""),
            ErrorCode.TASK_CONSTRAINT, {"constraint": constraint, "detail": detail},
        )


class InvalidStatusTransitionError(TaskError):
    """Raised when an illegal status transition is attempted."""
    def __init__(self, current: str, requested: str) -> None:
        super().__init__(
            f"Cannot transition from '{current}' to '{requested}'.",
            ErrorCode.TASK_TRANSITION, {"current": current, "requested": requested},
        )


class InvalidPriorityError(TaskError):
    """Raised when an unrecognised priority value is provided."""
    def __init__(self, value: str) -> None:
        super().__init__(
            f"'{value}' is not a valid priority. Use: LOW, MEDIUM, HIGH, CRITICAL.",
            ErrorCode.TASK_PRIORITY, {"value": value},
        )


class InvalidDueDateError(TaskError):
    """Raised when the due date is logically invalid."""
    def __init__(self, due_date: str, reason: str = "") -> None:
        super().__init__(
            f"Invalid due date '{due_date}'" + (f": {reason}" if reason else "."),
            ErrorCode.TASK_DATE, {"due_date": due_date, "reason": reason},
        )


class EmptyTitleError(TaskError):
    """Raised when the task title is empty or whitespace-only."""
    def __init__(self) -> None:
        super().__init__("Task title cannot be empty.", ErrorCode.TASK_TITLE)


# ─── search exceptions ────────────────────────────────────────────────────────

class SearchError(TaskGuardError):
    """Base class for search errors."""
    def __init__(self, message: str, code: str = ErrorCode.SEARCH_QUERY,
                 context: dict | None = None) -> None:
        super().__init__(message, code, Severity.WARNING, context)


class InvalidSearchQueryError(SearchError):
    """Raised when the FTS query string is malformed."""
    def __init__(self, query: str, reason: str = "") -> None:
        super().__init__(
            f"Invalid search query '{query}'" + (f": {reason}" if reason else "."),
            ErrorCode.SEARCH_QUERY, {"query": query, "reason": reason},
        )


class SearchTimeoutError(SearchError):
    """Raised when a search operation exceeds the time limit."""
    def __init__(self, timeout_s: float) -> None:
        super().__init__(
            f"Search timed out after {timeout_s:.1f}s.",
            ErrorCode.SEARCH_TIMEOUT, {"timeout_s": timeout_s},
        )


class SearchIndexError(SearchError):
    """Raised when the FTS index is corrupt or cannot be rebuilt."""
    def __init__(self, cause: str = "") -> None:
        super().__init__(
            f"Search index error: {cause}", ErrorCode.SEARCH_INDEX, {"cause": cause},
        )


# ─── export exceptions ────────────────────────────────────────────────────────

class ExportError(TaskGuardError):
    """Base class for export errors."""
    def __init__(self, message: str, code: str = ErrorCode.EXPORT_FILE_IO,
                 context: dict | None = None) -> None:
        super().__init__(message, code, Severity.ERROR, context)


class CSVExportError(ExportError):
    """Raised when CSV export fails."""
    def __init__(self, path: str, cause: str = "") -> None:
        super().__init__(
            f"CSV export to '{path}' failed: {cause}",
            ErrorCode.EXPORT_CSV, {"path": path, "cause": cause},
        )


class JSONExportError(ExportError):
    """Raised when JSON export fails."""
    def __init__(self, path: str, cause: str = "") -> None:
        super().__init__(
            f"JSON export to '{path}' failed: {cause}",
            ErrorCode.EXPORT_JSON, {"path": path, "cause": cause},
        )


class ExportFileIOError(ExportError):
    """Raised on generic file I/O failure during export."""
    def __init__(self, path: str, cause: str = "") -> None:
        super().__init__(
            f"File I/O error during export to '{path}': {cause}",
            ErrorCode.EXPORT_FILE_IO, {"path": path, "cause": cause},
        )


class InvalidExportFormatError(ExportError):
    """Raised when an unsupported export format is requested."""
    def __init__(self, fmt: str) -> None:
        super().__init__(
            f"Unsupported export format '{fmt}'. Use: csv, json.",
            ErrorCode.EXPORT_INVALID, {"format": fmt},
        )


# ─── notification exceptions ──────────────────────────────────────────────────

class NotificationError(TaskGuardError):
    """Base class for notification errors."""
    def __init__(self, message: str, code: str = ErrorCode.NOTIFY_SEND,
                 context: dict | None = None) -> None:
        super().__init__(message, code, Severity.WARNING, context)


class NotificationInitError(NotificationError):
    """Raised when the notification background task fails to start."""
    def __init__(self, cause: str = "") -> None:
        super().__init__(
            f"Notification service failed to initialise: {cause}",
            ErrorCode.NOTIFY_INIT, {"cause": cause},
        )


class NotificationSendError(NotificationError):
    """Raised when a notification cannot be delivered."""
    def __init__(self, cause: str = "") -> None:
        super().__init__(
            f"Failed to send notification: {cause}",
            ErrorCode.NOTIFY_SEND, {"cause": cause},
        )


# ─── CLI exceptions ───────────────────────────────────────────────────────────

class CLIError(TaskGuardError):
    """Base class for CLI errors."""
    def __init__(self, message: str, code: str = ErrorCode.CLI_COMMAND,
                 context: dict | None = None) -> None:
        super().__init__(message, code, Severity.WARNING, context)


class InvalidCommandError(CLIError):
    """Raised when an unrecognised CLI command is entered."""
    def __init__(self, command: str) -> None:
        super().__init__(
            f"Unknown command '{command}'. Type 'help' for available commands.",
            ErrorCode.CLI_COMMAND, {"command": command},
        )


class CLIParseError(CLIError):
    """Raised when argument parsing fails."""
    def __init__(self, reason: str) -> None:
        super().__init__(
            f"Argument parse error: {reason}",
            ErrorCode.CLI_PARSE, {"reason": reason},
        )


class CLIInputError(CLIError):
    """Raised on invalid interactive user input."""
    def __init__(self, field: str, value: str, reason: str = "") -> None:
        super().__init__(
            f"Invalid input for '{field}': '{value}'" + (f" — {reason}" if reason else "."),
            ErrorCode.CLI_INPUT, {"field": field, "value": value, "reason": reason},
        )


class AuthenticationError(CLIError):
    """Raised when master-password authentication fails."""
    def __init__(self) -> None:
        super().__init__(
            "Authentication failed. Incorrect master password.",
            ErrorCode.CLI_AUTH, {},
        )
    def __bool__(self) -> bool: return False
