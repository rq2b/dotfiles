#!/bin/bash
set -euo pipefail

SEARCH_ROOTS=(
    "$HOME/Syncthing"
    "$HOME/repos"
)

ITSTEP_MEDIA="$HOME/Syncthing/ITStep/Media"

title="$(
  hyprctl clients -j \
    | jq -r '.[] | select(.class == "obsidian") | .title' \
    | head -n 1
)"

[[ -n "${title:-}" && "$title" != "null" ]] || exit 1

trimmed="$(printf '%s' "$title" | sed 's/ - [^-]* - [^-]*$//')"

target_md="${trimmed}.md"

note_path=""

for root in "${SEARCH_ROOTS[@]}"; do
    found="$(
        find "$root" \
            \( -name .git -o -name node_modules -o -name .obsidian \) -prune \
            -o -type f -name "$target_md" -print -quit \
            2>/dev/null || true
    )"

    if [[ -n "$found" ]]; then
        note_path="$found"
        break
    fi
done

[[ -n "$note_path" ]] || exit 2

if [[ "$note_path" == *"/ITStep/"* ]]; then
    image_path="$ITSTEP_MEDIA"
else
    image_path="$(dirname "$note_path")"
fi

printf '%s\n%s\n' "$image_path" "$note_path"
