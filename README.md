# Dotfiles

A modular, cross-platform dotfiles repository managed with [dotdrop](https://github.com/deadc0de6/dotdrop), configured for macOS, Linux, and Windows (WSL).

Features a declarative profile architecture, unified toolchain management via `uv`, `cargo`, and GitHub releases/AppImages, and cross-harness AI agent skill sharing across Antigravity/Gemini and Claude Code.

---

## Architecture Overview

```text
.
├── config.yaml
└── dotfiles/
    ├── bash_aliases
    ├── gitconfig
    ├── config/
    │   ├── agents/
    │   │   ├── rules/
    │   │   └── skills/
    │   ├── nvim/
    │   ├── powerline/
    │   ├── rc/
    │   ├── tools.toml
    │   ├── wezterm/
    │   └── wezterm-mixins/
    ├── local/share/nvim/site/
    └── scripts/
        ├── ensure-toolchains.sh
        ├── init-profile.py
        ├── install-tools.py
        ├── link-agent-skills.sh
        └── persist-dotfiles-dir.sh
```

| Section | Component | Purpose |
| :--- | :--- | :--- |
| **Root** | `config.yaml` | Dotdrop profile & action definitions |
| **`dotfiles/`** | `bash_aliases` | Shell entry point: sources `rc/`, Powerline bindings, aliases |
| | `gitconfig` | Shared git config; includes the machine-local identities file |
| **`config/`** | `agents/` | Canonical cross-harness rules & skills |
| | `nvim/` | Neovim configuration & plugins |
| | `powerline/` | Prompt themes & configuration |
| | `rc/` | Modular shell runtime scripts |
| | `tools.toml` | Declarative CLI/GUI tool manifest |
| | `wezterm/` | WezTerm configuration & dynamic mixin loader |
| | `wezterm-mixins/` | Optional platform WezTerm mixins |
| **`local/`** | `share/nvim/site/` | Vim-plug plugin manager |
| **`scripts/`** | `ensure-toolchains.sh` | Bootstraps development toolchains |
| | `init-profile.py` | Interactive host profile & git identity wizard |
| | `install-tools.py` | Multi-manager tool installer |
| | `link-agent-skills.sh` | Symlinks agent configs across harnesses |
| | `persist-dotfiles-dir.sh` | Records the repo location as `$DOTFILES_DIR` on first install |

---

## Profiles

Profiles are decoupled into single-responsibility mixins that can be combined for any host or environment:

| Profile | Purpose | Key Dotfiles & Actions |
| :--- | :--- | :--- |
| **`bash`** | Core shell & prompt | Powerline themes, aliases, shell toolchain bootstrap (`powerline-status`), records `$DOTFILES_DIR` for the `dotdrop` alias. |
| **`neovim`** | Editor environment | `init.lua`, `coc-settings.json`, vim-plug, Neovim release installer. |
| **`wezterm`** | Terminal emulator | `wezterm.lua` (with mixin loader), completions, `wezterm` installer, `pokemon-terminal`, `terminal-pane-display` skill. |
| **`wsl`** | Windows Subsystem for Linux | Includes `[bash, neovim, user]` + `pokemon-terminal` (themes Windows Terminal, skips WezTerm GUI configs). |
| **`user`** | General CLI utilities | Installs modern Rust/Python/Go CLI tools (`dust`, `eza`, `bat`, `glow`, `termaid`, `ripgrep`). |
| **`gemini`** | Antigravity / Gemini CLI | Symlinks `~/.gemini/config/{skills,rules}` $\rightarrow$ `~/.config/agents/`. |
| **`claude`** | Claude Code | Symlinks `~/.claude/{skills,rules}` $\rightarrow$ `~/.config/agents/`. |
| **`wayland`** | Display server mixin | Deploys `~/.config/wezterm/mixins/wayland.lua` (`enable_wayland = false`). |
| **`rclone`** | Google Drive mount (Linux) | Installs `rclone` (GitHub release), deploys `~/.config/systemd/user/rclone-gdrive.service` mounting remote `gdrive:` at `~/GoogleDrive`. One-time setup: `rclone config create gdrive drive scope=drive`, then `systemctl --user enable --now rclone-gdrive`. |
| **`git`** | Git config & identities | Shared `~/.gitconfig`; identities are set up per machine by `init-profile.py`, see [Git Identities](#git-identities). |
| **`hotel-laptop-2.local`** | Primary workstation | Includes `[wezterm, neovim, user, gemini]`. |

---

## Tool Management (`tools.toml`)

CLI tools and application binaries are declared centrally in [`dotfiles/config/tools.toml`](dotfiles/config/tools.toml) and dispatched through [`install-tools.py`](dotfiles/scripts/install-tools.py).

### Supported Managers

1. **`uv` (Python tools)**:
   - Installs PyPI packages into isolated virtual environments via `uv tool install` (e.g., `powerline-status`, `termaid`).
   - Supports custom git forks with automatic editable local checkout detection (e.g., `pokemon-terminal`).

2. **`cargo` (Rust tools)**:
   - Installs crates to `~/.cargo/bin/` via `cargo install --locked` (e.g., `du-dust`, `eza`, `bat`, `ripgrep`).
   - Automatically skips recompilation if the binary is already present.

3. **`github-release` (Precompiled Binaries & AppImages)**:
   - Queries GitHub's releases API for the latest release tag.
   - Automatically unpacks standalone binaries from `.tar.gz` / `.zip` archives into `~/.local/bin/` (e.g., `glow`).
   - On Linux: installs AppImages to `~/.local/share/<app>/`, symlinks to `~/.local/bin/<app>`, and automatically extracts icons to generate desktop entries in `~/.local/share/applications/` (e.g., `wezterm`, `neovim`).
   - On macOS: detects existing Homebrew binaries or `.app` bundles (`/Applications/WezTerm.app`) in 0ms, falling back to `brew install` / `brew install --cask`.
   - Supports `skip_wsl = true` to prevent installing GUI AppImages inside headless WSL environments.

### Tool CLI Usage

```bash
# Install tools for a specific group
~/.local/bin/install-tools.py --group user
~/.local/bin/install-tools.py --group terminal
~/.local/bin/install-tools.py --group neovim

# Check for updates and upgrade tools to latest releases
~/.local/bin/install-tools.py --update

# Force reinstallation of a specific tool
~/.local/bin/install-tools.py --tool eza --force
```

---

## Agent Skills & Rules (`.config/agents/`)

AI agent skills and rules reside in a canonical, harness-agnostic directory structure:

```text
~/.config/agents/
├── rules/
│   ├── git-commit-trailers.md
│   └── preferred-tools.md
└── skills/
    └── terminal-pane-display/
        ├── SKILL.md
        └── scripts/
            ├── display.sh
            ├── resize_pane.sh
            └── close_pane.sh
```

| Section | Component | Purpose |
| :--- | :--- | :--- |
| **`rules/`** | `git-commit-trailers.md` | Attributes AI harness and consulted models in commit trailers |
| | `preferred-tools.md` | Enforces modern CLI tool preferences |
| **`skills/`** | `terminal-pane-display/` | Multi-pane auxiliary rendering in WezTerm |

- When the `gemini` and `claude` profiles are active, dotdrop establishes symlinks:
  - **Gemini / Antigravity**:
    - `~/.gemini/config/skills` $\rightarrow$ `~/.config/agents/skills`
    - `~/.gemini/config/rules` $\rightarrow$ `~/.config/agents/rules`
  - **Claude Code**:
    - `~/.claude/skills` $\rightarrow$ `~/.config/agents/skills`
    - `~/.claude/rules` $\rightarrow$ `~/.config/agents/rules`
- Skills and rules authored once under `.config/agents/` are automatically discovered and enforced by both Antigravity and Claude Code. Claude Code supports `.claude/rules/` directly and adheres to `AGENTS.md` standards.

---

## Git Identities

Git identities are **per machine** and never stored in this repo or in `config.yaml`:

- **`~/.gitconfig`** (dotdrop, `git` profile) is the same on every machine. It sets `user.useConfigOnly = true`, so git refuses to commit until an identity is configured, and includes `~/.config/git/identities.gitconfig` (git ignores the include if the file is missing).
- **`~/.config/git/identities.gitconfig`** holds the machine's **default identity** (for example, work on a work laptop, personal on a personal one) and one `includeIf "hasconfig:remote.*.url:…"` (git 2.36+) per **additional identity**.
- **`~/.config/git/identities/<name>.gitconfig`** holds each additional identity. Because they match on the remote URL, they apply wherever a repo is cloned. You can have any number of them.

Both are generated by `init-profile.py`: the wizard shows an identity step when the `git` capability is selected, and on a machine that already has a profile you can run just that step:

```bash
~/.local/bin/init-profile.py --identities
```

For each identity it asks for a name, email and, for additional identities, which remotes it applies to (GitHub users/orgs such as `HotelCalifornia`, which match both HTTPS and SSH URLs, or URL globs such as `git@gitlab.com:group/**`). It then offers existing GPG signing keys and SSH keys, or generates new ones (ed25519) on the spot and prints what to add to your Git host. Rerunning it reads the existing files back, so you can edit, add or remove identities later.

When it finishes, it checks that `~/.gitconfig` actually includes the identities file (otherwise git ignores them) and, if not, offers to deploy it with `dotdrop install -f -p <hostname> f_gitconfig` (the full wizard just points this out, since it already offers `dotdrop install`). Run from inside a repo, it also shows which identity that repo commits as.

Details:
- An identity with a GPG key turns on commit and tag signing. An additional identity without a key turns signing **off** and never falls back to the default's key (even `git commit -S` fails instead of signing as the wrong person).
- An additional identity's SSH key is used via `core.sshCommand` with `IdentitiesOnly=yes`, which is what lets two accounts on the same Git host coexist.
- Files carry a `# Generated by init-profile.py --identities` header; the wizard only deletes files with that header, so hand-written files in `identities/` are left alone.

Check which identity a repo resolves to with `git config --show-origin user.email`.

---

## Installation & Workflow

### 1. Initial Setup on a New Device

Dotdrop automatically resolves its default profile to the machine's **hostname**. To provision a new machine:

```bash
# 1. Clone the repository
git clone git@github.com:HotelCalifornia/dotfiles.git ~/dotfiles
cd ~/dotfiles

# 2. Bootstrap uv & development toolchains
./dotfiles/scripts/ensure-toolchains.sh

# 3. Install dotdrop via uv tool
uv tool install dotdrop

# 4. Interactively generate the host profile & install dotfiles
./dotfiles/scripts/init-profile.py
```

`init-profile.py` uses PEP 723 inline script metadata to run an interactive terminal wizard via `uv run` (powered by `questionary`):
- **Keyboard Navigation**: Use <kbd>↑</kbd>/<kbd>↓</kbd> arrows to navigate, <kbd>Space</kbd> to toggle checkboxes, and <kbd>Enter</kbd> to confirm.
- **Hostname Auto-Detection**: Queries `$(hostname)` with optional custom override.
- **Preset Selection & Pre-population**: Choose a starting preset (`Workstation`, `WSL Workstation`, `Headless`, `Minimal Shell`, or Custom), which automatically pre-populates the capabilities checklist for easy granular tweaking before proceeding.
- **AI Tool Integration**: Multi-select prompt for AI agents (`Antigravity`, `Claude Code`, or skip).
- **Git Identities**: When `git` is selected, set up the default identity and any additional ones, picking or generating GPG/SSH keys (see [Git Identities](#git-identities); `--identities` runs only this step).
- **Automated Bootstrap**: Writes the profile block into `config.yaml` and offers to execute `dotdrop install -a -f`.

Alternatively, you can manually add a profile matching `$(hostname)` to `config.yaml` and run `dotdrop install -a -f`.

### 2. Shell Startup & `$DOTFILES_DIR`

`~/.bashrc` sources `~/.bash_aliases`, which loads, in order:

1. `~/.config/rc/pre/*.sh` (early environment: `PATH`, platform tweaks, the recorded `$DOTFILES_DIR`)
2. Powerline: starts `powerline-daemon` and sources the bash bindings from the `powerline-status` uv tool venv (`$(uv tool dir)/powerline-status/lib/python3*/site-packages/powerline/bindings/bash/powerline.sh`; uv puts only executables in the venv's `bin/`, so the bindings aren't there)
3. Aliases and helper functions
4. `~/.config/rc/*.sh` (per-tool and per-host scripts)

On the first install of any profile that includes `bash`, the `persist_dotfiles_dir` action writes `export DOTFILES_DIR=<repo path>` to `~/.config/rc/pre/00-dotfiles.sh`. Later installs skip it. The `dotdrop` alias uses this to set `DOTDROP_CONFIG` (dotdrop only accepts `--cfg` after the subcommand, so the alias sets the environment variable instead), so `dotdrop` commands work from any directory. The alias falls back to `~/dotfiles` when the variable is unset. If you move the repo, delete `~/.config/rc/pre/00-dotfiles.sh` and reinstall to record the new location.

> The alias and `$DOTFILES_DIR` are only loaded in interactive shells. In scripts (or Claude Code `!` commands), run `dotdrop` from the repo root or pass `-c <repo>/config.yaml` after the subcommand.

### 3. Daily Workflow

Thanks to the `dotdrop` alias, these commands work from any directory once a profile has been installed:

```bash
# Compare local system files against the repository
dotdrop compare

# Apply changes and re-run profile actions
dotdrop install -a -f

# Check available profiles
dotdrop profiles

# Inspect dotfiles and actions attached to a specific profile
dotdrop detail -p wsl
dotdrop detail -p wezterm
```
