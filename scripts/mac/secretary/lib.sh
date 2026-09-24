#!/bin/bash
# Shared paths for the voice secretary layer (earbuds -> dictation -> Claude sessions -> spoken replies).
ROOT_DIR="/Users/remi/voice2clipboard"
SECRETARY_RUNTIME="${SECRETARY_RUNTIME:-$ROOT_DIR/runtime/secretary}"   # overridable for tests
INBOX_DIR="$SECRETARY_RUNTIME/inbox"          # queued spoken messages, oldest first
SPOKEN_DIR="$SECRETARY_RUNTIME/spoken"        # archive of what was read
TTS_PID_FILE="$SECRETARY_RUNTIME/tts.pid"     # afplay pid while speaking
TTS_STATE_FILE="$SECRETARY_RUNTIME/tts.state" # playing | paused
TTS_WAV="$SECRETARY_RUNTIME/tts_current.wav"
VOICE_MODE_FLAG="$SECRETARY_RUNTIME/voice_mode.on"
SESSION_FILE="$SECRETARY_RUNTIME/secretary_iterm_session"          # iTerm unique id dictations are typed into
SECRETARY_CLAUDE_SESSION_FILE="$SECRETARY_RUNTIME/secretary_claude_session"  # Claude session id of the secretary
SECRETARY_CLAUDE_PID_FILE="$SECRETARY_RUNTIME/secretary_claude_pid"          # its claude process
LOG_FILE="$SECRETARY_RUNTIME/secretary.log"
DING_SOUND="$ROOT_DIR/sounds/cue_ding.aiff"  # distinct from the recorder cues and the done sound
REFUSE_SOUND="$ROOT_DIR/sounds/cue_refuse.aiff"  # "cannot do that now": a press was received and refused
READY_SOUND="$ROOT_DIR/sounds/cue_ready.aiff"    # headset reconnected and the whole chain checks out
FAIL_SOUND="$ROOT_DIR/sounds/cue_fail.aiff"
HEADSET_NAME_PATTERN="${VOICE2CLIPBOARD_HEADSET_PATTERN:-Shokz|OpenFit}"   # Bluetooth name of the earbuds
# Voice engine since 2026-09-20: Kyutai Pocket TTS, through drop-in commands that keep the kokoro-say
# options and the "kokoro-daemon status|start" control words (the variable names are historical).
# To go back to Kokoro: .venv/bin/kokoro-say and .venv/bin/local-tts here, and the Kokoro voices below.
KOKORO_SAY="${KOKORO_SAY:-/Users/remi/local-tts-lab/bin/pocket-say}"   # overridable for tests
KOKORO_CTL="${KOKORO_CTL:-/Users/remi/local-tts-lab/bin/pocket-ctl}"
export KOKORO_SAY KOKORO_CTL
CLIP_CACHE_DIR="$SECRETARY_RUNTIME/clip_cache"   # short reusable clips: introductions, "2 older waiting."
SPEECH_RENDER="$ROOT_DIR/scripts/mac/secretary/speech_render.py"
export PYTORCH_ENABLE_MPS_FALLBACK=1
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
mkdir -p "$INBOX_DIR" "$SPOKEN_DIR" "$CLIP_CACHE_DIR"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG_FILE"; }

tts_pid() {
  local pid
  pid="$(cat "$TTS_PID_FILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then echo "$pid"; else rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE"; fi
}

