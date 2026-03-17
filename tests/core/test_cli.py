"""Tests for cli.py — CLI subcommands via click CliRunner."""

from __future__ import annotations

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

    def test_check_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["check", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.output

    def test_serve_missing_config(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--config", "/nonexistent/config.yaml"])
        assert result.exit_code != 0
