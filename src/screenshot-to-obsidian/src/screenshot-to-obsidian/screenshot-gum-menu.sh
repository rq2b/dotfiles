#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TMP_PATH="${1:?Usage: screenshot-gum-menu.sh /tmp/file.png name.png}"
IMG_NAME="${2:?Usage: screenshot-gum-menu.sh /tmp/file.png name.png}"
MOVE_CURSOR="$HOME/src/move-cursor-to-window/move-cursor-to-window.sh"
[[ -x "$MOVE_CURSOR" ]] || MOVE_CURSOR="$HOME/Scripts/move-cursor-to-window/move-cursor-to-window.sh"

notify_error() {
    local action="$1"
    local message="$2"
    if command -v notify-send >/dev/null 2>&1; then
        notify-send -u critical -t 5000 "Screenshot to Obsidian: $action failed" "$message" >/dev/null 2>&1 || true
    fi
    printf 'ERROR: %s: %s\n' "$action" "$message" >&2
}

fail() {
    local action="$1"
    local status="$2"
    local message="$3"
    notify_error "$action" "$message"
    exit "$status"
}

cleanup() {
    if [[ -n "${TMP_PATH:-}" ]]; then
        rm -f -- "$TMP_PATH" >/dev/null 2>&1 || true
    fi
}

[[ -f "$TMP_PATH" ]] || fail "Menu" 1 "temporary screenshot not found: $TMP_PATH"

trap cleanup EXIT

if [[ ! -x "$MOVE_CURSOR" ]]; then
    fail "Move cursor" 1 "cursor helper not found or not executable: $MOVE_CURSOR"
fi

if MOVE_ERROR="$("$MOVE_CURSOR" screenshot-gum 2>&1 >/dev/null)"; then
    MOVE_STATUS=0
else
    MOVE_STATUS=$?
fi
if (( MOVE_STATUS != 0 )); then
    fail "Move cursor" "$MOVE_STATUS" "cursor helper exited with code $MOVE_STATUS${MOVE_ERROR:+: $MOVE_ERROR}"
fi

if ACTIONS_STRING=$(gum choose --no-limit \
    --item.foreground="#878787" \
    --cursor.foreground="#fff" \
    --cursor.background="" \
    --selected.background="" \
    --header="" \
    --selected-prefix="✓ " \
    "Send to Obsidian" \
    "Save to Downloads" \
    "Copy to Clipboard" \
    "Open in Editor" \
    "Save to Location"); then
    GUM_STATUS=0
else
    GUM_STATUS=$?
fi

if (( GUM_STATUS != 0 )); then
    if (( GUM_STATUS == 1 || GUM_STATUS == 130 )); then
        exit 0
    fi
    fail "Gum menu" "$GUM_STATUS" "gum exited with code $GUM_STATUS"
fi

ACTIONS=()
while IFS= read -r LINE; do
    [[ -n "$LINE" ]] && ACTIONS+=("$LINE")
done <<< "$ACTIONS_STRING"

