#!/usr/bin/env bash

_xmirror_env_file="${XDG_CONFIG_HOME:-$HOME/.config}/xmirror/xmirror.env"

if [[ -f "$_xmirror_env_file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$_xmirror_env_file"
    set +a
fi

unset _xmirror_env_file