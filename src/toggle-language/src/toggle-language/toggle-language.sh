#!/usr/bin/env bash

STATE_FILE="${XDG_RUNTIME_DIR:-/tmp}/hyprland-lang-toggle"

current=$(
    hyprctl devices -j |
        jq -r '.keyboards[] | select(.main == true) | .active_keymap'
)

case "$current" in
    *Russian*)
        hyprctl switchxkblayout current 1 >/dev/null
        printf '%s\n' ukrainian > "$STATE_FILE"
        ;;

    *Ukrainian*)
        hyprctl switchxkblayout current 2 >/dev/null
        printf '%s\n' russian > "$STATE_FILE"
        ;;

    *)
        if [[ -f "$STATE_FILE" ]]; then
            last=$(<"$STATE_FILE")
        else
            last="russian"
        fi

        case "$last" in
            ukrainian)
                hyprctl switchxkblayout current 1 >/dev/null
                ;;
            *)
                hyprctl switchxkblayout current 2 >/dev/null
                ;;
        esac
        ;;
esac
