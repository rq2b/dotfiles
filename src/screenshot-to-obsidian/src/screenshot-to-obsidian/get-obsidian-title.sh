#!/bin/bash
set -euo pipefail

SYNC_DIR="$HOME/Syncthing"
ITSTEP_MEDIA="$HOME/Syncthing/ITStep/Media"

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

if TITLE="$(printf '%s' "$HYPRCTL_OUTPUT" | jq -r '.[] | select(.class == "obsidian" or .class == "md.obsidian.Obsidian") | .title' | head -n 1)"; then
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

if [[ ! -d "$SYNC_DIR" ]]; then
    notify_error "Obsidian search root does not exist: $SYNC_DIR"
    exit 1
fi

NOTE_PATH=""
if NOTE_PATH="$(find "$SYNC_DIR" -type f -name "$TARGET_MD" -print -quit 2>/tmp/screenshot-to-obsidian-find-error)"; then
    FIND_STATUS=0
else
    FIND_STATUS=$?
fi
FIND_ERROR="$(cat /tmp/screenshot-to-obsidian-find-error 2>/dev/null || true)"
rm -f /tmp/screenshot-to-obsidian-find-error
if (( FIND_STATUS != 0 )); then
    notify_error "could not search for $TARGET_MD${FIND_ERROR:+: $FIND_ERROR}"
    exit "$FIND_STATUS"
fi

if [[ -z "$NOTE_PATH" ]]; then
    notify_error "could not find Obsidian note: $TARGET_MD under $SYNC_DIR"
    exit 2
fi

if [[ "$NOTE_PATH" == *"/ITStep/"* ]]; then
    IMAGE_PATH="$ITSTEP_MEDIA"
else
    IMAGE_PATH="$(dirname "$NOTE_PATH")"
fi

printf '%s\n%s\n' "$IMAGE_PATH" "$NOTE_PATH"
