"""Download Station config tools: get_download_config, get_schedule."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mcp_synology.core.errors import SynologyError
from mcp_synology.core.formatting import (
    format_key_value,
    synology_error_response,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from mcp_synology.core.client import DsmClient


def _kbps_str(kbps: int) -> str:
    """Format a KB/s rate; 0 means unlimited per DSM convention."""
    if kbps <= 0:
        return "unlimited"
    return f"{kbps} KB/s"


def _bool_str(value: bool | None) -> str:
    if value is None:
        return "—"
    return "yes" if value else "no"


async def get_download_config(client: DsmClient) -> str:
    """Get Download Station global configuration."""
    try:
        data = await client.request(
            "SYNO.DownloadStation.Info",
            "getconfig",
            version=1,
        )
    except SynologyError as e:
        synology_error_response("Get download config", e)

    pairs: list[tuple[str, str]] = [
        ("Default destination", str(data.get("default_destination", "—"))),
        ("BT max download", _kbps_str(int(data.get("bt_max_download", 0)))),
        ("BT max upload", _kbps_str(int(data.get("bt_max_upload", 0)))),
        ("HTTP max download", _kbps_str(int(data.get("http_max_download", 0)))),
        ("FTP max download", _kbps_str(int(data.get("ftp_max_download", 0)))),
        ("NZB max download", _kbps_str(int(data.get("nzb_max_download", 0)))),
        ("eMule enabled", _bool_str(data.get("emule_enabled"))),
        ("eMule max download", _kbps_str(int(data.get("emule_max_download", 0)))),
        ("eMule max upload", _kbps_str(int(data.get("emule_max_upload", 0)))),
        ("Auto-unzip enabled", _bool_str(data.get("unzip_service_enabled"))),
    ]

    return format_key_value(pairs, title="Download Station configuration")


async def get_schedule(client: DsmClient) -> str:
    """Stub — replaced in Task 7."""
    raise NotImplementedError("get_schedule is implemented in Task 7")