# Sound clock of the message being played. The player process outlives its sound by more than a
# second (measured 2026-09-20: a 1.1 s cue keeps afplay alive 2.3 s), and during that tail the
# system used to believe a message was still playing: a single press meant "pause", in silence,
# when Remi wanted to dictate (half of all pauses in the log were followed by a second press
# within 6 s). The clock knows how much SOUND is left: "<seconds left> <epoch of the last
# (re)start, 0 while paused>". With under TTS_TAIL_S left the message counts as finished.
TTS_CLOCK_FILE="$SECRETARY_RUNTIME/tts.clock"
TTS_TAIL_S="${SECRETARY_TTS_TAIL_S:-0.3}"   # the sound itself starts about a quarter second after the player
now_hires() { perl -MTime::HiRes=time -e 'printf "%.2f", time'; }
wav_seconds() { afinfo "$1" 2>/dev/null | sed -nE 's/^estimated duration: ([0-9.]+) sec.*/\1/p'; }
tts_clock_start() { [[ -n "${1:-}" ]] && printf '%s %s\n' "$1" "$(now_hires)" >"$TTS_CLOCK_FILE"; }
tts_sound_left() {   # prints the seconds of sound left; nothing when unknown
  local left since
  [[ -f "$TTS_CLOCK_FILE" ]] || return 0
  read -r left since <"$TTS_CLOCK_FILE" || return 0
  [[ -n "$left" && -n "$since" ]] || return 0
  perl -e 'printf "%.2f", $ARGV[1] > 0 ? $ARGV[0] - ($ARGV[2] - $ARGV[1]) : $ARGV[0]' -- "$left" "$since" "$(now_hires)"
}
tts_sound_over() {
  local left; left="$(tts_sound_left)"
  [[ -n "$left" ]] && perl -e 'exit($ARGV[0] < $ARGV[1] ? 0 : 1)' -- "$left" "$TTS_TAIL_S"
}
# Pause and resume. Until 2026-09-21 a pause was SIGSTOP on afplay and a resume SIGCONT. Measured
# that day: afplay keeps to the wall clock, so after SIGCONT it drops or rushes through everything
# that "should" have played during the pause (a 12 s file paused for 4 s still ends after 12 s).
# Remi heard exactly that: the message resumed accelerated, then a piece was missing. A real
# pause therefore ends the player and remembers the position; say_now.sh, which owns the message
# (TTS_OWNER_FILE), waits and on resume plays the rest from a little before that point.
TTS_ENDED_FILE="$SECRETARY_RUNTIME/tts.ended"     # touched when a message stops sounding (see on_gesture.sh, "pause")
TTS_OWNER_FILE="$SECRETARY_RUNTIME/tts.owner"     # pid of the say_now.sh that owns the playing message
TTS_PAUSE_FILE="$SECRETARY_RUNTIME/tts.paused"    # exists while paused: seconds of sound that were left
TTS_RESUME_FILE="$SECRETARY_RUNTIME/tts.resume"   # request to the owner: play the rest now
tts_owner() { local o; o="$(cat "$TTS_OWNER_FILE" 2>/dev/null || true)"; [[ -n "$o" ]] && kill -0 "$o" 2>/dev/null && printf '%s' "$o"; }
tts_pause() {    # tts_pause <player pid>
  local left owner; left="$(tts_sound_left)"; owner="$(tts_owner)"
  if [[ -z "$owner" || -z "$left" || "$owner" == "$1" ]]; then
    # a message started by an older say_now.sh (no owner): the old way, better than nothing
    kill -STOP "$1" && echo paused >"$TTS_STATE_FILE" && log "tts paused (stopped player)"
    [[ -n "$left" ]] && printf '%s 0\n' "$left" >"$TTS_CLOCK_FILE"
    return
  fi
  rm -f "$TTS_RESUME_FILE"
  printf '%s\n' "$left" >"$TTS_PAUSE_FILE"
  printf '%s 0\n' "$left" >"$TTS_CLOCK_FILE"          # frozen clock
  echo "$owner" >"$TTS_PID_FILE"; echo paused >"$TTS_STATE_FILE"   # the message lives on in its owner
  kill -TERM "$1" 2>/dev/null
  log "tts paused"
}
tts_resume() {   # tts_resume <pid from the pid file>
  if [[ -f "$TTS_PAUSE_FILE" ]]; then : >"$TTS_RESUME_FILE"; log "tts resumed"; return; fi
  local left; left="$(tts_sound_left)"
  kill -CONT "$1" && echo playing >"$TTS_STATE_FILE" && log "tts resumed (continued player)"
  [[ -n "$left" ]] && tts_clock_start "$left"
}
# The sound is over but the player is still winding down: end it quietly. The message was heard
# in full, so it keeps its "played" note (written by say_now when the player exits).
tts_finish_if_over() {
  local pid; pid="$(tts_pid)"
  [[ -n "$pid" && "$pid" != "$$" ]] && tts_sound_over || return 1
  log "message was over (player winding down): this press starts fresh"
  kill -CONT "$pid" 2>/dev/null; kill -TERM "$pid" 2>/dev/null
  rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE" "$TTS_CLOCK_FILE"
}

