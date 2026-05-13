"""Shared helpers for Download Station tools."""

from __future__ import annotations

from mcp_synology.core.formatting import format_size

# DSM Download Station task status numeric codes (public API guide).
_STATUS_LABELS: dict[int, str] = {
    1: "waiting",
    2: "downloading",
    3: "paused",
    4: "finishing",
    5: "finished",
    6: "hash_checking",
    7: "seeding",
    8: "filehosting_waiting",
    9: "extracting",
    10: "error",
}

# Operator-facing groupings used by list_downloads(status_filter=...).
# "downloading" is interpreted as "in-flight or waiting for a slot, but not
# paused / finished / error" — so transient pre-active states (1 waiting,
# 8 filehosting_waiting) are bucketed there alongside actively-transferring
# states.
STATUS_GROUPS: dict[str, set[int]] = {
    "downloading": {1, 2, 4, 6, 8, 9},
    "finished": {5, 7},
    "paused": {3},
    "error": {10},
}


def format_task_status(status_code: int | None) -> str:
    """Translate a DSM numeric status to its label.

    Unknown codes return ``unknown(<n>)`` so the original value is preserved
    in diagnostic output; None returns plain ``unknown``.
    """
    if status_code is None:
        return "unknown"
    return _STATUS_LABELS.get(status_code, f"unknown({status_code})")


def format_transfer_progress(downloaded: int, total: int) -> str:
    """Render ``<downloaded> / <total> (<percent>%)``.

    When ``total == 0`` percent is shown as an em dash. When DSM reports
    ``downloaded > total`` (occasionally happens with seed-after-finish),
    percent is clamped to 100.
    """
    down_str = format_size(downloaded)
    total_str = format_size(total)
    if total <= 0:
        return f"{down_str} / {total_str} (—)"
    pct = min(100, int(downloaded * 100 / total))
    return f"{down_str} / {total_str} ({pct}%)"


_DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# Per DSM convention: 7 days × 24 hours. Each char encodes one hour.
SCHEDULE_PLAN_LENGTH = 7 * 24

_CELL_GLYPHS: dict[str, str] = {
    "0": ".",  # off
    "1": "#",  # on (full)
    "2": "~",  # throttled
    "3": "#",  # on + eMule (older DSM) — render same as on
}


def format_schedule_grid(plan: str) -> str:
    """Render a DSM Download Station weekly schedule plan as a text grid.

    ``plan`` is a 168-character string (7 days × 24 hours, Sun..Sat). Each
    character encodes one hour: '0'=off, '1'=on, '2'=throttled, '3'=on+eMule.

    Output is one row per day with a 24-cell hour grid, plus a legend line.
    """
    if len(plan) != SCHEDULE_PLAN_LENGTH:
        msg = (
            f"schedule_plan must be {SCHEDULE_PLAN_LENGTH} chars "
            f"(7 days × 24 hours), got {len(plan)}"
        )
        raise ValueError(msg)

    hour_header = "     " + " ".join(f"{h:02d}" for h in range(24))
    lines = [hour_header]
    for day_idx, name in enumerate(_DAY_NAMES):
        day_slice = plan[day_idx * 24 : (day_idx + 1) * 24]
        cells = " ".join(_CELL_GLYPHS.get(ch, "?") for ch in day_slice)
        lines.append(f"{name}  {cells}")

    lines.append("")
    lines.append("Legend: # = on   ~ = throttled   . = off")
    return "\n".join(lines)
