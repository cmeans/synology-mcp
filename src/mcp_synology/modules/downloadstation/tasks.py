"""Download Station task tools: list_downloads, get_download_info."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp.exceptions import ToolError

from mcp_synology.core.errors import SynologyError
from mcp_synology.core.formatting import (
    format_size,
    format_table,
    synology_error_response,
)
from mcp_synology.modules.downloadstation.helpers import (
    STATUS_GROUPS,
    format_task_status,
    format_transfer_progress,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp_synology.core.client import DsmClient

_VALID_STATUS_FILTERS: set[str] = {"all", *STATUS_GROUPS.keys()}


def _format_speed(bytes_per_sec: int) -> str:
    if bytes_per_sec <= 0:
        return "—"
    return f"{format_size(bytes_per_sec)}/s"


def _format_eta(downloaded: int, total: int, speed: int) -> str:
    if speed <= 0 or total <= downloaded:
        return "—"
    remaining = total - downloaded
    seconds = remaining // speed
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h{(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d{(seconds % 86400) // 3600}h"


async def list_downloads(
    client: DsmClient,
    *,
    status_filter: str = "all",
    offset: int = 0,
    limit: int = 100,
) -> str:
    """List download tasks in the Download Station queue.

    The DSM v1 ``SYNO.DownloadStation.Task.list`` endpoint does not support
    server-side status filtering, so we fetch and filter client-side. To keep
    each row cheap, only ``detail`` and ``transfer`` additional groups are
    requested — ``get_download_info`` fetches the full set for a single task.
    """
    if status_filter not in _VALID_STATUS_FILTERS:
        valid = ", ".join(sorted(_VALID_STATUS_FILTERS))
        msg = f"Unknown status_filter '{status_filter}'. Valid values: {valid}"
        raise ToolError(msg)

    try:
        data = await client.request(
            "SYNO.DownloadStation.Task",
            "list",
            version=1,
            params={
                "offset": str(offset),
                "limit": str(limit),
                "additional": "detail,transfer",
            },
        )
    except SynologyError as e:
        synology_error_response("List downloads", e)

    tasks: list[dict[str, Any]] = data.get("tasks", [])

    if status_filter != "all":
        wanted = STATUS_GROUPS[status_filter]
        tasks = [t for t in tasks if t.get("status") in wanted]

    if not tasks:
        return format_table(
            headers=["ID", "Title", "Type", "Status", "Size", "Progress", "Speed", "ETA"],
            rows=[],
            title=f"Download Station queue ({status_filter})",
        )

    rows: list[list[str]] = []
    for t in tasks:
        task_id = t.get("id", "—")
        title = t.get("title", "—")
        ttype = t.get("type", "—")
        status = format_task_status(t.get("status"))
        size_total = int(t.get("size", 0))
        transfer = t.get("additional", {}).get("transfer", {})
        size_down = int(transfer.get("size_downloaded", 0))
        speed_down = int(transfer.get("speed_download", 0))
        progress = format_transfer_progress(size_down, size_total)
        speed = _format_speed(speed_down)
        eta = _format_eta(size_down, size_total, speed_down)
        rows.append(
            [
                task_id,
                title,
                ttype,
                status,
                format_size(size_total),
                progress,
                speed,
                eta,
            ]
        )

    total = data.get("total", len(rows))
    title = f"Download Station queue ({status_filter})"
    result = format_table(
        headers=["ID", "Title", "Type", "Status", "Size", "Progress", "Speed", "ETA"],
        rows=rows,
        title=title,
    )
    result += f"\n\n{total} task(s) total; showing {len(rows)}."
    return result


async def get_download_info(
    client: DsmClient,
    *,
    task_id: str,
) -> str:
    """Stub — replaced in Task 4."""
    raise NotImplementedError("get_download_info is implemented in Task 4")
