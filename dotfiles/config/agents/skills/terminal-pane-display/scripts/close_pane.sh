#!/usr/bin/env bash
set -euo pipefail

WEZTERM_BIN=""
if command -v wezterm >/dev/null 2>&1; then
  WEZTERM_BIN="wezterm"
elif [[ -x "/Applications/WezTerm.app/Contents/MacOS/wezterm" ]]; then
  WEZTERM_BIN="/Applications/WezTerm.app/Contents/MacOS/wezterm"
else
  echo "Error: wezterm binary not found" >&2
  exit 1
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: close_pane.sh <pane_id>" >&2
  exit 1
fi

PANE_ID="$1"
"$WEZTERM_BIN" cli kill-pane --pane-id "$PANE_ID"
echo "Pane $PANE_ID closed."
