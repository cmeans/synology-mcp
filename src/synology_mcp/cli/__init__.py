"""CLI package: serve, setup, check subcommands (click-based).

Re-exports for backward compatibility:
- server.py imports: _check_for_update, _load_global_state, _save_global_state
- __main__.py imports: main
"""

from __future__ import annotations

from synology_mcp.cli.main import main
from synology_mcp.cli.setup import _CONFIG_DIR, _store_keyring
from synology_mcp.cli.version import (
    _check_for_update,
    _load_global_state,
    _save_global_state,
)

__all__ = [
    "_CONFIG_DIR",
    "_check_for_update",
    "_load_global_state",
    "_save_global_state",
    "_store_keyring",
    "main",
]
