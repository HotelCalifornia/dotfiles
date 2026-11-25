---
name: wezterm-local-config
description: >-
  Change WezTerm settings on this machine without breaking the dotdrop split: shared
  font/colors/mixins versus machine-local overrides, Pokémon backgrounds, reseeding the
  local entry point, or debugging a config that no longer loads. Use whenever the user
  asks to change their terminal theme, background, font, or WezTerm config file.
---

# WezTerm Configuration

WezTerm is split into a **managed shared module** and an **unmanaged local entry
point**:

| File | Owner | Contents |
| --- | --- | --- |
| `dotfiles/config/wezterm/dotfiles.lua` → `~/.config/wezterm/dotfiles.lua` | dotdrop (`d_wezterm`) | Shared base: font, color scheme, initial size, mixin loader |
| `~/.config/wezterm/wezterm.lua` | nobody (local) | Machine overrides; `pokemon` rewrites its background |
| `~/.config/wezterm/mixins/*.lua` | profile-dependent | Optional mixins (Wayland ships `wayland.lua`) |

Precedence is **base < mixins < local overrides**.

## Which file to edit

- **Applies to every machine** (font, palette, keybindings, tab bar): edit
  `dotfiles/config/wezterm/dotfiles.lua`, then
  `dotdrop install -f d_wezterm`.
- **This machine only** (background image, display/GPU quirks, local paths): edit
  `~/.config/wezterm/wezterm.lua` directly. It is not managed by dotdrop, so no
  install is needed and `pokemon` can rewrite it safely.
- **Platform mixin** (Wayland, etc.): add a file under
  `dotfiles/config/wezterm-mixins/` plus a dotfile entry targeting
  `~/.config/wezterm/mixins/<name>.lua`, and attach it to the relevant profile
  (`wayland` is the existing example).

Never put machine-specific paths or images in the shared module; they would be
deployed everywhere.

## Local entry point

The expected shape is:

```lua
-- Local WezTerm config (not managed by dotdrop). Settings here override the
-- shared config in dotfiles.lua; `pokemon` writes its background here.
return require('dotfiles')({
    -- overrides here
})
```

It must **call** the shared module with a table, not `return` a bare table, or
the shared defaults disappear. `pokemon` edits the table passed to that call.

### Seeding and reseeding

`seed-wezterm-local.sh` runs as a `wezterm` profile action. It is idempotent: if
the local file already contains `require('dotfiles')` it exits. Otherwise it
moves the existing file to `~/.config/wezterm/wezterm.lua.pre-split` and writes
the stub above.

Consequences:

- A pre-split config can lose its Pokémon background until `pokemon` runs again.
  Recover it from the `.pre-split` file if needed.
- To reseed manually: `bash ~/dotfiles/dotfiles/scripts/seed-wezterm-local.sh`.
- If the local file is deleted, the next install (or the seed action) recreates
  the stub.

## Pokémon background

`pokemon` is installed from the fork in `tools.toml` (group `terminal`, uv) and
edits `~/.config/wezterm/wezterm.lua` in place: it adds a `background` table to
the overrides. Run `pokemon` after reseeding to restore or change the image.
Because the file is unmanaged, this causes no dotdrop drift.

## Mixins

`dotfiles.lua` loads `wezterm.config_dir/mixins/*.lua` and calls a mixin's
function with the config, or merges a returned table (shallow). The Wayland
mixin is deployed by the `wayland` profile. Order is glob order, so name mixins
accordingly; local overrides still win.

## Reload and validate

- Reload WezTerm: `Cmd+R` on macOS, `Ctrl+Shift+R` elsewhere.
- Config errors: open the debug overlay (`Ctrl+Shift+L`) and check the error
  banner/log.
- Validate from a shell without opening a window:

  ```bash
  # macOS
  /Applications/WezTerm.app/Contents/MacOS/wezterm \
    --config-file ~/.config/wezterm/wezterm.lua show-keys >/dev/null
  # Linux
  wezterm --config-file ~/.config/wezterm/wezterm.lua show-keys >/dev/null
  ```

  Exit code 0 means the config parsed. `ls-fonts` is useful for font questions.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Shared font/colors stopped applying | local file returns a bare table or doesn't call `require('dotfiles')`; reseed |
| Background vanished | seed moved the old config to `.pre-split`; rerun `pokemon` |
| `dotdrop compare` reports wezterm drift | only `dotfiles.lua` is managed; the local `wezterm.lua` should not appear |
| Mixin not applied | file not in `~/.config/wezterm/mixins/`, or profile not deployed; check `dotdrop detail` |
| Config error after editing | validate with `show-keys`; mind Lua commas/returns |

Do not add `~/.config/wezterm/wezterm.lua` to `config.yaml`. The entire point of
the split is that it stays outside dotdrop.
