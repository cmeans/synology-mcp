"""Tests for modules/downloadstation/config.py — get_download_config, get_schedule."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import respx

from mcp_synology.modules.downloadstation.config import (
    get_download_config,
)
from tests.conftest import BASE_URL

if TYPE_CHECKING:
    from mcp_synology.core.client import DsmClient


class TestGetSchedule:
    @respx.mock
    async def test_renders_schedule_grid_and_flags(self, mock_client: DsmClient) -> None:
        from mcp_synology.modules.downloadstation.config import get_schedule

        sunday = "0" + "1" + "2" + "0" * 21
        plan = sunday + "0" * (168 - 24)

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": {
                    "enabled": True,
                    "emule_enabled": False,
                    "schedule_plan": plan,
                },
            }
        )
        result = await get_schedule(mock_client)
        assert "Sun" in result
        assert "Sat" in result
        assert "Legend" in result
        assert "Enabled" in result
        assert "eMule" in result

    @respx.mock
    async def test_disabled_schedule_shows_flag(self, mock_client: DsmClient) -> None:
        from mcp_synology.modules.downloadstation.config import get_schedule

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": {
                    "enabled": False,
                    "emule_enabled": False,
                    "schedule_plan": "0" * 168,
                },
            }
        )
        result = await get_schedule(mock_client)
        # The "Enabled" pair should render "no" (format_key_value spacing
        # may use either "Enabled: no" or "Enabled  no" — accept either).
        assert "Enabled" in result
        assert "no" in result

    @respx.mock
    async def test_dsm_error_propagates_as_tool_error(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.config import get_schedule

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": False, "error": {"code": 105}},
        )
        try:
            await get_schedule(mock_client)
        except ToolError as e:
            assert "105" in str(e) or "permission" in str(e).lower()
        else:
            raise AssertionError("expected ToolError")

    @respx.mock
    async def test_malformed_plan_renders_error_but_does_not_crash(
        self, mock_client: DsmClient
    ) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.config import get_schedule

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": {
                    "enabled": True,
                    "emule_enabled": False,
                    "schedule_plan": "0" * 100,
                },
            }
        )
        try:
            await get_schedule(mock_client)
        except ToolError as e:
            assert "168" in str(e) or "schedule_plan" in str(e)
        else:
            raise AssertionError("expected ToolError on malformed schedule_plan")


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


class TestGetScheduleNonStringPlan:
    """Covers the schedule_plan-is-not-a-string branch (a real DSM oddity to
    defend against — the API spec says string but a malformed firmware could
    return None or a number).
    """

    @respx.mock
    async def test_non_string_schedule_plan_raises_tool_error(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.config import get_schedule

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": {
                    "enabled": True,
                    "emule_enabled": False,
                    "schedule_plan": 12345,  # non-string — invariant violation
                },
            }
        )
        try:
            await get_schedule(mock_client)
        except ToolError as e:
            assert "schedule_plan" in str(e) or "not a string" in str(e)
        else:
            raise AssertionError("expected ToolError on non-string schedule_plan")


class TestGetDownloadConfigBoolNone:
    """Covers _bool_str(None) — when DSM omits a bool field (older firmware
    may omit unzip_service_enabled / emule_enabled), the field should render
    as an em dash rather than 'no' or crashing.
    """

    @respx.mock
    async def test_missing_emule_enabled_renders_em_dash(self, mock_client: DsmClient) -> None:
        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={
                "success": True,
                "data": {
                    "bt_max_download": 0,
                    "bt_max_upload": 0,
                    # emule_enabled deliberately absent
                    "default_destination": "downloads",
                    # unzip_service_enabled deliberately absent
                },
            }
        )
        result = await get_download_config(mock_client)
        # _bool_str(None) returns "—"
        assert "—" in result


class TestSetDownloadConfig:
    @respx.mock
    async def test_partial_update_sends_only_supplied_fields(self, mock_client: DsmClient) -> None:
        from mcp_synology.modules.downloadstation.config import set_download_config

        captured: dict = {}

        def _capture(request):
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json={"success": True, "data": {}})

        respx.get(f"{BASE_URL}/webapi/entry.cgi").mock(side_effect=_capture)
        result = await set_download_config(
            mock_client, bt_max_upload=500, default_destination="downloads"
        )
        params = captured["params"]
        assert params.get("bt_max_upload") == "500"
        assert params.get("default_destination") == "downloads"
        assert "bt_max_download" not in params
        assert "emule_max_download" not in params
        assert "bt_max_upload" in result
        assert "default_destination" in result

    async def test_no_fields_supplied_raises(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.config import set_download_config

        try:
            await set_download_config(mock_client)
        except ToolError as e:
            msg = str(e).lower()
            assert "nothing" in msg or "no fields" in msg
        else:
            raise AssertionError("expected ToolError on no-op call")

    @respx.mock
    async def test_dsm_error_propagates(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.config import set_download_config

        respx.get(f"{BASE_URL}/webapi/entry.cgi").respond(
            json={"success": False, "error": {"code": 105}},
        )
        try:
            await set_download_config(mock_client, bt_max_download=100)
        except ToolError as e:
            assert "105" in str(e) or "permission" in str(e).lower()
        else:
            raise AssertionError("expected ToolError")

    @respx.mock
    async def test_method_is_setconfig(self, mock_client: DsmClient) -> None:
        """Regression guard — setconfig method name."""
        from mcp_synology.modules.downloadstation.config import set_download_config

        captured: dict = {}

        def _capture(request):
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json={"success": True, "data": {}})

        respx.get(f"{BASE_URL}/webapi/entry.cgi").mock(side_effect=_capture)
        await set_download_config(mock_client, bt_max_download=0)
        params = captured["params"]
        assert params.get("method") == "setconfig"
        assert params.get("api") == "SYNO.DownloadStation.Info"
        assert params.get("bt_max_download") == "0"


class TestSetSchedule:
    @respx.mock
    async def test_partial_update_sends_only_supplied_fields(self, mock_client: DsmClient) -> None:
        from mcp_synology.modules.downloadstation.config import set_schedule

        captured: dict = {}

        def _capture(request):
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json={"success": True, "data": {}})

        respx.get(f"{BASE_URL}/webapi/entry.cgi").mock(side_effect=_capture)
        result = await set_schedule(mock_client, enabled=False)
        params = captured["params"]
        assert params.get("enabled") == "false"
        assert "schedule_plan" not in params
        assert "Enabled" in result or "enabled" in result

    async def test_schedule_plan_length_validated_client_side(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.config import set_schedule

        # Should validate length and raise BEFORE any HTTP call
        try:
            await set_schedule(mock_client, schedule_plan="0" * 100)
        except ToolError as e:
            assert "168" in str(e) or "schedule_plan" in str(e)
        else:
            raise AssertionError("expected ToolError on bad-length schedule_plan")

    @respx.mock
    async def test_valid_schedule_plan_sent_through(self, mock_client: DsmClient) -> None:
        from mcp_synology.modules.downloadstation.config import set_schedule

        captured: dict = {}

        def _capture(request):
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json={"success": True, "data": {}})

        respx.get(f"{BASE_URL}/webapi/entry.cgi").mock(side_effect=_capture)
        plan = "1" * 168
        await set_schedule(mock_client, schedule_plan=plan)
        assert captured["params"].get("schedule_plan") == plan

    async def test_no_fields_supplied_raises(self, mock_client: DsmClient) -> None:
        from mcp.server.fastmcp.exceptions import ToolError

        from mcp_synology.modules.downloadstation.config import set_schedule

        try:
            await set_schedule(mock_client)
        except ToolError as e:
            msg = str(e).lower()
            assert "nothing" in msg or "no fields" in msg
        else:
            raise AssertionError("expected ToolError on no-op call")

    @respx.mock
    async def test_method_is_setconfig(self, mock_client: DsmClient) -> None:
        from mcp_synology.modules.downloadstation.config import set_schedule

        captured: dict = {}

        def _capture(request):
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json={"success": True, "data": {}})

        respx.get(f"{BASE_URL}/webapi/entry.cgi").mock(side_effect=_capture)
        await set_schedule(mock_client, enabled=True)
        params = captured["params"]
        assert params.get("method") == "setconfig"
        assert params.get("api") == "SYNO.DownloadStation.Schedule"
