#!/usr/bin/env bash
set -euo pipefail

# Remove the newest item from Elephant's clipboard provider.
# Silent by design: no output on success.

# Query newest clipboard entry
raw="$(elephant query "clipboard;;1" 2>/dev/null || true)"
[[ -n "$raw" ]] || exit 0

# Extract identifier and qid
id="$(printf '%s\n' "$raw" | sed -n 's/.*identifier:"\([^"]*\)".*/\1/p' | head -n1)"
qid="$(printf '%s\n' "$raw" | sed -n 's/.*qid:\([0-9]\+\).*/\1/p' | head -n1)"

[[ -n "$id" && -n "$qid" ]] || exit 1

# Activate "remove" action (trailing ';' required by elephant)
elephant activate "clipboard;$id;remove;$qid;" >/dev/null 2>&1
