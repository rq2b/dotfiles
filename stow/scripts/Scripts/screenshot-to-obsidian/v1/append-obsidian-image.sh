#!/bin/bash
set -euo pipefail

NOTE_PATH="$1"
IMAGE_NAME="$2"

# Basic validation
[[ -f "$NOTE_PATH" ]] || {
  echo "Error: note does not exist: $NOTE_PATH" >&2
  exit 1
}

[[ -n "$IMAGE_NAME" ]] || {
  echo "Error: image name is empty" >&2
  exit 1
}

# Append a newline + Obsidian image link
printf '\n![[%s]]' "$IMAGE_NAME" >> "$NOTE_PATH"
