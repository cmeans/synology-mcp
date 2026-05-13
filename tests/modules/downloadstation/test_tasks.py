"""Tests for modules/downloadstation/tasks.py — list_downloads, get_download_info."""

from __future__ import annotations

from typing import TYPE_CHECKING

import respx

from mcp_synology.modules.downloadstation.tasks import list_downloads
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
