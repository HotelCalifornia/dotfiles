# Dotfiles

A modular, cross-platform dotfiles repository managed with [dotdrop](https://github.com/deadc0de6/dotdrop), configured for macOS, Linux, and Windows (WSL).

Features a declarative profile architecture, unified toolchain management via `uv`, `cargo`, and GitHub releases/AppImages, and cross-harness AI agent skill sharing across Antigravity/Gemini and Claude Code.

---

## Architecture Overview

```text
.
├── config.yaml                     # Dotdrop profile & action definitions
├── dotfiles/
│   ├── bash_aliases                # Shell aliases
│   ├── config/
│   │   ├── agents/                 # Canonical cross-harness AI agent configs
│   │   │   ├── rules/              # Modular agent rules (preferred-tools.md)
│   │   │   └── skills/             # Agent skills (terminal-pane-display)
│   │   ├── nvim/                   # Neovim configuration & plugins
│   │   ├── powerline/              # Powerline prompt themes & configuration
│   │   ├── rc/                     # Modular shell rc scripts (.wezterm-completion, vcpkg, mac)
│   │   ├── tools.toml              # Declarative manifest for CLI/GUI tools
│   │   ├── wezterm/                # WezTerm configuration with dynamic mixin loader
│   │   └── wezterm-mixins/         # Optional WezTerm mixins (e.g. wayland)
│   ├── local/share/nvim/site/      # Vim-plug manager
│   └── scripts/
│       ├── ensure-toolchains.sh    # Bootstraps uv & rustup/cargo non-interactively
│       ├── install-tools.py        # Multi-manager tool installer (uv, cargo, releases)
│       └── link-agent-skills.sh    # Symlinks canonical agent skills to Gemini & Claude
```

---

## Profiles

Profiles are decoupled into single-responsibility mixins that can be combined for any host or environment:

| Profile | Purpose | Key Dotfiles & Actions |
| :--- | :--- | :--- |
| **`bash`** | Core shell & prompt | Powerline themes, aliases, shell toolchain bootstrap (`powerline-status`). |
| **`neovim`** | Editor environment | `init.lua`, `coc-settings.json`, vim-plug, Neovim release installer. |
| **`wezterm`** | Terminal emulator | `wezterm.lua` (with mixin loader), completions, `wezterm` installer, `pokemon-terminal`, `terminal-pane-display` skill. |
| **`wsl`** | Windows Subsystem for Linux | Includes `[bash, neovim, user]` + `pokemon-terminal` (themes Windows Terminal, skips WezTerm GUI configs). |
| **`user`** | General CLI utilities | Installs modern Rust/Python/Go CLI tools (`dust`, `eza`, `bat`, `glow`, `termaid`, `ripgrep`). |
| **`gemini`** | Antigravity / Gemini CLI | Symlinks `~/.gemini/config/{skills,rules}` $\rightarrow$ `~/.config/agents/`. |
| **`claude`** | Claude Code | Symlinks `~/.claude/{skills,rules}` $\rightarrow$ `~/.config/agents/`. |
| **`wayland`** | Display server mixin | Deploys `~/.config/wezterm/mixins/wayland.lua` (`enable_wayland = false`). |
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
│   └── preferred-tools.md      # Enforces modern CLI tool preferences (rg, bat, eza, etc.)
└── skills/
    └── terminal-pane-display/
        ├── SKILL.md
        └── scripts/
            ├── display.sh
            ├── resize_pane.sh
            └── close_pane.sh
```

- When the `gemini` and `claude` profiles are active, dotdrop establishes symlinks:
  - **Gemini / Antigravity**:
    - `~/.gemini/config/skills` $\rightarrow$ `~/.config/agents/skills`
    - `~/.gemini/config/rules` $\rightarrow$ `~/.config/agents/rules`
  - **Claude Code**:
    - `~/.claude/skills` $\rightarrow$ `~/.config/agents/skills`
    - `~/.claude/rules` $\rightarrow$ `~/.config/agents/rules`
- Skills and rules authored once under `.config/agents/` are automatically discovered and enforced by both Antigravity and Claude Code. Claude Code supports `.claude/rules/` directly and adheres to `AGENTS.md` standards.

---

## Installation & Workflow

### 1. Initial Setup on a New Machine

```bash
# Clone the repository
git clone git@github.com:HotelCalifornia/dotfiles.git ~/dotfiles
cd ~/dotfiles

# Install dotdrop (if not already installed)
pip3 install --user dotdrop

# Install dotfiles and run bootstrap actions for your host profile
dotdrop install -p hotel-laptop-2.local -f
```

### 2. Daily Workflow

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
