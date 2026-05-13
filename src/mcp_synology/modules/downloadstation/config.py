"""Download Station config tools: get_download_config, get_schedule.

Stub bodies — replaced by Task 6 (get_download_config) and Task 7 (get_schedule).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_synology.core.client import DsmClient


async def get_download_config(client: DsmClient) -> str:
    """Stub — replaced in Task 6."""
    raise NotImplementedError("get_download_config is implemented in Task 6")


async def get_schedule(client: DsmClient) -> str:
    """Stub — replaced in Task 7."""
    raise NotImplementedError("get_schedule is implemented in Task 7")
