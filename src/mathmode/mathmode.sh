#!/usr/bin/env bash
set -euo pipefail

STATE="${XDG_RUNTIME_DIR:-/tmp}/hypr-mathmode.state"
ACTIVE_BORDER='rgba(ff8800ff)'

toggle() {
    if [[ -e "$STATE" ]]; then
        rm -f "$STATE"
        hyprctl dispatch submap reset >/dev/null
        hyprctl reload >/dev/null
    else
        touch "$STATE"
        hyprctl dispatch submap greek >/dev/null
        hyprctl keyword general:col.active_border "$ACTIVE_BORDER" >/dev/null
    fi
}

unicode() {
    (($#)) || {
        echo "Usage: $0 unicode <hex> [hex ...]" >&2
        exit 2
    }

    for hex in "$@"; do
        hex=${hex,,} # lowercase

        wtype -M ctrl -M shift u -m ctrl -m shift
        sleep 0.03
        wtype "$hex"
        sleep 0.03
        wtype -k Return
    done
}

case "${1:-}" in
    toggle)
        toggle
        ;;
    unicode)
        shift
        unicode "$@"
        ;;
    *)
        cat >&2 <<EOF
Usage:
  $0 toggle
  $0 unicode <hex> [hex ...]
EOF
        exit 2
        ;;
esac
