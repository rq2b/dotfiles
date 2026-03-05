#!/bin/bash
set -uo pipefail

GET_INFO="$HOME/Scripts/get-obsidian-title.sh"
APPEND_LINK="$HOME/Scripts/append-obsidian-image.sh"

TMP_PATH="$1"
IMG_NAME="$2"

# Get Obsidian note info
mapfile -t info < <("$GET_INFO" 2>/dev/null || true)
IMAGE_DIR="${info[0]:-}"
NOTE_PATH="${info[1]:-}"

if [[ -z "$IMAGE_DIR" || -z "$NOTE_PATH" ]]; then
  echo "Error: couldn't get image dir / note path" >&2
  exit 1
fi

# Copy to Obsidian and append link
# mkdir -p "$IMAGE_DIR"
cp -f "$TMP_PATH" "$IMAGE_DIR/$IMG_NAME"
"$APPEND_LINK" "$NOTE_PATH" "$IMG_NAME"