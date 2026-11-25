# Node.js via fnm (installed by the neovim profile; coc.nvim needs node).
# --use-on-cd switches versions when entering a directory with .nvmrc/.node-version.
_fnm_bin="$(command -v fnm || echo "$HOME/.cargo/bin/fnm")"
if [ -x "$_fnm_bin" ]; then
    eval "$("$_fnm_bin" env --use-on-cd --shell bash)"
fi
unset _fnm_bin
