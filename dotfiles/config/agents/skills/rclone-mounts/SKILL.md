---
name: rclone-mounts
description: >-
  Set up, repair, or explain the rclone Google Drive mounts on Linux: authorize the Drive
  remote, build the shared-drives combine remote, enable the systemd user units, and
  diagnose mount/OAuth/cache problems. Use for onboarding a Linux workstation that needs
  ~/GoogleDrive and ~/SharedDrives.
---

# rclone Google Drive Mounts (Linux)

The `rclone` mixin installs `rclone` (GitHub release, group `rclone`), deploys two
systemd **user** units, and runs `setup_rclone_mount` (creates `~/GoogleDrive`,
`~/SharedDrives`, `~/.cache/rclone`, then `systemctl --user daemon-reload`).

| Unit | Remote | Mount |
| --- | --- | --- |
| `rclone-gdrive.service` | `gdrive:` | `~/GoogleDrive` |
| `rclone-shared.service` | `shared:` (combine) | `~/SharedDrives` |

The units use `--vfs-cache-mode full` (10 GiB cache, 24 h max age), 5 min dir
cache, 1 min polling, and log to `~/.cache/rclone/{gdrive,shared}-mount.log`.
`ExecStop` uses `/usr/bin/fusermount3`.

**Linux only.** macOS has no systemd; use Homebrew rclone and a launch agent or
manual mount instead. The units are deployed but **not enabled** by dotdrop.

## Prerequisites

- A Linux host with a working user systemd session (`systemctl --user`).
- `fuse3` installed, with `fusermount3` at the path used by the unit (usually
  `/usr/bin/fusermount3`; adjust the unit if the distro differs).
- `rclone` present at `~/.local/bin/rclone` (the `install_rclone` action).
- Outbound HTTPS for OAuth and the Drive API.

Install the profile pieces:

```bash
dotdrop install -a -f -p <hostname>   # profile must include rclone
command -v rclone && rclone version
```

## 1. Authorize the Drive remote

With a browser on the machine:

```bash
rclone config create gdrive drive scope=drive
rclone lsd gdrive:            # verify
rclone about gdrive:          # quota/account check
```

Headless machines: run `rclone authorize "drive"` on a machine with a browser,
then on the headless host run `rclone config`, choose the existing/new `gdrive`
remote, answer **n** to "Use auto config?" and paste the resulting token.
Verify with `rclone lsd gdrive:`.

The OAuth token lives in `rclone.conf` (`rclone config file` shows the path,
normally `~/.config/rclone/rclone.conf`). Treat it as a secret; never commit it.
If it expires: `rclone config reconnect gdrive:`.

## 2. Build the shared-drives combine

List the shared drives and generate ready-made config:

```bash
rclone backend -o config drives gdrive:
```

That prints one `type = alias` block per shared drive plus a `[AllDrives]`
`type = combine` block whose `upstreams` map folder names to those aliases:

```ini
[My Drive]
type = alias
remote = gdrive,team_drive=0ABCDEF-01234567890,root_folder_id=:

[AllDrives]
type = combine
upstreams = "My Drive=My Drive:"
```

Append the blocks to `rclone.conf` and rename `[AllDrives]` to `[shared]` (the
unit mounts `shared:`). Syntax is `Name=remote:path`, space-separated, quoted
when a name contains spaces. Then:

```bash
rclone lsd shared:
```

To expose only selected drives, list them yourself with
`rclone backend drives gdrive:` and write one upstream per drive using
connection-string overrides (no alias blocks needed):

```ini
[shared]
type = combine
upstreams = "Team=gdrive,team_drive=<ID>:" "Archive=gdrive,team_drive=<ID2>:"
```

## 3. Enable and verify

```bash
systemctl --user daemon-reload
systemctl --user enable --now rclone-gdrive rclone-shared
systemctl --user status rclone-gdrive rclone-shared
journalctl --user -u rclone-gdrive -f     # live log
```

Checks:

```bash
systemctl --user is-active rclone-gdrive rclone-shared
findmnt ~/GoogleDrive ~/SharedDrives
ls ~/GoogleDrive ~/SharedDrives
tail -n 20 ~/.cache/rclone/gdrive-mount.log
```

To mount at boot without an interactive login: `loginctl enable-linger "$USER"`.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `Transport endpoint is not connected` | stale FUSE mount: `fusermount3 -uz ~/GoogleDrive`, restart the unit |
| Unit fails immediately | `rclone` missing at `~/.local/bin`, wrong remote name, or no user systemd bus |
| Empty `~/SharedDrives` | `[shared]` combine missing/misnamed, wrong `team_drive` IDs, or no access |
| Empty `~/GoogleDrive` but `rclone lsd gdrive:` works | unit uses a different config/user; check `rclone config file` and `journalctl --user` |
| OAuth expired / 401 | `rclone config reconnect gdrive:` |
| Cache grows large | VFS cache is bounded per unit (`--vfs-cache-max-size 10G`); clear `~/.cache/rclone/vfs*` while unmounted |
| `fusermount3: not found` on stop | distro path differs; update `ExecStop` in the repo unit and reinstall |
| Works after login only | enable lingering (`loginctl enable-linger`) |

Restart after config changes:

```bash
systemctl --user restart rclone-gdrive rclone-shared
```

## Onboarding checklist (work laptop)

1. Profile includes `rclone`; `dotdrop install -a -f -p "$(hostname)"`.
2. Install `fuse3`.
3. `rclone config create gdrive drive scope=drive` and verify `rclone about gdrive:`.
4. Generate/append `[shared]`; verify `rclone lsd shared:`.
5. `systemctl --user enable --now rclone-gdrive rclone-shared`.
6. Verify both mount points and `systemctl --user is-active`.
7. Enable lingering if the mounts must survive logout.

## Guardrails

- Never commit `rclone.conf` or OAuth tokens; keep the file mode `600`.
- Do not run the units as root; they are per-user mounts under `$HOME`.
- Do not edit the deployed unit copies in `~/.config/systemd/user` directly;
  change `dotfiles/config/systemd/user/*.service` and reinstall.
- `setup_rclone_mount` only creates directories and reloads systemd; enabling the
  units is always a deliberate manual step.
