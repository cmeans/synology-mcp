"""Tests for modules/downloadstation/helpers.py — pure-function helpers."""

from __future__ import annotations

import pytest

from mcp_synology.modules.downloadstation.helpers import (
    format_eta,
    format_speed,
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


class TestFormatSpeed:
    def test_zero_renders_em_dash(self) -> None:
        assert format_speed(0) == "—"

    def test_negative_renders_em_dash(self) -> None:
        assert format_speed(-100) == "—"

    def test_positive_renders_size_per_sec(self) -> None:
        out = format_speed(1024 * 1024)
        assert "/s" in out
        assert "1" in out  # 1 MB rendered as "1 MB" by format_size


class TestFormatEta:
    def test_zero_speed_returns_em_dash(self) -> None:
        assert format_eta(downloaded=0, total=1000, speed=0) == "—"

    def test_negative_speed_returns_em_dash(self) -> None:
        assert format_eta(downloaded=0, total=1000, speed=-5) == "—"

    def test_downloaded_equals_total_returns_em_dash(self) -> None:
        assert format_eta(downloaded=1000, total=1000, speed=10) == "—"

    def test_downloaded_exceeds_total_returns_em_dash(self) -> None:
        # DSM occasionally over-reports during seed-after-finish; should not negative ETA
        assert format_eta(downloaded=2000, total=1000, speed=10) == "—"

    def test_under_one_minute_renders_seconds(self) -> None:
        # 30 bytes remaining at 1 B/s → 30s
        assert format_eta(downloaded=0, total=30, speed=1) == "30s"

    def test_under_one_hour_renders_minutes(self) -> None:
        # 600 bytes remaining at 1 B/s → 600s → 10m
        assert format_eta(downloaded=0, total=600, speed=1) == "10m"

    def test_under_one_day_renders_hours_minutes(self) -> None:
        # 7200s = 2h0m
        assert format_eta(downloaded=0, total=7200, speed=1) == "2h0m"
        # 7320s = 2h2m
        assert format_eta(downloaded=0, total=7320, speed=1) == "2h2m"

    def test_one_day_or_more_renders_days_hours(self) -> None:
        # 86400s = exactly 1 day → 1d0h
        assert format_eta(downloaded=0, total=86400, speed=1) == "1d0h"
        # 90000s = 1d1h
        assert format_eta(downloaded=0, total=90000, speed=1) == "1d1h"
