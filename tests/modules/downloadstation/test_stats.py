"""Tests for modules/downloadstation/stats.py — get_download_stats."""

from __future__ import annotations

from typing import TYPE_CHECKING

import respx

from mcp_synology.modules.downloadstation.stats import get_download_stats
from tests.conftest import BASE_URL

if TYPE_CHECKING:
    from mcp_synology.core.client import DsmClient


class TestGetDownloadStats:
    @respx.mock
    async def test_renders_total_speeds(self, mock_client: DsmClient) -> None:
        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": {
                    "speed_download": 5242880,
                    "speed_upload": 1048576,
                },
            }
        )
        result = await get_download_stats(mock_client)
        assert "Download" in result
        assert "Upload" in result
        assert "eMule" not in result

    @respx.mock
    async def test_includes_emule_when_present(self, mock_client: DsmClient) -> None:
        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": {
                    "speed_download": 0,
                    "speed_upload": 0,
                    "emule_speed_download": 128 * 1024,
                    "emule_speed_upload": 64 * 1024,
                },
            }
        )
        result = await get_download_stats(mock_client)
        assert "eMule" in result

    @respx.mock
    async def test_dsm_error_propagates_as_tool_error(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": False, "error": {"code": 105}},
        )
        try:
            await get_download_stats(mock_client)
        except ToolError as e:
            assert "105" in str(e) or "permission" in str(e).lower()
        else:
            raise AssertionError("expected ToolError")
