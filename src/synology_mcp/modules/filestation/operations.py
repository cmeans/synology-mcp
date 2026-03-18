"""File Station operations: create_folder, rename, copy, move, delete, restore."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from synology_mcp.core.errors import SynologyError
from synology_mcp.core.formatting import format_error, format_status
from synology_mcp.modules.filestation.helpers import (
    escape_multi_path,
    file_type_icon,
    normalize_path,
)

if TYPE_CHECKING:
    from synology_mcp.core.client import DsmClient


async def create_folder(
    client: DsmClient,
    *,
    paths: list[str],
    force_parent: bool = True,
) -> str:
    """Create one or more new folders."""
    normalized = [normalize_path(p) for p in paths]

    # Build folder_path and name params from the paths
    folder_paths: list[str] = []
    names: list[str] = []
    for p in normalized:
        parent = "/".join(p.split("/")[:-1]) or "/"
        name = p.split("/")[-1]
        folder_paths.append(parent)
        names.append(name)

    try:
        data = await client.request(
            "SYNO.FileStation.CreateFolder",
            "create",
            params={
                "folder_path": escape_multi_path(folder_paths),
                "name": escape_multi_path(names),
                "force_parent": str(force_parent).lower(),
            },
        )
    except SynologyError as e:
        return format_error("Create folder", str(e), e.suggestion)

    folders = data.get("folders", [])
    lines = [format_status(f"Created {len(folders)} folder(s):")]
    for f in folders:
        path = f.get("path", "")
        lines.append(f"  \U0001f4c1 {path}")

    return "\n".join(lines)


async def rename(
    client: DsmClient,
    *,
    path: str,
    new_name: str,
) -> str:
    """Rename a file or folder."""
    normalized = normalize_path(path)

    # Validate new_name is just a name, not a path
    if "/" in new_name:
        return format_error(
            "Rename",
            "new_name should be just a filename, not a path.",
            "Use move_files to relocate files to a different directory.",
        )

    try:
        data = await client.request(
            "SYNO.FileStation.Rename",
            "rename",
            params={
                "path": normalized,
                "name": new_name,
            },
        )
    except SynologyError as e:
        return format_error("Rename", str(e), e.suggestion)

    files = data.get("files", [])
    if files:
        new_path = files[0].get("path", "")
        old_dir = "/".join(normalized.split("/")[:-1])
        old_name = normalized.split("/")[-1]
        return format_status(f"Renamed:\n  {old_dir}/{old_name} \u2192 {new_path}")

    return format_status(f"Renamed {normalized} to {new_name}")


async def copy_files(
    client: DsmClient,
    *,
    paths: list[str],
    dest_folder: str,
    overwrite: bool = False,
    file_type_indicator: str = "emoji",
    timeout: float = 120.0,
) -> str:
    """Copy files or folders to a destination."""
    return await _copy_move(
        client,
        paths=paths,
        dest_folder=dest_folder,
        overwrite=overwrite,
        remove_src=False,
        operation="Copy",
        file_type_indicator=file_type_indicator,
        timeout=timeout,
    )


async def move_files(
    client: DsmClient,
    *,
    paths: list[str],
    dest_folder: str,
    overwrite: bool = False,
    file_type_indicator: str = "emoji",
    timeout: float = 120.0,
) -> str:
    """Move files or folders to a new location."""
    return await _copy_move(
        client,
        paths=paths,
        dest_folder=dest_folder,
        overwrite=overwrite,
        remove_src=True,
        operation="Move",
        file_type_indicator=file_type_indicator,
        timeout=timeout,
    )


async def _copy_move(
    client: DsmClient,
    *,
    paths: list[str],
    dest_folder: str,
    overwrite: bool,
    remove_src: bool,
    operation: str,
    file_type_indicator: str = "emoji",
    timeout: float = 120.0,
) -> str:
    """Shared implementation for copy and move operations."""
    normalized = [normalize_path(p) for p in paths]
    dest = normalize_path(dest_folder)
    path_param = escape_multi_path(normalized)

    try:
        start_data = await client.request(
            "SYNO.FileStation.CopyMove",
            "start",
            params={
                "path": path_param,
                "dest_folder_path": dest,
                "overwrite": str(overwrite).lower(),
                "remove_src": str(remove_src).lower(),
            },
        )
    except SynologyError as e:
        return format_error(f"{operation} files", str(e), e.suggestion)

    taskid = start_data.get("taskid", "")

    # Poll for completion
    elapsed = 0.0
    interval = 0.5

    while elapsed < timeout:
        try:
            status = await client.request(
                "SYNO.FileStation.CopyMove",
                "status",
                params={"taskid": taskid},
            )
        except SynologyError as e:
            return format_error(f"{operation} files", str(e), e.suggestion)

        if status.get("finished", False):
            break

        await asyncio.sleep(interval)
        elapsed += interval
    else:
        # Timeout
        with contextlib.suppress(SynologyError):
            await client.request("SYNO.FileStation.CopyMove", "stop", params={"taskid": taskid})
        return format_error(
            f"{operation} files",
            f"Timed out after {timeout}s.",
            "The operation may still be running on the NAS.",
        )

    # Build response
    verb = "Copied" if not remove_src else "Moved"
    lines = [format_status(f"{verb} {len(normalized)} item(s) to {dest}/:")]
    for p in normalized:
        name = p.split("/")[-1]
        # Best guess without API isdir flag: names with extensions are files
        is_dir = "." not in name or name.startswith(".")
        icon = file_type_icon(is_dir, name, style=file_type_indicator)
        lines.append(f"  {icon} {name}")

    if remove_src:
        # Extract source directories
        src_dirs = {"/".join(p.split("/")[:-1]) for p in normalized}
        for d in sorted(src_dirs):
            lines.append(f"\nSource files have been removed from {d}/.")

    return "\n".join(lines)


async def delete_files(
    client: DsmClient,
    *,
    paths: list[str],
    recursive: bool = True,
    file_type_indicator: str = "emoji",
    recycle_bin_status: dict[str, bool] | None = None,
    timeout: float = 120.0,
) -> str:
    """Delete files or folders."""
    normalized = [normalize_path(p) for p in paths]
    path_param = escape_multi_path(normalized)

    try:
        start_data = await client.request(
            "SYNO.FileStation.Delete",
            "start",
            params={
                "path": path_param,
                "recursive": str(recursive).lower(),
            },
        )
    except SynologyError as e:
        return format_error("Delete files", str(e), e.suggestion)

    taskid = start_data.get("taskid", "")

    # Poll for completion
    elapsed = 0.0
    interval = 0.5

    while elapsed < timeout:
        try:
            status = await client.request(
                "SYNO.FileStation.Delete",
                "status",
                params={"taskid": taskid},
            )
        except SynologyError as e:
            return format_error("Delete files", str(e), e.suggestion)

        if status.get("finished", False):
            break

        await asyncio.sleep(interval)
        elapsed += interval
    else:
        with contextlib.suppress(SynologyError):
            await client.request("SYNO.FileStation.Delete", "stop", params={"taskid": taskid})
        return format_error(
            "Delete files",
            f"Timed out after {timeout}s.",
            "The operation may still be running on the NAS.",
        )

    # Determine recycle bin status per share
    shares_with_recycle: set[str] = set()
    shares_without_recycle: set[str] = set()
    for p in normalized:
        parts = p.split("/")
        share_name = parts[1] if len(parts) > 1 else ""
        if recycle_bin_status and share_name in recycle_bin_status:
            if recycle_bin_status[share_name]:
                shares_with_recycle.add(share_name)
            else:
                shares_without_recycle.add(share_name)
        else:
            shares_with_recycle.add(share_name)  # Assume recycle bin by default

    has_recycle = bool(shares_with_recycle)
    verb = "Deleted" if has_recycle else "Permanently deleted"

    lines = [format_status(f"{verb} {len(normalized)} item(s):")]
    for p in normalized:
        name = p.split("/")[-1]
        # Best guess without API isdir flag: names with extensions are files
        is_dir = "." not in name or name.startswith(".")
        icon = file_type_icon(is_dir, name, style=file_type_indicator)
        lines.append(f"  {icon} {p}")

    if shares_with_recycle:
        for share in sorted(shares_with_recycle):
            lines.append(
                f"\nRecycle bin is enabled on /{share} \u2014 "
                f"files can be recovered with list_recycle_bin and restore_from_recycle_bin."
            )
    if shares_without_recycle:
        for share in sorted(shares_without_recycle):
            lines.append(
                f"\n\u26a0 Recycle bin is NOT enabled on /{share} \u2014 "
                f"these files cannot be recovered."
            )

    return "\n".join(lines)


async def restore_from_recycle_bin(
    client: DsmClient,
    *,
    share: str,
    paths: list[str],
    dest_folder: str | None = None,
    overwrite: bool = False,
    file_type_indicator: str = "emoji",
    timeout: float = 120.0,
) -> str:
    """Restore files from a shared folder's recycle bin."""
    share_name = share.strip("/").split("/")[0]

    # Normalize recycle bin paths
    full_paths: list[str] = []
    restore_destinations: list[str] = []

    for p in paths:
        p = p.strip()
        # Ensure the path is within #recycle
        if f"/{share_name}/#recycle" in p:
            full_paths.append(normalize_path(p))
        elif p.startswith("#recycle"):
            full_paths.append(normalize_path(f"/{share_name}/{p}"))
        else:
            full_paths.append(normalize_path(f"/{share_name}/#recycle/{p}"))

        # Infer original path by stripping #recycle
        if dest_folder:
            restore_destinations.append(dest_folder)
        else:
            # /video/#recycle/Shows/Ep1.mkv -> /video/Shows/
            original = full_paths[-1].replace(f"/{share_name}/#recycle", f"/{share_name}")
            restore_destinations.append("/".join(original.split("/")[:-1]) or f"/{share_name}")

    # Use the first destination (or provided dest_folder)
    actual_dest = dest_folder or restore_destinations[0]
    if dest_folder is None and len(set(restore_destinations)) > 1:
        # Multiple different destinations — move each one separately
        results: list[str] = []
        for fp, dest in zip(full_paths, restore_destinations, strict=False):
            r = await _copy_move(
                client,
                paths=[fp],
                dest_folder=dest,
                overwrite=overwrite,
                remove_src=True,
                operation="Restore",
                file_type_indicator=file_type_indicator,
                timeout=timeout,
            )
            results.append(r)
        return "\n".join(results)

    result = await _copy_move(
        client,
        paths=full_paths,
        dest_folder=actual_dest,
        overwrite=overwrite,
        remove_src=True,
        operation="Restore",
        file_type_indicator=file_type_indicator,
        timeout=timeout,
    )

    # Rephrase from "Moved" to "Restored"
    return result.replace("[+] Moved", f"[+] Restored from /{share_name} recycle bin:")
