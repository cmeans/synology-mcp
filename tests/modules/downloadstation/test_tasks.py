"""Tests for modules/downloadstation/tasks.py — list_downloads, get_download_info."""

from __future__ import annotations

from typing import TYPE_CHECKING

import respx

from mcp_synology.modules.downloadstation.tasks import get_download_info, list_downloads
from tests.conftest import BASE_URL

if TYPE_CHECKING:
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
