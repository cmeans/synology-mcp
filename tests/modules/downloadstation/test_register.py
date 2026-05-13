"""Tests for modules/downloadstation/__init__.py — module registration code paths.

Mirrors the structure of tests/modules/filestation/test_register.py. As Phase 1
adds each tool, this file gains a test asserting the tool is registered when
allowed and absent when filtered out.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from mcp_synology.modules import RegisterContext
from mcp_synology.modules.downloadstation import MODULE_INFO, register


def _make_ctx(
    allowed: set[str] | None = None,
    settings: dict | None = None,
) -> tuple[FastMCP, MagicMock, RegisterContext]:
    server = FastMCP("test-ds")
    manager = MagicMock()
    fake_client = MagicMock()
    manager.get_client = AsyncMock(return_value=fake_client)
    manager.with_update_notice = MagicMock(side_effect=lambda s: s)

    if allowed is None:
        allowed = {t.name for t in MODULE_INFO.tools}

    ctx = RegisterContext(
        server=server,
        manager=manager,
        allowed_tools=allowed,
        settings_dict=settings or {},
        display_name="test-nas",
    )
    return server, manager, ctx


class TestDownloadstationModuleRegister:
    def test_module_info_declares_required_dsm_task_api(self) -> None:
        api_names = {req.api_name for req in MODULE_INFO.required_apis}
        assert "SYNO.DownloadStation.Task" in api_names
        required = [r for r in MODULE_INFO.required_apis if not r.optional]
        assert len(required) == 1
        assert required[0].api_name == "SYNO.DownloadStation.Task"

    def test_module_info_phase1_tools_present(self) -> None:
        tool_names = {t.name for t in MODULE_INFO.tools}
        assert tool_names == {
            "list_downloads",
            "get_download_info",
            "get_download_stats",
            "get_download_config",
            "get_schedule",
        }

    def test_module_info_phase1_tools_are_all_read_tier(self) -> None:
        from mcp_synology.modules import PermissionTier

        for tool in MODULE_INFO.tools:
            assert tool.permission_tier == PermissionTier.READ, (
                f"Phase 1 tool {tool.name} should be READ tier, got {tool.permission_tier}"
            )

    def test_register_no_tools_when_none_allowed(self) -> None:
        server, _manager, ctx = _make_ctx(allowed=set())
        register(ctx)
        assert server._tool_manager._tools == {}

    def test_register_all_tools_when_all_allowed(self) -> None:
        server, _manager, ctx = _make_ctx()
        register(ctx)
        registered = set(server._tool_manager._tools.keys())
        expected = {t.name for t in MODULE_INFO.tools}
        assert registered == expected
