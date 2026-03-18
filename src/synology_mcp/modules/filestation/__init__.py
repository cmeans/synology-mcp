"""File Station module: MODULE_INFO, register(), FileStationSettings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from synology_mcp.modules import (
    ApiRequirement,
    ModuleInfo,
    PermissionTier,
    ToolInfo,
)


class FileStationSettings(BaseModel):
    """File Station module settings."""

    hide_recycle_in_listings: bool = False
    file_type_indicator: Literal["emoji", "text"] = "emoji"
    async_timeout: int = Field(default=120, ge=10, le=3600)
    search_timeout: int | None = Field(default=None, ge=10, le=3600)
    copy_move_timeout: int | None = Field(default=None, ge=10, le=3600)
    delete_timeout: int | None = Field(default=None, ge=10, le=3600)
    dir_size_timeout: int | None = Field(default=None, ge=10, le=3600)
    search_poll_interval: float = Field(default=1.0, ge=0.5, le=10.0)


MODULE_INFO = ModuleInfo(
    name="filestation",
    description="Manage files and folders on the Synology NAS via File Station",
    required_apis=[
        ApiRequirement(api_name="SYNO.FileStation.Info", min_version=1),
        ApiRequirement(api_name="SYNO.FileStation.List", min_version=1),
        ApiRequirement(api_name="SYNO.FileStation.Search", min_version=1),
        ApiRequirement(api_name="SYNO.FileStation.DirSize", min_version=1),
        ApiRequirement(api_name="SYNO.FileStation.CreateFolder", min_version=1),
        ApiRequirement(api_name="SYNO.FileStation.Rename", min_version=1),
        ApiRequirement(api_name="SYNO.FileStation.CopyMove", min_version=1),
        ApiRequirement(api_name="SYNO.FileStation.Delete", min_version=1),
    ],
    tools=[
        # READ tools (6)
        ToolInfo(
            name="list_shares",
            description=(
                "List all shared folders on the NAS. This is the starting point for "
                "file navigation — call this first to discover available paths."
            ),
            permission_tier=PermissionTier.READ,
        ),
        ToolInfo(
            name="list_files",
            description=(
                "List files and folders in a directory. Supports glob pattern filtering, "
                "file type filtering, sorting, and pagination."
            ),
            permission_tier=PermissionTier.READ,
        ),
        ToolInfo(
            name="list_recycle_bin",
            description=(
                "List the contents of a shared folder's recycle bin. Shows recently "
                "deleted files that can be restored."
            ),
            permission_tier=PermissionTier.READ,
        ),
        ToolInfo(
            name="search_files",
            description=(
                "Search for files by name pattern, extension, size range, or modification "
                'date. Supports glob patterns and human-readable sizes like "500MB".'
            ),
            permission_tier=PermissionTier.READ,
        ),
        ToolInfo(
            name="get_file_info",
            description=(
                "Get detailed metadata for specific files or folders: size, owner, "
                "timestamps, permissions, and real path."
            ),
            permission_tier=PermissionTier.READ,
        ),
        ToolInfo(
            name="get_dir_size",
            description=(
                "Calculate the total size of a directory, including all files and "
                "subdirectories. Returns total size, file count, and directory count."
            ),
            permission_tier=PermissionTier.READ,
        ),
        # WRITE tools (6)
        ToolInfo(
            name="create_folder",
            description=(
                "Create one or more new folders. Creates parent directories automatically "
                "by default. Idempotent — creating an existing folder succeeds."
            ),
            permission_tier=PermissionTier.WRITE,
        ),
        ToolInfo(
            name="rename",
            description=(
                "Rename a file or folder. Provide the full current path and the new name "
                "(just the name, not a full path)."
            ),
            permission_tier=PermissionTier.WRITE,
        ),
        ToolInfo(
            name="copy_files",
            description=(
                "Copy files or folders to a destination folder. Source files remain in "
                "place. Set overwrite=true to replace existing files."
            ),
            permission_tier=PermissionTier.WRITE,
        ),
        ToolInfo(
            name="move_files",
            description=(
                "Move files or folders to a new location. Source files are REMOVED after "
                "transfer. Set overwrite=true to replace existing files."
            ),
            permission_tier=PermissionTier.WRITE,
        ),
        ToolInfo(
            name="delete_files",
            description=(
                "Delete files or folders. If the share has a recycle bin, files can be "
                "recovered. Otherwise deletion is permanent."
            ),
            permission_tier=PermissionTier.WRITE,
        ),
        ToolInfo(
            name="restore_from_recycle_bin",
            description=(
                "Restore deleted files from a shared folder's recycle bin to their "
                "original location or a specified destination."
            ),
            permission_tier=PermissionTier.WRITE,
        ),
    ],
    settings_schema=FileStationSettings,
)
