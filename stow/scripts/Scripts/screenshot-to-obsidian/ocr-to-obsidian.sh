#!/bin/bash
set -euo pipefail

TMP_PATH="${1:?Usage: ocr-to-obsidian.sh /tmp/file.png}"
OCR_PY="/home/rq2b/Scripts/screenshot-to-obsidian/main.py"

GET_NOTE="$HOME/Scripts/screenshot-to-obsidian/get-obsidian-title.sh"
APPEND="$HOME/Scripts/screenshot-to-obsidian/append-obsidian-image.sh"

[[ -f "$TMP_PATH" ]] || { echo "Error: temp image not found: $TMP_PATH" >&2; exit 1; }
[[ -x "$GET_NOTE" ]] || { echo "Error: missing executable: $GET_NOTE" >&2; exit 1; }
[[ -x "$APPEND" ]] || { echo "Error: missing executable: $APPEND" >&2; exit 1; }
[[ -f "$OCR_PY" ]] || { echo "Error: OCR script not found: $OCR_PY" >&2; exit 1; }

# get-obsidian-title.sh prints:
#   line1: image target directory
#   line2: markdown note path
NOTE_PATH="$("$GET_NOTE" | sed -n '2p')"

[[ -n "${NOTE_PATH:-}" && -f "$NOTE_PATH" ]] || {
  echo "Error: Could not resolve Obsidian note path (is Obsidian open, and note exists?)" >&2
  exit 2
}

# Run OCR and capture stdout
# Keep internal newlines; strip only trailing whitespace lines at the end
OCR_TEXT="$(python "$OCR_PY" "$TMP_PATH" || true)"
OCR_TEXT="$(printf '%s' "$OCR_TEXT" | sed -e :a -e '/^[[:space:]]*$/{$d;N;ba' -e '}' || true)"

if [[ -z "${OCR_TEXT//[[:space:]]/}" ]]; then
  echo "Warning: OCR returned empty text" >&2
  exit 0
fi

# Append as a fenced block so it’s readable/searchable
BLOCK="$OCR_TEXT"

"$APPEND" "$NOTE_PATH" --text "$BLOCK"