# The secretary's direct speech (say_now.sh without a ready file) notes its text here while its
# voice is being prepared. On 2026-09-21 an answer that had waited behind a playing message was
# killed in that state by a double press meant for the next inbox message: never spoken, no
# trace. Whatever stops a message in state "preparing" now puts that text in the inbox instead
# (ding, then a double press plays it). Once a message has started to sound, a stop is a stop.
TTS_TEXT_FILE="$SECRETARY_RUNTIME/tts.text"   # line 1: lang, line 2: voice, then the text
tts_requeue_if_unheard() {
  [[ "$(cat "$TTS_STATE_FILE" 2>/dev/null)" == "preparing" && -s "$TTS_TEXT_FILE" ]] || return 0
  local lang voice text
  lang="$(sed -n 1p "$TTS_TEXT_FILE")"; voice="$(sed -n 2p "$TTS_TEXT_FILE")"; text="$(tail -n +3 "$TTS_TEXT_FILE")"
  rm -f "$TTS_TEXT_FILE"
  [[ -n "$text" ]] || return 0
  if [[ "$voice" == "$SECRETARY_VOICE" || "$voice" == "$FRENCH_VOICE" ]]; then
    log "speech stopped before it was heard: moved to the inbox: $(printf '%s' "$text" | head -c 60)"
    "$ROOT_DIR/scripts/mac/secretary/inbox_post.sh" --from secretary --lang "${lang:-en}" "$text" >/dev/null 2>&1
  else
    log "speech in voice $voice stopped before it was heard (not re-queued: not the secretary's): $(printf '%s' "$text" | head -c 60)"
  fi
}
tts_stop() {
  tts_requeue_if_unheard
  local pid; pid="$(tts_pid)"
  if [[ -n "$pid" && "$pid" != "$$" ]]; then
    tts_sound_over || archive_note stopped
    kill -CONT "$pid" 2>/dev/null; kill -TERM "$pid" 2>/dev/null
    pkill -TERM -P "$pid" 2>/dev/null   # a say_now still synthesizing: also its kokoro child
  fi
  rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE" "$TTS_CURRENT_FILE" "$TTS_CLOCK_FILE" "$TTS_PAUSE_FILE" "$TTS_RESUME_FILE"
  local o; o="$(cat "$SPEECH_LOCK/pid" 2>/dev/null || true)"; [[ -n "$o" && "$o" != "$$" ]] && rm -rf "$SPEECH_LOCK"
}

# Run AppleScript lines against the iTerm session with this unique id (sessions cannot be
# addressed by id directly; iterate like voice_transcriber does). Prints "ok" or "not_found".
iterm_session_action() {
  local session_id="$1"; shift
  local lines="$*"
  osascript -e "
tell application \"iTerm2\"
    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                if (unique id of s as text) is \"$session_id\" then
                    tell s
                        $lines
                    end tell
                    return \"ok\"
                end if
            end repeat
        end repeat
    end repeat
end tell
return \"not_found\"" 2>/dev/null
}
iterm_session_exists() { [[ "$(iterm_session_action "$1" "get name")" == "ok" ]]; }

