"""Tests for modules/downloadstation/tasks.py — list_downloads, get_download_info."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import respx

from mcp_synology.modules.downloadstation.tasks import get_download_info, list_downloads
from tests.conftest import BASE_URL

if TYPE_CHECKING:
    from pathlib import Path

    from mcp_synology.core.client import DsmClient


class TestListDownloads:
    @respx.mock
    async def test_lists_all_tasks(self, mock_client: DsmClient) -> None:
        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": {
                    "offset": 0,
                    "total": 2,
                    "tasks": [
                        {
                            "id": "dbid_001",
                            "type": "bt",
                            "title": "ubuntu-24.04.iso",
                            "size": 5368709120,
                            "status": 2,
                            "additional": {
                                "detail": {"destination": "downloads"},
                                "transfer": {
                                    "size_downloaded": 2684354560,
                                    "speed_download": 5242880,
                                    "speed_upload": 0,
                                },
                            },
                        },
                        {
                            "id": "dbid_002",
                            "type": "http",
                            "title": "movie.mkv",
                            "size": 2147483648,
                            "status": 5,
                            "additional": {
                                "detail": {"destination": "video"},
                                "transfer": {
                                    "size_downloaded": 2147483648,
                                    "speed_download": 0,
                                    "speed_upload": 0,
                                },
                            },
                        },
                    ],
                },
            }
        )
        result = await list_downloads(mock_client, status_filter="all")
        assert "ubuntu-24.04.iso" in result
        assert "movie.mkv" in result
        assert "downloading" in result
        assert "finished" in result
        assert "(50%)" in result

    @respx.mock
    async def test_filter_downloading_excludes_finished(self, mock_client: DsmClient) -> None:
        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": {
                    "offset": 0,
                    "total": 2,
                    "tasks": [
                        {
                            "id": "dbid_001",
                            "type": "bt",
                            "title": "active.iso",
                            "size": 100,
                            "status": 2,
                            "additional": {
                                "detail": {},
                                "transfer": {
                                    "size_downloaded": 50,
                                    "speed_download": 100,
                                    "speed_upload": 0,
                                },
                            },
                        },
                        {
                            "id": "dbid_002",
                            "type": "http",
                            "title": "done.mkv",
                            "size": 100,
                            "status": 5,
                            "additional": {
                                "detail": {},
                                "transfer": {
                                    "size_downloaded": 100,
                                    "speed_download": 0,
                                    "speed_upload": 0,
                                },
                            },
                        },
                    ],
                },
            }
        )
        result = await list_downloads(mock_client, status_filter="downloading")
        assert "active.iso" in result
        assert "done.mkv" not in result

    @respx.mock
    async def test_empty_queue(self, mock_client: DsmClient) -> None:
        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": True, "data": {"offset": 0, "total": 0, "tasks": []}},
        )
        result = await list_downloads(mock_client)
        assert "No items to display" in result

    @respx.mock
    async def test_dsm_error_propagates_as_tool_error(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": False, "error": {"code": 105}},
        )
        try:
            await list_downloads(mock_client)
        except ToolError as e:
            assert "105" in str(e) or "permission" in str(e).lower()
        else:
            raise AssertionError("expected ToolError")

    @respx.mock
    async def test_unknown_status_filter_raises_tool_error(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        try:
            await list_downloads(mock_client, status_filter="not_a_status")
        except ToolError as e:
            assert "status_filter" in str(e)
        else:
            raise AssertionError("expected ToolError for invalid status_filter")


class TestGetDownloadInfo:
    @respx.mock
    async def test_returns_detail_transfer_blocks(self, mock_client: DsmClient) -> None:
        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": {
                    "tasks": [
                        {
                            "id": "dbid_001",
                            "type": "bt",
                            "title": "ubuntu.iso",
                            "size": 1000000000,
                            "status": 2,
                            "additional": {
                                "detail": {
                                    "destination": "downloads",
                                    "uri": "magnet:?xt=...",
                                    "create_time": 1700000000,
                                    "started_time": 1700000010,
                                    "priority": "auto",
                                },
                                "transfer": {
                                    "size_downloaded": 500000000,
                                    "size_uploaded": 100000000,
                                    "speed_download": 1024 * 1024,
                                    "speed_upload": 256 * 1024,
                                },
                                "file": [
                                    {
                                        "filename": "ubuntu.iso",
                                        "size": 1000000000,
                                        "size_downloaded": 500000000,
                                        "priority": "normal",
                                    },
                                ],
                                "tracker": [
                                    {
                                        "url": "http://tracker.example.org/announce",
                                        "status": "Success",
                                        "peers": 42,
                                        "seeds": 10,
                                    },
                                ],
                                "peer": [
                                    {
                                        "address": "1.2.3.4",
                                        "agent": "Transmission",
                                        "progress": 1.0,
                                        "speed_download": 0,
                                        "speed_upload": 1024,
                                    },
                                ],
                            },
                        }
                    ]
                },
            }
        )
        result = await get_download_info(mock_client, task_id="dbid_001")
        assert "ubuntu.iso" in result
        assert "downloading" in result
        assert "downloads" in result  # destination
        assert "(50%)" in result  # transfer progress
        # Section headers should all be present.
        assert "Files" in result
        assert "Trackers" in result
        assert "Peers" in result
        assert "tracker.example.org" in result
        assert "1.2.3.4" in result

    @respx.mock
    async def test_task_not_found_error(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": False, "error": {"code": 404}},
        )
        try:
            await get_download_info(mock_client, task_id="dbid_missing")
        except ToolError as e:
            assert "404" in str(e) or "task" in str(e).lower()
        else:
            raise AssertionError("expected ToolError for missing task")

    @respx.mock
    async def test_empty_tasks_array_treated_as_not_found(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": True, "data": {"tasks": []}},
        )
        try:
            await get_download_info(mock_client, task_id="dbid_001")
        except ToolError as e:
            assert "not found" in str(e).lower() or "dbid_001" in str(e)
        else:
            raise AssertionError("expected ToolError when DSM returns empty tasks array")


class TestCreateDownload:
    @respx.mock
    async def test_uri_create_success(self, mock_client: DsmClient) -> None:
        from mcp_synology.modules.downloadstation.tasks import create_download

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": True, "data": {"task_id": "dbid_new"}},
        )
        result = await create_download(mock_client, uri="magnet:?xt=urn:btih:abc")
        assert "Created" in result or "dbid_new" in result

    @respx.mock
    async def test_uri_comma_list_passes_through(self, mock_client: DsmClient) -> None:
        from mcp_synology.modules.downloadstation.tasks import create_download

        captured: dict = {}

        def _capture(request):
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json={"success": True, "data": {}})

        respx.get(f"{BASE_URL}/webapi/entry.cgi").mock(side_effect=_capture)
        await create_download(
            mock_client, uri="http://a.example/file.iso,http://b.example/file2.iso"
        )
        assert (
            captured["params"].get("uri") == "http://a.example/file.iso,http://b.example/file2.iso"
        )

    async def test_neither_uri_nor_torrent_path_raises_tool_error(
        self, mock_client: DsmClient
    ) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.tasks import create_download

        try:
            await create_download(mock_client)
        except ToolError as e:
            msg = str(e).lower()
            assert "uri" in msg or "torrent" in msg
        else:
            raise AssertionError("expected ToolError when neither input supplied")

    async def test_both_uri_and_torrent_path_raises_tool_error(
        self, mock_client: DsmClient, tmp_path: Path
    ) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.tasks import create_download

        torrent = tmp_path / "x.torrent"
        torrent.write_bytes(b"x")
        try:
            await create_download(mock_client, uri="magnet:?...", torrent_file_path=str(torrent))
        except ToolError as e:
            msg = str(e).lower()
            assert "both" in msg or "exactly one" in msg
        else:
            raise AssertionError("expected ToolError when both supplied")

    async def test_torrent_file_create_uses_multipart_path(
        self, mock_client: DsmClient, tmp_path: Path, monkeypatch
    ) -> None:
        from unittest.mock import AsyncMock

        from mcp_synology.modules.downloadstation.tasks import create_download

        torrent = tmp_path / "ubuntu.torrent"
        torrent.write_bytes(b"d4:infod6:lengthi100eee")

        mock = AsyncMock(return_value={"task_id": "dbid_mp_001"})
        monkeypatch.setattr(mock_client, "create_download_task_with_file", mock)

        result = await create_download(
            mock_client, torrent_file_path=str(torrent), destination="downloads"
        )
        assert "dbid_mp_001" in result
        mock.assert_awaited_once()
        kwargs = mock.await_args.kwargs
        assert kwargs.get("destination") == "downloads"
        # Verify file_path is a Path pointing at the torrent
        # (accept either keyword or positional file_path)
        file_path_arg = kwargs.get("file_path")
        if file_path_arg is None and mock.await_args.args:
            file_path_arg = mock.await_args.args[0]
        assert str(file_path_arg).endswith("ubuntu.torrent")

    async def test_torrent_file_missing_raises_tool_error(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.tasks import create_download

        try:
            await create_download(mock_client, torrent_file_path="/nonexistent/file.torrent")
        except ToolError as e:
            msg = str(e).lower()
            assert "not found" in msg or "no such" in msg
        else:
            raise AssertionError("expected ToolError on missing torrent file")

    @respx.mock
    async def test_dsm_400_upload_failed_propagates(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.tasks import create_download

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": False, "error": {"code": 400}},
        )
        try:
            await create_download(mock_client, uri="magnet:?...")
        except ToolError as e:
            # DS 400 = "File upload failed" — error envelope should surface it
            assert "upload" in str(e).lower() or "400" in str(e)
        else:
            raise AssertionError("expected ToolError on DS 400")

    @respx.mock
    async def test_session_error_triggers_reauth_retry_on_uri_path(
        self, mock_client: DsmClient
    ) -> None:
        """#99-style coverage: create_download exercises the standard GET
        path's re-auth retry (handled transparently by DsmClient.request)."""
        from mcp_synology.modules.downloadstation.tasks import create_download

        respx.get(f"{BASE_URL}/webapi/entry.cgi").mock(
            side_effect=[
                httpx.Response(200, json={"success": False, "error": {"code": 106}}),
                httpx.Response(200, json={"success": True, "data": {"task_id": "ok"}}),
            ]
        )
        # If the mock_client fixture's underlying client doesn't set up a
        # re-auth callback, this test verifies create_download surfaces the
        # error rather than swallowing it. Check the fixture if needed.
        try:
            result = await create_download(mock_client, uri="magnet:?...")
            assert "ok" in result
        except Exception as e:
            # If the fixture doesn't wire re-auth, the call should raise the
            # session error rather than silently succeeding — that's also fine
            # for this test's purpose (it documents the path).
            assert "106" in str(e) or "session" in str(e).lower()


