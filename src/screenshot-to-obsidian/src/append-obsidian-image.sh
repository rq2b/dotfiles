#!/bin/bash
set -euo pipefail

NOTE_PATH="${1:?Usage: append-obsidian-image.sh NOTE_PATH IMAGE_NAME | --text TEXT | --text-file FILE}"
MODE_OR_IMAGE="${2:?Missing second argument}"

# Basic validation
[[ -f "$NOTE_PATH" ]] || {
  echo "Error: note does not exist: $NOTE_PATH" >&2
  exit 1
}

case "$MODE_OR_IMAGE" in
  --text)
    TEXT="${3:-}"
    [[ -n "$TEXT" ]] || {
      echo "Error: text is empty" >&2
      exit 1
    }
    # Append a newline + text (preserve exactly)
    printf '\n%s\n' "$TEXT" >> "$NOTE_PATH"
    ;;

  --text-file)
    TEXT_FILE="${3:-}"
    [[ -n "$TEXT_FILE" && -f "$TEXT_FILE" ]] || {
      echo "Error: text file not found: $TEXT_FILE" >&2
      exit 1
    }
    printf '\n' >> "$NOTE_PATH"
    cat "$TEXT_FILE" >> "$NOTE_PATH"
    # printf '\n' >> "$NOTE_PATH"
    ;;

  *)
    IMAGE_NAME="$MODE_OR_IMAGE"
    [[ -n "$IMAGE_NAME" ]] || {
      echo "Error: image name is empty" >&2
      exit 1
    }
    # Append a newline + Obsidian image link
    printf '\n![[%s]]' "$IMAGE_NAME" >> "$NOTE_PATH"
    ;;
esac
