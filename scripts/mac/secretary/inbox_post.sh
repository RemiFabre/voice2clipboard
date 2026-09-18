#!/bin/bash
# Queue a spoken message and ding the earbuds. Usage: inbox_post.sh [--from name] [--lang en|fr] "text"
# The message is read when the user presses the earbud button (tts_toggle.sh / inbox_read_next.sh).
source "$(dirname "$0")/lib.sh"
from="agent"; lang="en"
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --from) from="$2"; shift 2 ;;
    --lang) lang="$2"; shift 2 ;;
    *) shift ;;
  esac
done
text="${*:-$(cat)}"
[[ -z "$text" ]] && exit 0
safe_from="$(printf '%s' "$from" | tr -c 'A-Za-z0-9_-' '_' | head -c 40)"
stamp="$(python3 -c 'import time; print(int(time.time()*1000))')"
printf 'lang=%s\nfrom=%s\n\n%s\n' "$lang" "$from" "$text" >"$INBOX_DIR/${stamp}-${safe_from}.txt"
log "inbox_post from=$from: $(printf '%s' "$text" | head -c 80)"
if dictation_active; then
  # queue silently now, ding once the dictation is over
  nohup bash -c 'source "$1/lib.sh"; wait_for_dictation_end; exec "$1/ding.sh"' _ "$(cd "$(dirname "$0")" && pwd)" >/dev/null 2>&1 &
else
  "$(dirname "$0")/ding.sh"
fi
