"""Download Station task tools: list_downloads, get_download_info.

Stub bodies — replaced by Task 3 (list_downloads) and Task 4 (get_download_info).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_synology.core.client import DsmClient


async def list_downloads(
    client: DsmClient,
    *,
    status_filter: str = "all",
    offset: int = 0,
    limit: int = 100,
) -> str:
    """Stub — replaced in Task 3."""
    raise NotImplementedError("list_downloads is implemented in Task 3")


async def get_download_info(
    client: DsmClient,
    *,
    task_id: str,
) -> str:
    """Stub — replaced in Task 4."""
    raise NotImplementedError("get_download_info is implemented in Task 4")
