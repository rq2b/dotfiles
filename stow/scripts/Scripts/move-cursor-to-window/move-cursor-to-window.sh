#!/usr/bin/env bash

set -euo pipefail

PATTERN="${1:-}"

if [[ -z "$PATTERN" ]]; then
  echo "Usage: $0 <window-class-or-pattern>" >&2
  exit 1
fi

WINDOW_JSON=$(
  hyprctl clients -j | jq -r --arg p "$PATTERN" '
    # 1) exact class match first (backward compatibility)
    (
      .[] | select(.class == $p)
    ),
    # 2) fallback: Omarchy-style class/title pattern match
    (
      .[] | select(
        (.class | test("\\b" + $p + "\\b"; "i")) or
        (.title | test("\\b" + $p + "\\b"; "i"))
      )
    )
    | @json
  ' | head -n 1
)

if [[ -z "$WINDOW_JSON" ]]; then
  echo "No window found matching: $PATTERN" >&2
  exit 2
fi

X=$(jq -r '.at[0]' <<< "$WINDOW_JSON")
Y=$(jq -r '.at[1]' <<< "$WINDOW_JSON")
W=$(jq -r '.size[0]' <<< "$WINDOW_JSON")
H=$(jq -r '.size[1]' <<< "$WINDOW_JSON")

CX=$(( X + W / 2 ))
CY=$(( Y + H / 2 ))

hyprctl dispatch movecursor "$CX $CY"