# One consistent voice per agent, chosen by a stable hash of its name; the secretary keeps the
# default voice so Remi always recognises it. French has a single native voice.
# Pocket TTS voices Remi kept on 2026-09-20, without cosette and jean (non-commercial source recordings).
# Kokoro values were: secretary af_heart, French ff_siwis, pool
# "af_bella af_nicole af_sky bf_emma bf_isabella am_adam am_michael bm_george bm_lewis am_liam af_nova bf_alice"
# 2026-09-20 late evening: Remi heard anna (then the builder's voice) and chose it for the secretary.
# alba, the secretary's voice until then, went to the end of the pool: last to be handed out.
SECRETARY_VOICE="anna"
FRENCH_VOICE="estelle"
VOICE_POOL_EN="vera fantine charles paul eponine azelma george mary jane michael eve bill_boerst peter_yearsley stuart_bell caro_davy alba"
# Sticky voices (Remi, 2026-09-20): a voice belongs to a role, a project or a durable job, not to
# whatever name a session happens to announce. secretary/voices.json lists the roles with their
# aliases and voices; voices.py looks a name up there, and gives a name it has never seen the
# least used voice of the pool, remembered in VOICES_LEARNED (untracked: names can be personal).
# The old hash of the name stays as the fallback, so a broken file never means silence.
VOICES_PY="$ROOT_DIR/scripts/mac/secretary/voices.py"
VOICES_LEARNED="${SECRETARY_VOICES_LEARNED:-$SECRETARY_RUNTIME/voices.learned.json}"   # per runtime: tests learn elsewhere
voices_query() { SECRETARY_VOICES_LEARNED="$VOICES_LEARNED" SECRETARY_VOICE_POOL="$VOICE_POOL_EN" python3 "$VOICES_PY" "$1" "$2" 2>/dev/null; }
# The role's spoken name: "session tower" for "claude control center"; the name itself when unknown.
display_name_for() { local d; d="$(voices_query display "${1:-}")"; printf '%s' "${d:-${1:-}}"; }
is_secretary_name() {
  case "$(printf '%s' "${1:-}" | tr 'A-Z' 'a-z')" in secretary|"the secretary") return 0 ;; esac
  [[ "$(voices_query display "${1:-}")" == "secretary" ]]
}
voice_for() {
  local name="${1:-}" lang="${2:-en}" v
  if [[ "$lang" == "fr" ]]; then echo "$FRENCH_VOICE"; return; fi
  if [[ -z "$name" ]]; then echo "$SECRETARY_VOICE"; return; fi
  v="$(voices_query voice "$name")"
  if [[ -n "$v" ]] && [[ "$v" == "$SECRETARY_VOICE" || " $VOICE_POOL_EN " == *" $v "* ]]; then echo "$v"; return; fi
  [[ -n "$v" ]] && log "voice_for: '$v' for '$name' is not a known voice, using the hash"
  if is_secretary_name "$name"; then echo "$SECRETARY_VOICE"; return; fi
  # positional parameters: same 1-based indexing in bash and zsh
  set -- $(echo "$VOICE_POOL_EN")
  local n=$# h idx
  h="$(printf '%s' "$name" | tr 'A-Z' 'a-z' | cksum | cut -d' ' -f1)"
  idx=$(( h % n + 1 ))
  eval "echo \${$idx}"
}

