---
name: manage-tools
description: >-
  Add, upgrade, remove, or debug a CLI tool or desktop app managed by this repository.
  Use when the user asks to install a tool the dotfiles way, edit tools.toml, choose
  between uv/cargo/github-release, investigate why a tool is missing from PATH or was not
  installed by a profile, fix a desktop entry (missing icon, taskbar grouping, URL
  handler), or check for tool updates.
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
| `install_apps` | `apps` (desktop apps: Obsidian, JetBrains Toolbox) |

**A tool that has no group matching an action is never installed.**

## Where binaries land

- **uv** → isolated venv under `$(uv tool dir)/<tool>`, executable symlinked into
  `~/.local/bin`.
- **cargo** → `~/.cargo/bin/<command>`.
- **github-release** → `~/.local/bin/<command>`; on Linux, AppImages go to
  `~/.local/share/<app>/` with a symlink and desktop entry. With `exec_args`, the
  `~/.local/bin` entry is a wrapper script instead of a symlink. With
  `extract = "full"`, the whole archive is unpacked to
  `~/.local/share/<app>/<version>/` and `binary_path` is linked. On macOS, an
  existing binary or `.app` bundle short-circuits, otherwise Homebrew is used when
  configured.
- **Desktop entries** → `~/.local/share/applications/<app_id or command>.desktop`,
  icon at `~/.local/share/icons/hicolor/128x128/apps/<icon_name>.png`.

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
| `github-release` (download) | `source = "jetbrains"` + `product_code` (JetBrains releases API instead of GitHub); `extract = "full"` + `binary_path` (app shipped as a directory tree); `binary` (file to pull from a single-binary archive) |
| `github-release` (launch/desktop) | `exec_args` (wrapper adds flags), `desktop_entry`, `desktop_name`, `desktop_comment`, `desktop_categories`, `desktop_terminal`, `icon_name`, `app_id`, `desktop_mime_types` |
| `github-release` (lifecycle) | `installed_paths` (globs; tool self-updates, installer skips it once any match exists and never deletes its older copies), `post_install_note` |

`arch_map` exists because projects disagree on names (`rclone` uses `amd64`, not
`x86_64`; Obsidian maps `x86_64` to `""` because its x86_64 AppImage has no
suffix). `skip_wsl = true` prevents installing GUI apps inside WSL.

## GUI apps (desktop entries)

- **Set `app_id`** to the window's Wayland app_id / X11 WM_CLASS. Read it from the
  `StartupWMClass` of the desktop file bundled in the app
  (`<AppImage> --appimage-extract '*.desktop'` in a scratch dir). The entry is then
  named `<app_id>.desktop` with a matching `StartupWMClass`. Without it, the
  taskbar shows no icon for the window and pinned entries can vanish (seen on
  COSMIC). An entry under the old `<command>.desktop` name is removed.
- **Electron AppImages** need `exec_args = ["--no-sandbox"]` where
  `kernel.apparmor_restrict_unprivileged_userns = 1` (Ubuntu 24.04+); otherwise
  they abort with a SUID sandbox error.
- **`desktop_mime_types`** fills `MimeType`. Any `x-scheme-handler/*` (e.g.
  `obsidian://`) is made the default via `xdg-mime` and switches `Exec` to `%U`;
  file types are only offered under "Open with", never claimed as default.
- Entries are regenerated on any run where they differ from the manifest or
  their icon file is missing, so manifest edits reach installed machines.
- Apps that self-update (JetBrains Toolbox) are bootstrap-only: set
  `installed_paths` to the unpacked binary's glob. Toolbox runs from wherever it
  was unpacked and writes its own desktop entry and autostart on first launch,
  so no `desktop_entry` for it; the user must launch it once.

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
| Window has no taskbar icon / pin disappears | `app_id` missing or wrong; set it from the bundled `StartupWMClass`. Already-open windows keep their old grouping until a new window opens |
| Desktop entry has a generic icon | icon not extractable; the installer follows symlinked AppImage icons, so check `icon_name` and the AppImage's `usr/share/icons` |
| Electron app exits with a sandbox error | add `exec_args = ["--no-sandbox"]` |
| JetBrains Toolbox not in app search | it has not been launched yet; run `jetbrains-toolbox` once |

## Guardrails

- Edit `dotfiles/config/tools.toml`, never `~/.config/tools.toml`.
- Test with `--tool` before running a whole group; groups may install several
  network tools.
- Assign tools to groups that an active profile actually installs, otherwise the
  manifest entry is dead weight.
- The manifest is tracked and shared; keep machine-specific overrides out of it.
  Put local source checkouts in `local_paths` using `~`.
