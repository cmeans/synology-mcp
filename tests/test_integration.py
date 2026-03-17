"""Integration tests — requires a real Synology NAS.

Run with: uv run pytest -m integration
Requires: tests/integration_config.yaml (see integration_config.yaml.example)
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
class TestIntegration:
    """Scaffold for real NAS tests. Requires integration_config.yaml."""

    async def test_connect_and_list_shares(self) -> None:
        """Connect to real NAS and list shares."""
        pytest.skip("Integration test — requires real NAS configuration.")

    async def test_search_files(self) -> None:
        """Search files on real NAS."""
        pytest.skip("Integration test — requires real NAS configuration.")

    async def test_get_file_info(self) -> None:
        """Get file info from real NAS."""
        pytest.skip("Integration test — requires real NAS configuration.")
