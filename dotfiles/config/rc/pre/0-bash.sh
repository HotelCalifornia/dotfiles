export BASH_SILENCE_DEPRECATION_WARNING=1

export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
export PATH="$HOME/.cargo/bin:$PATH"

alias ls="eza --icons"

alias ll="ls -laGF always"

bind "TAB: menu-complete"
bind "set show-all-if-ambiguous on"
bind "set menu-complete-display-prefix on"
