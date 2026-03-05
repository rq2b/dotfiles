#!/usr/bin/env bash

set -euo pipefail

CLASS="${1:-}"

if [[ -z "$CLASS" ]]; then
  echo "Usage: $0 <window-class>" >&2
  exit 1
fi

# Get matching window (first match)
WINDOW_JSON=$(hyprctl clients -j | jq -r --arg class "$CLASS" '
  .[] | select(.class == $class) | @json
' | head -n 1)

if [[ -z "$WINDOW_JSON" ]]; then
  echo "No window found with class: $CLASS" >&2
  exit 2
fi

# Extract geometry
X=$(jq -r '.at[0]' <<< "$WINDOW_JSON")
Y=$(jq -r '.at[1]' <<< "$WINDOW_JSON")
W=$(jq -r '.size[0]' <<< "$WINDOW_JSON")
H=$(jq -r '.size[1]' <<< "$WINDOW_JSON")

# Compute center
CX=$(( X + W / 2 ))
CY=$(( Y + H / 2 ))

# Move cursor
hyprctl dispatch movecursor "$CX $CY"
