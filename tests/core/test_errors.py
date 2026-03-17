"""Tests for core/errors.py — exception hierarchy and error_from_code factory."""

from synology_mcp.core.errors import (
    ApiNotFoundError,
    DiskFullError,
    FileExistsError,
    FileStationError,
    IllegalNameError,
    PathNotFoundError,
    PermissionError,
    SessionExpiredError,
    SynologyError,
    error_from_code,
)


class TestExceptionHierarchy:
    def test_base_exception_attributes(self) -> None:
        err = SynologyError("test error", code=100, suggestion="try again")
        assert str(err) == "test error"
        assert err.code == 100
        assert err.suggestion == "try again"

    def test_filestation_errors_inherit_from_synology_error(self) -> None:
        err = PathNotFoundError("not found", code=408)
        assert isinstance(err, FileStationError)
        assert isinstance(err, SynologyError)


class TestErrorFromCode:
    def test_common_permission_denied(self) -> None:
        err = error_from_code(105)
        assert isinstance(err, PermissionError)
        assert err.code == 105

    def test_session_expired_codes(self) -> None:
        for code in (106, 107, 119):
            err = error_from_code(code)
            assert isinstance(err, SessionExpiredError)
            assert err.code == code

    def test_api_not_found(self) -> None:
        err = error_from_code(102)
        assert isinstance(err, ApiNotFoundError)

    def test_filestation_path_not_found(self) -> None:
        err = error_from_code(408, api_name="SYNO.FileStation.List")
        assert isinstance(err, PathNotFoundError)
        assert err.code == 408
        assert err.suggestion is not None

    def test_filestation_file_exists(self) -> None:
        err = error_from_code(414, api_name="SYNO.FileStation.CopyMove")
        assert isinstance(err, FileExistsError)

    def test_filestation_disk_full(self) -> None:
        err = error_from_code(416, api_name="SYNO.FileStation.CopyMove")
        assert isinstance(err, DiskFullError)

    def test_filestation_illegal_name(self) -> None:
        for code in (418, 419):
            err = error_from_code(code, api_name="SYNO.FileStation.Rename")
            assert isinstance(err, IllegalNameError)

    def test_unknown_code(self) -> None:
        err = error_from_code(9999)
        assert isinstance(err, SynologyError)
        assert err.code == 9999
        assert "9999" in str(err)
