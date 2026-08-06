#!/bin/bash
set -euo pipefail

TMP_PATH="${1:?Usage: screenshot-gum-menu.sh /tmp/file.png name.png}"
IMG_NAME="${2:?Usage: screenshot-gum-menu.sh /tmp/file.png name.png}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MOVE_CURSOR="$HOME/src/move-cursor-to-window/move-cursor-to-window.sh"

"$MOVE_CURSOR" screenshot-gum >/dev/null 2>&1

gum_args=(
  choose
  --no-limit
  --item.foreground="#878787"
  --cursor.foreground="#fff"
  --cursor.background=""
  --selected.background=""
  --header=""
  --selected-prefix="✓ "
  "Send to Obsidian"
  "Save to Downloads"
  "Copy to Clipboard"
  "Open in Editor"
  "Save to Location"
)

ACTIONS_STRING=$(gum "${gum_args[@]}")


ACTIONS=()
while IFS= read -r line; do
  [[ -n "$line" ]] && ACTIONS+=("$line")
done <<< "$ACTIONS_STRING"

if [[ ${#ACTIONS[@]} -eq 0 ]]; then
  rm -f "$TMP_PATH"
  exit 0
fi

hyprctl dispatch movetoworkspacesilent special:screenshot-gum

trap '[[ -n "${TMP_PATH:-}" ]] && rm -f "$TMP_PATH"' EXIT

for ACTION in "${ACTIONS[@]}"; do
  if ! (
    set -euo pipefail

    case "$ACTION" in
      "Send to Obsidian")
        "$SCRIPT_DIR/screenshot-to-obsidian.sh" \
          "$TMP_PATH" "$IMG_NAME"
        ;;

      "Save to Downloads")
        cp -f "$TMP_PATH" "$HOME/Downloads/$IMG_NAME"
        ;;

      "Copy to Clipboard")
        setsid wl-copy \
          --type image/png \
          < "$TMP_PATH" \
          >/dev/null 2>&1 &
        ;;

      "Open in Editor")
        readonly TMP="$TMP_PATH"
        readonly OUT="$HOME/Downloads/$IMG_NAME"

        setsid bash -c '
            set -euo pipefail

            trap '\''rm -f "$1"'\'' EXIT

            satty \
                --filename "$1" \
                --output-filename "$2" \
                --actions-on-escape exit \
                --early-exit save save-as
        ' _ "$TMP" "$OUT" >/dev/null 2>&1 &

        TMP_PATH=""
        ;;

      "Save to Location")
        SAVE_PATH="$(
          zenity \
            --file-selection \
            --save \
            --filename="$HOME/$IMG_NAME" \
            --title="Save Screenshot"
        )"

        [[ -n "$SAVE_PATH" ]] && cp -f "$TMP_PATH" "$SAVE_PATH"
        ;;
    esac
  ); then
    notify-send -t 1000 "$ACTION failed"
  fi
done
for ACTION in "${ACTIONS[@]}"; do
  case "$ACTION" in
    "Send to Obsidian")
      if ! "$SCRIPT_DIR/screenshot-to-obsidian.sh" \
        "$TMP_PATH" "$IMG_NAME"; then
        notify-send -t 1000 "Send to Obsidian failed"
      fi
      ;;

    "Save to Downloads")
      cp -f "$TMP_PATH" "$HOME/Downloads/$IMG_NAME"
      ;;

    "Copy to Clipboard")
      setsid wl-copy \
        --type image/png \
        < "$TMP_PATH" \
        >/dev/null 2>&1 &
      ;;

    "Open in Editor")
      readonly TMP="$TMP_PATH"
      readonly OUT="$HOME/Downloads/$IMG_NAME"

      setsid bash -c '
        set -euo pipefail

        trap '\''rm -f "$1"'\'' EXIT

        satty \
          --filename "$1" \
          --output-filename "$2" \
          --actions-on-escape exit \
          --early-exit save save-as
      ' _ "$TMP" "$OUT" >/dev/null 2>&1

      TMP_PATH=""
      ;;

    "Save to Location")
      SAVE_PATH="$(
        zenity \
          --file-selection \
          --save \
          --filename="$HOME/$IMG_NAME" \
          --title="Save Screenshot"
      )"

      [[ -n "$SAVE_PATH" ]] && cp -f "$TMP_PATH" "$SAVE_PATH"
      ;;
  esac
done

