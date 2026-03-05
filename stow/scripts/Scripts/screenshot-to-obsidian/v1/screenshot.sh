#!/bin/bash
set -uo pipefail

TMP_DIR="/tmp"
HYPRSHOT_TIMEOUT=10
MAX_WAIT_SECONDS=10

# Setup paths
IMG_NAME="$(date +%F_%H-%M-%S).png"
TMP_PATH="$TMP_DIR/$IMG_NAME"
OUT_FILE="/tmp/hyprshot_out_$$.txt"

# Cleanup function
cleanup() {
  kill $HYPRSHOT_PID 2>/dev/null || true
  wait $HYPRSHOT_PID 2>/dev/null || true
  rm -f "$OUT_FILE"
}
trap cleanup EXIT

# Run hyprshot in background
timeout "${HYPRSHOT_TIMEOUT}s" hyprshot -m region -o "$TMP_DIR" -f "$IMG_NAME" -s > "$OUT_FILE" 2>&1 &
HYPRSHOT_PID=$!

# Wait for screenshot file or cancellation
deadline=$((SECONDS + MAX_WAIT_SECONDS))
while [[ ! -f "$TMP_PATH" ]] && [[ $SECONDS -lt $deadline ]]; do
  if [[ -f "$OUT_FILE" ]] && grep -qi "selection cancelled" "$OUT_FILE"; then
    exit 0
  fi
  sleep 0.1
done

# Wait for file to finish writing
# sleep 0.3

# Exit if no file was created
if [[ ! -f "$TMP_PATH" ]]; then
  exit 0
fi

hyprctl dispatch exec "[float; size 430 200; center 1] kitty -e $HOME/Scripts/screenshot-to-obsidian/screenshot-gum-menu.sh $TMP_PATH $IMG_NAME"
