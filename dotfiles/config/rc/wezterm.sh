alias wezterm=$WEZTERM_EXECUTABLE_DIR/wezterm

source $HOME/.wezterm-completion

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
