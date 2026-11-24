#!/usr/bin/env bash
# Record the dotfiles repo location once, so shells (bash_aliases sources
# ~/.config/rc/pre/*.sh) can find it without re-detecting it every time.
#
# Usage: persist-dotfiles-dir.sh <path to dotdrop config.yaml>
# Delete ~/.config/rc/pre/00-dotfiles.sh to re-record after moving the repo.
set -euo pipefail

out="$HOME/.config/rc/pre/00-dotfiles.sh"
[ -f "$out" ] && exit 0

if [ $# -ne 1 ] || [ ! -f "$1" ]; then
    echo "usage: ${0##*/} <path to config.yaml>" >&2
    exit 1
fi

dir="$(cd "$(dirname "$1")" && pwd)"
mkdir -p "$(dirname "$out")"
printf 'export DOTFILES_DIR=%q\n' "$dir" > "$out"
echo "recorded DOTFILES_DIR=$dir in $out"
