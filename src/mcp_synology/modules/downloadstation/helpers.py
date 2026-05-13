"""Shared helpers for Download Station tools.

Phase 1 adds:
- format_task_status: normalize DSM numeric task-status to a label
- format_schedule_grid: render a 7×24 weekly schedule grid as text
- format_transfer_progress: render "X / Y (Z%)" progress strings

Implementations land alongside the tools that use them.
"""

from __future__ import annotations
