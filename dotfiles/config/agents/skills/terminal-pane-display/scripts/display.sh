#!/usr/bin/env bash
set -euo pipefail

# Auto-detect WezTerm binary
WEZTERM_BIN=""
if command -v wezterm >/dev/null 2>&1; then
  WEZTERM_BIN="wezterm"
elif [[ -x "/Applications/WezTerm.app/Contents/MacOS/wezterm" ]]; then
  WEZTERM_BIN="/Applications/WezTerm.app/Contents/MacOS/wezterm"
else
  echo "Error: wezterm binary not found in PATH or /Applications/WezTerm.app" >&2
  exit 1
fi

# Locate bat binary
BAT_BIN=""
if command -v bat >/dev/null 2>&1; then
  BAT_BIN="bat"
elif [[ -x "${HOME}/.cargo/bin/bat" ]]; then
  BAT_BIN="${HOME}/.cargo/bin/bat"
fi

# Locate glow binary
GLOW_BIN=""
if command -v glow >/dev/null 2>&1; then
  GLOW_BIN="glow"
elif [[ -x "/opt/homebrew/bin/glow" ]]; then
  GLOW_BIN="/opt/homebrew/bin/glow"
elif [[ -x "/usr/local/bin/glow" ]]; then
  GLOW_BIN="/usr/local/bin/glow"
fi

# Locate termaid script
TERMAID_SCRIPT=""
if [[ -x "${HOME}/.gemini/config/plugins/termaid/scripts/termaid.py" ]]; then
  TERMAID_SCRIPT="${HOME}/.gemini/config/plugins/termaid/scripts/termaid.py"
elif command -v termaid >/dev/null 2>&1; then
  TERMAID_SCRIPT="termaid"
fi

# Sizing defaults:
# Visual media default: 26% (~51-55 columns)
# Markdown document default: 84 columns (glow default wrap is 80 cols + padding)
# Code display default: 125 columns (120 code columns + bat gutter)
DIRECTION="--right"
PERCENT="26"
EXPLICIT_CELLS=""
TARGET_PANE=""
EXISTING_PANE=""
TITLE=""
IMAGE_PATH=""
CODE_FILE=""
TEXT_FILE=""
COMMAND=""
KEEP_OPEN=1

usage() {
  cat << 'EOF'
Usage: display.sh [options]

Content Options:
  --image <path>          Display image via wezterm imgcat (defaults to ~26% width)
  --code <path>           Display formatted code via bat (guarantees >=120 cols without wrap)
  --text <path>           Display general text or markdown file
  --command <cmd>         Execute an arbitrary shell command in the pane

Sizing & Layout Options:
  --direction <dir>       Split direction: right, bottom, left, top (default: right)
  --percent <int>         Split percentage size (default: 26% for visual media)
  --cells <int>           Explicit column/row size in cells (e.g., 125 for 120-col code)
  --pane-id <id>          Base pane ID to split from (auto-detected if omitted)
  --update-pane <id>      Update an existing pane instead of creating a new split
  --no-keep-open          Close pane immediately after command completes
  -h, --help              Show this help
EOF
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --image) IMAGE_PATH="$2"; shift 2 ;;
    --code) CODE_FILE="$2"; shift 2 ;;
    --text) TEXT_FILE="$2"; shift 2 ;;
    --command) COMMAND="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --direction)
      case "$2" in
        right) DIRECTION="--right" ;;
        bottom) DIRECTION="--bottom" ;;
        left) DIRECTION="--left" ;;
        top) DIRECTION="--top" ;;
        *) echo "Unknown direction: $2" >&2; exit 1 ;;
      esac
      shift 2
      ;;
    --percent) PERCENT="$2"; shift 2 ;;
    --cells) EXPLICIT_CELLS="$2"; shift 2 ;;
    --pane-id) TARGET_PANE="$2"; shift 2 ;;
    --update-pane) EXISTING_PANE="$2"; shift 2 ;;
    --no-keep-open) KEEP_OPEN=0; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default sizing rules:
