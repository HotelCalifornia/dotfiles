---
name: terminal-pane-display
description: >-
  Splits a terminal pane in WezTerm to display images, media, code diffs, markdown documents,
  or arbitrary command outputs side-by-side with the active session. Use whenever the user
  asks to view an image, render visual media in the terminal, split an output window,
  or keep a persistent auxiliary display pane open.
---

# Terminal Pane Display Skill

This skill allows Antigravity to split an active WezTerm window into side-by-side or stacked panes and display rich content—specifically high-resolution images via `wezterm imgcat`, syntax-highlighted code via `bat`, markdown docs, or live command outputs—while keeping the pane alive and allowing dynamic width adjustments on the fly.

---

## Sizing & Layout Rules

1. **Visual Media & Auxiliary Outputs (Default < 50%):**  
   * For images, diagrams, or general auxiliary monitoring, default to a compact split percentage **< 50%** (specifically **~26% / ~51–55 columns**). This leaves the primary coding/agent pane unobstructed.
2. **Code Display Guarantee (120+ Columns Without Wrapping):**  
   * If the primary use case is displaying code, scripts, or diffs, the pane **must** accommodate at least **120 columns without line wrapping**, regardless of other layout preferences.
   * Passing `--code <file>` automatically allocates `--cells 125` (120 code columns + 5 columns for `bat` line numbers and gutter borders).
3. **On-the-Fly Dynamic Resizing:**  
   * Pane widths can be adjusted dynamically at any time using `scripts/resize_pane.sh` or `wezterm cli adjust-pane-size`. Switching an existing pane from an image to code automatically expands it to 125 columns.

---

## Helper Scripts

| Script | Purpose |
| :--- | :--- |
| [`scripts/display.sh`](./scripts/display.sh) | Splits a pane and displays an image, `bat`-formatted code, or command output. Returns the new `PANE_ID`. |
| [`scripts/resize_pane.sh`](./scripts/resize_pane.sh) | Adjusts the target pane to an exact column width on the fly (`resize_pane.sh <PANE_ID> <COLS>`). |
| [`scripts/close_pane.sh`](./scripts/close_pane.sh) | Closes a target pane cleanly by its `PANE_ID`. |

---

## Workflows & Usage

### Sizing Defaults
- **Images & Aux Panels**: Default to `~26%` width (~51-55 columns).
- **Markdown Documents**: Default to `84` columns (matches `glow`'s default 80-column rendering width plus margins).
- **Source Code**: Default to `125` columns (guarantees 120-column unwrapped lines plus `bat` line numbers and Git gutter).

### 1. Display Formatted Code via `bat` (>=120 Columns Unwrapped)

Displays syntax-highlighted code with line numbers, Git changes, and headers, sized at $\ge 125$ cells:

```bash
DISPLAY_SCRIPT="${HOME}/.config/agents/skills/terminal-pane-display/scripts/display.sh"

NEW_PANE_ID=$("$DISPLAY_SCRIPT" \
  --code "/path/to/source.rs" \
  --title "Source Implementation" \
  --direction right)

echo "Code displayed in Pane: $NEW_PANE_ID"
```

### 2. Display Markdown via `glow` + `termaid` + `bat` Pager (84 Columns)

- Preprocesses any ```mermaid blocks in the markdown document by piping them through `termaid --width 80` to convert diagrams into box-drawing Unicode text.
- Wraps the rendered diagrams in fenced code blocks so `glow` preserves alignment and box geometry.
- Passes the rendered document through `glow -p` with `PAGER="bat --style=plain --paging=never"`.
- Sized automatically to 84 columns:

```bash
DISPLAY_SCRIPT="${HOME}/.config/agents/skills/terminal-pane-display/scripts/display.sh"

NEW_PANE_ID=$("$DISPLAY_SCRIPT" \
  --text "/path/to/notes.md" \
  --title "Rendered Document" \
  --direction right)
```

### 3. Display an Image (Compact ~26% Split)

Opens a compact split (< 50%) matching the preferred visual width:

```bash
NEW_PANE_ID=$("$DISPLAY_SCRIPT" \
  --image "/path/to/diagram.png" \
  --title "Architecture Overview" \
  --direction right \
  --percent 26)
```

### 3. Dynamically Resize an Open Pane On the Fly

Adjust the pane to any width without closing or reloading:

```bash
RESIZE_SCRIPT="${HOME}/.config/agents/skills/terminal-pane-display/scripts/resize_pane.sh"

# Expand pane to 125 columns for wide code viewing
"$RESIZE_SCRIPT" 1 125

# Return pane to compact 51-column width for visual media
"$RESIZE_SCRIPT" 1 51
```

Or via direct WezTerm CLI:
```bash
# Expand right-split pane by 30 columns to the left
wezterm cli adjust-pane-size --pane-id 1 --amount 30 Left

# Shrink right-split pane by 30 columns to the right
wezterm cli adjust-pane-size --pane-id 1 --amount 30 Right
```

### 4. Update an Existing Pane

Push new content into an active pane (automatically handles width adjustments if switching between code and images):

```bash
# Push code into existing pane (auto-expands to >=125 cols if needed)
"$DISPLAY_SCRIPT" \
  --code "/path/to/script.sh" \
  --update-pane 1

# Push image into existing pane (auto-scales back to compact width)
"$DISPLAY_SCRIPT" \
  --image "/path/to/result.jpg" \
  --update-pane 1
```

### 5. Labels and Keep-Alive

The `print_label` function renders PS1-style banners:
```
[viewer] <title text> ❯
```
Label text is **automatically truncated** to fit the pane width. The column count is baked into the generated script at call time using arithmetic from the source pane's actual size and the requested `--percent` or `--cells` value — avoiding a race with `tput cols` querying before the PTY handshake completes.

The pane is kept alive non-interactively via `tail -f /dev/null` (zero CPU; works on macOS and Linux — `sleep infinity` is not supported on macOS).

### 6. Close the Pane When Finished

```bash
CLOSE_SCRIPT="${HOME}/.config/agents/skills/terminal-pane-display/scripts/close_pane.sh"
"$CLOSE_SCRIPT" 1
```
