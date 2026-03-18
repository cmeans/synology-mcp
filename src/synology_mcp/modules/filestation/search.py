"""File Station search tool: search_files."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from synology_mcp.core.errors import SynologyError
from synology_mcp.core.formatting import format_error, format_size, format_table, format_timestamp
from synology_mcp.modules.filestation.helpers import (
    file_type_icon,
    matches_pattern,
    normalize_path,
    parse_human_size,
)

if TYPE_CHECKING:
    from synology_mcp.core.client import DsmClient


async def search_files(
    client: DsmClient,
    *,
    folder_path: str,
    pattern: str | None = None,
    extension: str | None = None,
    filetype: str = "all",
    size_from: str | int | None = None,
    size_to: str | int | None = None,
    mtime_from: str | None = None,
    mtime_to: str | None = None,
    exclude_pattern: str | None = None,
    recursive: bool = True,
    limit: int = 500,
    additional: list[str] | None = None,
    file_type_indicator: str = "emoji",
    timeout: float = 120.0,
    poll_interval: float = 1.0,
) -> str:
    """Search for files by name, type, size, or modification date."""
    if additional is None:
        additional = ["size", "time"]

    normalized = normalize_path(folder_path)

    # Start search
    start_params: dict[str, Any] = {
        "folder_path": normalized,
        "recursive": str(recursive).lower(),
    }
    if pattern:
        if pattern.startswith("*.") and "." not in pattern[2:]:
            # Pure extension pattern like "*.mkv" — use DSM's extension filter
            # instead of pattern, which doesn't support glob wildcards
            if not extension:
                extension = pattern[2:]
        else:
            # Name pattern — DSM treats this as a substring/keyword match
            start_params["pattern"] = pattern
    if extension:
        start_params["extension"] = extension
    if filetype != "all":
        start_params["filetype"] = filetype
    if size_from is not None:
        start_params["size_from"] = str(parse_human_size(size_from))
    if size_to is not None:
        start_params["size_to"] = str(parse_human_size(size_to))
    if mtime_from:
        start_params["mtime_from"] = mtime_from
    if mtime_to:
        start_params["mtime_to"] = mtime_to

    try:
        start_data = await client.request("SYNO.FileStation.Search", "start", params=start_params)
    except SynologyError as e:
        return format_error("Search files", str(e), e.suggestion)

    taskid = start_data.get("taskid", "")

    # Poll for results
    import asyncio
    import time

    start_time = time.monotonic()
    interval = poll_interval
    all_files: list[dict[str, Any]] = []
    finished = False

    while (time.monotonic() - start_time) < timeout:
        try:
            list_data = await client.request(
                "SYNO.FileStation.Search",
                "list",
                params={
                    "taskid": taskid,
                    "additional": '["' + '","'.join(additional) + '"]',
                    "limit": str(limit),
                    "offset": "0",
                },
            )
        except SynologyError as e:
            return format_error("Search files", str(e), e.suggestion)

        all_files = list_data.get("files", [])
        finished = list_data.get("finished", False)

        if finished:
            break

        await asyncio.sleep(interval)

    # Clean up task
    with contextlib.suppress(SynologyError):
        await client.request("SYNO.FileStation.Search", "stop", params={"taskid": taskid})
    with contextlib.suppress(SynologyError):
        await client.request("SYNO.FileStation.Search", "clean", params={"taskid": taskid})

    # Apply client-side exclude_pattern
    excluded_count = 0
    if exclude_pattern:
        original_count = len(all_files)
        all_files = [
            f for f in all_files if not matches_pattern(f.get("name", ""), exclude_pattern)
        ]
        excluded_count = original_count - len(all_files)

    if not all_files:
        title_parts = [f"Search results in {normalized}"]
        if pattern:
            title_parts.append(f"(pattern: {pattern})")
        title = " ".join(title_parts)
        msg = f"{title}\n\n0 results found."
        if not finished:
            msg += " (search timed out — try narrowing the scope)"
        else:
            msg += " Try broadening the pattern or checking the folder path."
        return msg

    # Build results table
    title_parts = [f"Search results in {normalized}"]
    if pattern:
        title_parts.append(f"(pattern: {pattern}")
        if exclude_pattern:
            title_parts[-1] += f", excluding: {exclude_pattern}"
        title_parts[-1] += ")"

    title = " ".join(title_parts)

    headers = ["Type", "Name", "Path", "Size", "Modified"]
    rows: list[list[str]] = []
    for f in all_files:
        is_dir = f.get("isdir", False)
        name = f.get("name", "")
        icon = file_type_icon(is_dir, name, style=file_type_indicator)
        fpath = f.get("path", "")
        # Show parent directory
        parent = "/".join(fpath.split("/")[:-1]) + "/" if "/" in fpath else ""

        add_info = f.get("additional", {})
        size = "—" if is_dir else format_size(add_info.get("size", 0))
        mtime = add_info.get("time", {}).get("mtime", 0)
        modified = format_timestamp(mtime) if mtime else "—"

        rows.append([icon, name, parent, size, modified])

    result = format_table(headers=headers, rows=rows, title=title)
    result += f"\n\n{len(all_files)} results found"
    if excluded_count > 0:
        result += f" ({excluded_count} excluded by filter)"
    result += "."
    if not finished:
        result += " (search timed out — partial results shown)"

    return result
