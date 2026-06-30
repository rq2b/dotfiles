# If not running interactively, don't do anything
[[ $- != *i* ]] && return

# omarchy defaults
[[ -f /usr/share/omarchy-zsh/shell/zoptions ]] && source /usr/share/omarchy-zsh/shell/zoptions
[[ -f /usr/share/omarchy-zsh/shell/all ]] && source /usr/share/omarchy-zsh/shell/all

# aliases

alias claer='clear'
alias terminal-copy='kitty @ get-text --extent=all | wl-copy'
alias striprefs="perl -0777 -i -pe 's/\s*:contentReference\[oaicite:\d+\]\{index=\d+\}//g'"
alias ctx="xctx"
alias ncat="xcat"

# yt-dlp

ytopus() {
    yt-dlp \
        -f "bestaudio[ext=webm]/bestaudio" \
        --extract-audio \
        --audio-format opus \
        --audio-quality 0 \
        --embed-metadata \
        --embed-thumbnail \
        -o "%(title)s.%(ext)s" \
        "$@"
}

ytopus-playlist() {
    yt-dlp \
        -f "bestaudio[ext=webm]/bestaudio" \
        --extract-audio \
        --audio-format opus \
        --audio-quality 0 \
        --embed-metadata \
        --embed-thumbnail \
        -o "%(playlist_index)03d - %(title)s.%(ext)s" \
        "$@"
}

ytopus-dir() {
    local dest="$1"
    shift

    mkdir -p "$dest"

    yt-dlp \
        -f "bestaudio[ext=webm]/bestaudio" \
        --extract-audio \
        --audio-format opus \
        --audio-quality 0 \
        --embed-metadata \
        --embed-thumbnail \
        -o "$dest/%(playlist_index)03d - %(title)s.%(ext)s" \
        "$@"
}

ytmusic-playlist() {
    local url="$1"

    yt-dlp \
        -f "bestaudio[ext=webm]/bestaudio" \
        --extract-audio \
        --audio-format opus \
        --audio-quality 0 \
        --embed-metadata \
        --embed-thumbnail \
        -o "%(playlist_title)s/%(playlist_index)03d - %(title)s.%(ext)s" \
        "$url"
}

yttxt() {
    if [[ $# -ne 1 ]]; then
        echo "Usage: yttxt <youtube-url>"
        return 1
    fi

    local url="$1"

    yt-dlp \
        --skip-download \
        --write-auto-subs \
        --write-subs \
        --sub-langs "en-orig,en.*" \
        --sub-format srt \
        --convert-subs srt \
        -o "%(title)s.%(ext)s" \
        "$url" || return

    local srt
    srt=$(ls -t *.en-orig.srt *.en.srt 2>/dev/null | head -n1) || return

    srt2txt "$srt" > "${srt%.srt}.txt"

    echo "Created ${srt%.srt}.txt"
}

# utils

detach() {
    if [[ $# -eq 0 ]]; then
        echo "Usage: detach <command> [args...]"
        return 1
    fi

    local cmd="$1"
    local name log

    name=$(basename -- "$cmd")
    log="/tmp/${name}.log"

    setsid "$@" </dev/null >>"$log" 2>&1 &
    echo "Detached: $*"
    echo "Log: $log"
}
srt2txt() {
    if [[ $# -ne 1 ]]; then
        echo "Usage: srt2txt <file.srt>"
        return 1
    fi

    perl -ne '
        chomp;
        next if /^\d+$/;
        next if /-->/;
        next if /^\s*$/;
        s/^>>\s*//;
        s/<[^>]+>//g;
        print "$_\n";
    ' "$1" |
    awk '!seen[$0]++'
}

# modules

if [[ -d ~/.zshrc.d ]]; then
    for f (~/.zshrc.d/*.zsh(N)); do
        source "$f"
    done
fi
