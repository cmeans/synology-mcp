"""Tests for core/client.py — DSM API client."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
import respx

if TYPE_CHECKING:
    from pathlib import Path

from mcp_synology.core.client import DsmClient
from mcp_synology.core.errors import (
    ApiNotFoundError,
    PathNotFoundError,
    SessionExpiredError,
    SynologyError,
)
from tests.conftest import BASE_URL, make_api_cache, make_client, make_minimal_api_cache

# Local aliases so the existing test bodies don't need a wholesale rename.
_make_client = make_client
_default_cache = make_minimal_api_cache


class TestQueryApiInfo:
    @respx.mock
    async def test_query_api_info_success(self) -> None:
        respx.get(f"{BASE_URL}/webapi/query.cgi").respond(
            json={
                "success": True,
                "data": {
                    "SYNO.API.Auth": {
                        "path": "entry.cgi",
                        "minVersion": 1,
                        "maxVersion": 7,
                    },
                    "SYNO.FileStation.List": {
                        "path": "entry.cgi",
                        "minVersion": 1,
                        "maxVersion": 2,
                    },
                },
            }
        )
        async with DsmClient(base_url=BASE_URL) as client:
            cache = await client.query_api_info()
        assert "SYNO.API.Auth" in cache
        assert cache["SYNO.API.Auth"].max_version == 7
        assert "SYNO.FileStation.List" in cache

    @respx.mock
    async def test_query_api_info_error(self) -> None:
        respx.get(f"{BASE_URL}/webapi/query.cgi").respond(
            json={"success": False, "error": {"code": 102}}
        )
        async with DsmClient(base_url=BASE_URL) as client:
            with pytest.raises(ApiNotFoundError):
                await client.query_api_info()


class TestNegotiateVersion:
    def test_negotiate_picks_highest_compatible(self) -> None:
        client = _make_client(_default_cache())
        version = client.negotiate_version("SYNO.API.Auth", min_version=3, max_version=6)
        assert version == 6

    def test_negotiate_nas_lower_than_requested(self) -> None:
        client = _make_client(_default_cache())
        version = client.negotiate_version("SYNO.FileStation.List", min_version=1, max_version=5)
        assert version == 2  # NAS max is 2

    def test_negotiate_api_not_found(self) -> None:
        client = _make_client(_default_cache())
        with pytest.raises(ApiNotFoundError):
            client.negotiate_version("SYNO.NonExistent.API")

    def test_negotiate_no_compatible_version(self) -> None:
        client = _make_client(_default_cache())
        with pytest.raises(ApiNotFoundError, match="no compatible"):
            client.negotiate_version("SYNO.FileStation.List", min_version=5)


class TestRequest:
    @respx.mock
    async def test_request_success(self) -> None:
        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": {"shares": [{"name": "video"}]},
            }
        )
        async with _make_client(_default_cache()) as client:
            data = await client.request("SYNO.FileStation.List", "list_share", version=2)
        assert data["shares"][0]["name"] == "video"

    @respx.mock
    async def test_request_injects_session_id(self) -> None:
        route = respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": True, "data": {}}
        )
        async with _make_client(_default_cache()) as client:
            client.sid = "test-session-id"
            await client.request("SYNO.FileStation.List", "list_share", version=2)
        assert route.calls[0].request.url.params["_sid"] == "test-session-id"

    @respx.mock
    async def test_request_error_maps_to_exception(self) -> None:
        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": False, "error": {"code": 408}}
        )
        async with _make_client(_default_cache()) as client:
            with pytest.raises(PathNotFoundError):
                await client.request("SYNO.FileStation.List", "getinfo", version=2)

    @respx.mock
    async def test_request_api_not_in_cache(self) -> None:
        async with _make_client(_default_cache()) as client:
            with pytest.raises(ApiNotFoundError):
                await client.request("SYNO.NonExistent", "method")

    @respx.mock
    async def test_request_session_error_triggers_reauth(self) -> None:
        call_count = 0

        def side_effect(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json={"success": False, "error": {"code": 106}})
            return httpx.Response(200, json={"success": True, "data": {"result": "ok"}})

        respx.get(f"{BASE_URL}/webapi/entry.cgi").mock(side_effect=side_effect)

        reauth_called = False

        async def mock_reauth() -> None:
            nonlocal reauth_called
            reauth_called = True

        async with _make_client(_default_cache()) as client:
            client.set_re_auth_callback(mock_reauth)
            data = await client.request("SYNO.FileStation.List", "list_share", version=2)

        assert reauth_called
        assert data["result"] == "ok"
        assert call_count == 2

    @respx.mock
    async def test_request_session_error_no_callback(self) -> None:
        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": False, "error": {"code": 106}}
        )
        async with _make_client(_default_cache()) as client:
            with pytest.raises(SessionExpiredError):
                await client.request("SYNO.FileStation.List", "list_share", version=2)

    @respx.mock
    async def test_request_no_retry_on_105(self) -> None:
        """Error 105 (permission denied) should NOT trigger re-auth."""
        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": False, "error": {"code": 105}}
        )
        reauth_called = False

        async def mock_reauth() -> None:
            nonlocal reauth_called
            reauth_called = True

        async with _make_client(_default_cache()) as client:
            client.set_re_auth_callback(mock_reauth)
            with pytest.raises(SynologyError):
                await client.request("SYNO.FileStation.List", "list_share", version=2)
        assert not reauth_called


class TestEscapePathParam:
    def test_single_path(self) -> None:
        assert DsmClient.escape_path_param(["/video/test"]) == "/video/test"

    def test_multiple_paths(self) -> None:
        result = DsmClient.escape_path_param(["/video/a", "/music/b"])
        assert result == "/video/a,/music/b"

    def test_comma_in_path(self) -> None:
        result = DsmClient.escape_path_param(["/video/file,name.mkv"])
        assert result == "/video/file\\,name.mkv"

    def test_backslash_in_path(self) -> None:
        result = DsmClient.escape_path_param(["/video/path\\file"])
        assert result == "/video/path\\\\file"


class TestCreateDownloadTaskWithFile:
    """Multipart-upload form of SYNO.DownloadStation.Task.create."""

    @respx.mock
    async def test_uploads_torrent_and_returns_data(self, tmp_path: Path) -> None:
        client = make_client(make_api_cache())
        torrent = tmp_path / "ubuntu.torrent"
        torrent.write_bytes(b"d4:infod6:lengthi100eee")

        respx.post(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": True, "data": {"task_id": "dbid_new_001"}},
        )

        async with client:
            result = await client.create_download_task_with_file(
                file_path=torrent,
                filename="ubuntu.torrent",
                destination="downloads",
            )
            assert result == {"task_id": "dbid_new_001"}

    @respx.mock
    async def test_dsm_error_raises_typed_exception(self, tmp_path: Path) -> None:
        from mcp_synology.core.downloadstation_errors import DownloadStationError

        client = make_client(make_api_cache())
        torrent = tmp_path / "bad.torrent"
        torrent.write_bytes(b"not a torrent")

        respx.post(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": False, "error": {"code": 400}},
        )

        async with client:
            try:
                await client.create_download_task_with_file(
                    file_path=torrent,
                    filename="bad.torrent",
                )
            except DownloadStationError as e:
                assert "upload" in str(e).lower()
            else:
                raise AssertionError("expected DownloadStationError on code 400")

    @respx.mock
    async def test_session_error_triggers_one_reauth_retry(self, tmp_path: Path) -> None:
        client = make_client(make_api_cache())
        torrent = tmp_path / "fine.torrent"
        torrent.write_bytes(b"d4:infod6:lengthi100eee")

        reauth_count = 0

        async def fake_reauth() -> None:
            nonlocal reauth_count
            reauth_count += 1
            client._sid = "new_sid"  # noqa: SLF001 — test injection

        client._re_auth_callback = fake_reauth  # noqa: SLF001

        respx.post(f"{BASE_URL}/webapi/entry.cgi").mock(
            side_effect=[
                httpx.Response(200, json={"success": False, "error": {"code": 106}}),
                httpx.Response(200, json={"success": True, "data": {"task_id": "dbid_002"}}),
            ]
        )

        async with client:
            result = await client.create_download_task_with_file(
                file_path=torrent, filename="fine.torrent"
            )
            assert result == {"task_id": "dbid_002"}
            assert reauth_count == 1
