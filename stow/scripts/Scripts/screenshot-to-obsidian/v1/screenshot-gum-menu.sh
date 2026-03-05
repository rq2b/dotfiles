#!/bin/bash
set -euo pipefail

TMP_PATH="${1:?Usage: screenshot-gum-menu.sh /tmp/file.png name.png}"
IMG_NAME="${2:?Usage: screenshot-gum-menu.sh /tmp/file.png name.png}"

CLIP_REMOVE_LAST="/home/rq2b/Scripts/clipboard-elephant/clipboard-remove-last-item.sh"
COPY_SELECTED=0

# Show action selection menu
ACTIONS_STRING=$(gum choose --no-limit \
  --header "Screenshot saved. Select actions..." \
  --selected-prefix="✓ " \
  "Send to Obsidian" \
  "Save to Downloads" \
  "Copy to Clipboard" \
  "Pick save location")

# Convert newline-separated string to array
ACTIONS=()
while IFS= read -r line; do
  [[ -n "$line" ]] && ACTIONS+=("$line")
done <<< "$ACTIONS_STRING"

# Exit if no actions selected - clear clipboard + delete temp
if [[ ${#ACTIONS[@]} -eq 0 ]]; then
  rm -f "$TMP_PATH"
  wl-copy --clear
  exit 0
fi

for ACTION in "${ACTIONS[@]}"; do
  case "$ACTION" in
    "Send to Obsidian")
      "$HOME/Scripts/screenshot-to-obsidian/screenshot-to-obsidian.sh" "$TMP_PATH" "$IMG_NAME"
      ;;
    "Save to Downloads")
      cp -f "$TMP_PATH" "$HOME/Downloads/$IMG_NAME"
      ;;
    "Copy to Clipboard")
      COPY_SELECTED=1
      ;;
    "Pick save location")
      SAVE_PATH=$(zenity --file-selection --save --filename="$HOME/$IMG_NAME" --title="Save Screenshot")
      if [[ -n "$SAVE_PATH" ]]; then
        cp -f "$TMP_PATH" "$SAVE_PATH"
      fi
      ;;
  esac
done

# If user did NOT select "Copy to Clipboard", remove the last clipboard item
if [[ "$COPY_SELECTED" -eq 0 ]]; then
  "$CLIP_REMOVE_LAST"
fi

rm -f "$TMP_PATH"
