"""Tests for modules/downloadstation/helpers.py — pure-function helpers."""

from __future__ import annotations

import pytest

from mcp_synology.modules.downloadstation.helpers import (
    format_task_status,
    format_transfer_progress,
)


class TestFormatScheduleGrid:
    def test_all_off(self) -> None:
        from mcp_synology.modules.downloadstation.helpers import format_schedule_grid

        plan = "0" * 168
        out = format_schedule_grid(plan)
        assert "Sun" in out
        assert "Sat" in out
        assert "00" in out and "23" in out

    def test_all_on(self) -> None:
        from mcp_synology.modules.downloadstation.helpers import format_schedule_grid

        plan = "1" * 168
        out = format_schedule_grid(plan)
        # '.' is the off-marker; should not appear in any grid row
        # (the legend line is excluded from this check).
        grid_lines = [line for line in out.splitlines() if not line.startswith("Legend")]
        assert all("." not in line for line in grid_lines)

    def test_mixed_throttle(self) -> None:
        from mcp_synology.modules.downloadstation.helpers import format_schedule_grid

        sunday = "0" + "1" + "2" + "0" * 21
        plan = sunday + "0" * (168 - 24)
        out = format_schedule_grid(plan)
        assert "Sun" in out

    def test_invalid_length_raises(self) -> None:
        from mcp_synology.modules.downloadstation.helpers import format_schedule_grid

        with pytest.raises(ValueError, match="168"):
            format_schedule_grid("0" * 100)


class TestFormatTaskStatus:
    @pytest.mark.parametrize(
        ("status_code", "expected"),
        [
            (1, "waiting"),
            (2, "downloading"),
            (3, "paused"),
            (4, "finishing"),
            (5, "finished"),
            (6, "hash_checking"),
            (7, "seeding"),
            (8, "filehosting_waiting"),
            (9, "extracting"),
            (10, "error"),
        ],
    )
    def test_known_status_codes(self, status_code: int, expected: str) -> None:
        assert format_task_status(status_code) == expected

    def test_unknown_status_code_returns_unknown_with_value(self) -> None:
        assert format_task_status(99) == "unknown(99)"

    def test_none_status_returns_unknown(self) -> None:
        assert format_task_status(None) == "unknown"


class TestFormatTransferProgress:
    def test_zero_size(self) -> None:
        assert format_transfer_progress(downloaded=0, total=0) == "0 B / 0 B (—)"

    def test_partial(self) -> None:
        # 512 MB / 1 GB = exactly 50% (512 * 1024 * 1024 / 1024 * 1024 * 1024)
        out = format_transfer_progress(downloaded=512 * 1024 * 1024, total=1024 * 1024 * 1024)
        assert "(50%)" in out
        # Tightened beyond plan: assert the unit too so a future change to
        # format_size's boundary doesn't pass silently.
        assert "512 MB" in out

    def test_complete(self) -> None:
        out = format_transfer_progress(downloaded=1000, total=1000)
        assert "(100%)" in out

    def test_total_smaller_than_downloaded_clamps_to_100(self) -> None:
        out = format_transfer_progress(downloaded=2000, total=1000)
        assert "(100%)" in out
