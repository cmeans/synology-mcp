"""Download Station task tools: list_downloads, get_download_info."""

from __future__ import annotations

import logging
from pathlib import Path
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
    format_eta,
    format_speed,
    format_task_status,
    format_transfer_progress,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp_synology.core.client import DsmClient

_VALID_STATUS_FILTERS: set[str] = {"all", *STATUS_GROUPS.keys()}


def _format_epoch(epoch: int | None) -> str:
    """Render an epoch timestamp using the shared formatter; '—' for None/0."""
    if not epoch:
        return "—"
    return format_timestamp(float(epoch))


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
        speed = format_speed(speed_down)
        eta = format_eta(size_down, size_total, speed_down)
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
            ("Speed (down)", format_speed(int(transfer.get("speed_download", 0)))),
            ("Speed (up)", format_speed(int(transfer.get("speed_upload", 0)))),
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
                format_speed(int(p.get("speed_download", 0))),
                format_speed(int(p.get("speed_upload", 0))),
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


async def create_download(
    client: DsmClient,
    *,
    uri: str | None = None,
    torrent_file_path: str | None = None,
    destination: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> str:
    """Create one or more download tasks.

    Pass exactly one of:
    - ``uri``: comma-separated URIs (HTTP, FTP, magnet, etc.)
    - ``torrent_file_path``: local path to a .torrent or .nzb file (multipart upload)
    """
    if uri is None and torrent_file_path is None:
        error_response(
            ErrorCode.INVALID_PARAMETER,
            "Create download failed: must supply either `uri` or `torrent_file_path`.",
            retryable=False,
            valid=["uri", "torrent_file_path"],
        )
    if uri is not None and torrent_file_path is not None:
        error_response(
            ErrorCode.INVALID_PARAMETER,
            "Create download failed: supply exactly one of `uri` or `torrent_file_path`, not both.",
            retryable=False,
        )

    if torrent_file_path is not None:
        path = Path(torrent_file_path).expanduser()
        if not path.is_file():
            error_response(
                ErrorCode.NOT_FOUND,
                f"Create download failed: torrent file not found at {torrent_file_path!r}.",
                retryable=False,
                param="torrent_file_path",
                value=torrent_file_path,
            )
        try:
            data = await client.create_download_task_with_file(
                file_path=path,
                filename=path.name,
                destination=destination,
                username=username,
                password=password,
            )
        except SynologyError as e:
            synology_error_response(f"Create download ({path.name})", e)
        task_id = data.get("task_id", "—") if isinstance(data, dict) else "—"
        return f"Created download task {task_id} from file {path.name}."

    # URI path — standard GET
    params: dict[str, str] = {"uri": uri or ""}
    if destination is not None:
        params["destination"] = destination
    if username is not None:
        params["username"] = username
    if password is not None:
        params["password"] = password

    try:
        data = await client.request(
            "SYNO.DownloadStation.Task",
            "create",
            version=1,
            params=params,
        )
    except SynologyError as e:
        synology_error_response("Create download", e)

    task_id = data.get("task_id", "—") if isinstance(data, dict) else "—"
    n_uris = len((uri or "").split(","))
    return f"Created {n_uris} download task(s); first id: {task_id}."


async def delete_download(
    client: DsmClient,
    *,
    task_ids: list[str],
    delete_data: bool,
    force_complete: bool = False,
) -> str:
    """Delete one or more download tasks.

    ``delete_data`` must be explicitly set:
    - ``True``: call DSM Task.delete, which removes task records AND their
      downloaded files from disk. This is DSM v1's only supported deletion
      mode.
    - ``False``: REFUSED — DSM v1 Task.delete has no "remove task, keep files"
      mode. The flag is required to be explicit so the caller never assumes a
      "safe" delete that DSM doesn't actually support.

    ``force_complete`` marks errored tasks as complete before deletion.
    """
    if not task_ids:
        error_response(
            ErrorCode.INVALID_PARAMETER,
            "Delete download failed: task_ids list is empty.",
            retryable=False,
            param="task_ids",
            value=task_ids,
        )

    if not delete_data:
        error_response(
            ErrorCode.INVALID_PARAMETER,
            "Delete download failed: delete_data=False is not supported. "
            "DSM v1 Task.delete removes the task AND its files unconditionally. "
            "Pass delete_data=True to acknowledge the destructive side effect.",
            retryable=False,
            param="delete_data",
            value=False,
        )

    ids_joined = ",".join(task_ids)

    try:
        data = await client.request(
            "SYNO.DownloadStation.Task",
            "delete",
            version=1,
            params={
                "id": ids_joined,
                "force_complete": str(force_complete).lower(),
            },
        )
    except SynologyError as e:
        synology_error_response("Delete download", e)

    results = data if isinstance(data, list) else data.get("results", [])
    rows: list[list[str]] = []
    for r in results:
        err = r.get("error", 0)
        status = "ok" if err == 0 else f"error {err}"
        rows.append([r.get("id", "—"), status])

    return format_table(
        headers=["Task ID", "Result"],
        rows=rows,
        title=f"Delete download — {len(task_ids)} task(s), files removed",
    )


async def pause_download(
    client: DsmClient,
    *,
    task_ids: list[str],
) -> str:
    """Stub — replaced in Task 6."""
    raise NotImplementedError("pause_download is implemented in Task 6")


async def resume_download(
    client: DsmClient,
    *,
    task_ids: list[str],
) -> str:
    """Stub — replaced in Task 6."""
    raise NotImplementedError("resume_download is implemented in Task 6")


async def edit_download(
    client: DsmClient,
    *,
    task_ids: list[str],
    destination: str | None = None,
) -> str:
    """Stub — replaced in Task 7."""
    raise NotImplementedError("edit_download is implemented in Task 7")
