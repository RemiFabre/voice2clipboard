#!/bin/bash
# Queue a spoken message for the earbuds. Usage: inbox_post.sh [--from name] [--lang en|fr] "text"
# Without --lang the language is guessed from the text (speech_render.py lang; English unless
# clearly French). The introduction and the counts are said in the message's language and voice.
# The text is queued at once and this script returns; in the background the voice is rendered
# (the sender's voice, its introduction, the "N older waiting" counts), and only then does the
# ding play. So when Remi hears the ding, the message is ready and starts the moment he presses.
# If the render fails, the ding still plays and playback falls back to rendering on demand.
source "$(dirname "$0")/lib.sh"
from="agent"; lang=""
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --from) from="$2"; shift 2 ;;
    --lang) lang="$2"; shift 2 ;;
    *) shift ;;
  esac
done
text="${*:-$(cat)}"
[[ -z "$text" ]] && exit 0
lang_note=""
if [[ "$lang" != "en" && "$lang" != "fr" ]]; then
  lang="$(python3 "$SPEECH_RENDER" lang "$text" 2>/dev/null)"; lang_note=" (guessed)"
  [[ "$lang" == "fr" ]] || lang="en"
fi
safe_from="$(printf '%s' "$from" | tr -c 'A-Za-z0-9_-' '_' | head -c 40)"
stamp="$(python3 -c 'import time; print(int(time.time()*1000))')"
stem="$INBOX_DIR/${stamp}-${safe_from}"
printf 'lang=%s\nfrom=%s\n\n%s\n' "$lang" "$from" "$text" >"$stem.txt"
log "inbox_post from=$from lang=$lang$lang_note: $(printf '%s' "$text" | head -c 80)"
: >"$stem.rendering"   # until the voice is ready this message does not exist for a double press (lib.sh)
(
  voice="$(voice_for "$from" "$lang")"
  started="$(date +%s)"
  if render_speech "$lang" "$voice" "$stem.wav.tmp.wav" "$text" && [[ -f "$stem.txt" ]]; then
    mv "$stem.wav.tmp.wav" "$stem.wav"
    intro="$(intro_text_for "$from" "$lang")"
    [[ -n "$intro" ]] && cached_clip "$lang" "$voice" "$intro" >/dev/null
    waiting="$(ls "$INBOX_DIR"/*.txt 2>/dev/null | wc -l | tr -d ' ')"
    for n in $(seq 1 "$(( waiting < 5 ? waiting : 5 ))"); do cached_clip "$lang" "$voice" "$(count_text "$lang" "$n")" >/dev/null; done
    if [[ "$lang" != "en" ]]; then   # the short answers of a double press, in this language too
      cached_clip "$lang" "$(voice_for "" "$lang")" "$(not_ready_text "$lang")" >/dev/null
      cached_clip "$lang" "$(voice_for "" "$lang")" "$(no_messages_text "$lang")" >/dev/null
    fi
    log "inbox_post pre-rendered [$voice] in $(( $(date +%s) - started )) s: $(basename "$stem")"
  else
    rm -f "$stem.wav.tmp.wav"   # already read, or the render failed: playback renders on demand
    log "inbox_post: no pre-render for $(basename "$stem") (read before it was ready, or the voice failed)"
  fi
  rm -f "$stem.rendering"
  [[ -f "$stem.txt" ]] && "$(dirname "$0")/ding.sh"
) >/dev/null 2>&1 &
disown 2>/dev/null || true
