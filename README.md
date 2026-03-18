# synology-mcp

MCP server for Synology NAS devices. Exposes Synology DSM API functionality as MCP tools that Claude can use.

## Features

- **File Station** — browse, search, move, copy, delete, and organize files on your NAS (12 tools)
- **Permission tiers** — READ (safe browsing) or WRITE (file operations), configured per module
- **2FA support** — full two-factor authentication with device token bootstrap; once set up, re-authentication is automatic with no OTP prompts
- **Secure credentials** — OS keyring integration that works transparently, including from Claude Desktop on Linux (auto-detects D-Bus session). See [docs/credentials.md](docs/credentials.md) for details.
- **Multi-NAS** — manage multiple NAS devices with separate configs, credentials, and state
- **Zero-config start** — interactive setup creates config, stores credentials, and emits a Claude Desktop snippet

## Quick Start

### 1. Run interactive setup

```bash
# Clone and install
git clone https://github.com/cmeans/synology-mcp.git
cd synology-mcp
uv sync

# Interactive setup — prompts for host, credentials, handles 2FA
uv run synology-mcp setup
```

Setup will:
- Prompt for NAS host, HTTPS preference, and permission level
- Prompt for DSM username and password
- Store credentials in the OS keyring
- Connect to the NAS and validate login
- Handle 2FA if enabled (prompts for OTP, stores device token)
- Write a config file to `~/.config/synology-mcp/{instance_id}.yaml`
- Print a Claude Desktop JSON snippet ready to copy-paste

### 2. Add to Claude Desktop

Copy the JSON snippet from setup into your `claude_desktop_config.json`. Or manually:

```json
{
  "mcpServers": {
    "synology": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/synology-mcp",
        "run", "synology-mcp", "serve",
        "--config", "~/.config/synology-mcp/config.yaml"
      ]
    }
  }
}
```

No `env` block needed — keyring credentials are accessed automatically on all platforms.

### 3. Verify

```bash
uv run synology-mcp check                    # Validates credentials work
uv run synology-mcp setup --list             # Shows all configured NAS instances
```

### Alternative: env-var-only mode

No config file needed if `SYNOLOGY_HOST` is set:

```bash
SYNOLOGY_HOST=192.168.1.100 uv run synology-mcp check
```

## 2FA Support

synology-mcp fully supports DSM accounts with two-factor authentication:

1. **Bootstrap** — `synology-mcp setup` detects 2FA, prompts for your OTP code, and stores a device token in the keyring
2. **Silent re-auth** — subsequent logins use the device token automatically (no OTP prompts)
3. **Per-instance** — each NAS config gets its own device token, so mixed 2FA/non-2FA setups work fine

If a device token expires or is revoked, run `synology-mcp setup` again to re-bootstrap.

## Keyring & Credentials

Credentials are stored in the OS keyring and accessed transparently:

| Platform | Backend | Notes |
|----------|---------|-------|
| macOS | Keychain | Just works |
| Windows | Credential Manager | Just works |
| Linux | GNOME Keyring / KWallet | Auto-detects D-Bus session, works from Claude Desktop |
| Docker | N/A | Use env vars or config file credentials |

Credential resolution order: **env vars > config file > keyring**. Explicit sources override the implicit default.

See [docs/credentials.md](docs/credentials.md) for keyring service names, multi-NAS setup, and how to inspect/remove stored credentials.

## Configuration

See `examples/` for sample configs:
- `config-minimal.yaml` — quick start
- `config-power-user.yaml` — HTTPS, custom settings, logging
- `config-docker.yaml` — environment-variable-driven

## Debugging

Two ways to enable debug logging:

```bash
synology-mcp check --verbose                          # --verbose flag on setup/check
SYNOLOGY_LOG_LEVEL=debug synology-mcp serve           # env var, works for all commands
```

Or set it persistently in your config file:

```yaml
logging:
  level: debug
  file: ~/.local/state/synology-mcp/primary/server.log  # optional, logs to stderr by default
```

Debug output includes every DSM API request/response (passwords masked), credential resolution steps, config discovery, version negotiation, and module registration decisions.

## Design Docs

Detailed specs live in `docs/specs/`:
- `architecture.md` — layered architecture, auth strategy, session lifecycle
- `filestation-module-spec.md` — all 12 File Station tools
- `config-schema-spec.md` — YAML config structure and validation
- `project-scaffolding-spec.md` — repo structure, CI, testing

## Development

```bash
uv sync --extra dev                        # Install dependencies
uv run ruff check src/ tests/              # Lint
uv run ruff format --check src/ tests/     # Format check
uv run mypy src/                           # Type check
uv run pytest                              # Run tests
uv run pytest -m integration               # Integration tests (requires NAS)
```

## Acknowledgements

This project was built using a **Spec-First Coding** approach — a human-AI collaboration model where design precedes implementation and specs are the contract between the two.

Unlike vibe coding, where you describe what you want and let the AI generate code on the fly, spec-first coding treats design as a separate, deliberate phase. The four specs in `docs/specs/` were developed through extended conversation — exploring trade-offs, rejecting alternatives, and documenting decisions with rationale. Only after the specs were complete did implementation begin, with the specs serving as the source of truth across 11 build phases.

The result: every line of code traces back to a design decision that was made intentionally, not improvised.

## License

MIT

---

Copyright (c) 2026 Chris Means