# Render text to a wav in a given voice (dictionary pronunciation applied, long texts in chunks).
# A failure of the main engine must never mean silence: the render is retried once with Kokoro,
# whose daemon starts on demand, in a fixed fallback voice.
FALLBACK_SAY="${FALLBACK_SAY:-/Users/remi/local-tts-lab/.venv/bin/kokoro-say}"
render_speech() {   # render_speech <lang> <voice> <out.wav> <text>
  # Tests never reach a real voice engine. On 2026-09-21 a test suite whose stand-in voice produced
  # no file fell through to the real Kokoro fallback below: every run started real Kokoro daemons
  # (in racing pairs, 2 GB each, never stopped) and rendered on them, which fed that evening's
  # memory exhaustion and reboot. Any runtime other than the live one is a test.
  if [[ "$SECRETARY_RUNTIME" != "$ROOT_DIR/runtime/secretary" && "${SECRETARY_ALLOW_REAL_VOICE:-0}" != "1" ]]; then
    case "$KOKORO_SAY" in /Users/remi/local-tts-lab/*) log "render_speech: test runtime, real voice engine refused"; return 1 ;; esac
    local FALLBACK_SAY="$KOKORO_SAY"
  fi
  "$KOKORO_CTL" kokoro-daemon status >/dev/null 2>&1 || "$KOKORO_CTL" kokoro-daemon start >/dev/null 2>&1
  python3 "$SPEECH_RENDER" render --lang "$1" --voice "$2" --out "$3" "$4" >/dev/null 2>&1 && return 0
  [[ "$KOKORO_SAY" == "$FALLBACK_SAY" ]] && return 1
  log "render_speech: main voice engine failed, falling back to kokoro"
  local fallback_voice="af_heart"; [[ "$1" == "fr" ]] && fallback_voice="ff_siwis"
  KOKORO_SAY="$FALLBACK_SAY" python3 "$SPEECH_RENDER" render --lang "$1" --voice "$fallback_voice" --out "$3" "$4" >/dev/null 2>&1
}
# Path of a cached short clip, rendered on first use: introductions ("micro duck here.") and
# counts ("2 older waiting.") are the same every time, so they are never rendered twice.
cached_clip() {     # cached_clip <lang> <voice> <text>  -> prints the wav path, or nothing on failure
  local key file
  key="$(printf '%s|%s|%s' "$1" "$2" "$3" | cksum | cut -d' ' -f1)"
  file="$CLIP_CACHE_DIR/$2-$key.wav"
  [[ -s "$file" ]] || render_speech "$1" "$2" "$file" "$3" || return 1
  [[ -s "$file" ]] && printf '%s' "$file"
}
clip_is_cached() { local key; key="$(printf '%s|%s|%s' "$1" "$2" "$3" | cksum | cut -d' ' -f1)"; [[ -s "$CLIP_CACHE_DIR/$2-$key.wav" ]]; }
# A message exists for a double press only once its voice is rendered (Remi, 2026-09-20: he
# pressed twice two seconds after a message was queued, heard the press confirmation, then 22 s
# of nothing while it rendered). inbox_post.sh marks a message "<stem>.rendering" while its voice
# is being made; such a message is skipped. A marker older than RENDERING_MAX_S belongs to a
# render that died: the message is then read anyway, rendered on demand as before.
RENDERING_MAX_S="${SECRETARY_RENDERING_MAX_S:-180}"
NOT_READY_TEXT="Not ready yet."    # said (cached clip, plays at once) when only unrendered messages wait
DING_OWED="$SECRETARY_RUNTIME/ding_owed"   # he was told "not ready yet": the ding that follows must not be skipped
message_rendering() {   # message_rendering <message.txt>
  local m="${1%.txt}.rendering"
  [[ -f "$m" ]] && [[ $(( $(date +%s) - $(stat -f %m "$m" 2>/dev/null || echo 0) )) -lt "$RENDERING_MAX_S" ]]
}
inbox_next_playable() {   # newest message that is not being rendered; prints nothing when there is none
  local f
  for f in $(ls "$INBOX_DIR"/*.txt 2>/dev/null | sort -r); do
    message_rendering "$f" || { printf '%s' "$f"; return 0; }
  done
  return 1
}
inbox_rendering_count() { local f n=0; for f in "$INBOX_DIR"/*.txt; do [[ -f "$f" ]] && message_rendering "$f" && n=$((n + 1)); done; printf '%s' "$n"; }
# True when a double press will produce speech at once (pre-rendered message, or one of the two
# cached sentences): the speech itself is then the feedback, and the "working on it" ticks
# would only play over its first words.
next_message_ready() {
  local next; next="$(inbox_next_playable)"
  if [[ -n "$next" ]]; then [[ -s "${next%.txt}.wav" ]]; return; fi
  if [[ "$(inbox_rendering_count)" -gt 0 ]]; then clip_is_cached en "$SECRETARY_VOICE" "$NOT_READY_TEXT"
  else clip_is_cached en "$SECRETARY_VOICE" "No new messages."; fi
}
intro_text_for() { local d; d="$(display_name_for "$1")"; if [[ "$d" == "secretary" ]] || is_secretary_name "$1"; then printf ''; else printf '%s here.' "$d"; fi; }

# Dictation state. The recorder lock (pid of the running recorder) is the source of truth. The
# pending marker only bridges the second between an earbud press and the recorder writing its
# lock: the recorder removes it as soon as the lock exists and again when it exits, and on its own
# it is trusted for DICTATION_PENDING_MAX_S seconds, no more. (It used to be 20 s: a recorder
# killed right after the press then made every press look "busy" and get refused in silence.)
DICTATION_LOCK="${DICTATION_LOCK:-/tmp/voice2clipboard_quick_autopaste.pid}"
DICTATION_STOP_FILE="/tmp/voice2clipboard_quick_autopaste.stop"
DICTATION_PRESS_FILE="/tmp/voice2clipboard_quick_autopaste.press"   # presses handed to the running recorder
DICTATION_PHASE_FILE="/tmp/voice2clipboard_quick_autopaste.phase"
DICTATION_PENDING="$SECRETARY_RUNTIME/dictation_pending"
DICTATION_PENDING_MAX_S="${SECRETARY_PENDING_MAX_S:-5}"
recorder_alive() {
  local pid; pid="$(cat "$DICTATION_LOCK" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}
dictation_pending_fresh() {
  [[ -f "$DICTATION_PENDING" ]] || return 1
  local age=$(( $(date +%s) - $(stat -f %m "$DICTATION_PENDING" 2>/dev/null || echo 0) ))
  [[ "$age" -lt "$DICTATION_PENDING_MAX_S" ]] && return 0
  rm -f "$DICTATION_PENDING"; return 1
}
dictation_active() { recorder_alive || dictation_pending_fresh; }
# Press received, recorder not up yet.
dictation_pending_only() { ! recorder_alive && dictation_pending_fresh; }

# A press that cannot be honoured must never be silent: silence has to mean "success", not
# "broken". Short low tone, distinct from every other cue; the reason goes to the log.
play_cue() { [[ "${SECRETARY_CUES_MUTED:-0}" == "1" ]] || afplay "$1" >/dev/null 2>&1 & }
refuse_cue() { log "refused: ${1:-unspecified}"; play_cue "$REFUSE_SOUND"; }

is_headset_name() { printf '%s' "${1:-}" | grep -Eqi "$HEADSET_NAME_PATTERN"; }

# Health flags: one small file per topic, "ok" or a one-line problem, for the self-check and for
# anything that watches the secretary from outside (the Session Tower reads this directory).
HEALTH_DIR="$SECRETARY_RUNTIME/health"
health_set() {   # health_set <topic> <ok|problem text>
  mkdir -p "$HEALTH_DIR"
  printf '%s\t%s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$2" >"$HEALTH_DIR/$1.tmp" && mv "$HEALTH_DIR/$1.tmp" "$HEALTH_DIR/$1"
}
health_problem() { local v; v="$(cut -f2- "$HEALTH_DIR/$1" 2>/dev/null)"; [[ -n "$v" && "$v" != "ok" ]] && printf '%s' "$v"; }

# Call mode watch. On 2026-09-20 at 18:10 a robot daemon opened the Mac's default microphone,
# which was the headset: the headset sat in call mode with no dictation running, where it keeps
# double presses to itself and sends a single press as a hang-up, so "the buttons were dead". The
# button app writes who has the headset microphone open to HEADSET_MIC_FILE
# ("<time>\topen\t<pid>:<exe>,..." | "closed" | "absent"); whether that is a problem is decided
# here: it is one when the microphone is open and no dictation is running.
HEADSET_MIC_FILE="$SECRETARY_RUNTIME/headset_mic"
CALLMODE_NOTIFIED_FILE="$SECRETARY_RUNTIME/callmode_notified"
# Programs whose use of the headset microphone is a real call: flagged, but never spoken into.
CALLMODE_QUIET_APPS="${SECRETARY_CALLMODE_QUIET_APPS:-zoom|FaceTime|Teams|Slack|Discord|Webex|Skype|WhatsApp|Signal}"
headset_mic_state() { local v; v="$(cut -f2 "$HEADSET_MIC_FILE" 2>/dev/null)"; printf '%s' "${v:-unknown}"; }
headset_mic_holders() { cut -f3 "$HEADSET_MIC_FILE" 2>/dev/null | tr ',' '\n' | grep -E '^[0-9]+:' || true; }
PS_BIN="${SECRETARY_PS:-ps}"   # overridable for tests
process_friendly_name() {   # process_friendly_name <pid> <exe>: a name Remi would recognise
  local pid="$1" exe="${2:-unknown}" cmd word name=""
  cmd="$("$PS_BIN" -p "$pid" -o command= 2>/dev/null || true)"
  if [[ "$cmd" == *.app/* ]]; then name="${cmd%%.app/*}"; name="${name##*/}"
  elif [[ "$exe" =~ ^([Pp]ython|node|ruby|perl|bash|sh|zsh|java|uv)[0-9.]*$ ]]; then
    # an interpreter: the script or module it runs says more than "python3.12"
    local skip=1 take_next=0
    for word in $cmd; do
      if [[ "$skip" == 1 ]]; then skip=0; continue; fi
      if [[ "$take_next" == 1 ]]; then name="$word"; break; fi
      if [[ "$word" == "-m" ]]; then take_next=1; continue; fi
      [[ "$word" == -* ]] && continue
      name="${word##*/}"; break
    done
  fi
  [[ -n "$name" ]] || name="$exe"
  name="${name%.py}"
  printf '%s' "$name" | tr '_-' '  '
}
# Prints the problem (one line) when the headset is in call mode with no dictation; nothing when
# all is well. Sets the health flag "callmode" either way. Cheap: reads two small files.
callmode_problem() {
  local state holders entry pid exe names="" rec
  state="$(headset_mic_state)"
  if [[ "$state" != "open" ]] || dictation_active; then
    [[ "$(cut -f2- "$HEALTH_DIR/callmode" 2>/dev/null)" == "ok" ]] || health_set callmode ok
    return 0
  fi
  rec="$(cat "$DICTATION_LOCK" 2>/dev/null || true)"
  while IFS= read -r entry; do
    [[ -n "$entry" ]] || continue
    pid="${entry%%:*}"; exe="${entry#*:}"
    [[ "$pid" == "$rec" ]] && continue
    names+="${names:+ and }$(process_friendly_name "$pid" "$exe")"
  done < <(headset_mic_holders)
  local text="the headset is in call mode because ${names:-another program} is using its microphone, so the buttons cannot work until it stops"
  # CALLMODE_PEEK=1: report without raising the flag (first of the two looks in on_headset.sh)
  if [[ "${CALLMODE_PEEK:-0}" != "1" ]]; then
    [[ "$(cut -f2- "$HEALTH_DIR/callmode" 2>/dev/null)" == "$text" ]] || health_set callmode "$text"
  fi
  printf '%s' "$text"
}

