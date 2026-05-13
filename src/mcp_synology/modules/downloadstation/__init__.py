"""Download Station module: MODULE_INFO, register(), DownloadStationSettings.

Phase 1 (READ tools): list_downloads, get_download_info, get_download_stats,
get_download_config, get_schedule. Phase 2 adds task CRUD writes; Phase 3
adds BT search + RSS. See docs/superpowers/specs/2026-05-13-downloadstation-module-design.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from mcp_synology.modules import (
    ApiRequirement,
    ModuleInfo,
    PermissionTier,
    ToolInfo,
    default_annotations,
)

if TYPE_CHECKING:
    from mcp_synology.modules import RegisterContext


class DownloadStationSettings(BaseModel):
    """Download Station module settings."""

    enabled_extras: list[str] = Field(default_factory=list)


MODULE_INFO = ModuleInfo(
    name="downloadstation",
    description=("Manage Synology Download Station tasks, schedule, and configuration"),
    required_apis=[
        ApiRequirement(api_name="SYNO.DownloadStation.Task", min_version=1),
        ApiRequirement(api_name="SYNO.DownloadStation.Info", min_version=1, optional=True),
        ApiRequirement(api_name="SYNO.DownloadStation.Schedule", min_version=1, optional=True),
        ApiRequirement(api_name="SYNO.DownloadStation.Statistic", min_version=1, optional=True),
        ApiRequirement(api_name="SYNO.DownloadStation.RSS.Site", min_version=1, optional=True),
        ApiRequirement(api_name="SYNO.DownloadStation.RSS.Feed", min_version=1, optional=True),
        ApiRequirement(api_name="SYNO.DownloadStation.BTSearch", min_version=1, optional=True),
        ApiRequirement(api_name="SYNO.DownloadStation2.Task", min_version=1, optional=True),
    ],
    tools=[
        ToolInfo(
            name="list_downloads",
            description=(
                "List download tasks in the Download Station queue. Filter by status "
                "(downloading/finished/paused/error/all). Returns a table with id, title, "
                "type (bt/http/ftp/nzb), status, size, progress%, current speed, and ETA."
            ),
            permission_tier=PermissionTier.READ,
        ),
        ToolInfo(
            name="get_download_info",
            description=(
                "Get detailed information for a specific download task: detail (status, "
                "destination, URI), transfer (size downloaded/uploaded, speed, peers), "
                "files (per-file selection for BT), trackers (BT only), peers (BT only). "
                "Use list_downloads first to find the task_id."
            ),
            permission_tier=PermissionTier.READ,
        ),
        ToolInfo(
            name="get_download_stats",
            description=(
                "Get current Download Station throughput statistics: total download and "
                "upload speed across all tasks, plus per-service (BT, HTTP/FTP, eMule) "
                "breakdowns when those services are enabled."
            ),
            permission_tier=PermissionTier.READ,
        ),
        ToolInfo(
            name="get_download_config",
            description=(
                "Get Download Station global configuration: BT max upload/download speeds, "
                "default destination, scheduled-throttling plan summary, eMule enable state, "
                "and other DSM-level DS settings."
            ),
            permission_tier=PermissionTier.READ,
        ),
        ToolInfo(
            name="get_schedule",
            description=(
                "Get the Download Station weekly schedule as a 7-day × 24-hour grid. Each "
                "cell shows whether downloads are off, on, or throttled at that hour. "
                "Useful for verifying off-peak bandwidth policies."
            ),
            permission_tier=PermissionTier.READ,
        ),
    ],
    settings_schema=DownloadStationSettings,
)


def register(ctx: RegisterContext) -> None:
    """Register Download Station tools with the MCP server."""
    from mcp_synology.modules.downloadstation.config import (
        get_download_config,
        get_schedule,
    )
    from mcp_synology.modules.downloadstation.stats import get_download_stats
    from mcp_synology.modules.downloadstation.tasks import (
        get_download_info,
        list_downloads,
    )

    server = ctx.server
    manager = ctx.manager

    _tool_annos = {
        t.name: t.annotations or default_annotations(t.permission_tier) for t in MODULE_INFO.tools
    }

    def _desc(name: str) -> str:
        return next(t.description for t in MODULE_INFO.tools if t.name == name)

    if "list_downloads" in ctx.allowed_tools:

        @server.tool(
            name="list_downloads",
            description=_desc("list_downloads"),
            annotations=_tool_annos["list_downloads"],
        )
        async def tool_list_downloads(
            status_filter: str = "all",
            offset: int = 0,
            limit: int = 100,
        ) -> str:
            client = await manager.get_client()
            return await list_downloads(
                client,
                status_filter=status_filter,
                offset=offset,
                limit=limit,
            )

    if "get_download_info" in ctx.allowed_tools:

        @server.tool(
            name="get_download_info",
            description=_desc("get_download_info"),
            annotations=_tool_annos["get_download_info"],
        )
        async def tool_get_download_info(task_id: str) -> str:
            client = await manager.get_client()
            return await get_download_info(client, task_id=task_id)

    if "get_download_stats" in ctx.allowed_tools:

        @server.tool(
            name="get_download_stats",
            description=_desc("get_download_stats"),
            annotations=_tool_annos["get_download_stats"],
        )
        async def tool_get_download_stats() -> str:
            client = await manager.get_client()
            return await get_download_stats(client)

    if "get_download_config" in ctx.allowed_tools:

        @server.tool(
            name="get_download_config",
            description=_desc("get_download_config"),
            annotations=_tool_annos["get_download_config"],
        )
        async def tool_get_download_config() -> str:
            client = await manager.get_client()
            return await get_download_config(client)

    if "get_schedule" in ctx.allowed_tools:

        @server.tool(
            name="get_schedule",
            description=_desc("get_schedule"),
            annotations=_tool_annos["get_schedule"],
        )
        async def tool_get_schedule() -> str:
            client = await manager.get_client()
            return await get_schedule(client)
