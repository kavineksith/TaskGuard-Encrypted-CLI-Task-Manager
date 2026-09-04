"""
TaskGuard - Terminal Display
Box-drawing tables, task detail cards, stats dashboard.
Pure Python — zero external dependencies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.core.models import Task, Priority, Status
from src.ui.colors import (
    Colors, priority_colored, status_colored,
    PRIORITY_COLORS, STATUS_COLORS,
)

# ─── box-drawing characters ───────────────────────────────────────────────────
TL = "\u250c"; TR = "\u2510"; BL = "\u2514"; BR = "\u2518"
HL = "\u2500"; VL = "\u2502"; TM = "\u252c"; BM = "\u2534"
LM = "\u251c"; RM = "\u2524"; CR = "\u253c"
DHL = "\u2550"; DVL = "\u2551"
DTL = "\u2554"; DTR = "\u2557"; DBL = "\u255a"; DBR = "\u255d"
DHM = "\u2564"; DBM = "\u2567"


def _pad(text: str, width: int) -> str:
    """Left-pad *text* to *width*, truncating with '…' if too long."""
    plain = _strip_ansi(text)
    if len(plain) > width:
        return text[:width - 1] + "\u2026"
    return text + " " * (width - len(plain))


def _strip_ansi(text: str) -> str:
    import re
    return re.sub(r"\033\[[0-9;]*m", "", text)


# ─── task list table ──────────────────────────────────────────────────────────

_COL_WIDTHS = {
    "#":          4,
    "ID":         10,
    "TITLE":      38,
    "PRIORITY":   12,
    "STATUS":     16,
    "DUE DATE":   18,
    "UPDATED":    18,
}


def print_task_table(tasks: list[Task], title: str = "Tasks") -> None:
    if not tasks:
        print(Colors.DIM + "  No tasks found." + Colors.RESET)
        return

    cols   = list(_COL_WIDTHS.keys())
    widths = list(_COL_WIDTHS.values())
    total  = sum(widths) + len(widths) * 3 + 1

    # ── top border ──
    inner = TM.join(HL * (w + 2) for w in widths)
    print(Colors.BOLD + Colors.BLUE + TL + inner + TR + Colors.RESET)

    # ── title bar ──
    print(
        Colors.BOLD + Colors.BLUE + VL + Colors.RESET
        + Colors.BOLD + Colors.BRIGHT_WHITE
        + f" {title} ".center(total - 2)
        + Colors.RESET
        + Colors.BOLD + Colors.BLUE + VL + Colors.RESET
    )

    # ── header row ──
    sep = LM + TM.join(HL * (w + 2) for w in widths) + RM
    print(Colors.BOLD + Colors.BLUE + sep + Colors.RESET)
    cells = " " + (" " + VL + " ").join(
        Colors.BOLD + Colors.CYAN + _pad(c, w) + Colors.RESET
        for c, w in zip(cols, widths)
    ) + " "
    print(Colors.BOLD + Colors.BLUE + VL + Colors.RESET
          + cells
          + Colors.BOLD + Colors.BLUE + VL + Colors.RESET)

    # ── divider ──
    div = LM + CR.join(HL * (w + 2) for w in widths) + RM
    print(Colors.BOLD + Colors.BLUE + div + Colors.RESET)

    # ── rows ──
    for i, task in enumerate(tasks, 1):
        due  = task.due_date.strftime("%Y-%m-%d %H:%M") if task.due_date else "-"
        upd  = task.updated_at.strftime("%Y-%m-%d %H:%M")
        tid  = task.id[:8] + ".."

        overdue_flag = Colors.RED + Colors.BOLD if task.is_overdue() else ""
        reset        = Colors.RESET

        row_cells = [
            _pad(Colors.DIM + str(i) + reset, widths[0]),
            _pad(Colors.DIM + tid      + reset, widths[1]),
            _pad(overdue_flag + task.title[:widths[2]] + reset, widths[2]),
            _pad(priority_colored(task.priority.value), widths[3]),
            _pad(status_colored(task.status.value),     widths[4]),
            _pad(
                (Colors.RED if task.is_overdue() else Colors.DIM) + due + reset,
                widths[5]
            ),
            _pad(Colors.DIM + upd + reset, widths[6]),
        ]

        cells = " " + (" " + Colors.BLUE + VL + Colors.RESET + " ").join(row_cells) + " "
        print(Colors.BLUE + VL + Colors.RESET
              + cells
              + Colors.BLUE + VL + Colors.RESET)

    # ── bottom border ──
    bot = BL + BM.join(HL * (w + 2) for w in widths) + BR
    print(Colors.BOLD + Colors.BLUE + bot + Colors.RESET)
    print(Colors.DIM + f"  {len(tasks)} task(s) displayed." + Colors.RESET)


# ─── single task detail card ──────────────────────────────────────────────────

def print_task_detail(task: Task) -> None:
    w = 72
    border = Colors.BOLD + Colors.BLUE + DTL + DHL * (w - 2) + DTR + Colors.RESET

    def row(label: str, value: str) -> str:
        lbl = Colors.BOLD + Colors.CYAN + f"  {label:<15}" + Colors.RESET
        return Colors.BOLD + Colors.BLUE + DVL + Colors.RESET + lbl + value + " " * max(0, w - 18 - len(_strip_ansi(value))) + Colors.BOLD + Colors.BLUE + DVL + Colors.RESET

    def divider() -> str:
        return Colors.BOLD + Colors.BLUE + LM + HL * (w - 2) + RM + Colors.RESET

    print(border)
    print(Colors.BOLD + Colors.BLUE + DVL + Colors.RESET
          + Colors.BOLD + Colors.BRIGHT_WHITE + " TASK DETAIL".center(w - 2) + Colors.RESET
          + Colors.BOLD + Colors.BLUE + DVL + Colors.RESET)
    print(divider())
    print(row("ID",          Colors.DIM + task.id + Colors.RESET))
    print(row("Title",       Colors.BOLD + Colors.WHITE + task.title + Colors.RESET))
    print(row("Priority",    priority_colored(task.priority.value)))
    print(row("Status",      status_colored(task.status.value)))

    due_str = task.due_date.strftime("%Y-%m-%d %H:%M UTC") if task.due_date else "-"
    if task.is_overdue():
        due_str = Colors.RED + Colors.BOLD + due_str + " (OVERDUE)" + Colors.RESET
    print(row("Due Date",    due_str))
    print(row("Created",     Colors.DIM + task.created_at.strftime("%Y-%m-%d %H:%M UTC") + Colors.RESET))
    print(row("Updated",     Colors.DIM + task.updated_at.strftime("%Y-%m-%d %H:%M UTC") + Colors.RESET))
    print(divider())
    print(row("Tags",        Colors.CYAN + ", ".join(task.tags) if task.tags else Colors.DIM + "-" + Colors.RESET))

    if task.description:
        print(divider())
        print(Colors.BOLD + Colors.BLUE + DVL + Colors.RESET
              + Colors.BOLD + Colors.CYAN + "  Description" + Colors.RESET + Colors.BOLD + Colors.BLUE + DVL + Colors.RESET)
        for line in _wrap(task.description, w - 4):
            print(Colors.BOLD + Colors.BLUE + DVL + Colors.RESET
                  + "  " + line + " " * max(0, w - 4 - len(line))
                  + Colors.BOLD + Colors.BLUE + DVL + Colors.RESET)

    if task.notes:
        print(divider())
        print(Colors.BOLD + Colors.BLUE + DVL + Colors.RESET
              + Colors.BOLD + Colors.CYAN + "  Notes" + Colors.RESET + Colors.BOLD + Colors.BLUE + DVL + Colors.RESET)
        for line in _wrap(task.notes, w - 4):
            print(Colors.BOLD + Colors.BLUE + DVL + Colors.RESET
                  + "  " + line + " " * max(0, w - 4 - len(line))
                  + Colors.BOLD + Colors.BLUE + DVL + Colors.RESET)

    bottom = Colors.BOLD + Colors.BLUE + DBL + DHL * (w - 2) + DBR + Colors.RESET
    print(bottom)


# ─── stats dashboard ─────────────────────────────────────────────────────────

def print_stats(stats: dict) -> None:
    total = stats.get("total", 0)
    w     = 48

    print(Colors.BOLD + Colors.BLUE + DTL + DHL * (w - 2) + DTR + Colors.RESET)
    print(Colors.BOLD + Colors.BLUE + DVL
          + Colors.BRIGHT_WHITE + Colors.BOLD + " TASK STATISTICS".center(w - 2) + Colors.RESET
          + Colors.BOLD + Colors.BLUE + DVL + Colors.RESET)
    print(Colors.BOLD + Colors.BLUE + LM + HL * (w - 2) + RM + Colors.RESET)

    print(Colors.BOLD + Colors.BLUE + DVL + Colors.RESET
          + Colors.BOLD + f"  Total tasks: {total}" + Colors.RESET
          + " " * (w - 16 - len(str(total)))
          + Colors.BOLD + Colors.BLUE + DVL + Colors.RESET)

    print(Colors.BOLD + Colors.BLUE + LM + HL * (w - 2) + RM + Colors.RESET)
    print(Colors.BOLD + Colors.BLUE + DVL + Colors.RESET
          + Colors.BOLD + Colors.CYAN + "  By Status" + Colors.RESET
          + " " * (w - 13) + Colors.BOLD + Colors.BLUE + DVL + Colors.RESET)

    for s, cnt in sorted(stats.get("by_status", {}).items()):
        bar = _mini_bar(cnt, total)
        label = s.replace("_", " ").title()
        line  = f"  {label:<18} {bar} {cnt}"
        c     = STATUS_COLORS.get(s, "")
        print(Colors.BOLD + Colors.BLUE + DVL + Colors.RESET
              + c + line + Colors.RESET
              + " " * max(0, w - 2 - len(line))
              + Colors.BOLD + Colors.BLUE + DVL + Colors.RESET)

    print(Colors.BOLD + Colors.BLUE + LM + HL * (w - 2) + RM + Colors.RESET)
    print(Colors.BOLD + Colors.BLUE + DVL + Colors.RESET
          + Colors.BOLD + Colors.CYAN + "  By Priority" + Colors.RESET
          + " " * (w - 15) + Colors.BOLD + Colors.BLUE + DVL + Colors.RESET)

    for p, cnt in sorted(stats.get("by_priority", {}).items(),
                         key=lambda kv: -ord(kv[0][0])):
        bar   = _mini_bar(cnt, total)
        label = p.replace("_", " ").title()
        line  = f"  {label:<18} {bar} {cnt}"
        c     = PRIORITY_COLORS.get(p, "")
        print(Colors.BOLD + Colors.BLUE + DVL + Colors.RESET
              + c + line + Colors.RESET
              + " " * max(0, w - 2 - len(line))
              + Colors.BOLD + Colors.BLUE + DVL + Colors.RESET)

    print(Colors.BOLD + Colors.BLUE + DBL + DHL * (w - 2) + DBR + Colors.RESET)


# ─── helpers ─────────────────────────────────────────────────────────────────

def _mini_bar(count: int, total: int, width: int = 12) -> str:
    if total == 0:
        filled = 0
    else:
        filled = round(count / total * width)
    return "[" + "\u2588" * filled + "\u2591" * (width - filled) + "]"


def _wrap(text: str, width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 <= width:
            current = (current + " " + word).strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def print_banner() -> None:
    """Print the application startup banner."""
    from src.constants import APP_NAME, APP_VERSION
    lines = [
        f"  {APP_NAME} v{APP_VERSION}",
        "  Encrypted CLI Task Manager",
        "  Type 'help' for commands.",
    ]
    w = 50
    print(Colors.BOLD + Colors.BLUE + DTL + DHL * (w - 2) + DTR + Colors.RESET)
    for line in lines:
        print(Colors.BOLD + Colors.BLUE + DVL + Colors.RESET
              + Colors.BOLD + Colors.BRIGHT_CYAN + line.ljust(w - 2) + Colors.RESET
              + Colors.BOLD + Colors.BLUE + DVL + Colors.RESET)
    print(Colors.BOLD + Colors.BLUE + DBL + DHL * (w - 2) + DBR + Colors.RESET)


def print_success(msg: str) -> None:
    print(Colors.success(f"  [OK] {msg}"))


def print_error(msg: str) -> None:
    print(Colors.error(f"  [ERR] {msg}"), file=__import__("sys").stderr)


def print_warning(msg: str) -> None:
    print(Colors.warning(f"  [WARN] {msg}"))


def print_info(msg: str) -> None:
    print(Colors.info(f"  [INFO] {msg}"))