# Output volume guard. On 2026-09-19 at 23:44 the keyboard's volume-down key left the headset's
# music volume at zero and muted. The next day every message, ding and cue played into silence, so
# presses that worked felt dead (two hours of "broken" buttons), while dictations still
# gave their cues: in call mode the headset is another audio device with its own volume. All our
# feedback is sound, so sound itself has to be checked: when the headset output is muted or at
# zero, lift it to OUTPUT_RESTORE_LEVEL. Never lowers anything, never touches another output
# (muted Mac speakers are a choice), and costs one osascript call (0.13 s) when all is well.
#   ensure_audible            raise when needed (a press, a spoken problem, the reconnect check)
#   ensure_audible --report   only log and flag it (unsolicited sounds must not undo a deliberate zero)
OUTPUT_MIN_AUDIBLE="${SECRETARY_OUTPUT_MIN_AUDIBLE:-3}"        # percent; at or below this nothing is heard
OUTPUT_RESTORE_LEVEL="${SECRETARY_OUTPUT_RESTORE_LEVEL:-30}"   # percent; Remi's usual level is around 50
VOLUME_CTL="${SECRETARY_VOLUME_CTL:-osascript}"                # overridable for tests
PYTHON_AUDIO="${SECRETARY_PYTHON_AUDIO:-/Users/remi/.virtualenvs/voice2clipboard/bin/python}"
output_volume_read() {   # prints "<0-100> <true|false>"; nothing for an output without a volume
  "$VOLUME_CTL" -e 'get volume settings' 2>/dev/null | sed -nE 's/^output volume:([0-9]+),.*output muted:(true|false).*/\1 \2/p'
}
output_device_name() {
  if [[ -n "${SECRETARY_OUTPUT_NAME:-}" ]]; then printf '%s' "$SECRETARY_OUTPUT_NAME"; return; fi
  "$PYTHON_AUDIO" -c "import sounddevice as sd; print(sd.query_devices(kind='output')['name'])" 2>/dev/null
}
ensure_audible() {
  [[ "${SECRETARY_VOLUME_GUARD:-1}" == "1" ]] || return 0
  local vol muted name
  read -r vol muted <<<"$(output_volume_read)"
  [[ "$vol" =~ ^[0-9]+$ ]] || return 0
  if [[ "$muted" == "false" && "$vol" -gt "$OUTPUT_MIN_AUDIBLE" ]]; then
    [[ -n "$(health_problem output)" ]] && health_set output ok
    return 0
  fi
  name="$(output_device_name)"
  if ! is_headset_name "$name"; then
    log "volume guard: output '${name:-unknown}' is silent (volume=$vol muted=$muted), left alone: not the headset"
    return 0
  fi
  if [[ "${1:-}" == "--report" ]]; then
    log "volume guard: the headset output is silent (volume=$vol muted=$muted), this sound will not be heard"
    health_set output "the headset volume is at zero or muted: dings and messages are not heard"
    return 1
  fi
  [[ "$vol" -gt "$OUTPUT_RESTORE_LEVEL" ]] && OUTPUT_RESTORE_LEVEL="$vol"   # muted at a higher level: only unmute
  "$VOLUME_CTL" -e "set volume output volume $OUTPUT_RESTORE_LEVEL" -e "set volume without output muted" >/dev/null 2>&1
  log "volume guard: the headset output was silent (volume=$vol muted=$muted), raised to $OUTPUT_RESTORE_LEVEL"
  health_set output ok
}