# 1. Code files (non-markdown) -> at least 125 columns (120 code cols + line numbers/gutter)
# 2. Markdown files rendered with glow -> 84 columns (glow renders at 80 cols max width)
IS_MARKDOWN=0
if [[ "$TEXT_FILE" =~ \.(md|markdown)$ || "$CODE_FILE" =~ \.(md|markdown)$ ]]; then
  IS_MARKDOWN=1
fi

if [[ -z "$EXPLICIT_CELLS" ]]; then
  if [[ -n "$CODE_FILE" && $IS_MARKDOWN -eq 0 ]]; then
    EXPLICIT_CELLS="125"
  elif [[ $IS_MARKDOWN -eq 1 ]]; then
    EXPLICIT_CELLS="84"
  fi
fi

# Auto-detect base pane if needed
if [[ -z "$TARGET_PANE" && -z "$EXISTING_PANE" ]]; then
  if [[ -n "${WEZTERM_PANE:-}" ]]; then
    TARGET_PANE="$WEZTERM_PANE"
  else
    TARGET_PANE=$("$WEZTERM_BIN" cli list 2>/dev/null | awk 'NR>1 && $6 ~ /agy/ {print $3; exit}')
    if [[ -z "$TARGET_PANE" ]]; then
      TARGET_PANE=$("$WEZTERM_BIN" cli list 2>/dev/null | awk 'NR==2 {print $3}')
    fi
  fi
fi

# Pre-determine column width for label truncation in the generated script.
# For --update-pane: we know (or set) the exact target width.
# For --cells: the new pane will be exactly that many cols.
# For --percent: estimate from the source pane's current width.
ACTIVE_PANE_TARGET="${EXISTING_PANE:-$TARGET_PANE}"
PANE_COLS=""
if [[ -n "$EXISTING_PANE" ]]; then
  # Auto-resize existing pane based on content type if no explicit cells requested:
  if [[ -n "$EXPLICIT_CELLS" ]]; then
    "$SCRIPT_DIR/resize_pane.sh" "$EXISTING_PANE" "$EXPLICIT_CELLS" >/dev/null 2>&1 || true
    PANE_COLS="$EXPLICIT_CELLS"
  elif [[ -n "$CODE_FILE" && $IS_MARKDOWN -eq 0 ]]; then
    "$SCRIPT_DIR/resize_pane.sh" "$EXISTING_PANE" 125 >/dev/null 2>&1 || true
    PANE_COLS="125"
  elif [[ $IS_MARKDOWN -eq 1 ]]; then
    "$SCRIPT_DIR/resize_pane.sh" "$EXISTING_PANE" 84 >/dev/null 2>&1 || true
    PANE_COLS="84"
  elif [[ -n "$IMAGE_PATH" ]]; then
    "$SCRIPT_DIR/resize_pane.sh" "$EXISTING_PANE" 51 >/dev/null 2>&1 || true
    PANE_COLS="51"
  else
    # Read the existing pane's current width
    PANE_COLS=$("$WEZTERM_BIN" cli list 2>/dev/null | awk -v pid="$EXISTING_PANE" '$3 == pid {split($5, a, "x"); print a[1]}')
  fi
fi

if [[ -z "$PANE_COLS" ]]; then
  if [[ -n "$EXPLICIT_CELLS" ]]; then
    # --cells gives us an exact column count for the new pane
    PANE_COLS="$EXPLICIT_CELLS"
  elif [[ -n "$TARGET_PANE" ]]; then
    # --percent split: estimate new pane width as (source_cols * PERCENT / 100)
    SRC_COLS=$("$WEZTERM_BIN" cli list 2>/dev/null | awk -v pid="$TARGET_PANE" '$3 == pid {split($5, a, "x"); print a[1]}')
    if [[ -n "$SRC_COLS" && "$SRC_COLS" -gt 0 ]]; then
      PANE_COLS=$(( SRC_COLS * PERCENT / 100 ))
    fi
  fi
