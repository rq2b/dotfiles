#!/usr/bin/env bash

SOCK="$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock"

socat -U - UNIX-CONNECT:"$SOCK" | while IFS= read -r line; do
    case "$line" in
        openwindow*Typora*License\ Info)
            hyprctl dispatch closewindow title:^License\ Info$
            ;;
    esac
done
