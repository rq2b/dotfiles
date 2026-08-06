#!/bin/bash
set -euo pipefail

TMP_PATH="${1:?Usage: screenshot-gum-menu.sh /tmp/file.png name.png}"
IMG_NAME="${2:?Usage: screenshot-gum-menu.sh /tmp/file.png name.png}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MOVE_CURSOR="$HOME/src/move-cursor-to-window/move-cursor-to-window.sh"

"$MOVE_CURSOR" screenshot-gum

ACTIONS_STRING=$(gum choose --no-limit \
  --header "Screenshot saved. Select actions..." \
  --selected-prefix="✓ " \
  "Send to Obsidian" \
  "Save to Downloads" \
  "Copy to Clipboard" \
  "Open in Editor" \
  "Save to Location")

ACTIONS=()
while IFS= read -r line; do
  [[ -n "$line" ]] && ACTIONS+=("$line")
done <<< "$ACTIONS_STRING"

if [[ ${#ACTIONS[@]} -eq 0 ]]; then
  rm -f "$TMP_PATH"
  exit 0
fi

hyprctl dispatch movetoworkspacesilent special:screenshot-gum
# --- Run remaining actions in the user's chosen order (minus OCR) ---
for ACTION in "${ACTIONS[@]}"; do
  case "$ACTION" in
    "Send to Obsidian")
      "$SCRIPT_DIR/screenshot-to-obsidian.sh" "$TMP_PATH" "$IMG_NAME"
      ;;
    "Save to Downloads")
      cp -f "$TMP_PATH" "$HOME/Downloads/$IMG_NAME"
      ;;
    "Copy to Clipboard")
      wl-copy --foreground --type image/png < "$TMP_PATH"
      ;;
    "Open in Editor")
      TMP="$TMP_PATH"

      setsid bash -c '
          satty \
              --filename "$1" \
              --output-filename "$2"
          rm -f "$1"
      ' _ "$TMP" "$HOME/Downloads/$IMG_NAME" \
          >/dev/null 2>&1 < /dev/null &
      TMP_PATH=""
      ;;
    "Save to Location")
      SAVE_PATH=$(zenity --file-selection --save --filename="$HOME/$IMG_NAME" --title="Save Screenshot")
      if [[ -n "$SAVE_PATH" ]]; then
        cp -f "$TMP_PATH" "$SAVE_PATH"
      fi
      ;;
  esac
done

[[ -n "${TMP_PATH:-}" ]] && rm -f "$TMP_PATH"
