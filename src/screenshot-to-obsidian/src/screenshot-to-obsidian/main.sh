#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="/tmp"
IMG_NAME="$(date +%F_%H-%M-%S).png"
TMP_PATH="$TMP_DIR/$IMG_NAME"

notify_error() {
    local title="$1"
    local message="$2"
    if command -v notify-send >/dev/null 2>&1; then
        notify-send -u critical -t 5000 "$title" "$message" >/dev/null 2>&1 || true
    fi
    printf 'ERROR: %s: %s\n' "$title" "$message" >&2
}

fail() {
    local status="$1"
    local message="$2"
    notify_error "Screenshot to Obsidian" "$message"
    exit "$status"
}

require_command() {
    local command
    for command in "$@"; do
        command -v "$command" >/dev/null 2>&1 || fail 127 "required command not found: $command"
    done
}

cleanup() {
    if [[ -n "${WAYFREEZE_PID:-}" ]]; then
        kill "$WAYFREEZE_PID" >/dev/null 2>&1 || true
        wait "$WAYFREEZE_PID" >/dev/null 2>&1 || true
    fi
}

trap cleanup EXIT


require_command pkill hyprctl jq slurp wayfreeze grim kitty

if pkill slurp >/dev/null 2>&1; then
    exit 0
fi

if pkill wayfreeze >/dev/null 2>&1; then
    exit 0
fi

get_rectangles() {
    local monitor_json
    local focused_workspace
    local secondary_workspace

    monitor_json="$(hyprctl monitors -j 2>&1)" || fail 1 "hyprctl monitors failed: $monitor_json"
    focused_workspace="$(printf '%s' "$monitor_json" | jq -r '.[] | select(.focused).activeWorkspace.id' 2>&1)" || fail 1 "could not read focused workspace: $focused_workspace"
    secondary_workspace="$(printf '%s' "$monitor_json" | jq -r '.[] | select(.focused | not).activeWorkspace.id' 2>&1)" || fail 1 "could not read secondary workspace: $secondary_workspace"

    [[ -n "$focused_workspace" && "$focused_workspace" != "null" ]] || fail 1 "could not determine focused workspace"
    [[ -n "$secondary_workspace" && "$secondary_workspace" != "null" ]] || fail 1 "could not determine secondary workspace"

    printf '%s\n' '0,0 1920x1080' '1920,-840 1080x1920'

    local clients_json
    clients_json="$(hyprctl clients -j 2>&1)" || fail 1 "hyprctl clients failed: $clients_json"
    printf '%s' "$clients_json" | jq -r --arg ws "$focused_workspace" --arg sec "$secondary_workspace" '.[] | select(.workspace.id == ($ws|tonumber) or .workspace.id == ($sec|tonumber)) | "\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"' 2>&1 || fail 1 "could not extract visible window rectangles"
}

RECTS="$(get_rectangles)"
[[ -n "$RECTS" ]] || fail 1 "no selectable rectangles were produced"

wayfreeze >/dev/null 2>&1 &
WAYFREEZE_PID=$!
sleep .1

if ! kill -0 "$WAYFREEZE_PID" >/dev/null 2>&1; then
    wait "$WAYFREEZE_PID" >/dev/null 2>&1 || true
    fail 1 "wayfreeze exited before selection started"
fi

if SELECTION="$(printf '%s\n' "$RECTS" | slurp 2>/tmp/screenshot-to-obsidian-slurp-error-$BASHPID)"; then
    SLURP_STATUS=0
else
    SLURP_STATUS=$?
fi
SLURP_ERROR="$(cat /tmp/screenshot-to-obsidian-slurp-error-$BASHPID 2>/dev/null || true)"
rm -f /tmp/screenshot-to-obsidian-slurp-error-$BASHPID

kill "$WAYFREEZE_PID" >/dev/null 2>&1 || true
wait "$WAYFREEZE_PID" >/dev/null 2>&1 || true
WAYFREEZE_PID=""

if (( SLURP_STATUS != 0 )); then
    if [[ -z "$SLURP_ERROR" && ( "$SLURP_STATUS" -eq 1 || "$SLURP_STATUS" -eq 130 ) ]]; then
        exit 0
    fi
    fail "$SLURP_STATUS" "slurp failed with exit code $SLURP_STATUS${SLURP_ERROR:+: $SLURP_ERROR}"
fi

[[ -n "${SELECTION:-}" ]] || exit 0

if [[ "$SELECTION" =~ ^([0-9]+),([0-9]+)[[:space:]]([0-9]+)x([0-9]+)$ ]]; then
    if (( BASH_REMATCH[3] * BASH_REMATCH[4] < 20 )); then
        CLICK_X="${BASH_REMATCH[1]}"
        CLICK_Y="${BASH_REMATCH[2]}"
        while IFS= read -r RECT; do
            if [[ "$RECT" =~ ^([0-9]+),([0-9]+)[[:space:]]([0-9]+)x([0-9]+)$ ]]; then
                RECT_X="${BASH_REMATCH[1]}"
                RECT_Y="${BASH_REMATCH[2]}"
                RECT_WIDTH="${BASH_REMATCH[3]}"
                RECT_HEIGHT="${BASH_REMATCH[4]}"
                if (( CLICK_X >= RECT_X && CLICK_X < RECT_X + RECT_WIDTH && CLICK_Y >= RECT_Y && CLICK_Y < RECT_Y + RECT_HEIGHT )); then
                    SELECTION="${RECT_X},${RECT_Y} ${RECT_WIDTH}x${RECT_HEIGHT}"
                    break
                fi
            fi
        done <<< "$RECTS"
    fi
fi

if GRIM_ERROR="$(grim -g "$SELECTION" "$TMP_PATH" 2>&1 >/dev/null)"; then
    GRIM_STATUS=0
else
    GRIM_STATUS=$?
fi
if (( GRIM_STATUS != 0 )); then
    rm -f "$TMP_PATH"
    fail "$GRIM_STATUS" "grim failed with exit code $GRIM_STATUS${GRIM_ERROR:+: $GRIM_ERROR}"
fi

[[ -f "$TMP_PATH" ]] || exit 0

printf -v SAFE_SCRIPT '%q' "$SCRIPT_DIR/screenshot-gum-menu.sh"
printf -v SAFE_TMP '%q' "$TMP_PATH"
printf -v SAFE_NAME '%q' "$IMG_NAME"
DISPATCH="[float; size 430 250; center 1] kitty --class screenshot-gum -e $SAFE_SCRIPT $SAFE_TMP $SAFE_NAME"

if DISPATCH_ERROR="$(hyprctl dispatch exec "$DISPATCH" 2>&1 >/dev/null)"; then
    DISPATCH_STATUS=0
else
    DISPATCH_STATUS=$?
fi
if (( DISPATCH_STATUS != 0 )); then
    fail "$DISPATCH_STATUS" "hyprctl failed to launch screenshot menu with exit code $DISPATCH_STATUS${DISPATCH_ERROR:+: $DISPATCH_ERROR}"
fi
