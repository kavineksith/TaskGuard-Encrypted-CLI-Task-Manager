# TaskGuard — Encrypted CLI Task Manager

**Version:** 1.0.0  
**Author:** Security Portfolio Project  
**License:** MIT  

---

## The Problem

Most task managers store your data in plaintext — on disk, in the cloud, or in unprotected SQLite files. For security professionals and anyone handling sensitive project information, this is unacceptable. Existing free tools offer no encryption, weak export options, or clunky interfaces.

**TaskGuard** solves this by providing:

- **AES-256-GCM encryption** of all sensitive task content at rest
- **Argon2id key derivation** — purpose-built for password hashing, resistant to GPU cracking
- A **fast, colorised CLI** with both interactive REPL and single-command (scriptable) modes
- **FTS5 full-text search** with prefix matching and tag filtering
- **Priority and status management** with enforced transition rules
- **Overdue/due-soon notifications** with a background async poller
- **CSV and JSON export** with optional filters
- A full **JSON-lines audit log** for every operation

---

## Architecture

```
taskguard/
├── src/
│   ├── constants.py              # Error codes, app metadata, transition maps
│   ├── core/
│   │   ├── exceptions.py         # 25+ custom exception classes (TGS-XXXX codes)
│   │   └── models.py             # Task, Priority, Status — full dunder suites
│   ├── crypto/
│   │   └── vault.py              # AES-256-GCM + Argon2id KDF
│   ├── database/
│   │   ├── schema.py             # DDL: tables, FTS5, indices, audit log
│   │   └── repository.py         # Async CRUD via aiosqlite, async generators
│   ├── services/
│   │   ├── task_service.py       # Business logic, validation, bulk ops
│   │   ├── export_service.py     # CSV/JSON export, streaming generator
│   │   └── notification_service.py  # Terminal banners, background poller
│   ├── ui/
│   │   ├── colors.py             # ANSI escape codes, priority/status colours
│   │   ├── display.py            # Box-drawing tables, detail cards, stats dashboard
│   │   └── progress.py           # Custom progress bar + spinner (zero dependencies)
│   ├── logging_setup/
│   │   └── logger.py             # QueueHandler/QueueListener, ANSI + JSON-lines sinks
│   └── cli/
│       ├── parser.py             # argparse — all commands with flags
│       └── interactive.py        # Full REPL with readline history
├── tests/                        # 181 tests, 100% pass rate
├── main.py                       # Entry point
├── requirements.txt
├── setup.py / setup.cfg
└── run.sh                        # Bootstrap script (Python check, venv, deps)
```

### Key Design Decisions

| Concern | Decision |
|---|---|
| Encryption | AES-256-GCM — authenticated encryption; tampered data raises `TamperedDataError` |
| Key derivation | Argon2id (3 iterations, 64 MiB, 2-way parallel) — resistant to side-channel attacks |
| Async I/O | `aiosqlite` throughout; `asyncio.Semaphore(8)` caps concurrent DB ops |
| Search | SQLite FTS5 with Porter stemmer; plaintext title/tags stored for searchability |
| Logging | `QueueHandler`/`QueueListener` — non-blocking; ANSI console + JSON-lines audit file |
| Status transitions | Enforced via `STATUS_TRANSITIONS` map; illegal moves raise `InvalidStatusTransitionError` |
| Memory efficiency | `AsyncGenerator` yields in repository and export layers — large datasets never fully loaded |
| Error codes | Every exception carries a `TGS-XXXX` code for structured log correlation |

---

## Requirements

- Python 3.12 or higher
- Linux / macOS / WSL2 (Windows without WSL2 is unsupported for the `run.sh` script)

Dependencies (auto-installed by `run.sh`):

```
aiosqlite>=0.20.0
cryptography>=42.0.0
argon2-cffi>=23.1.0
```

---

## Installation & First Run

```bash
git clone <repo-url>
cd taskguard
chmod +x run.sh
./run.sh
```

