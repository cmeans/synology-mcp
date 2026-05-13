"""Download Station task tools: list_downloads, get_download_info."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mcp_synology.core.errors import ErrorCode, SynologyError
from mcp_synology.core.formatting import (
    error_response,
    format_key_value,
    format_size,
    format_table,
    format_timestamp,
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
        error_response(
            ErrorCode.INVALID_PARAMETER,
            f"List downloads failed: unknown status_filter {status_filter!r}.",
            retryable=False,
            param="status_filter",
            value=status_filter,
            valid=sorted(_VALID_STATUS_FILTERS),
        )

    try:
        data = await client.request(
            "SYNO.DownloadStation.Task",
            "list",
            version=1,
            params={
                "offset": str(offset),
                "limit": str(limit),
                # DS Task API uses comma-separated additional groups, not the
                # JSON-array format FileStation v2 uses.
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
    """Get detailed information for a single download task.

    Requests all ``additional`` groups in one round-trip and renders them as
    distinct sections.
    """
    try:
        data = await client.request(
            "SYNO.DownloadStation.Task",
            "getinfo",
            version=1,
            params={
                "id": task_id,
                # DS Task API uses comma-separated additional groups, not the
                # JSON-array format FileStation v2 uses.
                "additional": "detail,transfer,file,tracker,peer",
            },
        )
    except SynologyError as e:
        synology_error_response(f"Get download info ({task_id})", e)

    tasks: list[dict[str, Any]] = data.get("tasks", [])
    if not tasks:
        error_response(
            ErrorCode.NOT_FOUND,
            f"Task {task_id!r} not found.",
            retryable=False,
            param="task_id",
            value=task_id,
        )
    task = tasks[0]

    sections: list[str] = []

    # Header block
    header_pairs = [
        ("ID", task.get("id", "—")),
        ("Title", task.get("title", "—")),
        ("Type", task.get("type", "—")),
        ("Status", format_task_status(task.get("status"))),
        ("Size", format_size(int(task.get("size", 0)))),
    ]
    sections.append(format_key_value(header_pairs, title="Task"))

    add = task.get("additional", {}) or {}

    # Detail block
    detail = add.get("detail", {}) or {}
    if detail:
        detail_pairs = [
            ("Destination", detail.get("destination", "—")),
            ("URI", detail.get("uri", "—")),
            ("Priority", detail.get("priority", "—")),
            ("Created", _format_epoch(detail.get("create_time"))),
            ("Started", _format_epoch(detail.get("started_time"))),
            ("Completed", _format_epoch(detail.get("completed_time"))),
        ]
        sections.append(format_key_value(detail_pairs, title="Detail"))

    # Transfer block
    transfer = add.get("transfer", {}) or {}
    if transfer:
        size_total = int(task.get("size", 0))
        size_down = int(transfer.get("size_downloaded", 0))
        size_up = int(transfer.get("size_uploaded", 0))
        transfer_pairs = [
            ("Downloaded", format_transfer_progress(size_down, size_total)),
            ("Uploaded", format_size(size_up)),
            ("Speed (down)", _format_speed(int(transfer.get("speed_download", 0)))),
            ("Speed (up)", _format_speed(int(transfer.get("speed_upload", 0)))),
        ]
        sections.append(format_key_value(transfer_pairs, title="Transfer"))

    # File table (BT)
    files = add.get("file", []) or []
    if files:
        file_rows = [
            [
                f.get("filename", "—"),
                format_size(int(f.get("size", 0))),
                format_transfer_progress(int(f.get("size_downloaded", 0)), int(f.get("size", 0))),
                f.get("priority", "—"),
            ]
            for f in files
        ]
        sections.append(
            format_table(
                headers=["File", "Size", "Progress", "Priority"],
                rows=file_rows,
                title="Files",
            )
        )

    # Tracker table (BT)
    trackers = add.get("tracker", []) or []
    if trackers:
        tracker_rows = [
            [
                tr.get("url", "—"),
                tr.get("status", "—"),
                str(tr.get("peers", 0)),
                str(tr.get("seeds", 0)),
            ]
            for tr in trackers
        ]
        sections.append(
            format_table(
                headers=["Tracker", "Status", "Peers", "Seeds"],
                rows=tracker_rows,
                title="Trackers",
            )
        )

    # Peer table (BT)
    peers = add.get("peer", []) or []
    if peers:
        peer_rows = [
            [
                p.get("address", "—"),
                p.get("agent", "—"),
                f"{int(float(p.get('progress', 0)) * 100)}%",
                _format_speed(int(p.get("speed_download", 0))),
                _format_speed(int(p.get("speed_upload", 0))),
            ]
            for p in peers
        ]
        sections.append(
            format_table(
                headers=["Peer", "Client", "Progress", "Down", "Up"],
                rows=peer_rows,
                title="Peers",
            )
        )

    return "\n\n".join(sections)


def _format_epoch(epoch: int | None) -> str:
    """Render an epoch timestamp using the shared formatter; '—' for None/0."""
    if not epoch:
        return "—"
    return format_timestamp(float(epoch))
