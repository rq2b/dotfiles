#!/usr/bin/env bash
set -euo pipefail

STATE="${XDG_RUNTIME_DIR:-/tmp}/hypr-mathmode.state"

# CHANGE THIS to your normal active border color from config:
ORANGE_ACTIVE_BORDER='rgba(ff8800ff)'

if [[ -f "$STATE" ]]; then
  # OFF
  rm -f "$STATE"
  hyprctl dispatch submap reset >/dev/null
  hyprctl reload >/dev/null
else
  # ON
  : >"$STATE"
  hyprctl dispatch submap greek >/dev/null
  hyprctl keyword general:col.active_border "$ORANGE_ACTIVE_BORDER" >/dev/null
fi