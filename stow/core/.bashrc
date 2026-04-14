# If not running interactively, don't do anything (leave this at the top of this file)
[[ $- != *i* ]] && return

# All the default Omarchy aliases and functions
# (don't mess with these directly, just overwrite them here!)
source ~/.local/share/omarchy/default/bash/rc

# Add your own exports, aliases, and functions here.
#
# Make an alias for invoking commands you use constantly
# alias p='python'

# aliases
alias claer='clear'
alias terminal-copy='kitty @ get-text --extent=all | wl-copy'

alias download-opus='yt-dlp -f "bestaudio[ext=webm]/bestaudio" \
  --extract-audio --audio-format opus --audio-quality 0 \
  --embed-metadata --embed-thumbnail \
  --parse-metadata "%(title)s:%(meta_title)s" \
  -o "%(title)s.%(ext)s"'

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

# loading modular shell configs
if [ -d "$HOME/.bashrc.d" ]; then
  for f in "$HOME"/.bashrc.d/*.sh; do
    [ -e "$f" ] || continue
    . "$f"
  done
fi
