#!/usr/bin/env bash

readonly XMIRROR_DATASET_TABLE="${XDG_CONFIG_HOME:-$HOME/.config}/xmirror/datasets.tab"

DATASET_NAMES=()
DATASET_PATHS=()
DATASET_PRE_MIRROR_HOOKS=()
DATASET_POST_MIRROR_HOOKS=()
DATASET_PRE_RESTORE_HOOKS=()
DATASET_POST_RESTORE_HOOKS=()
DATASET_EXCLUDES=()

_xmirror_trim_cr() {
    printf '%s' "${1%$'\r'}"
}

_xmirror_empty_to_blank() {
    local value="$1"
    if [[ "$value" == "-" ]]; then
        printf '\n'
    else
        printf '%s\n' "$value"
    fi
}

_xmirror_csv_to_newlines() {
    local value="$1"

    if [[ "$value" == "-" || -z "$value" ]]; then
        printf '\n'
        return 0
    fi

    printf '%s\n' "$value" | tr ',' '\n'
}

load_datasets_tab() {
    [[ -f "$XMIRROR_DATASET_TABLE" ]] || {
        printf 'xmirror-config: dataset table not found: %s\n' "$XMIRROR_DATASET_TABLE" >&2
        return 1
    }

    DATASET_NAMES=()
    DATASET_PATHS=()
    DATASET_PRE_MIRROR_HOOKS=()
    DATASET_POST_MIRROR_HOOKS=()
    DATASET_PRE_RESTORE_HOOKS=()
    DATASET_POST_RESTORE_HOOKS=()
    DATASET_EXCLUDES=()

    local line_no=0
    local name path pre_mirror post_mirror pre_restore post_restore excludes extra

    while IFS=$'\t' read -r name path pre_mirror post_mirror pre_restore post_restore excludes extra; do
        line_no=$((line_no + 1))

        name="$(_xmirror_trim_cr "${name:-}")"
        path="$(_xmirror_trim_cr "${path:-}")"
        pre_mirror="$(_xmirror_trim_cr "${pre_mirror:-}")"
        post_mirror="$(_xmirror_trim_cr "${post_mirror:-}")"
        pre_restore="$(_xmirror_trim_cr "${pre_restore:-}")"
        post_restore="$(_xmirror_trim_cr "${post_restore:-}")"
        excludes="$(_xmirror_trim_cr "${excludes:-}")"
        extra="$(_xmirror_trim_cr "${extra:-}")"

        [[ -n "$name" ]] || continue
        [[ "$name" =~ ^[[:space:]]*# ]] && continue

        [[ -z "$extra" ]] || {
            printf 'xmirror-config: too many fields in %s at line %d\n' "$XMIRROR_DATASET_TABLE" "$line_no" >&2
            return 1
        }

        [[ -n "$path" ]] || {
            printf 'xmirror-config: missing path in %s at line %d\n' "$XMIRROR_DATASET_TABLE" "$line_no" >&2
            return 1
        }

        [[ "$path" != "-" ]] || {
            printf 'xmirror-config: invalid path "-" in %s at line %d\n' "$XMIRROR_DATASET_TABLE" "$line_no" >&2
            return 1
        }

        DATASET_NAMES+=("$name")
        DATASET_PATHS+=("$path")
        DATASET_PRE_MIRROR_HOOKS+=("$(_xmirror_empty_to_blank "$pre_mirror")")
        DATASET_POST_MIRROR_HOOKS+=("$(_xmirror_empty_to_blank "$post_mirror")")
        DATASET_PRE_RESTORE_HOOKS+=("$(_xmirror_empty_to_blank "$pre_restore")")
        DATASET_POST_RESTORE_HOOKS+=("$(_xmirror_empty_to_blank "$post_restore")")
        DATASET_EXCLUDES+=("$(_xmirror_csv_to_newlines "$excludes")")
    done < "$XMIRROR_DATASET_TABLE"
}