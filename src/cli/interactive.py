"""
TaskGuard - Interactive Shell
Full-featured REPL with readline history, command dispatch, and colored output.
"""

from __future__ import annotations

import asyncio
import readline
import shlex
import sys
from datetime import datetime
from typing import Optional

from src.core.exceptions import (
    TaskGuardError, InvalidCommandError, CLIInputError,
    InvalidStatusTransitionError,
)
from src.core.models import Priority, Status
from src.services.task_service import TaskService
from src.services.export_service import ExportService
from src.services.notification_service import NotificationService
from src.ui.colors import Colors
from src.ui.display import (
    print_task_table, print_task_detail, print_stats,
    print_success, print_error, print_warning, print_info, print_banner,
)
from src.ui.progress import SpinnerBar

PROMPT = Colors.BOLD + Colors.BLUE + "taskguard" + Colors.RESET + Colors.CYAN + " > " + Colors.RESET

HELP_TEXT = f"""
{Colors.BOLD}{Colors.BRIGHT_CYAN}Available Commands{Colors.RESET}
{Colors.DIM}{'─' * 60}{Colors.RESET}

{Colors.BOLD}Task Management:{Colors.RESET}
  add                    Create a new task (interactive prompts)
  list                   List all tasks
  list -s STATUS         Filter by status
  list -p PRIORITY       Filter by priority
  list --overdue         Show only overdue tasks
  view  <id>             Show full task detail
  edit  <id>             Edit a task (interactive prompts)
  done  <id>             Mark task as COMPLETED
  delete <id>            Delete a task (confirms before deletion)

{Colors.BOLD}Search & Filter:{Colors.RESET}
  search <query>         Full-text search across title and tags
  filter -s STATUS -p PRIORITY   Combined filter

{Colors.BOLD}Bulk Operations:{Colors.RESET}
  bulk-delete <id1> <id2> ...
  bulk-status <STATUS> <id1> <id2> ...

{Colors.BOLD}Analytics:{Colors.RESET}
  stats                  Show task statistics dashboard
  notify                 Check overdue / due-soon notifications now

{Colors.BOLD}Export:{Colors.RESET}
  export csv             Export all tasks to CSV
  export json            Export all tasks to JSON
  export csv -s STATUS   Export filtered tasks

{Colors.BOLD}System:{Colors.RESET}
  help                   Show this help
  clear                  Clear terminal
  quit / exit            Exit TaskGuard

{Colors.BOLD}Priority values:{Colors.RESET}  LOW  MEDIUM  HIGH  CRITICAL
{Colors.BOLD}Status values:{Colors.RESET}     NOT_STARTED  PENDING  ONGOING  ON_HOLD  COMPLETED  NOT_COMPLETED
{Colors.DIM}{'─' * 60}{Colors.RESET}
"""


