#!/usr/bin/env bash
# Ensure uv and rust/cargo toolchains are installed non-interactively.
set -euo pipefail

# 1. Ensure uv is installed
if command -v uv >/dev/null 2>&1 || [ -x "$HOME/.local/bin/uv" ]; then
    echo "[toolchains] uv is already installed."
else
    echo "[toolchains] uv not found; installing via official standalone installer..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "[toolchains] uv successfully installed to ~/.local/bin/uv."
fi

# 2. Ensure rustup/cargo is installed
if command -v cargo >/dev/null 2>&1 || [ -x "$HOME/.cargo/bin/cargo" ]; then
    echo "[toolchains] cargo is already installed."
else
    echo "[toolchains] cargo not found; installing Rust via rustup (non-interactive)..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile default
    echo "[toolchains] Rust/cargo successfully installed to ~/.cargo/bin/cargo."
fi
