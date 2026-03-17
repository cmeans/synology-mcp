"""Tests for cli.py — CLI subcommands via click CliRunner."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path

from click.testing import CliRunner

from synology_mcp.cli import main


class TestCli:
    def test_version(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "synology-mcp" in result.output

    def test_serve_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.output

    def test_setup_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["setup", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.output
        assert "--list" in result.output

    def test_check_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["check", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.output

    def test_serve_missing_config(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--config", "/nonexistent/config.yaml"])
        assert result.exit_code != 0

    def test_short_config_flag_serve(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "-c", "/nonexistent/config.yaml"])
        assert result.exit_code != 0

    def test_short_config_flag_check(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["check", "-c", "/nonexistent/config.yaml"])
        assert result.exit_code != 0


class TestSetupList:
    def test_list_no_configs(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch("synology_mcp.cli._CONFIG_DIR", tmp_path / "nonexistent"):
            result = runner.invoke(main, ["setup", "--list"])
        assert result.exit_code == 0
        assert "No configurations found" in result.output

    def test_list_with_configs(self, tmp_path: Path) -> None:
        config_file = tmp_path / "my-nas.yaml"
        config_file.write_text(
            "schema_version: 1\n"
            "instance_id: my-nas\n"
            "alias: HomeNAS\n"
            "connection:\n"
            "  host: 192.168.1.100\n"
            "modules:\n"
            "  filestation:\n"
            "    enabled: true\n"
        )
        runner = CliRunner()
        with patch("synology_mcp.cli._CONFIG_DIR", tmp_path):
            result = runner.invoke(main, ["setup", "--list"])
        assert result.exit_code == 0
        assert "my-nas.yaml" in result.output
        assert "HomeNAS" in result.output
        assert "192.168.1.100" in result.output

    def test_list_short_flag(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch("synology_mcp.cli._CONFIG_DIR", tmp_path / "nonexistent"):
            result = runner.invoke(main, ["setup", "-l"])
        assert result.exit_code == 0
        assert "No configurations found" in result.output


class TestSetupInteractive:
    def test_interactive_setup_creates_config(self, tmp_path: Path) -> None:
        """When no config file exists, interactive mode prompts and writes a file."""
        runner = CliRunner()
        config_dir = tmp_path / "config"

        # Clear any SYNOLOGY_ env vars to ensure clean state
        clean_env: dict[str, str] = {
            k: v for k, v in os.environ.items() if not k.startswith("SYNOLOGY_")
        }

        connect_result: dict[str, Any] = {"success": True, "hostname": "MyNAS"}

        # Input order: host, https(n), permission(read), alias(""),
        # username, password, hostname-confirm(y)
        with (
            patch("synology_mcp.cli._CONFIG_DIR", config_dir),
            patch("synology_mcp.core.config.discover_config_path", side_effect=FileNotFoundError),
            patch("synology_mcp.cli._store_keyring", return_value=True),
            patch("synology_mcp.cli.asyncio.run", return_value=connect_result),
            patch.dict(os.environ, clean_env, clear=True),
        ):
            result = runner.invoke(
                main,
                ["setup"],
                input="192.168.1.50\nn\nread\n\nadmin\npassword\ny\n",
            )

        assert "Let's create one" in result.output
        assert result.exit_code == 0
        # Config file should have been written
        assert (config_dir / "192-168-1-50.yaml").exists()

    def test_interactive_setup_aborts_on_overwrite_decline(self, tmp_path: Path) -> None:
        """If config file exists and user declines overwrite, abort."""
        runner = CliRunner()
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "192-168-1-50.yaml").write_text("old\n")

        clean_env: dict[str, str] = {
            k: v for k, v in os.environ.items() if not k.startswith("SYNOLOGY_")
        }

        connect_result: dict[str, Any] = {"success": True}

        with (
            patch("synology_mcp.cli._CONFIG_DIR", config_dir),
            patch("synology_mcp.core.config.discover_config_path", side_effect=FileNotFoundError),
            patch("synology_mcp.cli._store_keyring", return_value=True),
            patch("synology_mcp.cli.asyncio.run", return_value=connect_result),
            patch.dict(os.environ, clean_env, clear=True),
        ):
            result = runner.invoke(
                main,
                ["setup"],
                input="192.168.1.50\nn\nread\n\nadmin\npassword\nn\n",
            )

        assert "Aborted" in result.output


class TestEnvVarMode:
    def test_serve_env_var_mode(self) -> None:
        """When SYNOLOGY_HOST is set and no config file, synthesize config."""
        from synology_mcp.core.config import _synthesize_env_config

        env = {"SYNOLOGY_HOST": "10.0.0.5"}
        with patch.dict(os.environ, env, clear=False):
            config = _synthesize_env_config()

        assert config is not None
        assert config.connection is not None
        assert config.connection.host == "10.0.0.5"
        assert config.instance_id == "10-0-0-5"
        assert config.modules["filestation"].permission == "read"

    def test_no_env_var_returns_none(self) -> None:
        from synology_mcp.core.config import _synthesize_env_config

        clean_env: dict[str, str] = {
            k: v for k, v in os.environ.items() if not k.startswith("SYNOLOGY_")
        }
        with patch.dict(os.environ, clean_env, clear=True):
            config = _synthesize_env_config()

        assert config is None

    def test_load_config_falls_back_to_env(self, tmp_path: Path) -> None:
        """load_config falls back to env-var mode when no config file exists."""
        from synology_mcp.core.config import load_config

        env: dict[str, str] = {
            "SYNOLOGY_HOST": "10.0.0.99",
        }
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("SYNOLOGY_")}
        clean_env.update(env)

        with patch.dict(os.environ, clean_env, clear=True):
            config = load_config(None)

        assert config is not None
        assert config.connection is not None
        assert config.connection.host == "10.0.0.99"

    def test_load_config_explicit_path_no_fallback(self) -> None:
        """Explicit --config path should not fall back to env-var mode."""
        import pytest

        from synology_mcp.core.config import load_config

        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")


class TestAliasField:
    def test_alias_in_config(self) -> None:
        raw: dict[str, Any] = {
            "schema_version": 1,
            "alias": "HomeNAS",
            "connection": {"host": "192.168.1.100"},
            "modules": {"filestation": {"enabled": True}},
        }
        from synology_mcp.core.config import AppConfig

        config = AppConfig(**raw)
        assert config.alias == "HomeNAS"
        assert config.display_name == "HomeNAS"

    def test_display_name_falls_back_to_instance_id(self) -> None:
        raw: dict[str, Any] = {
            "schema_version": 1,
            "connection": {"host": "192.168.1.100"},
            "modules": {"filestation": {"enabled": True}},
        }
        from synology_mcp.core.config import AppConfig

        config = AppConfig(**raw)
        assert config.alias is None
        assert config.display_name == "192-168-1-100"

    def test_display_name_with_alias_and_instance_id(self) -> None:
        raw: dict[str, Any] = {
            "schema_version": 1,
            "instance_id": "my-nas",
            "alias": "Office NAS",
            "connection": {"host": "10.0.0.1"},
            "modules": {"filestation": {"enabled": True}},
        }
        from synology_mcp.core.config import AppConfig

        config = AppConfig(**raw)
        assert config.display_name == "Office NAS"


class TestFetchDsmInfo:
    async def test_fetch_dsm_info_not_in_cache(self) -> None:
        """When SYNO.DSM.Info is not in the API cache, return empty dict."""
        from synology_mcp.core.client import DsmClient

        async with DsmClient(base_url="http://nas:5000") as client:
            result = await client.fetch_dsm_info()
        assert result == {}

    async def test_fetch_dsm_info_in_cache(self) -> None:
        """When SYNO.DSM.Info is available, call getinfo and return data."""
        import respx

        from synology_mcp.core.client import DsmClient
        from synology_mcp.core.state import ApiInfoEntry

        with respx.mock:
            respx.get("http://nas:5000/webapi/entry.cgi").respond(
                json={
                    "success": True,
                    "data": {
                        "model": "DS1618+",
                        "hostname": "MyNAS",
                        "version_string": "DSM 7.1.1-42962 Update 6",
                    },
                }
            )
            async with DsmClient(base_url="http://nas:5000") as client:
                client._api_cache = {
                    "SYNO.DSM.Info": ApiInfoEntry(path="entry.cgi", min_version=1, max_version=2),
                }
                result = await client.fetch_dsm_info()

        assert result["hostname"] == "MyNAS"
        assert result["model"] == "DS1618+"