On first run you will be prompted to create a **master password**. This password is passed through Argon2id to derive the 256-bit AES key. A 32-byte random salt is written to `~/.taskguard/taskguard.cfg` (permissions: `600`). **Do not lose this password** — there is no recovery mechanism.

To use a custom data directory:

```bash
export TASKGUARD_DATA_DIR="/secure/path"
./run.sh
```

To pass the password non-interactively (CI / scripting):

```bash
export TASKGUARD_PASSWORD="my-pass"
./run.sh list --status PENDING
```

---

## Interactive Shell

Run `./run.sh` (no arguments) to enter the REPL:

```
taskguard > 
```

### Task Management Commands

| Command | Description |
|---|---|
| `add` | Create a new task (guided prompts) |
| `list` | List all tasks |
| `list -s PENDING` | Filter by status |
| `list -p HIGH` | Filter by priority |
| `list --overdue` | Show only overdue tasks |
| `view <id>` | Full task detail card |
| `edit <id>` | Edit any field interactively |
| `done <id>` | Mark task COMPLETED |
| `delete <id>` | Delete (asks for confirmation) |

### Search

```
taskguard > search backend deploy
taskguard > search "infrastructure OR cloud"
```

FTS5 supports boolean operators (`AND`, `OR`, `NOT`) and prefix matching.

### Bulk Operations

```
taskguard > bulk-delete <id1> <id2> <id3>
taskguard > bulk-status COMPLETED <id1> <id2>
```

### Analytics

```
taskguard > stats
taskguard > notify
```

### Export

```
taskguard > export csv
taskguard > export json -s PENDING -p HIGH
```

---

## Non-Interactive (Scriptable) Mode

All REPL commands are available as CLI subcommands:

```bash
# Create a task
./run.sh add "Patch CVE-2024-1234" --priority CRITICAL --status PENDING \
  --due "2024-12-31 09:00" --tags "security,urgent" \
  --description "Apply vendor patch to prod servers"

# List by status and priority
./run.sh list --status ONGOING --priority HIGH

# Search
./run.sh search "patch vulnerability"

# Update
./run.sh edit <id> --status COMPLETED

# Export (filtered)
./run.sh export csv --status COMPLETED --output done_tasks.csv

# Statistics
./run.sh stats
```

---

## Priority Levels

| Value | Description |
|---|---|
| `CRITICAL` | Drop everything — do it now |
| `HIGH` | Important, do today |
| `MEDIUM` | Normal priority (default) |
| `LOW` | Do when time permits |

---

## Status Values & Transitions

```
NOT_STARTED  -->  PENDING  -->  ONGOING  -->  COMPLETED
                    |               |
                    +----> ON_HOLD <-+----> NOT_COMPLETED
                    |                           |
                    +---------------------------+
```

| From | Allowed Next |
|---|---|
| `NOT_STARTED` | `PENDING`, `ON_HOLD` |
| `PENDING` | `ONGOING`, `ON_HOLD`, `NOT_COMPLETED` |
| `ONGOING` | `COMPLETED`, `ON_HOLD`, `NOT_COMPLETED` |
| `ON_HOLD` | `PENDING`, `ONGOING`, `NOT_COMPLETED` |
| `COMPLETED` | *(terminal)* |
| `NOT_COMPLETED` | `PENDING` |

---

## Data Storage

All data is stored in `~/.taskguard/` (or `$TASKGUARD_DATA_DIR`):

| File | Purpose |
|---|---|
| `taskguard.db` | SQLite database (WAL mode, FTS5 search index, audit log) |
| `taskguard.cfg` | Argon2id salt (binary, `chmod 600`) |
| `taskguard_audit.jsonl` | JSON-lines event log (append-only) |
| `exports/` | CSV and JSON export files |

### What is encrypted?

The following fields are encrypted with AES-256-GCM per task record:

- **Title**
- **Description**
- **Tags**
- **Notes**

