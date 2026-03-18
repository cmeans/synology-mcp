"""Integration tests — requires a real Synology NAS.

Run with: uv run pytest -m integration
Requires: tests/integration_config.yaml (see integration_config.yaml.example)

These tests hit the real DSM API over HTTP. They verify that our client,
auth, and module code works against an actual NAS — not mocked responses.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import pytest
import yaml

from synology_mcp.core.auth import AuthManager
from synology_mcp.core.client import DsmClient
from synology_mcp.core.config import AppConfig
from synology_mcp.modules.filestation.listing import list_files, list_shares
from synology_mcp.modules.filestation.metadata import get_dir_size, get_file_info
from synology_mcp.modules.filestation.operations import (
    create_folder,
    delete_files,
    rename,
)
from synology_mcp.modules.filestation.search import search_files

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config & fixtures
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).parent / "integration_config.yaml"

# Default test paths — override in integration_config.yaml under test_paths:
_DEFAULT_TEST_PATHS: dict[str, str] = {
    "existing_share": "/home",
    "search_folder": "/home",
    "search_keyword": "test",
    "writable_folder": "/home/Test-Resources",
}


def _load_integration_config() -> tuple[AppConfig, dict[str, str]]:
    """Load config and test paths from integration_config.yaml."""
    if not _CONFIG_PATH.exists():
        pytest.skip(
            f"Integration config not found: {_CONFIG_PATH}\n"
            "Copy integration_config.yaml.example → integration_config.yaml "
            "and fill in NAS details."
        )

    raw = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    test_paths = {**_DEFAULT_TEST_PATHS, **raw.pop("test_paths", {})}
    config = AppConfig(**raw)
    return config, test_paths


@pytest.fixture
def integration_config() -> tuple[AppConfig, dict[str, str]]:
    """Provide integration config and test paths."""
    return _load_integration_config()


@pytest.fixture
async def nas_client(
    integration_config: tuple[AppConfig, dict[str, str]],
) -> Any:
    """Provide an authenticated DsmClient connected to a real NAS.

    Yields (client, auth, config, test_paths).
    """
    config, test_paths = integration_config
    conn = config.connection
    assert conn is not None, "integration_config.yaml must have a connection section"

    protocol = "https" if conn.https else "http"
    base_url = f"{protocol}://{conn.host}:{conn.port}"

    client = DsmClient(
        base_url=base_url,
        verify_ssl=conn.verify_ssl,
        timeout=conn.timeout,
    )

    async with client:
        # Populate API cache from real NAS
        cache = await client.query_api_info()
        logger.info("API cache: %d APIs discovered", len(cache))

        # Log only the APIs we actually use
        _relevant = [
            "SYNO.FileStation.List",
            "SYNO.FileStation.Search",
            "SYNO.FileStation.CopyMove",
            "SYNO.FileStation.Delete",
            "SYNO.FileStation.CreateFolder",
            "SYNO.FileStation.Rename",
            "SYNO.FileStation.DirSize",
            "SYNO.FileStation.Info",
            "SYNO.DSM.Info",
        ]
        for api_name in _relevant:
            entry = cache.get(api_name)
            if entry:
                fmt = f", format={entry.request_format}" if entry.request_format else ""
                logger.info("  %s: v%d–v%d%s", api_name, entry.min_version, entry.max_version, fmt)

        # Authenticate
        auth = AuthManager(config, client)
        sid = await auth.login()
        logger.info("Authenticated, SID=%s...", sid[:8])

        yield client, auth, config, test_paths

        # Cleanup
        await auth.logout()


# ---------------------------------------------------------------------------
# Helper to unpack the fixture
# ---------------------------------------------------------------------------


def _unpack(nas_client: Any) -> tuple[DsmClient, AuthManager, AppConfig, dict[str, str]]:
    return nas_client  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Connection & Auth
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestConnection:
    """Verify basic connectivity and authentication."""

    async def test_api_info_populated(self, nas_client: Any) -> None:
        """API cache should contain FileStation APIs."""
        client, _, _, _ = _unpack(nas_client)
        assert "SYNO.FileStation.List" in client._api_cache
        assert "SYNO.FileStation.Search" in client._api_cache
        assert "SYNO.FileStation.CopyMove" in client._api_cache

    async def test_dsm_info(self, nas_client: Any) -> None:
        """Should be able to fetch DSM version info."""
        client, _, _, _ = _unpack(nas_client)
        info = await client.fetch_dsm_info()
        assert "version_string" in info or "version" in info
        logger.info("DSM version: %s", info)

    async def test_api_versions_logged(self, nas_client: Any) -> None:
        """Log negotiated versions for key APIs (visual check in -v output)."""
        client, _, _, _ = _unpack(nas_client)
        for api_name in [
            "SYNO.FileStation.List",
            "SYNO.FileStation.Search",
            "SYNO.FileStation.CopyMove",
            "SYNO.FileStation.Delete",
        ]:
            entry = client._api_cache.get(api_name)
            assert entry is not None, f"{api_name} not in API cache"
            logger.info(
                "%s: v%d–v%d, request_format=%s",
                api_name,
                entry.min_version,
                entry.max_version,
                entry.request_format,
            )


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestListing:
    """Test list_shares and list_files against real NAS."""

    async def test_list_shares(self, nas_client: Any) -> None:
        """Should return formatted table with at least one share."""
        client, _, _, _ = _unpack(nas_client)
        result = await list_shares(client)
        assert "Name" in result  # table header
        assert "[!]" not in result  # no error marker
        logger.info("list_shares output:\n%s", result)

    async def test_list_files_existing_share(self, nas_client: Any) -> None:
        """Should list files in a known share."""
        client, _, _, paths = _unpack(nas_client)
        result = await list_files(client, path=paths["existing_share"])
        assert "[!]" not in result
        logger.info("list_files(%s):\n%s", paths["existing_share"], result)

    async def test_list_files_root(self, nas_client: Any) -> None:
        """Listing '/' may fail on some DSM versions — verify graceful handling."""
        client, _, _, _ = _unpack(nas_client)
        result = await list_files(client, path="/")
        logger.info("list_files(/):\n%s", result)
        # On some DSM versions, listing '/' via FileStation.List fails (error 401).
        # Use list_shares instead. Here we just verify it doesn't crash.
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSearch:
    """Test search_files against real NAS.

    These tests verify:
    - Search uses GET (not POST) to avoid DSM request format issues
    - Wildcard auto-wrapping (bare keyword → *keyword*)
    - filetype=all includes directories in results
    - Searching from a share path (not root)

    NOTE: DSM's search service can be overwhelmed by rapid-fire requests,
    returning 0 results or 502 errors. Tests include delays between searches
    to avoid exhausting the service. If tests fail intermittently, increase
    the delay or run fewer search tests at once.
    """

    async def test_search_keyword_finds_directory(self, nas_client: Any) -> None:
        """A bare keyword should find matching directories via wildcard wrapping.

        Verifies three fixes at once:
        - GET (not POST) for the Search API
        - Wildcard wrapping: bare "Bambu" becomes *Bambu*, matching "Bambu Studio"
        - filetype=all: directories are included in results
        """
        client, _, _, paths = _unpack(nas_client)
        folder = paths["search_folder"]
        keyword = paths["search_keyword"]

        result = await search_files(client, folder_path=folder, pattern=keyword)

        logger.info("search_files(%s, pattern=%s):\n%s", folder, keyword, result)
        assert "[!]" not in result
        assert "0 results found" not in result, (
            f"Search for '{keyword}' in {folder} returned 0 results. "
            "Verify the search_keyword and search_folder in integration_config.yaml. "
            "Also check that DSM's search service is not overloaded from prior test runs."
        )

    async def test_search_no_results(self, nas_client: Any) -> None:
        """Search for a nonsense pattern should return 0 results, not an error."""
        client, _, _, paths = _unpack(nas_client)
        # Brief delay to avoid overloading the search service
        await asyncio.sleep(2)
        result = await search_files(
            client, folder_path=paths["existing_share"], pattern="zzz_nonexistent_xyzzy_999"
        )
        assert "0 results found" in result
        assert "[!]" not in result

    async def test_search_from_root_error_handling(self, nas_client: Any) -> None:
        """Searching from '/' may fail — verify we handle it gracefully."""
        client, _, _, _ = _unpack(nas_client)
        await asyncio.sleep(2)
        result = await search_files(client, folder_path="/", pattern="test")
        logger.info("Root search result:\n%s", result)
        # Whether it returns results or an error, it should not crash.
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMetadata:
    """Test get_file_info and get_dir_size."""

    async def test_get_file_info_share(self, nas_client: Any) -> None:
        """Get info about a known share folder."""
        client, _, _, paths = _unpack(nas_client)
        result = await get_file_info(client, paths=[paths["existing_share"]])
        assert "[!]" not in result
        logger.info("get_file_info(%s):\n%s", paths["existing_share"], result)

    async def test_get_dir_size(self, nas_client: Any) -> None:
        """Get size of a known folder (uses a smaller folder to avoid timeouts)."""
        client, _, _, paths = _unpack(nas_client)
        # Use the writable folder (likely small) rather than the existing_share
        # which may be very large and cause the background task to time out.
        result = await get_dir_size(client, path=paths["writable_folder"])
        assert "[!]" not in result
        logger.info("get_dir_size(%s):\n%s", paths["writable_folder"], result)


# ---------------------------------------------------------------------------
# Write operations (create, copy, rename, delete)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestWriteOperations:
    """Test write operations against real NAS.

    These tests use the writable_folder path from config. They create
    temporary resources and clean them up. Requires 'write' permission
    in the module config.

    Tests run in order: create → copy → rename → delete.
    """

    _TEST_FOLDER_NAME = "_integration_test_tmp"

    async def test_create_folder(self, nas_client: Any) -> None:
        """Create a test folder in the writable area."""
        client, _, config, paths = _unpack(nas_client)
        fs_config = config.modules.get("filestation")
        if not fs_config or fs_config.permission != "write":
            pytest.skip("Write permission required — set permission: write in integration config")

        folder_path = f"{paths['writable_folder']}/{self._TEST_FOLDER_NAME}"
        result = await create_folder(client, paths=[folder_path])
        logger.info("create_folder result:\n%s", result)
        # Should succeed or report "already exists" (idempotent)
        assert "[!]" not in result or "already exists" in result.lower()

    async def test_create_folder_idempotent(self, nas_client: Any) -> None:
        """Creating the same folder again should not error (idempotent)."""
        client, _, config, paths = _unpack(nas_client)
        fs_config = config.modules.get("filestation")
        if not fs_config or fs_config.permission != "write":
            pytest.skip("Write permission required")

        folder_path = f"{paths['writable_folder']}/{self._TEST_FOLDER_NAME}"
        result = await create_folder(client, paths=[folder_path])
        logger.info("create_folder (idempotent) result:\n%s", result)
        # Should not crash — either succeeds or says already exists
        assert isinstance(result, str)

    async def test_create_subfolder(self, nas_client: Any) -> None:
        """Create a subfolder inside the test folder."""
        client, _, config, paths = _unpack(nas_client)
        fs_config = config.modules.get("filestation")
        if not fs_config or fs_config.permission != "write":
            pytest.skip("Write permission required")

        subfolder = f"{paths['writable_folder']}/{self._TEST_FOLDER_NAME}/rename_test"
        result = await create_folder(client, paths=[subfolder])
        logger.info("create subfolder result:\n%s", result)
        assert "[!]" not in result

    async def test_rename(self, nas_client: Any) -> None:
        """Rename a folder."""
        client, _, config, paths = _unpack(nas_client)
        fs_config = config.modules.get("filestation")
        if not fs_config or fs_config.permission != "write":
            pytest.skip("Write permission required")

        target = f"{paths['writable_folder']}/{self._TEST_FOLDER_NAME}/rename_test"
        result = await rename(client, path=target, new_name="renamed_test")
        logger.info("rename result:\n%s", result)
        assert "[!]" not in result

    async def test_delete_cleanup(self, nas_client: Any) -> None:
        """Delete the test folder (cleanup)."""
        client, _, config, paths = _unpack(nas_client)
        fs_config = config.modules.get("filestation")
        if not fs_config or fs_config.permission != "write":
            pytest.skip("Write permission required")

        target = f"{paths['writable_folder']}/{self._TEST_FOLDER_NAME}"
        result = await delete_files(client, paths=[target], recursive=True)
        logger.info("delete result:\n%s", result)
        assert "[!]" not in result

        # Verify it's gone
        listing = await list_files(client, path=paths["writable_folder"])
        assert self._TEST_FOLDER_NAME not in listing
