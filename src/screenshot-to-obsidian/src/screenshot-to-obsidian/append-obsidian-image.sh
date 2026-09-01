#!/bin/bash
set -euo pipefail

NOTE_PATH="${1:?Usage: append-obsidian-image.sh NOTE_PATH IMAGE_NAME | --text TEXT | --text-file FILE}"
MODE_OR_IMAGE="${2:?Missing second argument}"

[[ -f "$NOTE_PATH" ]] || {
    printf 'Error: note does not exist: %s\n' "$NOTE_PATH" >&2
    exit 1
}

case "$MODE_OR_IMAGE" in
    --text)
        TEXT="${3:-}"
        [[ -n "$TEXT" ]] || {
            printf 'Error: text is empty\n' >&2
            exit 1
        }
        printf '\n%s\n' "$TEXT" >> "$NOTE_PATH"
        ;;
    --text-file)
        TEXT_FILE="${3:-}"
        [[ -n "$TEXT_FILE" && -f "$TEXT_FILE" ]] || {
            printf 'Error: text file not found: %s\n' "$TEXT_FILE" >&2
            exit 1
        }
        printf '\n' >> "$NOTE_PATH"
        cat "$TEXT_FILE" >> "$NOTE_PATH"
        ;;
    *)
        IMAGE_NAME="$MODE_OR_IMAGE"
        [[ -n "$IMAGE_NAME" ]] || {
            printf 'Error: image name is empty\n' >&2
            exit 1
        }
        printf '\n![[%s]]' "$IMAGE_NAME" >> "$NOTE_PATH"
        ;;
esac
