# If not running interactively, don't do anything (leave this at the top of this file)
[[ $- != *i* ]] && return

# All the default Omarchy aliases and functions
# (don't mess with these directly, just overwrite them here!)
source ~/.local/share/omarchy/default/bash/rc

# Append history instead of overwriting it (atomic writes)
shopt -s histappend

# Command completion suggestions
for completion in ~/.local/share/bash-completion/*; do
    [[ -f "$completion" ]] && source "$completion"
done

# Add your own exports, aliases, and functions here.
#
# Make an alias for invoking commands you use constantly
# alias p='python'

# aliases
alias claer='clear'
alias striprefs="perl -0777 -i -pe 's/\s*:contentReference\[oaicite:\d+\]\{index=\d+\}//g'"
alias ctx="xctx"
alias ncat="xcat"

# utility functions
detach() {
  if [ "$#" -eq 0 ]; then
    echo "Usage: detach <command> [args...]"
    return 1
  fi

  local cmd="$1"
  local name log
  name="$(basename -- "$cmd")"
  log="/tmp/${name}.log"

  setsid "$@" </dev/null >>"$log" 2>&1 &
  echo "Detached: $*"
  echo "Log: $log"
}

terminal-copy() {
    if [ -n "$HERDR_PANE_ID" ]; then
        herdr pane read "$HERDR_PANE_ID" --source recent-unwrapped --lines 100000 | wl-copy
    elif [ -n "$KITTY_WINDOW_ID" ]; then
        kitty @ get-text --extent=all | wl-copy
    else
        echo "terminal-copy: not running inside Kitty or Herdr" >&2
        return 1
    fi
}

# loading modular shell configs
if [ -d "$HOME/.bashrc.d" ]; then
  for f in "$HOME"/.bashrc.d/*.sh; do
    [ -e "$f" ] || continue
    . "$f"
  done
fi
