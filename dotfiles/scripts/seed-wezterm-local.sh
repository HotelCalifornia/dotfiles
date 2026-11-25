#!/usr/bin/env bash
# Seed ~/.config/wezterm/wezterm.lua: the machine-local WezTerm entry point that
# loads the dotdrop-managed dotfiles.lua. dotdrop never manages this file, so
# tools like `pokemon` can rewrite it freely. An older full config (from before
# the split) is kept as wezterm.lua.pre-split and its background carried over
# by pokemon on its next run.
set -euo pipefail
dir="${XDG_CONFIG_HOME:-$HOME/.config}/wezterm"
local_cfg="$dir/wezterm.lua"
mkdir -p "$dir"
if [ -f "$local_cfg" ] && grep -q "require('dotfiles')" "$local_cfg"; then
    exit 0
fi
if [ -f "$local_cfg" ]; then
    mv "$local_cfg" "$local_cfg.pre-split"
    echo "seed-wezterm-local: moved old config to $local_cfg.pre-split"
fi
cat > "$local_cfg" <<'LUA'
-- Local WezTerm config (not managed by dotdrop). Settings here override the
-- shared config in dotfiles.lua; `pokemon` writes its background here.
return require('dotfiles')({
})
LUA
echo "seed-wezterm-local: created $local_cfg"
