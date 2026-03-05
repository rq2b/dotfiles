#!/bin/bash
set -euo pipefail

TMP_PATH="${1:?Usage: screenshot-gum-menu.sh /tmp/file.png name.png}"
IMG_NAME="${2:?Usage: screenshot-gum-menu.sh /tmp/file.png name.png}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MOVE_CURSOR="$HOME/Scripts/move-cursor-to-window/move-cursor-to-window.sh"

"$MOVE_CURSOR" screenshot-gum

ACTIONS_STRING=$(gum choose --no-limit \
  --header "Screenshot saved. Select actions..." \
  --selected-prefix="✓ " \
  "Send to Obsidian" \
  "Save to Downloads" \
  "Copy to Clipboard" \
  "Open in Editor" \
  "Save to Location" \
  "OCR")

ACTIONS=()
while IFS= read -r line; do
  [[ -n "$line" ]] && ACTIONS+=("$line")
done <<< "$ACTIONS_STRING"

if [[ ${#ACTIONS[@]} -eq 0 ]]; then
  rm -f "$TMP_PATH"
  exit 0
fi

hyprctl dispatch movetoworkspacesilent special:screenshot-gum

# --- Run OCR first if selected ---
OCR_SELECTED=0
NEW_ACTIONS=()
for a in "${ACTIONS[@]}"; do
  if [[ "$a" == "OCR" ]]; then
    OCR_SELECTED=1
  else
    NEW_ACTIONS+=("$a")
  fi
done
ACTIONS=("${NEW_ACTIONS[@]}")

if [[ $OCR_SELECTED -eq 1 ]]; then
  "$SCRIPT_DIR/ocr-to-obsidian.sh" "$TMP_PATH"
fi

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
      wl-copy --type image/png < "$TMP_PATH"
      ;;
    "Open in Editor")
      satty --filename "$TMP_PATH" --output-filename "$HOME/Downloads/$IMG_NAME"
      ;;
    "Save to Location")
      SAVE_PATH=$(zenity --file-selection --save --filename="$HOME/$IMG_NAME" --title="Save Screenshot")
      if [[ -n "$SAVE_PATH" ]]; then
        cp -f "$TMP_PATH" "$SAVE_PATH"
      fi
      ;;
  esac
done

rm -f "$TMP_PATH"
