#!/bin/bash
set -euo pipefail

SEARCH_DIRS=(
    "$HOME/Syncthing/core"
    "$HOME/Syncthing/Desolate"
    "$HOME/Syncthing/grade11"
    "$HOME/repos/itstep"
)

notify_error() {
    local message="$1"
    if command -v notify-send >/dev/null 2>&1; then
        notify-send -u critical -t 5000 "Screenshot to Obsidian: Obsidian lookup failed" "$message" >/dev/null 2>&1 || true
    fi
    printf 'Error: %s\n' "$message" >&2
}

HYPRCTL_OUTPUT=""
if ! HYPRCTL_OUTPUT="$(hyprctl clients -j 2>&1)"; then
    notify_error "hyprctl clients failed: $HYPRCTL_OUTPUT"
    exit 1
fi

if TITLE="$(printf '%s' "$HYPRCTL_OUTPUT" |
    jq -r '.[] | select(.class == "obsidian" or .class == "md.obsidian.Obsidian") | .title' |
    head -n 1)"; then
    STATUS=0
else
    STATUS=$?
fi

if (( STATUS != 0 )); then
    notify_error "could not parse Hyprland client data"
    exit 1
fi

if [[ -z "${TITLE:-}" || "$TITLE" == "null" ]]; then
    notify_error "no open Obsidian window with a usable title was found"
    exit 1
fi

TRIMMED="$(printf '%s' "$TITLE" | sed 's/ - [^-]* - [^-]*$//')"
TARGET_MD="${TRIMMED}.md"

NOTE_PATH=""
FIND_ERROR=""

for SEARCH_DIR in "${SEARCH_DIRS[@]}"; do
    [[ -d "$SEARCH_DIR" ]] || continue

    FIND_ERROR_FILE="$(mktemp)"

    if NOTE_PATH="$(find "$SEARCH_DIR" -type f -name "$TARGET_MD" -print -quit 2>"$FIND_ERROR_FILE")"; then
        FIND_STATUS=0
    else
        FIND_STATUS=$?
    fi

    FIND_ERROR="$(cat "$FIND_ERROR_FILE" 2>/dev/null || true)"
    rm -f "$FIND_ERROR_FILE"

    if (( FIND_STATUS != 0 )); then
        notify_error "could not search for $TARGET_MD in $SEARCH_DIR${FIND_ERROR:+: $FIND_ERROR}"
        exit "$FIND_STATUS"
    fi

    [[ -n "$NOTE_PATH" ]] && break
done

if [[ -z "$NOTE_PATH" ]]; then
    notify_error "could not find Obsidian note: $TARGET_MD under configured search roots"
    exit 2
fi

IMAGE_PATH="$(dirname "$NOTE_PATH")"

printf '%s\n%s\n' "$IMAGE_PATH" "$NOTE_PATH"
