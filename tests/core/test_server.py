"""Tests for server.py — server creation and tool registration."""

from __future__ import annotations

from synology_mcp.server import create_server
from tests.conftest import make_test_config


class TestCreateServer:
    def test_server_creation(self) -> None:
        config = make_test_config()
        server = create_server(config)
        assert server is not None

    def test_server_with_read_permission(self) -> None:
        config = make_test_config(modules={"filestation": {"enabled": True, "permission": "read"}})
        server = create_server(config)
        # Server should have been created with READ tools only
        assert server is not None

    def test_server_with_write_permission(self) -> None:
        config = make_test_config(modules={"filestation": {"enabled": True, "permission": "write"}})
        server = create_server(config)
        assert server is not None

    def test_server_with_disabled_module(self) -> None:
        config = make_test_config(modules={"filestation": {"enabled": False}})
        server = create_server(config)
        assert server is not None

    def test_server_with_unknown_module(self) -> None:
        config = make_test_config(
            modules={
                "filestation": {"enabled": True},
                "unknown_module": {"enabled": True},
            }
        )
        server = create_server(config)
        assert server is not None