if (( ${#ACTIONS[@]} == 0 )); then
    exit 0
fi

if WORKSPACE_ERROR="$(hyprctl dispatch movetoworkspacesilent special:screenshot-gum 2>&1 >/dev/null)"; then
    WORKSPACE_STATUS=0
else
    WORKSPACE_STATUS=$?
fi
if (( WORKSPACE_STATUS != 0 )); then
    fail "Workspace dispatch" "$WORKSPACE_STATUS" "hyprctl exited with code $WORKSPACE_STATUS${WORKSPACE_ERROR:+: $WORKSPACE_ERROR}"
fi

for ACTION in "${ACTIONS[@]}"; do
    case "$ACTION" in
        "Send to Obsidian")
            if ERROR_OUTPUT="$("$SCRIPT_DIR/screenshot-to-obsidian.sh" "$TMP_PATH" "$IMG_NAME" 2>&1 >/dev/null)"; then
                STATUS=0
            else
                STATUS=$?
            fi
            if (( STATUS != 0 )); then
                fail "$ACTION" "$STATUS" "screenshot-to-obsidian exited with code $STATUS${ERROR_OUTPUT:+: $ERROR_OUTPUT}"
            fi
            ;;
        "Save to Downloads")
            DESTINATION="$HOME/Downloads/$IMG_NAME"
            if ! cp -f -- "$TMP_PATH" "$DESTINATION" 2>/tmp/screenshot-to-obsidian-action-error-$BASHPID; then
                ERROR_OUTPUT="$(cat /tmp/screenshot-to-obsidian-action-error-$BASHPID 2>/dev/null || true)"
                rm -f /tmp/screenshot-to-obsidian-action-error-$BASHPID
                fail "$ACTION" 1 "could not copy screenshot to $DESTINATION${ERROR_OUTPUT:+: $ERROR_OUTPUT}"
            fi
            rm -f /tmp/screenshot-to-obsidian-action-error-$BASHPID
            ;;
        "Copy to Clipboard")
            if wl-copy --type image/png < "$TMP_PATH" >/dev/null 2>/tmp/screenshot-to-obsidian-action-error-$BASHPID; then
                STATUS=0
            else
                STATUS=$?
            fi
            if (( STATUS != 0 )); then
                ERROR_OUTPUT="$(cat /tmp/screenshot-to-obsidian-action-error-$BASHPID 2>/dev/null || true)"
                rm -f /tmp/screenshot-to-obsidian-action-error-$BASHPID
                fail "$ACTION" "$STATUS" "wl-copy exited with code $STATUS${ERROR_OUTPUT:+: $ERROR_OUTPUT}"
            fi
            rm -f /tmp/screenshot-to-obsidian-action-error-$BASHPID
            ;;
        "Open in Editor")
            readonly TMP="$TMP_PATH"
            readonly OUT="$HOME/Downloads/$IMG_NAME"
            setsid bash -c '
                set -euo pipefail
                trap '\''rm -f -- "$1"'\'' EXIT
                satty \
                    --filename "$1" \
                    --output-filename "$2" \
                    --actions-on-escape exit \
                    --early-exit save save-as
            ' _ "$TMP" "$OUT" >/dev/null 2>/tmp/screenshot-to-obsidian-action-error-$BASHPID &
            SATTY_PID=$!
            if wait "$SATTY_PID"; then
                STATUS=0
            else
                STATUS=$?
            fi
            if (( STATUS != 0 )); then
                ERROR_OUTPUT="$(cat /tmp/screenshot-to-obsidian-action-error-$BASHPID 2>/dev/null || true)"
                rm -f /tmp/screenshot-to-obsidian-action-error-$BASHPID
                fail "$ACTION" "$STATUS" "satty exited with code $STATUS${ERROR_OUTPUT:+: $ERROR_OUTPUT}"
            fi
            rm -f /tmp/screenshot-to-obsidian-action-error-$BASHPID
            TMP_PATH=""
            ;;
        "Save to Location")
            if SAVE_PATH=$(zenity --file-selection --save --filename="$HOME/$IMG_NAME" --title="Save Screenshot" 2>/tmp/screenshot-to-obsidian-action-error-$BASHPID); then
                STATUS=0
            else
                STATUS=$?
            fi
            ERROR_OUTPUT="$(cat /tmp/screenshot-to-obsidian-action-error-$BASHPID 2>/dev/null || true)"
            rm -f /tmp/screenshot-to-obsidian-action-error-$BASHPID
            if (( STATUS != 0 )); then
                if (( STATUS == 1 || STATUS == 130 )); then
                    continue
                fi
                fail "$ACTION" "$STATUS" "zenity exited with code $STATUS${ERROR_OUTPUT:+: $ERROR_OUTPUT}"
            fi
            if [[ -n "$SAVE_PATH" ]]; then
                if ! cp -f -- "$TMP_PATH" "$SAVE_PATH" 2>/tmp/screenshot-to-obsidian-action-error-$BASHPID; then
                    ERROR_OUTPUT="$(cat /tmp/screenshot-to-obsidian-action-error-$BASHPID 2>/dev/null || true)"
                    rm -f /tmp/screenshot-to-obsidian-action-error-$BASHPID
                    fail "$ACTION" 1 "could not copy screenshot to $SAVE_PATH${ERROR_OUTPUT:+: $ERROR_OUTPUT}"
                fi
                rm -f /tmp/screenshot-to-obsidian-action-error-$BASHPID
            fi
            ;;
    esac
done
