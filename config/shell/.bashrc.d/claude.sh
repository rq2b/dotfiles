export CLAUDE_PROXY_DIR="$HOME/repos/claude-sandbox"

proxy-up() {
  docker compose -f "$CLAUDE_PROXY_DIR/docker-compose.yml" up -d proxy
}

cc() {
  proxy-up >/dev/null || return
  sbx run --name "${CLAUDE_SBX_NAME:-claude-$(basename "$PWD")}" claude
}

claude-profile() {
    if (( $# != 2 )); then
        echo "Usage: claude-profile <sandbox> <profile>"
        return 1
    fi

    local sandbox="$1"
    local profile="$2"

    local profile_file="$HOME/.config/claude/sandboxes/${profile}.env"

    if [[ ! -f "$profile_file" ]]; then
        echo "Profile not found:"
        echo "  $profile_file"
        return 1
    fi

    echo "Installing profile '$profile' into '$sandbox'..."

    sbx cp "$profile_file" "$sandbox:/etc/claude.env"

    sbx exec "$sandbox" bash -c '
cat >/etc/sandbox-persistent.sh <<EOF
#!/usr/bin/env bash

set -a

[ -f /etc/claude.env ] && . /etc/claude.env

set +a
EOF

chmod +x /etc/sandbox-persistent.sh
'

    echo
}

claude-profile-check() {
    if (( $# != 1 )); then
        echo "Usage: claude-profile-check <sandbox>"
        return 1
    fi

    local sandbox="$1"

    local token
    token="$(sbx exec "$sandbox" bash -c '
        grep -m1 "^TOKEN_NAME=" /etc/claude.env 2>/dev/null | cut -d= -f2-
    ')"

    if [[ -z "$token" ]]; then
        echo "Token name is not set."
    else
        echo "$token"
    fi
}

cc-native() {
    proxy-up >/dev/null || return

    if [[ -z "${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
        echo "ANTHROPIC_AUTH_TOKEN is not set."
        return 1
    fi

    ANTHROPIC_BASE_URL=http://127.0.0.1:8787 \
        claude --dangerously-skip-permissions "$@"
}

claude-source-profile() {
    if (( $# != 1 )); then
        echo "Usage: claude-source-profile <profile>"
        return 1
    fi

    local profile="$HOME/.config/claude/sandboxes/$1.env"

    [[ -f "$profile" ]] || {
        echo "Profile not found: $profile"
        return 1
    }

    set -a
    source "$profile"
    set +a
}
