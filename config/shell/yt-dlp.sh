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
    local lang="en"
    local url id srt txt

    case "$1" in
        --english|-e)
            lang="en"
            shift
            ;;
        --russian|-r)
            lang="ru"
            shift
            ;;
        --ukrainian|-u)
            lang="uk"
            shift
            ;;
    esac

    for url in "$@"; do
        id=$(yt-dlp --get-id "$url") || {
            echo "Failed to get video ID: $url" >&2
            continue
        }

        yt-dlp \
            --skip-download \
            --write-subs \
            --write-auto-subs \
            --sub-langs "$lang" \
            --sub-format srt \
            --output "%(title)s [%(id)s].%(ext)s" \
            "$url" || continue

        srt=$(find . -maxdepth 1 -type f \
            -name "*[$id].*.srt" \
            -print -quit)

        if [[ -z $srt || ! -f $srt ]]; then
            echo "No $lang SRT found for $url" >&2
            continue
        fi

        txt="${srt%.srt}.txt"

        awk '
        /^[0-9]+$/        { next }
        / --> /           { next }
        /^$/              { next }
        /^\[[^]]+\]$/     { next }
        { print }
        ' "$srt" > "$txt"

        rm -f -- *"[$id]".*.srt

        echo "Created: $txt"
    done
}
