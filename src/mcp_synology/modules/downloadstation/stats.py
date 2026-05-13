"""Download Station stats tool: get_download_stats."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mcp_synology.core.errors import SynologyError
from mcp_synology.core.formatting import (
    format_key_value,
    format_size,
    synology_error_response,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp_synology.core.client import DsmClient


def _speed_str(bytes_per_sec: int) -> str:
    if bytes_per_sec <= 0:
        return "—"
    return f"{format_size(bytes_per_sec)}/s"


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
        ("Download (total)", _speed_str(speed_down)),
        ("Upload (total)", _speed_str(speed_up)),
    ]

    # eMule fields are only present when the eMule service is enabled. Use
    # explicit key-presence checks rather than `or 0` so a real 0 reading
    # (eMule enabled but idle) is preserved and rendered.
    emule_down = data.get("emule_speed_download")
    emule_up = data.get("emule_speed_upload")
    if emule_down is not None or emule_up is not None:
        pairs.append(("Download (eMule)", _speed_str(int(emule_down or 0))))
        pairs.append(("Upload (eMule)", _speed_str(int(emule_up or 0))))

    return format_key_value(pairs, title="Download Station throughput")
