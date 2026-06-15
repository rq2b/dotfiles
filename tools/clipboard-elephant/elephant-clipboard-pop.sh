#!/usr/bin/env bash
set -euo pipefail

# Delete newest Elephant clipboard entry (the one you'd see at the top in Walker)
#
# Elephant exposes clipboard entries via:
#   elephant query "clipboard;;N"
#
# Each line includes:
#   identifier:"<ID>"  ... actions:"remove" ... qid:<NUMBER>
#
# To trigger an action, Elephant expects a semicolon payload with 5 fields:
#   provider;identifier;action;qid;<extra>
# For clipboard remove, <extra> can be empty, but MUST exist -> trailing ';'.

need_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Missing: $1" >&2; exit 127; }; }
need_cmd elephant
need_cmd sed

raw="$(elephant query "clipboard;;1" || true)"
[[ -n "$raw" ]] || { echo "No clipboard items (or elephant not running)." >&2; exit 1; }

id="$(printf '%s\n' "$raw" | sed -n 's/.*identifier:"\([^"]*\)".*/\1/p' | head -n1)"
qid="$(printf '%s\n' "$raw" | sed -n 's/.*qid:\([0-9]\+\).*/\1/p' | head -n1)"

if [[ -z "$id" || -z "$qid" ]]; then
  echo "Failed to parse identifier/qid from:" >&2
  printf '%s\n' "$raw" >&2
  exit 2
fi

echo "Newest clipboard entry:"
printf '%s\n\n' "$raw"
echo "Parsed: identifier=$id qid=$qid"
echo "Removing it..."

elephant activate "clipboard;$id;remove;$qid;"

echo "Done. Verify with:"
echo "  elephant query \"clipboard;;5\""
