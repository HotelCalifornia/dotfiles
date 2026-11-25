#!/usr/bin/env bash
set -euo pipefail

AGENT="${1:-}"
SKILLS_SRC="${HOME}/.config/agents/skills"
RULES_SRC="${HOME}/.config/agents/rules"
mkdir -p "$SKILLS_SRC"
mkdir -p "$RULES_SRC"

link_path() {
  local src="$1"
  local dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [[ -e "$dst" && ! -L "$dst" ]]; then
    echo "[link-agent-skills] Moving existing directory/file $dst to ${dst}.bak..."
    mv "$dst" "${dst}.bak"
  fi
  ln -sfn "$src" "$dst"
  echo "[link-agent-skills] Linked $dst -> $src"
}

case "$AGENT" in
  gemini)
    link_path "$SKILLS_SRC" "${HOME}/.gemini/config/skills"
    link_path "$RULES_SRC" "${HOME}/.gemini/config/rules"
    ;;
  claude)
    link_path "$SKILLS_SRC" "${HOME}/.claude/skills"
    link_path "$RULES_SRC" "${HOME}/.claude/rules"
    ;;
  opencode)
    # OpenCode reads the vendor-neutral ~/.agents/skills compatibility source.
    link_path "$SKILLS_SRC" "${HOME}/.agents/skills"
    ;;
  *)
    echo "Usage: $0 {gemini|claude|opencode}" >&2
    exit 1
    ;;
esac