fi
PANE_COLS="${PANE_COLS:-51}"

# Build execution script
TMP_SCRIPT=$(mktemp /tmp/wezterm_display_XXXXXX)
mv "$TMP_SCRIPT" "${TMP_SCRIPT}.sh"
TMP_SCRIPT="${TMP_SCRIPT}.sh"
cat << 'HEADER' > "$TMP_SCRIPT"
#!/usr/bin/env bash
clear

# PS1-style label renderer using ANSI escape codes
# Format: [viewer] <text> ❯   (cyan / blue / green — matches the viewer PS1 palette)
# PANE_COLS is baked in at generation time (known before the PTY handshake completes),
# with a live tput fallback for any edge cases.
HEADER

cat << EOF >> "$TMP_SCRIPT"
_BAKED_COLS=${PANE_COLS}
TERMAID_SCRIPT="${TERMAID_SCRIPT}"
GLOW_BIN="${GLOW_BIN}"
BAT_BIN="${BAT_BIN}"
EOF

cat << 'HEADER_BODY' >> "$TMP_SCRIPT"
print_label() {
  local text="$1"
  local cols="${_BAKED_COLS}"
  [[ -z "$cols" || "$cols" -le 0 ]] && cols=$(tput cols 2>/dev/null || echo 80)
  # prefix "[viewer] " = 9 display cols; suffix " ❯" = 2 display cols → 11 reserved
  local max_text=$(( cols - 11 ))
  if [[ ${#text} -gt $max_text && $max_text -gt 0 ]]; then
    text="${text:0:$max_text}"
  fi
  printf '\033[36m[viewer]\033[0m \033[34m%s\033[0m \033[32m❯\033[0m\n' "$text"
}

# Helper to render markdown through termaid (rendering mermaid blocks as ASCII/box-drawing text)
# before passing to glow. Box-drawing characters are wrapped in fenced code blocks so glow preserves alignment.
render_markdown_file() {
  local target_file="$1"
  local termaid_bin="${TERMAID_SCRIPT}"
  local glow_bin="${GLOW_BIN}"
  local bat_bin="${BAT_BIN}"
  local cols="${_BAKED_COLS}"
  [[ -z "$cols" || "$cols" -le 0 ]] && cols=$(tput cols 2>/dev/null || echo 80)
  local glow_width=$(( cols - 2 ))
  [[ $glow_width -lt 40 ]] && glow_width=40

  if [[ -n "$glow_bin" ]]; then
    if [[ -n "$termaid_bin" ]] && command -v python3 >/dev/null 2>&1; then
      python3 - "$target_file" "$termaid_bin" << 'PYEOF' | (
import sys, subprocess, re

file_path = sys.argv[1]
termaid_cmd = sys.argv[2]

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

def replace_mermaid(match):
    code = match.group(1).strip()
    try:
        res = subprocess.run(
            ["python3", termaid_cmd, "--width", "80"],
            input=code,
            text=True,
            capture_output=True,
            check=True
        )
        return "```text\n" + res.stdout.rstrip() + "\n```"
    except Exception:
        return match.group(0)

pattern = re.compile(r'```mermaid\s*\n(.*?)\n```', re.DOTALL)
sys.stdout.write(pattern.sub(replace_mermaid, content))
PYEOF
        if [[ -n "$bat_bin" ]]; then
          PAGER="$bat_bin --style=plain --paging=never" "$glow_bin" -w "$glow_width" -p -
        else
          "$glow_bin" -w "$glow_width" -p -
        fi
      )
    else
      if [[ -n "$bat_bin" ]]; then
        PAGER="$bat_bin --style=plain --paging=never" "$glow_bin" -w "$glow_width" -p "$target_file"
      else
        "$glow_bin" -w "$glow_width" -p "$target_file"
      fi
    fi
  elif [[ -n "$bat_bin" ]]; then
    "$bat_bin" --style=plain --paging=never "$target_file"
  else
    cat "$target_file"
  fi
}
HEADER_BODY

if [[ -n "$TITLE" ]]; then
  cat << EOF >> "$TMP_SCRIPT"
print_label "$TITLE"
EOF
fi

if [[ -n "$IMAGE_PATH" ]]; then
  cat << EOF >> "$TMP_SCRIPT"
"$WEZTERM_BIN" imgcat "$IMAGE_PATH"
EOF
fi

if [[ -n "$CODE_FILE" ]]; then
  cat << EOF >> "$TMP_SCRIPT"
if [[ "$CODE_FILE" =~ \.(md|markdown)$ ]]; then
  render_markdown_file "$CODE_FILE"
elif [[ -n "$BAT_BIN" ]]; then
  "$BAT_BIN" --style=numbers,changes,header --color=always --paging=never "$CODE_FILE"
else
  cat "$CODE_FILE"
fi
EOF
fi

if [[ -n "$TEXT_FILE" ]]; then
  cat << EOF >> "$TMP_SCRIPT"
if [[ "$TEXT_FILE" =~ \.(md|markdown)$ ]]; then
  render_markdown_file "$TEXT_FILE"
elif [[ -n "$BAT_BIN" ]]; then
  "$BAT_BIN" --style=plain --paging=never "$TEXT_FILE"
elif [[ -n "$GLOW_BIN" ]]; then
  "$GLOW_BIN" -p "$TEXT_FILE"
else
  cat "$TEXT_FILE"
fi
EOF
fi

if [[ -n "$COMMAND" ]]; then
  cat << EOF >> "$TMP_SCRIPT"
$COMMAND
EOF
fi

if [[ $KEEP_OPEN -eq 1 ]]; then
  cat << 'FOOTER' >> "$TMP_SCRIPT"
echo ""
print_label "Pane is active — close with agent command."

# Non-interactive keep-alive: no shell prompt, no input loop
# (tail -f /dev/null: zero CPU, works on macOS + Linux; sleep infinity fails on macOS)
tail -f /dev/null
FOOTER
fi

chmod +x "$TMP_SCRIPT"

if [[ -n "$EXISTING_PANE" ]]; then
  if ! "$WEZTERM_BIN" cli list 2>/dev/null | awk -v pid="$EXISTING_PANE" '$3 == pid {found=1} END {exit !found}'; then
    EXISTING_PANE=""
  fi
fi

if [[ -n "$EXISTING_PANE" ]]; then
  # Interrupt whatever is currently running in the pane (e.g. tail -f /dev/null), clear, and run new script
  printf '\x03\x03' | "$WEZTERM_BIN" cli send-text --pane-id "$EXISTING_PANE" --no-paste
  sleep 0.1
  "$WEZTERM_BIN" cli send-text --pane-id "$EXISTING_PANE" --no-paste "$TMP_SCRIPT"$'\n'
  echo "$EXISTING_PANE"
else
  SIZE_ARG="--percent $PERCENT"
  if [[ -n "$EXPLICIT_CELLS" ]]; then
    SIZE_ARG="--cells $EXPLICIT_CELLS"
  fi

  SPLIT_ARGS=("$DIRECTION")
  if [[ -n "$TARGET_PANE" ]]; then
    SPLIT_ARGS+=(--pane-id "$TARGET_PANE")
  fi
  if [[ -n "$EXPLICIT_CELLS" ]]; then
    SPLIT_ARGS+=(--cells "$EXPLICIT_CELLS")
  else
    SPLIT_ARGS+=(--percent "$PERCENT")
  fi

  NEW_PANE=$("$WEZTERM_BIN" cli split-pane "${SPLIT_ARGS[@]}")
  sleep 0.2
  "$WEZTERM_BIN" cli send-text --pane-id "$NEW_PANE" --no-paste "$TMP_SCRIPT"$'\n'
  echo "$NEW_PANE"
fi
