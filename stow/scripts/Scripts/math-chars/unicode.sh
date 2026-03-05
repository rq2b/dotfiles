#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <hexcode> [hexcode ...]   (example: $0 03B1 03B2 03B3)" >&2
  exit 2
fi

# Types any number of Unicode codepoints via Ctrl+Shift+U <hex> Enter
# Small sleeps help apps like Teams reliably catch the sequence.
for hex in "$@"; do
  hex="$(printf '%s' "$hex" | tr '[:upper:]' '[:lower:]')"
  wtype -M ctrl -M shift u -m ctrl -m shift
  sleep 0.05
  wtype "$hex"
  sleep 0.05
  wtype -k Return
done