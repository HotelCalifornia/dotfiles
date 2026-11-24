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

if [[ $# -lt 2 ]]; then
  echo "Usage: resize_pane.sh <pane_id> <target_width_in_columns>" >&2
  echo "Example: resize_pane.sh 1 125" >&2
  exit 1
fi

PANE_ID="$1"
TARGET_COLS="$2"

# Get current pane width from wezterm cli list
PANE_INFO=$("$WEZTERM_BIN" cli list | awk -v pid="$PANE_ID" '$3 == pid {print $5}')

if [[ -z "$PANE_INFO" ]]; then
  echo "Error: Pane $PANE_ID not found in active wezterm panes" >&2
  exit 1
fi

CURRENT_COLS=$(echo "$PANE_INFO" | cut -d'x' -f1)

DELTA=$((TARGET_COLS - CURRENT_COLS))

if [[ $DELTA -gt 0 ]]; then
  # Expand to the left (assuming right-split pane)
  "$WEZTERM_BIN" cli adjust-pane-size --pane-id "$PANE_ID" --amount "$DELTA" Left
  echo "Resized pane $PANE_ID from ${CURRENT_COLS} to ${TARGET_COLS} columns (+${DELTA})."
elif [[ $DELTA -lt 0 ]]; then
  # Shrink to the right
  SHRINK=$(( -DELTA ))
  "$WEZTERM_BIN" cli adjust-pane-size --pane-id "$PANE_ID" --amount "$SHRINK" Right
  echo "Resized pane $PANE_ID from ${CURRENT_COLS} to ${TARGET_COLS} columns (-${SHRINK})."
else
  echo "Pane $PANE_ID is already ${CURRENT_COLS} columns wide."
fi