The following are stored **plaintext** (required for SQL filtering, sorting, and notifications):

- `id`, `priority`, `status`, `created_at`, `updated_at`, `due_date`

The FTS5 search index also stores plaintext title and tags for fast full-text search. This is a deliberate trade-off between searchability and confidentiality.

---

## Audit Log Format

Every CRUD operation and notification event is written to `taskguard_audit.jsonl`:

```json
{"timestamp":"2024-11-15T10:30:00.123456","level":"INFO","event":"TASK_CREATED","task_id":"a1b2c3...","extra":{}}
{"timestamp":"2024-11-15T10:31:00.000000","level":"WARNING","event":"NOTIFY_OVERDUE","count":2,"extra":{}}
```

---

## Running the Test Suite

```bash
./run.sh test
```

Or directly:

```bash
python -m pytest tests/ -v
```

**181 tests, 100% pass rate** covering:

- All 25+ exception classes (dunders, codes, severity, context)
- Vault: encrypt/decrypt, tamper detection, key derivation, salt persistence
- Repository: full CRUD, async generators, FTS search, overdue/due-soon queries
- TaskService: business logic, status transitions, bulk operations
- ExportService: CSV/JSON output, streaming generator, invalid format handling
- NotificationService: overdue detection, seen-id deduplication, force-notify

---

## Troubleshooting

**Wrong password on startup**

```
[ERR] Authentication failed. Incorrect master password.
```

The salt in `~/.taskguard/taskguard.cfg` is correct; you entered the wrong password. There is no recovery — by design.

**Database locked**

```
[TGS-1001] Cannot connect to database
```

Another `taskguard` process may be running. SQLite WAL mode allows concurrent readers but only one writer. Kill other instances and retry.

**FTS search returns no results**

The search index may be stale after a crash. Re-index by running any `edit` command, which rebuilds the FTS entry for that task. Full re-index support can be added via `taskguard admin reindex` in a future version.

**Permission denied on config file**

```
[TGS-2006] Key store I/O error
```

Check that `~/.taskguard/taskguard.cfg` has `600` permissions:

```bash
chmod 600 ~/.taskguard/taskguard.cfg
```

**Python version too old**

```
[ERR] Python 3.12+ required. Found: 3.11.x
```

Install Python 3.12+ and ensure it is on your `PATH`. Use `pyenv` if your system Python is older.

**Colors not displaying**

Set `TERM=xterm-256color` or run inside a terminal that supports ANSI escape codes. Colors are automatically disabled if stdout is not a TTY (e.g., when piping output).

---

## Legal Disclaimer

TaskGuard is provided **"as is"**, without warranty of any kind, express or implied.

- This software is intended for **lawful personal and professional task management** only.
- The AES-256-GCM encryption provided here is designed to protect your own data on your own systems. It is **not a substitute for full-disk encryption** or a formal secrets management system.
- The authors accept no liability for data loss, data corruption, or security breaches arising from use or misuse of this software.
- Do not use this tool to store classified, legally privileged, or regulated data without appropriate review.
- The master password is the sole key to your data. **Loss of the master password means permanent, unrecoverable loss of all task data.** Keep a secure backup.
- This project is a **security portfolio demonstration**. It has not undergone formal third-party cryptographic review.

---

## Security Notes

- Argon2id parameters (`time_cost=3`, `memory_cost=64MiB`, `parallelism=2`) follow the OWASP minimum recommendations for interactive logins. Increase `ARGON2_TIME_COST` in `src/constants.py` for higher-security environments.
- Each task record uses a **unique random 12-byte nonce** — nonce reuse is impossible under normal operation.
- The `taskguard.cfg` salt file is written with `chmod 600`. Protect your `~/.taskguard/` directory accordingly.
- The plaintext FTS index (`tasks_fts` table) means that task titles and tags can be read without the master password if an attacker has direct SQLite access. Consider full-disk encryption for the data directory if this is a concern.