# iTerm exports ITERM_SESSION_ID as "w5t0p0:<unique id>"; AppleScript knows the unique id only.
iterm_unique_id_from_env() { local v="${ITERM_SESSION_ID:-}"; [[ -n "$v" ]] && printf '%s' "${v##*:}"; }
# Same, read from the environment of another process (the secretary's claude).
iterm_unique_id_of_pid() {
  local v; v="$(ps eww -o command= -p "$1" 2>/dev/null | tr ' ' '\n' | sed -n 's/^ITERM_SESSION_ID=//p' | head -n 1)"
  [[ -n "$v" ]] && printf '%s' "${v##*:}"
}
# Print the iTerm unique id of a live secretary window, healing a stale registration when the
# secretary's claude process is still running in another window (it was resumed by hand, or
# rotated by something other than start_secretary.sh). Returns 1 when there is no live window.
secretary_target_resolve() {
  local s pid found
  s="$(cat "$SESSION_FILE" 2>/dev/null || true)"
  if [[ -n "$s" ]] && iterm_session_exists "$s"; then printf '%s' "$s"; return 0; fi
  pid="$(cat "$SECRETARY_CLAUDE_PID_FILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    found="$(iterm_unique_id_of_pid "$pid")"
    if [[ -n "$found" ]] && iterm_session_exists "$found"; then
      printf '%s' "$found" >"$SESSION_FILE"
      log "secretary window healed: ${s:-none} -> $found (claude pid $pid)"
      printf '%s' "$found"; return 0
    fi
  fi
  return 1
}

