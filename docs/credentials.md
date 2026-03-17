# Credential Storage

synology-mcp stores credentials in your OS keyring (macOS Keychain, Windows Credential Manager, Linux Secret Service / GNOME Keyring / KDE Wallet).

## Keyring Service Name

Credentials are stored under the service name:

```
synology-mcp/{instance_id}
```

Where `instance_id` is:
- The value of `instance_id` in your config file, if set explicitly
- Derived from `connection.host` otherwise:
  - IP addresses: dots become hyphens (`192.168.1.100` -> `192-168-1-100`)
  - Hostnames: first component only (`nas.local` -> `nas`)

## Stored Keys

Each service stores up to three keys:

| Key | Description |
|-----|-------------|
| `username` | DSM login username |
| `password` | DSM login password |
| `device_id` | 2FA device token (only present after 2FA bootstrap) |

## Inspecting Keyring Entries

You can inspect stored credentials using your OS keyring tools or Python's `keyring` CLI:

```bash
# List what's stored for a given instance
python -m keyring get synology-mcp/192-168-1-100 username

# Or using the keyring CLI directly
keyring get synology-mcp/nas-primary username
```

## Removing Credentials

```bash
keyring del synology-mcp/192-168-1-100 username
keyring del synology-mcp/192-168-1-100 password
keyring del synology-mcp/192-168-1-100 device_id
```

## Credential Resolution Order

When authenticating, synology-mcp checks these sources in order:

1. **Environment variables** (highest priority) — `SYNOLOGY_USERNAME`, `SYNOLOGY_PASSWORD`, `SYNOLOGY_DEVICE_ID`
2. **Config file** — `auth.username`, `auth.password` — triggers a plaintext warning
3. **OS keyring** (default) — set via `synology-mcp setup`

Explicit sources (env vars, config file) override the implicit default (keyring). This means setting `SYNOLOGY_PASSWORD=x` will always use that password, even if the keyring has a different one stored.

## Multiple NAS Configurations

Each NAS gets its own keyring entry keyed by `instance_id`. If you have two NAS devices:

```yaml
# ~/.config/synology-mcp/nas-primary.yaml
instance_id: nas-primary
connection:
  host: 192.168.1.100

# ~/.config/synology-mcp/nas-backup.yaml
instance_id: nas-backup
connection:
  host: 192.168.1.200
```

Their credentials are stored independently:
- `synology-mcp/nas-primary` — username, password, device_id
- `synology-mcp/nas-backup` — username, password, device_id

Run `synology-mcp setup --list` to see all configured instances.
