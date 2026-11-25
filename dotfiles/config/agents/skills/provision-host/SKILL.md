---
name: provision-host
description: >-
  Create or update a dotdrop host profile for a new machine, choose presets and mixins,
  or explain how this repo is installed on a fresh system. Use when the user asks to set
  up dotfiles on a new host, add this hostname to config.yaml, change a machine's
  capabilities, or bootstrap toolchains and dotdrop.
---

# Host Provisioning

Each machine gets a profile named exactly as `$(hostname)`, because dotdrop's
default profile is the hostname. A profile is a list of mixins plus optional
extra dotfiles (the macOS rc hooks).

## Fresh-machine order

```bash
git clone git@github.com:HotelCalifornia/dotfiles.git ~/dotfiles
cd ~/dotfiles
./dotfiles/scripts/ensure-toolchains.sh     # uv + rustup, non-interactive
uv tool install dotdrop
./dotfiles/scripts/init-profile.py          # interactive wizard
```

`ensure-toolchains.sh` uses upstream `curl | sh` installers. On a host where that
is not acceptable, install `uv` and `cargo` first, then continue.

## Presets

| Preset | Include list | Notes |
| --- | --- | --- |
| `1` Workstation | `wezterm, neovim, user, git` | Suggests macOS rc hooks; default on macOS |
| `2` WSL Workstation | `wsl, neovim, user, git` | Default when running under Microsoft/WSL |
| `3` Headless / Server | `neovim, user, git` | No terminal GUI |
| `4` Minimal Shell | `bash, user` | Smallest useful set |

`gemini` and `claude` are selected separately (`--agents`); both include the
`ai` mixin, which deploys the shared rules and skills plus `link-agent-skills.sh`.
Add `rclone` only on Linux hosts that need the Drive mounts.

## Non-interactive (the only path an agent can drive)

The wizard and `--identities` require a real TTY. In a non-TTY, the script forces
`--non-interactive`; use flags instead.

```bash
# Preview the block without touching config.yaml
~/.local/bin/init-profile.py --non-interactive --hostname "$(hostname)" \
  --preset 1 --agents gemini --mac-rc --dry-run

# Write it, then install
~/.local/bin/init-profile.py --non-interactive --hostname "$(hostname)" \
  --preset 1 --agents gemini --mac-rc

dotdrop install -a -f
```

Flags:

- `--include a,b,c` — explicit mixins; overrides `--preset`.
- `--agents gemini,claude` — appends harness mixins (each includes `ai`).
- `--mac-rc` — adds `f_most.sh`, `f_1-mac.sh`, `f_1-pyenv.sh`, `f_2-direnv.sh`,
  `f_vcpkg.sh` on macOS.
- `--force` — overwrite an existing profile. **Destructive to that block**; only
  use when the user confirms.
- `--install` — run `dotdrop install -a -f` after writing.
- `--config <path>` — use a non-default `config.yaml`.

The installed copy (`~/.local/bin/init-profile.py`) finds the repo via
`$DOTFILES_DIR`, the current directory, `~/dotfiles`, or `--config`. In agent
shells `$DOTFILES_DIR` is unset, so run it from the repo root.

## Interactive wizard (hand off to the human)

Requires a terminal. It offers presets, a capability checklist, AI harnesses, and
a git-identity step. If the user asks for this interactively, tell them to run:

```bash
cd ~/dotfiles && ./dotfiles/scripts/init-profile.py
```

It writes the profile block, optionally writes git identities, and offers to run
`dotdrop install -a -f`.

## Git identities

Profiles that include `git` deploy the shared `~/.gitconfig`; the identity itself
is machine-local:

```bash
~/.local/bin/init-profile.py --identities      # TTY only
```

If the TTY is unavailable, hand off rather than fabricating one. After adding
identities, ensure `f_gitconfig` is deployed (`dotdrop install -f f_gitconfig`).
See the `git-signing` skill for diagnosis and key work.

## Linux specifics

- `rclone` mixin: installs `rclone` and deploys the systemd user units; it does
  not enable them. Follow the `rclone-mounts` skill.
- `wayland` mixin: deploys the WezTerm Wayland mixin.
- `apps` mixin: installs Obsidian and JetBrains Toolbox (desktop entries, `obsidian://`
  handler). Toolbox must be launched once before it appears in app search.
- WSL: the `wsl` mixin includes `bash, neovim, user`; GUI tools marked
  `skip_wsl` are not installed.

## Changing an existing host

- **Small change:** edit that host's `include`/`dotfiles` in `config.yaml`
  directly, then `dotdrop install -f`. Keep the edit minimal; profiles are shared
  history.
- **Regenerate:** rerun the wizard (interactive) or the non-interactive command
  with `--force`. This replaces the whole profile block.
- Never point `-p` at another machine's profile unless explicitly asked; it
  deploys the wrong mixin set.

## Verify

```bash
dotdrop profiles | grep -F "$(hostname)"
dotdrop detail -p "$(hostname)"     # resolved dotfiles
dotdrop compare -p "$(hostname)"    # should be clean after install
```

`$DOTFILES_DIR` is recorded on the first install into
`~/.config/rc/pre/00-dotfiles.sh`. If the repo moves, delete that file and
reinstall.
