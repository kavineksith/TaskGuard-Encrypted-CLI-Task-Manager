"""
TaskGuard - Database Schema
DDL statements for the SQLite database.
All schema objects are created with IF NOT EXISTS for idempotent initialisation.
"""

# ─── core table ──────────────────────────────────────────────────────────────
CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    id             TEXT    PRIMARY KEY NOT NULL,
    priority       TEXT    NOT NULL,
    status         TEXT    NOT NULL,
    created_at     TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL,
    due_date       TEXT,
    encrypted_data BLOB    NOT NULL,
    nonce          BLOB    NOT NULL
);
"""

# ─── performance indices ──────────────────────────────────────────────────────
CREATE_IDX_PRIORITY   = "CREATE INDEX IF NOT EXISTS idx_tasks_priority   ON tasks(priority);"
CREATE_IDX_STATUS     = "CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status);"
CREATE_IDX_DUE_DATE   = "CREATE INDEX IF NOT EXISTS idx_tasks_due_date   ON tasks(due_date);"
CREATE_IDX_CREATED_AT = "CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);"
CREATE_IDX_UPDATED_AT = "CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at);"
CREATE_IDX_STATUS_PRIO= (
    "CREATE INDEX IF NOT EXISTS idx_tasks_status_priority "
    "ON tasks(status, priority);"
)

# ─── full-text search index ───────────────────────────────────────────────────
# Stores plaintext title/tags for FTS; acceptable trade-off for searchability.
CREATE_FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
    task_id  UNINDEXED,
    title,
    tags,
    tokenize = 'porter ascii'
);
"""

# ─── audit / event log table ─────────────────────────────────────────────────
CREATE_AUDIT_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp  TEXT    NOT NULL,
    event      TEXT    NOT NULL,
    task_id    TEXT,
    actor      TEXT    DEFAULT 'cli',
    detail     TEXT
);
"""

CREATE_IDX_AUDIT_TASK = (
    "CREATE INDEX IF NOT EXISTS idx_audit_task ON audit_log(task_id);"
)
CREATE_IDX_AUDIT_TS   = (
    "CREATE INDEX IF NOT EXISTS idx_audit_ts   ON audit_log(timestamp);"
)

# ─── PRAGMA pragmas for performance ──────────────────────────────────────────
PRAGMA_JOURNAL_WAL  = "PRAGMA journal_mode=WAL;"
PRAGMA_FOREIGN_KEYS = "PRAGMA foreign_keys=ON;"
PRAGMA_SYNCHRONOUS  = "PRAGMA synchronous=NORMAL;"
PRAGMA_CACHE_SIZE   = "PRAGMA cache_size=-16384;"   # 16 MiB page cache

# ─── DDL execution order ──────────────────────────────────────────────────────
ALL_SCHEMA_DDL: list[str] = [
    PRAGMA_JOURNAL_WAL,
    PRAGMA_FOREIGN_KEYS,
    PRAGMA_SYNCHRONOUS,
    PRAGMA_CACHE_SIZE,
    CREATE_TASKS_TABLE,
    CREATE_IDX_PRIORITY,
    CREATE_IDX_STATUS,
    CREATE_IDX_DUE_DATE,
    CREATE_IDX_CREATED_AT,
    CREATE_IDX_UPDATED_AT,
    CREATE_IDX_STATUS_PRIO,
    CREATE_FTS_TABLE,
    CREATE_AUDIT_TABLE,
    CREATE_IDX_AUDIT_TASK,
    CREATE_IDX_AUDIT_TS,
]

# ─── query templates ──────────────────────────────────────────────────────────
# Using named placeholders for clarity and safety (all ? positional)

INSERT_TASK = """
INSERT INTO tasks (id, priority, status, created_at, updated_at,
                   due_date, encrypted_data, nonce)
VALUES (?, ?, ?, ?, ?, ?, ?, ?);
"""

SELECT_TASK_BY_ID = """
SELECT id, priority, status, created_at, updated_at,
       due_date, encrypted_data, nonce
FROM   tasks
WHERE  id = ?;
"""

UPDATE_TASK = """
UPDATE tasks
SET    priority       = ?,
       status         = ?,
       updated_at     = ?,
       due_date       = ?,
       encrypted_data = ?,
       nonce          = ?
WHERE  id = ?;
"""

DELETE_TASK = "DELETE FROM tasks WHERE id = ?;"

SELECT_ALL_TASKS = """
SELECT id, priority, status, created_at, updated_at,
       due_date, encrypted_data, nonce
FROM   tasks
ORDER  BY priority DESC, due_date ASC NULLS LAST, created_at DESC;
"""

SELECT_TASKS_BY_STATUS = """
SELECT id, priority, status, created_at, updated_at,
       due_date, encrypted_data, nonce
FROM   tasks
WHERE  status = ?
ORDER  BY priority DESC, due_date ASC NULLS LAST;
"""

SELECT_TASKS_BY_PRIORITY = """
SELECT id, priority, status, created_at, updated_at,
       due_date, encrypted_data, nonce
FROM   tasks
WHERE  priority = ?
ORDER  BY due_date ASC NULLS LAST, created_at DESC;
"""

SELECT_TASKS_DUE_BEFORE = """
SELECT id, priority, status, created_at, updated_at,
       due_date, encrypted_data, nonce
FROM   tasks
WHERE  due_date IS NOT NULL
  AND  due_date <= ?
  AND  status NOT IN ('COMPLETED', 'NOT_COMPLETED')
ORDER  BY due_date ASC;
"""

SELECT_TASKS_OVERDUE = """
SELECT id, priority, status, created_at, updated_at,
       due_date, encrypted_data, nonce
FROM   tasks
WHERE  due_date IS NOT NULL
  AND  due_date < ?
  AND  status NOT IN ('COMPLETED', 'NOT_COMPLETED')
ORDER  BY due_date ASC;
"""

COUNT_TASKS        = "SELECT COUNT(*) FROM tasks;"
COUNT_BY_STATUS    = "SELECT status, COUNT(*) FROM tasks GROUP BY status;"
COUNT_BY_PRIORITY  = "SELECT priority, COUNT(*) FROM tasks GROUP BY priority;"

INSERT_FTS = """
INSERT INTO tasks_fts (task_id, title, tags)
VALUES (?, ?, ?);
"""

UPDATE_FTS = """
INSERT OR REPLACE INTO tasks_fts (task_id, title, tags)
VALUES (?, ?, ?);
"""

DELETE_FTS = "DELETE FROM tasks_fts WHERE task_id = ?;"

SEARCH_FTS = """
SELECT f.task_id, f.rank
FROM   tasks_fts f
WHERE  tasks_fts MATCH ?
ORDER  BY rank;
"""

SELECT_TASKS_BY_IDS = """
SELECT id, priority, status, created_at, updated_at,
       due_date, encrypted_data, nonce
FROM   tasks
WHERE  id IN ({placeholders});
"""

INSERT_AUDIT = """
INSERT INTO audit_log (timestamp, event, task_id, actor, detail)
VALUES (?, ?, ?, ?, ?);
"""
