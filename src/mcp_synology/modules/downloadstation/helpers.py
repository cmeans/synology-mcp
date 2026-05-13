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
