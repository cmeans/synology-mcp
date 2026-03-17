"""CLI: serve, setup, check subcommands (click-based)."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import click

from synology_mcp import __version__

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _init_early_logging(*, verbose: bool = False) -> None:
    """Configure logging early so config discovery/loading is visible.

    Checks --verbose flag first, then SYNOLOGY_LOG_LEVEL env var.
    Falls back to INFO. Will be reconfigured after config is loaded
    if the config specifies a different level.
    """
    if verbose:
        level = logging.DEBUG
    else:
        env_level = os.environ.get("SYNOLOGY_LOG_LEVEL", "info").upper()
        level = getattr(logging, env_level, logging.INFO)
    logging.basicConfig(level=level, format=_LOG_FORMAT, stream=sys.stderr)


def _configure_logging(level: str, log_file: str | None = None) -> None:
    """Reconfigure logging from loaded config values."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if log_file:
        file_handler = logging.FileHandler(os.path.expanduser(log_file), encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        root.addHandler(file_handler)


@click.group()
@click.version_option(version=__version__, prog_name="synology-mcp")
def main() -> None:
    """synology-mcp — MCP server for Synology NAS."""


@main.command()
@click.option("--config", type=click.Path(), help="Path to config file")
def serve(config: str | None) -> None:
    """Start the MCP server (launched by Claude Desktop)."""
    _init_early_logging()

    from synology_mcp.core.config import load_config
    from synology_mcp.server import create_server

    try:
        app_config = load_config(config)
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    _configure_logging(app_config.logging.level, app_config.logging.file)

    server = create_server(app_config)
    server.run(transport="stdio")


@main.command()
@click.option("--config", type=click.Path(), help="Path to config file")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
def setup(config: str | None, verbose: bool) -> None:
    """Interactive credential setup and 2FA bootstrap."""
    _init_early_logging(verbose=verbose)

    from synology_mcp.core.config import load_config

    try:
        app_config = load_config(config)
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if not verbose:
        _configure_logging(app_config.logging.level, app_config.logging.file)

    assert app_config.connection is not None
    click.echo(f"Setting up credentials for {app_config.connection.host}")
    click.echo(f"Instance: {app_config.instance_id}")
    click.echo()

    username = click.prompt("DSM username")
    password = click.prompt("DSM password", hide_input=True)

    # Try to store in keyring
    service = f"synology-mcp/{app_config.instance_id}"
    try:
        import keyring

        keyring.set_password(service, "username", username)
        keyring.set_password(service, "password", password)
        click.echo("\nCredentials stored in OS keyring.")
    except Exception:  # noqa: BLE001
        click.echo(
            "\nKeyring not available. Set environment variables instead:\n"
            f"  export SYNOLOGY_USERNAME={username}\n"
            f"  export SYNOLOGY_PASSWORD=<your-password>"
        )
        return

    # Attempt login to validate and handle 2FA
    click.echo("\nAttempting login...")
    asyncio.run(_setup_login(app_config, username, password, service))


async def _setup_login(config: object, username: str, password: str, service: str) -> None:
    """Attempt login during setup, handle 2FA if needed."""
    from synology_mcp.core.config import AppConfig

    assert isinstance(config, AppConfig)
    assert config.connection is not None

    from synology_mcp.core.client import DsmClient

    protocol = "https" if config.connection.https else "http"
    base_url = f"{protocol}://{config.connection.host}:{config.connection.port}"

    async with DsmClient(
        base_url=base_url,
        verify_ssl=config.connection.verify_ssl,
        timeout=config.connection.timeout,
    ) as client:
        await client.query_api_info()

        # Attempt login
        try:
            data = await client.request(
                "SYNO.API.Auth",
                "login",
                version=6,
                params={
                    "account": username,
                    "passwd": password,
                    "format": "sid",
                },
            )
            sid = data.get("sid")
            if sid:
                click.echo(click.style("Login successful!", fg="green"))
                # Logout
                client.sid = sid
                await client.request("SYNO.API.Auth", "logout", version=6, params={})
        except Exception as e:  # noqa: BLE001
            error_code = getattr(e, "code", None)
            if error_code == 403:
                click.echo("2FA is required. Enter the OTP code from your authenticator app.")
                otp_code = click.prompt("OTP code")

                try:
                    data = await client.request(
                        "SYNO.API.Auth",
                        "login",
                        version=6,
                        params={
                            "account": username,
                            "passwd": password,
                            "otp_code": otp_code,
                            "enable_device_token": "yes",
                            "device_name": "SynologyMCP",
                            "format": "sid",
                        },
                    )
                    device_id = data.get("did", "")
                    if device_id:
                        import keyring

                        keyring.set_password(service, "device_id", device_id)
                        click.echo(click.style("2FA bootstrap complete!", fg="green"))
                        click.echo("Device token stored in keyring.")
                    else:
                        click.echo(click.style("Login successful!", fg="green"))

                    sid = data.get("sid")
                    if sid:
                        client.sid = sid
                        await client.request("SYNO.API.Auth", "logout", version=6, params={})
                except Exception as e2:  # noqa: BLE001
                    click.echo(click.style(f"Login failed: {e2}", fg="red"), err=True)
            else:
                click.echo(click.style(f"Login failed: {e}", fg="red"), err=True)


@main.command()
@click.option("--config", type=click.Path(), help="Path to config file")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
def check(config: str | None, verbose: bool) -> None:
    """Validate stored credentials can authenticate."""
    _init_early_logging(verbose=verbose)

    from synology_mcp.core.config import load_config

    try:
        app_config = load_config(config)
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if not verbose:
        _configure_logging(app_config.logging.level, app_config.logging.file)

    click.echo(f"Checking credentials for instance '{app_config.instance_id}'...")
    asyncio.run(_check_login(app_config))


async def _check_login(config: object) -> None:
    """Validate credentials by attempting a login."""
    from synology_mcp.core.auth import AuthManager
    from synology_mcp.core.client import DsmClient
    from synology_mcp.core.config import AppConfig

    assert isinstance(config, AppConfig)
    assert config.connection is not None

    protocol = "https" if config.connection.https else "http"
    base_url = f"{protocol}://{config.connection.host}:{config.connection.port}"

    async with DsmClient(
        base_url=base_url,
        verify_ssl=config.connection.verify_ssl,
        timeout=config.connection.timeout,
    ) as client:
        await client.query_api_info()

        auth = AuthManager(config, client)
        try:
            await auth.login()
            click.echo(click.style("Authentication successful!", fg="green"))
            await auth.logout()
        except Exception as e:  # noqa: BLE001
            click.echo(click.style(f"Authentication failed: {e}", fg="red"), err=True)
            sys.exit(1)
