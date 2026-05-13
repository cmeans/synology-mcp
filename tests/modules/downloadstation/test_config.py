"""Tests for modules/downloadstation/config.py — get_download_config, get_schedule."""

from __future__ import annotations

from typing import TYPE_CHECKING

import respx

from mcp_synology.modules.downloadstation.config import (
    get_download_config,
)
from tests.conftest import BASE_URL

if TYPE_CHECKING:
    from mcp_synology.core.client import DsmClient


class TestGetDownloadConfig:
    @respx.mock
    async def test_renders_known_fields(self, mock_client: DsmClient) -> None:
        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": {
                    "bt_max_download": 0,
                    "bt_max_upload": 100,
                    "emule_enabled": False,
                    "emule_max_download": 0,
                    "emule_max_upload": 0,
                    "default_destination": "downloads",
                    "unzip_service_enabled": True,
                },
            }
        )
        result = await get_download_config(mock_client)
        assert "BT max download" in result
        assert "unlimited" in result.lower()  # bt_max_download=0 renders unlimited
        assert "downloads" in result  # default_destination
        assert "eMule" in result  # row present whether enabled or not

    @respx.mock
    async def test_dsm_error_propagates_as_tool_error(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": False, "error": {"code": 105}},
        )
        try:
            await get_download_config(mock_client)
        except ToolError as e:
            assert "105" in str(e) or "permission" in str(e).lower()
        else:
            raise AssertionError("expected ToolError")
