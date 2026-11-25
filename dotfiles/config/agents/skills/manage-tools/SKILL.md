---
name: manage-tools
description: >-
  Add, upgrade, remove, or debug a CLI tool managed by this repository. Use when the user
  asks to install a tool the dotfiles way, edit tools.toml, choose between uv/cargo/
  github-release, investigate why a tool is missing from PATH or was not installed by a
  profile, or check for tool updates.
---

# Tool Management

Tools are declared once in `dotfiles/config/tools.toml`, deployed to
`~/.config/tools.toml`, and installed by `~/.local/bin/install-tools.py`. Profiles
call the installer per group:

| Action | Group |
| --- | --- |
| `install_shell_tools` | `shell` |
| `install_wezterm` | `wezterm` |
| `install_terminal_tools` | `terminal` |
| `install_neovim_tools` | `neovim` |
| `install_user_tools` | `user` |
| `install_rclone` | `rclone` |

**A tool that has no group matching an action is never installed.**

## Where binaries land

- **uv** → isolated venv under `$(uv tool dir)/<tool>`, executable symlinked into
  `~/.local/bin`.
- **cargo** → `~/.cargo/bin/<command>`.
- **github-release** → `~/.local/bin/<command>`; on Linux, AppImages go to
  `~/.local/share/<app>/` with a symlink and desktop entry. On macOS, an existing
  binary or `.app` bundle short-circuits, otherwise Homebrew is used when
  configured.

## Manifest shape

```toml
[tools.ripgrep]
manager = "cargo"
group = "user"
command = "rg"          # when the binary differs from the table key

[tools.glow]
manager = "github-release"
group = "user"
command = "glow"
repo = "charmbracelet/glow"
asset = "glow_.*_Linux_{arch}\\.tar\\.gz$"
brew = "glow"
```

Fields by manager:

| Manager | Useful fields |
| --- | --- |
| `uv` | PyPI name = table key; `command` if different; `fork` (git URL) and `local_paths` for editable checkouts |
| `cargo` | `command` for the binary; optional `version` (pinned); skips when the binary already exists |
| `github-release` | `repo`, `asset` regex with `{arch}`, `arch_map`, `brew`, `brew_cask`, `app_bundle`, `skip_wsl`, `desktop_*`, `command` |

`arch_map` exists because projects disagree on names (`rclone` uses `amd64`, not
`x86_64`). `skip_wsl = true` prevents installing GUI apps inside WSL.

## Choosing a manager

1. **Rust tool** → `cargo` (built locally; no network binary trust).
2. **Python tool** → `uv`.
3. **Prebuilt binary with no good package** → `github-release`.
4. Prefer an existing group over inventing one. If a genuinely new category is
   needed, add an action (`~/.local/bin/install-tools.py --group <name>`) and
   attach it to the profiles that should install it.
5. Do not pin versions unless reproducibility requires it. Release tools always
   follow the latest GitHub release.

## Add a tool

```bash
# 1. Check whether it is already there
command -v <command> || true

# 2. Add [tools.<name>] to dotfiles/config/tools.toml with a manager + group

# 3. Deploy the manifest and install just that tool
dotdrop install -f f_tools.toml
~/.local/bin/install-tools.py --tool <name>

# 4. Verify from a fresh shell
command -v <command> && <command> --version

# 5. If it belongs in a profile's install set, the group is already covered by
#    that profile's install_* action; otherwise add the action to the profile.
dotdrop compare        # manifest drift check
```

Useful installer flags: `--tool <name>`, `--group <group>`, `--manager
<uv|cargo|github-release|appimage>`, `--update`, `--force`. `--update` re-checks
release tools for newer versions; cargo tools skip unless `--force`; uv tools
reinstall with `--force`.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `No tools found matching group='x'` | group typo, or no tool has that `group`/`groups` |
| Release tool: "no release asset matched" | `asset` regex or `{arch}`/`arch_map` is wrong; check the release's asset names |
| Installed but `command not found` | `~/.local/bin` or `~/.cargo/bin` not on PATH in this shell |
| Tool repeatedly reinstalls/skips | cargo skips existing binaries; use `--force` to rebuild |
| macOS ignored the asset | existing Homebrew binary/`.app` is used first; set `brew`/`brew_cask` or remove it intentionally |
| GitHub API check failed | installer keeps an existing install and warns; retry later or `--force` |
| GUI tool installed in WSL | set `skip_wsl = true` |

## Guardrails

- Edit `dotfiles/config/tools.toml`, never `~/.config/tools.toml`.
- Test with `--tool` before running a whole group; groups may install several
  network tools.
- Assign tools to groups that an active profile actually installs, otherwise the
  manifest entry is dead weight.
- The manifest is tracked and shared; keep machine-specific overrides out of it.
  Put local source checkouts in `local_paths` using `~`.
