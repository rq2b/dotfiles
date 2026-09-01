#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
GET_INFO="$SCRIPT_DIR/get-obsidian-title.sh"
APPEND_LINK="$SCRIPT_DIR/append-obsidian-image.sh"
TMP_PATH="${1:?Usage: screenshot-to-obsidian.sh /tmp/file.png name.png}"
IMG_NAME="${2:?Usage: screenshot-to-obsidian.sh /tmp/file.png name.png}"

notify_error() {
    local message="$1"
    if command -v notify-send >/dev/null 2>&1; then
        notify-send -u critical -t 5000 "Screenshot to Obsidian: Obsidian action failed" "$message" >/dev/null 2>&1 || true
    fi
    printf 'Error: %s\n' "$message" >&2
}


[[ -f "$TMP_PATH" ]] || {
    printf 'Error: temp image not found: %s\n' "$TMP_PATH" >&2
    exit 1
}
[[ -x "$GET_INFO" ]] || {
    printf 'Error: missing executable: %s\n' "$GET_INFO" >&2
    exit 1
}
[[ -x "$APPEND_LINK" ]] || {
    printf 'Error: missing executable: %s\n' "$APPEND_LINK" >&2
    exit 1
}

if INFO_OUTPUT=$("$GET_INFO"); then
    STATUS=0
else
    STATUS=$?
fi
if (( STATUS != 0 )); then
    printf '%s\n' "$INFO_OUTPUT" >&2
    exit "$STATUS"
fi

mapfile -t INFO <<< "$INFO_OUTPUT"
IMAGE_DIR="${INFO[0]:-}"
NOTE_PATH="${INFO[1]:-}"

if [[ -z "$IMAGE_DIR" || -z "$NOTE_PATH" ]]; then
    printf 'Error: could not get image directory / note path\n' >&2
    exit 1
fi

if ! cp -f -- "$TMP_PATH" "$IMAGE_DIR/$IMG_NAME"; then
    printf 'Error: could not copy screenshot to %s\n' "$IMAGE_DIR/$IMG_NAME" >&2
    exit 1
fi

if ! "$APPEND_LINK" "$NOTE_PATH" "$IMG_NAME"; then
    printf 'Error: could not append image link to %s\n' "$NOTE_PATH" >&2
    exit 1
fi
