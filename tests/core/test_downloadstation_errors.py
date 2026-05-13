"""Tests for DOWNLOADSTATION_ERROR_CODES dispatch.

DS overloads the 400-series with different semantics than FileStation, so the
typed exception raised must depend on both the numeric code AND the source API.
"""

from __future__ import annotations

import pytest

from mcp_synology.core.downloadstation_errors import (
    DOWNLOADSTATION_ERROR_CODES,
    DownloadStationError,
)
from mcp_synology.core.errors import error_from_code


class TestDownloadstationErrorCodes:
    @pytest.mark.parametrize(
        ("code", "expected_in_message"),
        [
            (400, "upload failed"),
            (401, "max number of tasks"),
            (402, "destination denied"),
            (403, "destination doesn't exist"),
            (404, "task id"),
            (405, "invalid task action"),
            (406, "no default destination"),
            (407, "set destination failed"),
            (408, "file doesn't exist"),
        ],
    )
    def test_known_codes_have_actionable_message(self, code: int, expected_in_message: str) -> None:
        message, suggestion = DOWNLOADSTATION_ERROR_CODES[code]
        combined = f"{message} {suggestion}".lower()
        assert expected_in_message.lower() in combined
        assert suggestion.strip(), f"code {code} has empty suggestion"

    def test_all_codes_400_through_408_present(self) -> None:
        for code in range(400, 409):
            assert code in DOWNLOADSTATION_ERROR_CODES, f"missing code {code}"


class TestErrorFromCodeDispatchesDsApi:
    def test_ds_api_400_routes_to_download_error_not_filestation(self) -> None:
        exc = error_from_code(400, "SYNO.DownloadStation.Task")
        assert isinstance(exc, DownloadStationError)
        assert "upload" in str(exc).lower()

    def test_filestation_api_400_still_uses_filestation_map(self) -> None:
        exc = error_from_code(400, "SYNO.FileStation.List")
        assert "invalid" in str(exc).lower()

    def test_unknown_ds_code_falls_back_to_dsm_error(self) -> None:
        exc = error_from_code(999, "SYNO.DownloadStation.Task")
        assert exc is not None
