"""Tests for modules/downloadstation/helpers.py — pure-function helpers."""

from __future__ import annotations

import pytest

from mcp_synology.modules.downloadstation.helpers import (
    format_task_status,
    format_transfer_progress,
)


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
        assert "512" in out

    def test_complete(self) -> None:
        out = format_transfer_progress(downloaded=1000, total=1000)
        assert "(100%)" in out

    def test_total_smaller_than_downloaded_clamps_to_100(self) -> None:
        out = format_transfer_progress(downloaded=2000, total=1000)
        assert "(100%)" in out
