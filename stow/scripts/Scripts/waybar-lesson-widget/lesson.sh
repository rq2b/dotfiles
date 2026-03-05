#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SCHEDULE="$DIR/schedule.json"

# Dependencies: jq
command -v jq >/dev/null 2>&1 || { echo "jq missing"; exit 0; }

# Current time pieces
now_epoch=$(date +%s)
dow=$(LC_ALL=C date +%A | tr '[:upper:]' '[:lower:]')   # monday/tuesday/...
today=$(date +%F)                              # YYYY-MM-DD
time_hms=$(date +%H:%M:%S)
date_fmt=$(date '+%A, %d.%m.%y')

# Pull today's lessons as compact JSON array
lessons_json=$(jq -c --arg d "$dow" '.days[$d] // []' "$SCHEDULE" 2>/dev/null || echo "[]")
lesson_count=$(jq 'length' <<<"$lessons_json")

# Helper: "HH:MM" -> epoch for today
to_epoch_today() {
  local hhmm="$1"
  date -d "${today} ${hhmm}:00" +%s
}

fmt_hms() {
  local s="$1"
  if (( s < 0 )); then s=0; fi

  local h=$(( s / 3600 ))
  local m=$(( (s % 3600) / 60 ))
  local r=$(( s % 60 ))

  if (( h > 0 )); then
    printf "%dh %02dm %02ds" "$h" "$m" "$r"
  else
    printf "%dm %02ds" "$m" "$r"
  fi
}

status_text=""
tooltip=""

if (( lesson_count == 0 )); then
  status_text=""
  tooltip="No lessons scheduled for today."
else
  # Find current or next lesson
  current_idx=-1
  next_idx=-1

  for i in $(seq 0 $((lesson_count - 1))); do
    start=$(jq -r ".[$i].start" <<<"$lessons_json")
    end=$(jq -r ".[$i].end" <<<"$lessons_json")

    start_epoch=$(to_epoch_today "$start")
    end_epoch=$(to_epoch_today "$end")

    if (( now_epoch >= start_epoch && now_epoch < end_epoch )); then
      current_idx=$i
      break
    fi

    if (( now_epoch < start_epoch )); then
      next_idx=$i
      break
    fi
  done

  if (( current_idx >= 0 )); then
    name=$(jq -r ".[$current_idx].name" <<<"$lessons_json")
    start=$(jq -r ".[$current_idx].start" <<<"$lessons_json")
    end=$(jq -r ".[$current_idx].end" <<<"$lessons_json")
    end_epoch=$(to_epoch_today "$end")
    left=$(( end_epoch - now_epoch ))
    status_text="$name [$(fmt_hms "$left") left]"
    tooltip="$name - ${start}–${end}"

    # Also show next lesson in tooltip if exists
    if (( current_idx + 1 < lesson_count )); then
      nname=$(jq -r ".[$((current_idx + 1))].name" <<<"$lessons_json")
      nstart=$(jq -r ".[$((current_idx + 1))].start" <<<"$lessons_json")
      tooltip="${tooltip} - ${nname} @ ${nstart}"
    else
      tooltip="${tooltip}"
    fi

  elif (( next_idx >= 0 )); then
    name=$(jq -r ".[$next_idx].name" <<<"$lessons_json")
    start=$(jq -r ".[$next_idx].start" <<<"$lessons_json")
    end=$(jq -r ".[$next_idx].end" <<<"$lessons_json")
    start_epoch=$(to_epoch_today "$start")
    in_s=$(( start_epoch - now_epoch ))
    status_text="$name [in $(fmt_hms "$in_s")]"
    tooltip="$name - ${start}–${end}"

  else
    # After last lesson
    last_name=$(jq -r ".[-1].name" <<<"$lessons_json")
    last_end=$(jq -r ".[-1].end" <<<"$lessons_json")
    status_text=""
    tooltip="Last: ${last_name} - Ended: ${last_end}"
  fi
fi

# Escape quotes/backslashes/newlines for JSON
json_escape() {
  sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e ':a;N;$!ba;s/\n/\\n/g'
}

base="${date_fmt} - ${time_hms}"
if [[ -n "${status_text}" ]]; then
  text="${base} - ${status_text}"
else
  text="${base}"
fi

printf '{"text":"%s","tooltip":"%s","class":"lesson"}\n' \
  "$(printf '%s' "$text" | json_escape)" \
  "$(printf '%s' "$tooltip" | json_escape)"
