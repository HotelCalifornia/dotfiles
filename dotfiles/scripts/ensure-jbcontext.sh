#!/usr/bin/env bash
# Ensure JetBrains Air Context CLI (jbcontext) is installed non-interactively.
# Opt-in via the `jbcontext` profile; do not enable on CUI/restricted hosts.
set -euo pipefail

JBCONTEXT_BIN="${HOME}/.jbcontext/bin/jbcontext"
LOCAL_BIN="${HOME}/.local/bin"

if command -v jbcontext >/dev/null 2>&1 || [ -x "$JBCONTEXT_BIN" ]; then
    echo "[jbcontext] jbcontext is already installed."
else
    echo "[jbcontext] jbcontext not found; installing via JetBrains release installer..."
    curl -fsSL https://download.jetbrains.com/jetbrains-context/release/download-jbcontext.sh | bash
    echo "[jbcontext] jbcontext installed."
fi

if [ -x "$JBCONTEXT_BIN" ] && [ ! -e "${LOCAL_BIN}/jbcontext" ]; then
    mkdir -p "$LOCAL_BIN"
    ln -sfn "$JBCONTEXT_BIN" "${LOCAL_BIN}/jbcontext"
    echo "[jbcontext] Linked ${LOCAL_BIN}/jbcontext -> ${JBCONTEXT_BIN}"
fi