class InteractiveShell:
    """
    REPL for TaskGuard. Uses asyncio.run() for each command dispatch.
    Readline history is maintained in memory.
    """

    def __init__(
        self,
        task_svc:   TaskService,
        export_svc: ExportService,
        notify_svc: NotificationService,
    ) -> None:
        self._task_svc   = task_svc
        self._export_svc = export_svc
        self._notify_svc = notify_svc
        self._running    = False

        # command dispatch table
        self._commands: dict[str, callable] = {
            "add":          self._cmd_add,
            "list":         self._cmd_list,
            "view":         self._cmd_view,
            "edit":         self._cmd_edit,
            "done":         self._cmd_done,
            "delete":       self._cmd_delete,
            "search":       self._cmd_search,
            "filter":       self._cmd_filter,
            "bulk-delete":  self._cmd_bulk_delete,
            "bulk-status":  self._cmd_bulk_status,
            "stats":        self._cmd_stats,
            "notify":       self._cmd_notify,
            "export":       self._cmd_export,
            "help":         self._cmd_help,
            "clear":        self._cmd_clear,
            "quit":         self._cmd_quit,
            "exit":         self._cmd_quit,
        }
        readline.set_history_length(200)

    # ── entry point ───────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the interactive REPL. Blocks until the user quits."""
        print_banner()
        self._running = True
        self._notify_svc.start()

        # Startup notification check
        asyncio.run(self._notify_svc.check_and_notify())

        while self._running:
            try:
                raw = input(PROMPT).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not raw:
                continue

            readline.add_history(raw)
            try:
                parts = shlex.split(raw)
            except ValueError as exc:
                print_error(f"Parse error: {exc}")
                continue

            cmd, *args = parts
            handler = self._commands.get(cmd.lower())

            if handler is None:
                print_error(str(InvalidCommandError(cmd)))
                continue

            try:
                asyncio.run(handler(args))
            except TaskGuardError as exc:
                print_error(str(exc))
            except Exception as exc:
                print_error(f"Unexpected error: {exc}")

        self._notify_svc.stop()
        print(Colors.DIM + "  Goodbye." + Colors.RESET)

    # ── command handlers ──────────────────────────────────────────────────────

    async def _cmd_add(self, args: list[str]) -> None:
        """Interactive task creation."""
        print(Colors.BOLD + Colors.CYAN + "\n  -- New Task --" + Colors.RESET)

        title = self._prompt("Title", required=True)
        desc  = self._prompt("Description (optional)")
        pri   = self._prompt_choice("Priority", [p.value for p in Priority], "MEDIUM")
        sts   = self._prompt_choice("Status",   [s.value for s in Status],   "NOT_STARTED")
        tags_raw = self._prompt("Tags (comma-separated, optional)")
        tags  = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
        notes = self._prompt("Notes (optional)")
        due_str = self._prompt("Due date (YYYY-MM-DD HH:MM or blank)")
        due   = self._parse_datetime(due_str) if due_str else None

        async with SpinnerBar("Creating task"):
            task = await self._task_svc.create_task(
                title=title, priority=pri, status=sts,
                description=desc, tags=tags, notes=notes, due_date=due,
            )
        print_success(f"Task created: {task.id}")
        print_task_detail(task)

    async def _cmd_list(self, args: list[str]) -> None:
        status   = self._extract_flag(args, "-s", "--status")
        priority = self._extract_flag(args, "-p", "--priority")
        overdue  = "--overdue" in args or "-o" in args

        sts  = Status.from_string(status)     if status   else None
        pri  = Priority.from_string(priority) if priority else None

        async with SpinnerBar("Loading"):
            tasks = await self._task_svc.list_tasks(status=sts, priority=pri, overdue=overdue)

        label = "Tasks"
        if sts:      label += f" | Status: {sts.value}"
        if pri:      label += f" | Priority: {pri.value}"
        if overdue:  label += " | OVERDUE"
        print_task_table(tasks, title=label)

    async def _cmd_view(self, args: list[str]) -> None:
        if not args:
            print_error("Usage: view <task-id>"); return
        task = await self._task_svc.get_task(args[0])
        print_task_detail(task)

    async def _cmd_edit(self, args: list[str]) -> None:
        if not args:
            print_error("Usage: edit <task-id>"); return
        task_id = args[0]
        task    = await self._task_svc.get_task(task_id)
        print_task_detail(task)

        print(Colors.DIM + "\n  Press ENTER to keep current value.\n" + Colors.RESET)
        title  = self._prompt(f"Title [{task.title}]") or None
        desc   = self._prompt(f"Description [{task.description or '-'}]") or None
        pri    = self._prompt(f"Priority [{task.priority.value}]") or None
        sts    = self._prompt(f"Status [{task.status.value}]") or None
        tags_r = self._prompt(f"Tags [{', '.join(task.tags) or '-'}]")
        tags   = [t.strip() for t in tags_r.split(",") if t.strip()] if tags_r else None
        notes  = self._prompt(f"Notes [{task.notes or '-'}]") or None
        due_s  = self._prompt(f"Due date [{task.due_date or '-'}]  (clear='-')")
        clear_due = due_s == "-"
        due    = self._parse_datetime(due_s) if due_s and due_s != "-" else None

        async with SpinnerBar("Saving"):
            updated = await self._task_svc.update_task(
                task_id, title=title, priority=pri, status=sts,
                description=desc, tags=tags, notes=notes,
                due_date=due, clear_due=clear_due,
            )
        print_success("Task updated.")
        print_task_detail(updated)

    async def _cmd_done(self, args: list[str]) -> None:
        if not args:
            print_error("Usage: done <task-id>"); return
        task = await self._task_svc.change_status(args[0], "COMPLETED")
        print_success(f"Task '{task.title}' marked COMPLETED.")

    async def _cmd_delete(self, args: list[str]) -> None:
        if not args:
            print_error("Usage: delete <task-id>"); return
        task_id = args[0]
        task    = await self._task_svc.get_task(task_id)
        confirm = self._prompt(
            f"Delete '{task.title}'? This cannot be undone. (yes/no)"
        ).lower()
        if confirm not in ("yes", "y"):
            print_info("Deletion cancelled."); return
        await self._task_svc.delete_task(task_id)
        print_success(f"Task '{task.title}' deleted.")

    async def _cmd_search(self, args: list[str]) -> None:
        if not args:
            print_error("Usage: search <query>"); return
        q = " ".join(args)
        async with SpinnerBar("Searching"):
            results = await self._task_svc.search(q)
        print_task_table(results, title=f"Search: {q!r}")

    async def _cmd_filter(self, args: list[str]) -> None:
        await self._cmd_list(args)

    async def _cmd_bulk_delete(self, args: list[str]) -> None:
        if not args:
            print_error("Usage: bulk-delete <id1> <id2> ..."); return
        confirm = self._prompt(f"Delete {len(args)} tasks? (yes/no)").lower()
        if confirm not in ("yes", "y"):
            print_info("Cancelled."); return
        async with SpinnerBar("Deleting"):
            results = await self._task_svc.bulk_delete(args)
        for tid, status in results.items():
            if status == "deleted":
                print_success(f"{tid[:8]}: {status}")
            else:
                print_error(f"{tid[:8]}: {status}")

    async def _cmd_bulk_status(self, args: list[str]) -> None:
        if len(args) < 2:
            print_error("Usage: bulk-status <STATUS> <id1> <id2> ..."); return
        new_status, *ids = args
        async with SpinnerBar("Updating"):
            results = await self._task_svc.bulk_status_change(ids, new_status)
        for tid, status in results.items():
            if status == "updated":
                print_success(f"{tid[:8]}: {status}")
            else:
                print_error(f"{tid[:8]}: {status}")

    async def _cmd_stats(self, args: list[str]) -> None:
        async with SpinnerBar("Computing"):
            stats = await self._task_svc.get_stats()
        print_stats(stats)

    async def _cmd_notify(self, args: list[str]) -> None:
        count = await self._notify_svc.check_and_notify(force=True)
        if count == 0:
            print_success("No overdue or due-soon tasks.")

    async def _cmd_export(self, args: list[str]) -> None:
        if not args:
            print_error("Usage: export <csv|json> [-s STATUS] [-p PRIORITY]"); return
        fmt    = args[0].lower()
        status = self._extract_flag(args[1:], "-s", "--status")
        pri    = self._extract_flag(args[1:], "-p", "--priority")
        filt   = {}
        if status: filt["status"]   = status
        if pri:    filt["priority"] = pri

        async with SpinnerBar(f"Exporting {fmt.upper()}"):
            path = await self._export_svc.export(fmt, filters=filt)
        print_success(f"Exported to: {path}")

    async def _cmd_help(self, args: list[str]) -> None:
        print(HELP_TEXT)

    async def _cmd_clear(self, args: list[str]) -> None:
        import os
        os.system("clear" if os.name != "nt" else "cls")

    async def _cmd_quit(self, args: list[str]) -> None:
        self._running = False

    # ── input helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _prompt(label: str, required: bool = False) -> str:
        while True:
            try:
                val = input(
                    Colors.CYAN + f"  {label}: " + Colors.RESET
                ).strip()
            except (EOFError, KeyboardInterrupt):
                print(); return ""
            if required and not val:
                print_warning("This field is required.")
                continue
            return val

    @staticmethod
    def _prompt_choice(label: str, choices: list[str], default: str) -> str:
        opts = "/".join(choices)
        while True:
            val = input(
                Colors.CYAN + f"  {label} [{opts}] (default={default}): " + Colors.RESET
            ).strip().upper()
            if not val:
                return default
            if val in choices:
                return val
            print_warning(f"Invalid choice. Options: {opts}")

    @staticmethod
    def _extract_flag(args: list[str], *flags: str) -> Optional[str]:
        for f in flags:
            if f in args:
                idx = args.index(f)
                if idx + 1 < len(args):
                    return args[idx + 1]
        return None

    @staticmethod
    def _parse_datetime(s: str) -> Optional[datetime]:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
            try:
                return datetime.strptime(s.strip(), fmt)
            except ValueError:
                pass
        print_warning(f"Could not parse date '{s}'. Use YYYY-MM-DD HH:MM.")
        return None
