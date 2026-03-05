#!/bin/bash
set -euo pipefail

TMP_DIR="/tmp"

IMG_NAME="$(date +%F_%H-%M-%S).png"
TMP_PATH="$TMP_DIR/$IMG_NAME"

pkill slurp && exit 0
pkill wayfreeze && exit 0

get_rectangles() {
  local ws=$(hyprctl monitors -j | jq -r '.[]|select(.focused).activeWorkspace.id') sec=$(hyprctl monitors -j | jq -r '.[]|select(.focused|not).activeWorkspace.id')
  { echo "0,0 1920x1080"; echo "1920,-840 1080x1920"; hyprctl clients -j | jq -r --arg ws "$ws" --arg sec "$sec" '.[]|select(.workspace.id==($ws|tonumber) or .workspace.id==($sec|tonumber))|"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"'; }
}


RECTS="$(get_rectangles)"
wayfreeze & PID=$!; trap 'kill "$PID" 2>/dev/null || true' EXIT
sleep .1; SELECTION="$(printf '%s\n' "$RECTS" | slurp 2>/dev/null || true)"
kill "$PID" 2>/dev/null || true; trap - EXIT


[[ -z "${SELECTION:-}" ]] && exit 0

if [[ "$SELECTION" =~ ^([0-9]+),([0-9]+)[[:space:]]([0-9]+)x([0-9]+)$ ]]; then
  if (( ${BASH_REMATCH[3]} * ${BASH_REMATCH[4]} < 20 )); then
    click_x="${BASH_REMATCH[1]}"
    click_y="${BASH_REMATCH[2]}"
    while IFS= read -r rect; do
      if [[ "$rect" =~ ^([0-9]+),([0-9]+)[[:space:]]([0-9]+)x([0-9]+) ]]; then
        rect_x="${BASH_REMATCH[1]}"
        rect_y="${BASH_REMATCH[2]}"
        rect_width="${BASH_REMATCH[3]}"
        rect_height="${BASH_REMATCH[4]}"
        if (( click_x >= rect_x && click_x < rect_x+rect_width && click_y >= rect_y && click_y < rect_y+rect_height )); then
          SELECTION="${rect_x},${rect_y} ${rect_width}x${rect_height}"
          break
        fi
      fi
    done <<< "$RECTS"
  fi
fi

grim -g "$SELECTION" "$TMP_PATH" || exit 1
[[ -f "$TMP_PATH" ]] || exit 0

hyprctl dispatch exec "[float; size 430 250; center 1] kitty --class screenshot-gum -e $HOME/Scripts/screenshot-to-obsidian/screenshot-gum-menu.sh $TMP_PATH $IMG_NAME"
