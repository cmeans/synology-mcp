"""Download Station stats tool: get_download_stats."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mcp_synology.core.errors import SynologyError
from mcp_synology.core.formatting import (
    format_key_value,
    synology_error_response,
)
from mcp_synology.modules.downloadstation.helpers import format_speed

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp_synology.core.client import DsmClient


async def get_download_stats(client: DsmClient) -> str:
    """Get current throughput totals across the Download Station queue."""
    try:
        data = await client.request(
            "SYNO.DownloadStation.Statistic",
            "getinfo",
            version=1,
        )
    except SynologyError as e:
        synology_error_response("Get download stats", e)

    speed_down = int(data.get("speed_download", 0))
    speed_up = int(data.get("speed_upload", 0))

    pairs: list[tuple[str, str]] = [
        ("Download (total)", format_speed(speed_down)),
        ("Upload (total)", format_speed(speed_up)),
    ]

    # eMule fields are only present when the eMule service is enabled. Use
    # explicit key-presence checks rather than `or 0` so a real 0 reading
    # (eMule enabled but idle) is preserved and rendered.
    emule_down = data.get("emule_speed_download")
    emule_up = data.get("emule_speed_upload")
    if emule_down is not None or emule_up is not None:
        pairs.append(("Download (eMule)", format_speed(int(emule_down or 0))))
        pairs.append(("Upload (eMule)", format_speed(int(emule_up or 0))))

    return format_key_value(pairs, title="Download Station throughput")
