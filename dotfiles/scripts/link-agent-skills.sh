#!/usr/bin/env bash
set -euo pipefail

AGENT="${1:-}"
SOURCE="${HOME}/.config/agents/skills"
mkdir -p "$SOURCE"

case "$AGENT" in
  gemini)
    TARGET="${HOME}/.gemini/config/skills"
    mkdir -p "${HOME}/.gemini/config"
    ;;
  claude)
    TARGET="${HOME}/.claude/skills"
    mkdir -p "${HOME}/.claude"
    ;;
  *)
    echo "Usage: $0 {gemini|claude}" >&2
    exit 1
    ;;
esac

# If target exists and is a directory (not a symlink), safely rename to .bak
if [[ -e "$TARGET" && ! -L "$TARGET" ]]; then
  echo "[link-agent-skills] Moving existing directory $TARGET to ${TARGET}.bak..."
  mv "$TARGET" "${TARGET}.bak"
fi

ln -sfn "$SOURCE" "$TARGET"
echo "[link-agent-skills] Linked $TARGET -> $SOURCE"
