"""
TaskGuard - Entry Point
Boot sequence: parse args → authenticate → init DB → dispatch command or REPL.
"""

from __future__ import annotations

import asyncio
import getpass
import os
import sys
from pathlib import Path
from datetime import datetime

from src.constants import DB_FILENAME, CONFIG_FILENAME, LOG_FILENAME, EXPORT_DIR
from src.core.exceptions import (
    TaskGuardError, AuthenticationError, DatabaseSchemaError,
)
from src.core.models import Priority, Status
from src.crypto.vault import Vault
from src.database.repository import TaskRepository
from src.services.task_service import TaskService
from src.services.export_service import ExportService
from src.services.notification_service import NotificationService
from src.logging_setup.logger import configure_logging, shutdown_logging, get_logger
from src.cli.parser import build_parser
from src.cli.interactive import InteractiveShell
from src.ui.display import (
    print_task_table, print_task_detail, print_stats,
    print_success, print_error, print_info,
)
from src.ui.colors import Colors

logger = get_logger(__name__)


# ─── data directory resolution ────────────────────────────────────────────────

def _resolve_data_dir(cli_dir: str | None) -> Path:
    if cli_dir:
        return Path(cli_dir).expanduser().resolve()
    env = os.environ.get("TASKGUARD_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".taskguard"


# ─── password resolution ──────────────────────────────────────────────────────

def _resolve_password(cli_pass: str | None) -> str:
    if cli_pass:
        return cli_pass
    env = os.environ.get("TASKGUARD_PASSWORD")
    if env:
        return env
    try:
        return getpass.getpass(
            Colors.BOLD + Colors.CYAN + "  Master password: " + Colors.RESET
        )
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)


# ─── bootstrap ────────────────────────────────────────────────────────────────

async def _bootstrap(data_dir: Path, vault: Vault) -> tuple[
    TaskService, ExportService, NotificationService
]:
    db_path  = data_dir / DB_FILENAME
    repo     = TaskRepository(db_path, vault)
    await repo.init_schema()

    task_svc   = TaskService(repo)
    export_svc = ExportService(task_svc, data_dir / EXPORT_DIR)
    notify_svc = NotificationService(task_svc)
    return task_svc, export_svc, notify_svc


# ─── non-interactive command dispatch ────────────────────────────────────────

async def _dispatch(ns, task_svc: TaskService, export_svc: ExportService,
                    notify_svc: NotificationService) -> int:
    """Execute a single argparse command. Returns exit code."""

    cmd = ns.command

    if cmd == "add":
        tags = [t.strip() for t in ns.tags.split(",") if t.strip()] if ns.tags else []
        due  = _parse_dt(ns.due)
        task = await task_svc.create_task(
            title=ns.title, priority=ns.priority, status=ns.status,
            description=ns.description, tags=tags, notes=ns.notes, due_date=due,
        )
        print_success(f"Task created: {task.id}")
        print_task_detail(task)

    elif cmd == "list":
        sts  = Status.from_string(ns.status)     if ns.status   else None
        pri  = Priority.from_string(ns.priority) if ns.priority else None
        tasks = await task_svc.list_tasks(status=sts, priority=pri, overdue=ns.overdue)
        label = "Tasks"
        if sts:  label += f" | {sts.value}"
        if pri:  label += f" | {pri.value}"
        if ns.overdue: label += " | OVERDUE"
        print_task_table(tasks, title=label)

    elif cmd == "view":
        task = await task_svc.get_task(ns.id)
        print_task_detail(task)

    elif cmd == "edit":
        tags = [t.strip() for t in ns.tags.split(",") if t.strip()] if ns.tags else None
        due  = _parse_dt(ns.due) if ns.due else None
        task = await task_svc.update_task(
            ns.id,
            title=ns.title, priority=ns.priority, status=ns.status,
            description=ns.description, tags=tags, notes=ns.notes,
            due_date=due, clear_due=ns.clear_due,
        )
        print_success("Task updated.")
        print_task_detail(task)

    elif cmd == "delete":
        if not ns.yes:
            task = await task_svc.get_task(ns.id)
            ans  = input(
                Colors.YELLOW + f"  Delete '{task.title}'? (yes/no): " + Colors.RESET
            ).strip().lower()
            if ans not in ("yes", "y"):
                print_info("Cancelled."); return 0
        await task_svc.delete_task(ns.id)
        print_success(f"Task {ns.id} deleted.")

    elif cmd == "done":
        task = await task_svc.change_status(ns.id, "COMPLETED")
        print_success(f"'{task.title}' marked COMPLETED.")

    elif cmd == "search":
        results = await task_svc.search(ns.query)
        print_task_table(results, title=f"Search: {ns.query!r}")

    elif cmd == "stats":
        stats = await task_svc.get_stats()
        print_stats(stats)

    elif cmd == "notify":
        count = await notify_svc.check_and_notify(force=True)
        if count == 0:
            print_success("No overdue or due-soon tasks.")

    elif cmd == "export":
        filt = {}
        if ns.status:   filt["status"]   = ns.status
        if ns.priority: filt["priority"] = ns.priority
        path = await export_svc.export(ns.format, filename=ns.output, filters=filt)
        print_success(f"Exported to: {path}")

    return 0


# ─── datetime helper ──────────────────────────────────────────────────────────

def _parse_dt(s: str | None):
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    print_error(f"Cannot parse date '{s}'. Use YYYY-MM-DD [HH:MM]")
    return None


# ─── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = build_parser()
    ns     = parser.parse_args()

    data_dir = _resolve_data_dir(ns.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    configure_logging(
        log_dir   = data_dir,
        log_file  = LOG_FILENAME,
        level     = ns.log_level,
        quiet     = ns.quiet or bool(ns.command),  # quiet console in scripted mode
    )

    password  = _resolve_password(ns.password)
    cfg_path  = data_dir / CONFIG_FILENAME

    try:
        vault = Vault.from_password(password, cfg_path)
    except TaskGuardError as exc:
        print_error(str(exc))
        return 1

    try:
        task_svc, export_svc, notify_svc = asyncio.run(
            _bootstrap(data_dir, vault)
        )
    except TaskGuardError as exc:
        print_error(f"Startup failed: {exc}")
        return 1

    exit_code = 0
    try:
        if ns.command:
            exit_code = asyncio.run(
                _dispatch(ns, task_svc, export_svc, notify_svc)
            )
        else:
            shell = InteractiveShell(task_svc, export_svc, notify_svc)
            shell.run()
    except TaskGuardError as exc:
        print_error(str(exc))
        exit_code = 1
    except KeyboardInterrupt:
        print()
    finally:
        shutdown_logging()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