# Block until no dictation is active, then a short grace so the stop cue and paste finish.
wait_for_dictation_end() {
  local waited=0
  while dictation_active && [[ "$waited" -lt 1800 ]]; do sleep 0.5; waited=$((waited + 1)); done
  sleep 2
}

# One playback at a time. tts_pid() already tells whether afplay is speaking; "audio busy" also
# covers a dictation. Press-driven playback interrupts (SAY_NOW_INTERRUPT=1); anything else waits.
audio_busy() { dictation_active || [[ -n "$(tts_pid)" ]]; }
wait_for_audio_free() {
  local waited=0
  while audio_busy && [[ "$waited" -lt 1800 ]]; do sleep 0.5; waited=$((waited + 1)); done
  sleep 1
}

# Hard guard: exactly one speech at a time. The lock is an atomic mkdir holding the speaker's pid;
# a stale lock (dead pid) is cleared. say_now takes it before synthesis and releases it at the end.
SPEECH_LOCK="$SECRETARY_RUNTIME/speech.lock"
speech_lock_acquire() {
  local owner
  if mkdir "$SPEECH_LOCK" 2>/dev/null; then echo $$ >"$SPEECH_LOCK/pid"; return 0; fi
  owner="$(cat "$SPEECH_LOCK/pid" 2>/dev/null || true)"
  if [[ -z "$owner" ]] || ! kill -0 "$owner" 2>/dev/null; then
    rm -rf "$SPEECH_LOCK"; mkdir "$SPEECH_LOCK" 2>/dev/null && { echo $$ >"$SPEECH_LOCK/pid"; return 0; }
  fi
  return 1
}
speech_lock_release() { [[ "$(cat "$SPEECH_LOCK/pid" 2>/dev/null)" == "$$" ]] && rm -rf "$SPEECH_LOCK"; }
speech_lock_owner() { local o; o="$(cat "$SPEECH_LOCK/pid" 2>/dev/null || true)"; [[ -n "$o" ]] && kill -0 "$o" 2>/dev/null && echo "$o"; }

# Archive of every message ever played or discarded (spoken/); pruned only past ARCHIVE_MAX_MB.
ARCHIVE_MAX_MB="${SECRETARY_ARCHIVE_MAX_MB:-300}"
TTS_CURRENT_FILE="$SECRETARY_RUNTIME/tts.current"   # archived file of the message now playing
archive_note() { local f; f="$(cat "$TTS_CURRENT_FILE" 2>/dev/null || true)"; [[ -n "$f" && -f "$f" ]] && printf 'status=%s %s\n' "$1" "$(date '+%Y-%m-%d %H:%M:%S')" >>"$f"; }
archive_prune() {
  local used; used="$(du -sm "$SPOKEN_DIR" 2>/dev/null | cut -f1)"
  while [[ "${used:-0}" -gt "$ARCHIVE_MAX_MB" ]]; do
    local oldest; oldest="$(ls "$SPOKEN_DIR"/*.txt 2>/dev/null | sort | head -n 1)"; [[ -n "$oldest" ]] || break
    rm -f "$oldest"; used="$(du -sm "$SPOKEN_DIR" 2>/dev/null | cut -f1)"
  done
}
DING_COOLDOWN_S="${SECRETARY_DING_COOLDOWN_S:-20}"
DING_STAMP="$SECRETARY_RUNTIME/last_ding"
