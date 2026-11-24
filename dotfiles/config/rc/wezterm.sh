if [ -n "$WEZTERM_EXECUTABLE_DIR" ]; then
	alias wezterm="$WEZTERM_EXECUTABLE_DIR/wezterm"
elif [ -x "/Applications/WezTerm.app/Contents/MacOS/wezterm" ] && ! command -v wezterm >/dev/null 2>&1; then
	alias wezterm="/Applications/WezTerm.app/Contents/MacOS/wezterm"
fi

if [ -f "${XDG_CONFIG_HOME:-$HOME/.config}/rc/.wezterm-completion" ]; then
	source "${XDG_CONFIG_HOME:-$HOME/.config}/rc/.wezterm-completion"
elif [ -f "$HOME/.wezterm-completion" ]; then
	source "$HOME/.wezterm-completion"
fi

woman() {
	wezterm cli split-pane --right -- man $* > /dev/null 2>&1
}

nvs() {
	wezterm cli split-pane --right -- nvim $* > /dev/null 2>&1
}

hl() {
	highlight -O truecolor --syntax $1 ${@:2}
}

nvc() {
	wezterm cli split-pane --top --percent 90 --cwd $(pwd) -- nvim .
}
