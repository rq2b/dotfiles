#!/bin/bash
set -euo pipefail

TMP_DIR="/tmp"

IMG_NAME="$(date +%F_%H-%M-%S).png"
TMP_PATH="$TMP_DIR/$IMG_NAME"

pkill slurp && exit 0
pkill wayfreeze && exit 0

get_rectangles() {
  local visible_workspaces_json

  # Build the list of ACTUALLY visible workspaces.
  #
  # Important behavior:
  # - if a monitor has a special workspace active,
  #   ONLY the special workspace is considered visible
  #   for snapping purposes
  #
  # This prevents underlying workspace windows from
  # becoming selectable while scratchpad is open.
  visible_workspaces_json="$(
    hyprctl monitors -j |
      jq -c '
        map(
          if .specialWorkspace.name != ""
          then .specialWorkspace.name
          else .activeWorkspace.name
          end
        )
        | unique
      '
  )"

  {
    #
    # Dynamic monitor rectangles
    #
    # This automatically supports:
    # - vertical monitors
    # - monitor rearrangement
    # - scaling changes
    # - transform changes
    #
    hyprctl monitors -j |
    jq -r '
      .[]
      | (
          if (.transform == 1 or .transform == 3 or .transform == 5 or .transform == 7)
          then "\(.x),\(.y) \(.height)x\(.width)"
          else "\(.x),\(.y) \(.width)x\(.height)"
          end
        )
    '

    #
    # Window rectangles
    #
    hyprctl clients -j |
      jq -r \
        --argjson visible "$visible_workspaces_json" '
          .[]
          | select(
              (
                .workspace.name as $ws
                | $visible | index($ws)
              )
              and
              .mapped == true
              and
              .hidden == false
            )
          | "\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"
        '
  }
}

RECTS="$(get_rectangles)"

wayfreeze &
PID=$!

trap 'kill "$PID" 2>/dev/null || true' EXIT

sleep .1

SELECTION="$(
  printf '%s\n' "$RECTS" |
    slurp 2>/dev/null || true
)"

kill "$PID" 2>/dev/null || true
trap - EXIT

[[ -z "${SELECTION:-}" ]] && exit 0

#
# If the selected region is tiny,
# treat it as a click and snap
# to the matching rectangle.
#
if [[ "$SELECTION" =~ ^([0-9]+),([0-9]+)[[:space:]]([0-9]+)x([0-9]+)$ ]]; then
  if (( ${BASH_REMATCH[3]} * ${BASH_REMATCH[4]} < 20 )); then
    click_x="${BASH_REMATCH[1]}"
    click_y="${BASH_REMATCH[2]}"

    while IFS= read -r rect; do
      if [[ "$rect" =~ ^([0-9]+),([0-9]+)[[:space:]]([0-9]+)x([0-9]+)$ ]]; then
        rect_x="${BASH_REMATCH[1]}"
        rect_y="${BASH_REMATCH[2]}"
        rect_width="${BASH_REMATCH[3]}"
        rect_height="${BASH_REMATCH[4]}"

        if (( click_x >= rect_x &&
              click_x < rect_x + rect_width &&
              click_y >= rect_y &&
              click_y < rect_y + rect_height )); then
          SELECTION="${rect_x},${rect_y} ${rect_width}x${rect_height}"
          break
        fi
      fi
    done <<< "$RECTS"
  fi
fi

grim -g "$SELECTION" "$TMP_PATH" || exit 1

[[ -f "$TMP_PATH" ]] || exit 0

hyprctl dispatch exec \
  "[float; size 430 250; center 1] \
   kitty --class screenshot-gum \
   -e $HOME/src/screenshot-to-obsidian/screenshot-gum-menu.sh \
   $TMP_PATH $IMG_NAME"