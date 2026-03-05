#!/bin/bash
set -euo pipefail

SYNC_DIR="$HOME/Syncthing"
ITSTEP_MEDIA="$HOME/Syncthing/ITStep/Media"

# 1) Get an Obsidian window title (focused or not)
title="$(
  hyprctl clients -j \
    | jq -r '.[] | select(.class == "obsidian") | .title' \
    | head -n 1
)"

# If Obsidian isn't open, exit silently
[[ -n "${title:-}" && "$title" != "null" ]] || exit 1

# 2) Trim the last two " - ..." segments from the right
trimmed="$(printf '%s' "$title" | sed 's/ - [^-]* - [^-]*$//')"

# 3) Target markdown filename
target_md="${trimmed}.md"

# 4) Find the first matching markdown file
note_path="$(
  find "$SYNC_DIR" -type f -name "$target_md" -print -quit 2>/dev/null || true
)"

# If not found, exit silently
[[ -n "$note_path" ]] || exit 2

# 5) Apply image path rules
if [[ "$note_path" == *"/ITStep/"* ]]; then
  image_path="$ITSTEP_MEDIA"
else
  image_path="$(dirname "$note_path")"
fi

# 6) Output:
#    first: image target directory
#    second: markdown note path
printf '%s\n%s\n' "$image_path" "$note_path"
