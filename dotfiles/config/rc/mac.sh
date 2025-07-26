export BASH_SILENCE_DEPRECATION_WARNING=1

export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"

alias ls="exa --icons"

alias ll="ls -laFG"

bind "TAB: menu-complete"
bind "set show-all-if-ambiguous on"
bind "set menu-complete-display-prefix on"