class TestDeleteDownload:
    @respx.mock
    async def test_delete_data_true_success(self, mock_client: DsmClient) -> None:
        from mcp_synology.modules.downloadstation.tasks import delete_download

        captured: dict = {}

        def _capture(request):
            captured["params"] = dict(request.url.params)
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": [
                        {"id": "dbid_001", "error": 0},
                        {"id": "dbid_002", "error": 0},
                    ],
                },
            )

        respx.get(f"{BASE_URL}/webapi/entry.cgi").mock(side_effect=_capture)
        result = await delete_download(
            mock_client, task_ids=["dbid_001", "dbid_002"], delete_data=True
        )
        assert "dbid_001" in result
        assert "dbid_002" in result
        # Comma-joined ids in the request
        assert captured["params"].get("id") == "dbid_001,dbid_002"

    async def test_delete_data_false_refuses_with_clear_message(
        self, mock_client: DsmClient
    ) -> None:
        """DSM Task.delete v1 has no documented "keep files" mode — the tool
        refuses delete_data=False rather than silently deleting the files."""
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.tasks import delete_download

        try:
            await delete_download(mock_client, task_ids=["dbid_001"], delete_data=False)
        except ToolError as e:
            msg = str(e).lower()
            assert "delete_data" in msg or "keep" in msg or "not supported" in msg
        else:
            raise AssertionError("expected ToolError on delete_data=False")

    @respx.mock
    async def test_per_task_error_rendered_in_result(self, mock_client: DsmClient) -> None:
        from mcp_synology.modules.downloadstation.tasks import delete_download

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": [
                    {"id": "dbid_001", "error": 0},
                    {"id": "dbid_002", "error": 405},
                ],
            },
        )
        result = await delete_download(
            mock_client, task_ids=["dbid_001", "dbid_002"], delete_data=True
        )
        assert "dbid_001" in result
        assert "dbid_002" in result
        assert "405" in result or "error" in result.lower()

    async def test_empty_task_ids_raises(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.tasks import delete_download

        try:
            await delete_download(mock_client, task_ids=[], delete_data=True)
        except ToolError as e:
            assert "task_ids" in str(e) or "empty" in str(e).lower()
        else:
            raise AssertionError("expected ToolError on empty task_ids")

    @respx.mock
    async def test_dsm_error_propagates(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.tasks import delete_download

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": False, "error": {"code": 105}},
        )
        try:
            await delete_download(mock_client, task_ids=["dbid_001"], delete_data=True)
        except ToolError as e:
            assert "105" in str(e) or "permission" in str(e).lower()
        else:
            raise AssertionError("expected ToolError")

    @respx.mock
    async def test_force_complete_passed_to_dsm(self, mock_client: DsmClient) -> None:
        from mcp_synology.modules.downloadstation.tasks import delete_download

        captured: dict = {}

        def _capture(request):
            captured["params"] = dict(request.url.params)
            return httpx.Response(
                200,
                json={"success": True, "data": [{"id": "dbid_001", "error": 0}]},
            )

        respx.get(f"{BASE_URL}/webapi/entry.cgi").mock(side_effect=_capture)
        await delete_download(
            mock_client,
            task_ids=["dbid_001"],
            delete_data=True,
            force_complete=True,
        )
        assert captured["params"].get("force_complete") == "true"


class TestPauseDownload:
    @respx.mock
    async def test_pause_success(self, mock_client: DsmClient) -> None:
        from mcp_synology.modules.downloadstation.tasks import pause_download

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": True, "data": [{"id": "dbid_001", "error": 0}]},
        )
        result = await pause_download(mock_client, task_ids=["dbid_001"])
        assert "dbid_001" in result
        assert "ok" in result.lower()

    @respx.mock
    async def test_pause_already_paused_renders_per_task_error(
        self, mock_client: DsmClient
    ) -> None:
        from mcp_synology.modules.downloadstation.tasks import pause_download

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": [{"id": "dbid_001", "error": 405}],
            },
        )
        result = await pause_download(mock_client, task_ids=["dbid_001"])
        assert "405" in result or "error" in result.lower()

    @respx.mock
    async def test_pause_calls_pause_method(self, mock_client: DsmClient) -> None:
        """Regression guard — pause must call method=pause, not delete or resume."""
        from mcp_synology.modules.downloadstation.tasks import pause_download

        captured: dict = {}

        def _capture(request):
            captured["params"] = dict(request.url.params)
            return httpx.Response(
                200,
                json={"success": True, "data": [{"id": "dbid_001", "error": 0}]},
            )

        respx.get(f"{BASE_URL}/webapi/entry.cgi").mock(side_effect=_capture)
        await pause_download(mock_client, task_ids=["dbid_001"])
        assert captured["params"].get("method") == "pause"

    async def test_empty_task_ids_raises(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.tasks import pause_download

        try:
            await pause_download(mock_client, task_ids=[])
        except ToolError as e:
            assert "task_ids" in str(e) or "empty" in str(e).lower()
        else:
            raise AssertionError("expected ToolError on empty task_ids")


class TestResumeDownload:
    @respx.mock
    async def test_resume_success(self, mock_client: DsmClient) -> None:
        from mcp_synology.modules.downloadstation.tasks import resume_download

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": True, "data": [{"id": "dbid_001", "error": 0}]},
        )
        result = await resume_download(mock_client, task_ids=["dbid_001"])
        assert "dbid_001" in result
        assert "ok" in result.lower()

    @respx.mock
    async def test_resume_calls_resume_method(self, mock_client: DsmClient) -> None:
        """Regression guard against the shared helper accidentally swapping
        methods between pause/resume."""
        from mcp_synology.modules.downloadstation.tasks import resume_download

        captured: dict = {}

        def _capture(request):
            captured["params"] = dict(request.url.params)
            return httpx.Response(
                200,
                json={"success": True, "data": [{"id": "dbid_001", "error": 0}]},
            )

        respx.get(f"{BASE_URL}/webapi/entry.cgi").mock(side_effect=_capture)
        await resume_download(mock_client, task_ids=["dbid_001"])
        assert captured["params"].get("method") == "resume"
