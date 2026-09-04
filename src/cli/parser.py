"""
TaskGuard - Argument Parser
argparse-based CLI for non-interactive / scripted usage.
All commands mirror the interactive shell, but accept flags directly.
"""

from __future__ import annotations

import argparse
import sys

from src.constants import APP_NAME, APP_VERSION


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the root ArgumentParser."""
    parser = argparse.ArgumentParser(
        prog        = "taskguard",
        description = f"{APP_NAME} — Encrypted CLI Task Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Priority values : LOW | MEDIUM | HIGH | CRITICAL\n"
            "Status values   : NOT_STARTED | PENDING | ONGOING | "
            "ON_HOLD | COMPLETED | NOT_COMPLETED\n\n"
            "Run without subcommand to enter the interactive shell."
        ),
    )
    parser.add_argument(
        "--version", action="version",
        version=f"{APP_NAME} {APP_VERSION}",
    )
    parser.add_argument(
        "--data-dir", metavar="DIR", default=None,
        help="Directory for database and config files (default: ~/.taskguard)",
    )
    parser.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO", help="Logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress console log output (audit file still written)",
    )
    parser.add_argument(
        "--password", metavar="PASS", default=None,
        help="Master password (use env var TASKGUARD_PASSWORD for safety)",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # ── add ───────────────────────────────────────────────────────────────────
    p_add = sub.add_parser("add", help="Create a new task")
    p_add.add_argument("title", help="Task title")
    p_add.add_argument("-d", "--description", default="", metavar="TEXT")
    p_add.add_argument("-p", "--priority",    default="MEDIUM",
                       choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"])
    p_add.add_argument("-s", "--status",      default="NOT_STARTED",
                       choices=["NOT_STARTED","PENDING","ONGOING",
                                "ON_HOLD","COMPLETED","NOT_COMPLETED"])
    p_add.add_argument("-t", "--tags",        default="", metavar="TAG1,TAG2",
                       help="Comma-separated tags")
    p_add.add_argument("-n", "--notes",       default="", metavar="TEXT")
    p_add.add_argument("--due",               metavar="YYYY-MM-DD HH:MM",
                       default=None, help="Due date/time (UTC)")

    # ── list ──────────────────────────────────────────────────────────────────
    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("-s", "--status",   default=None,
                        choices=["NOT_STARTED","PENDING","ONGOING",
                                 "ON_HOLD","COMPLETED","NOT_COMPLETED"])
    p_list.add_argument("-p", "--priority", default=None,
                        choices=["LOW","MEDIUM","HIGH","CRITICAL"])
    p_list.add_argument("--overdue",        action="store_true",
                        help="Show only overdue tasks")

    # ── view ──────────────────────────────────────────────────────────────────
    p_view = sub.add_parser("view", help="Show full task detail")
    p_view.add_argument("id", help="Task id (or partial prefix)")

    # ── edit ──────────────────────────────────────────────────────────────────
    p_edit = sub.add_parser("edit", help="Update a task's fields")
    p_edit.add_argument("id", help="Task id")
    p_edit.add_argument("--title",       default=None)
    p_edit.add_argument("--description", default=None)
    p_edit.add_argument("--priority",    default=None,
                        choices=["LOW","MEDIUM","HIGH","CRITICAL"])
    p_edit.add_argument("--status",      default=None,
                        choices=["NOT_STARTED","PENDING","ONGOING",
                                 "ON_HOLD","COMPLETED","NOT_COMPLETED"])
    p_edit.add_argument("--tags",        default=None, metavar="TAG1,TAG2")
    p_edit.add_argument("--notes",       default=None)
    p_edit.add_argument("--due",         default=None, metavar="YYYY-MM-DD HH:MM")
    p_edit.add_argument("--clear-due",   action="store_true",
                        help="Remove the due date")

    # ── delete ────────────────────────────────────────────────────────────────
    p_del = sub.add_parser("delete", help="Delete a task")
    p_del.add_argument("id", help="Task id")
    p_del.add_argument("-y", "--yes", action="store_true",
                       help="Skip confirmation prompt")

    # ── search ────────────────────────────────────────────────────────────────
    p_search = sub.add_parser("search", help="Full-text search tasks")
    p_search.add_argument("query", help="Search terms")

    # ── done ─────────────────────────────────────────────────────────────────
    p_done = sub.add_parser("done", help="Mark a task COMPLETED")
    p_done.add_argument("id", help="Task id")

    # ── stats ─────────────────────────────────────────────────────────────────
    sub.add_parser("stats", help="Show task statistics dashboard")

    # ── notify ────────────────────────────────────────────────────────────────
    sub.add_parser("notify", help="Check overdue / due-soon tasks now")

    # ── export ────────────────────────────────────────────────────────────────
    p_exp = sub.add_parser("export", help="Export tasks to CSV or JSON")
    p_exp.add_argument("format", choices=["csv", "json"], help="Output format")
    p_exp.add_argument("-o", "--output", default=None,
                       metavar="FILENAME", help="Output filename (auto-generated if omitted)")
    p_exp.add_argument("-s", "--status",   default=None,
                       choices=["NOT_STARTED","PENDING","ONGOING",
                                "ON_HOLD","COMPLETED","NOT_COMPLETED"])
    p_exp.add_argument("-p", "--priority", default=None,
                       choices=["LOW","MEDIUM","HIGH","CRITICAL"])

    return parser
