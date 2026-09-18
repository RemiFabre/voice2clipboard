#!/bin/bash
# Shared paths for the voice secretary layer (earbuds -> dictation -> Claude sessions -> spoken replies).
ROOT_DIR="/Users/remi/voice2clipboard"
SECRETARY_RUNTIME="$ROOT_DIR/runtime/secretary"
INBOX_DIR="$SECRETARY_RUNTIME/inbox"          # queued spoken messages, oldest first
SPOKEN_DIR="$SECRETARY_RUNTIME/spoken"        # archive of what was read
TTS_PID_FILE="$SECRETARY_RUNTIME/tts.pid"     # afplay pid while speaking
TTS_STATE_FILE="$SECRETARY_RUNTIME/tts.state" # playing | paused
TTS_WAV="$SECRETARY_RUNTIME/tts_current.wav"
VOICE_MODE_FLAG="$SECRETARY_RUNTIME/voice_mode.on"
SESSION_FILE="$SECRETARY_RUNTIME/secretary_iterm_session"
LOG_FILE="$SECRETARY_RUNTIME/secretary.log"
DING_SOUND="$ROOT_DIR/sounds/cue_ding.aiff"  # distinct from the recorder cues and the done sound
KOKORO_SAY="/Users/remi/local-tts-lab/.venv/bin/kokoro-say"
KOKORO_CTL="/Users/remi/local-tts-lab/.venv/bin/local-tts"
export PYTORCH_ENABLE_MPS_FALLBACK=1
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"
mkdir -p "$INBOX_DIR" "$SPOKEN_DIR"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG_FILE"; }

tts_pid() {
  local pid
  pid="$(cat "$TTS_PID_FILE" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then echo "$pid"; else rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE"; fi
}

tts_stop() {
  local pid; pid="$(tts_pid)"
  if [[ -n "$pid" ]]; then kill -CONT "$pid" 2>/dev/null; kill -TERM "$pid" 2>/dev/null; fi
  rm -f "$TTS_PID_FILE" "$TTS_STATE_FILE"
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
# default voice (af_heart) so Remi always recognises it. French has a single Kokoro voice.
VOICE_POOL_EN="af_bella af_nicole af_sky bf_emma bf_isabella am_adam am_michael bm_george bm_lewis am_liam af_nova bf_alice"
is_secretary_name() { case "$(printf '%s' "${1:-}" | tr 'A-Z' 'a-z')" in secretary|"the secretary"|voice2clipboard|"voice to clipboard") return 0 ;; *) return 1 ;; esac; }
voice_for() {
  local name="${1:-}" lang="${2:-en}"
  if [[ "$lang" == "fr" ]]; then echo "ff_siwis"; return; fi
  if [[ -z "$name" ]] || is_secretary_name "$name"; then echo "af_heart"; return; fi
  # positional parameters: same 1-based indexing in bash and zsh
  set -- $(echo "$VOICE_POOL_EN")
  local n=$# h idx
  h="$(printf '%s' "$name" | tr 'A-Z' 'a-z' | cksum | cut -d' ' -f1)"
  idx=$(( h % n + 1 ))
  eval "echo \${$idx}"
}

# A dictation is running (recorder lock alive) or about to start (marker touched by the earbud
# press, valid 20 s). Speech and dings must not start while this is true.
DICTATION_LOCK="/tmp/voice2clipboard_quick_autopaste.pid"
DICTATION_PENDING="$SECRETARY_RUNTIME/dictation_pending"
dictation_active() {
  local pid
  pid="$(cat "$DICTATION_LOCK" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then return 0; fi
  if [[ -f "$DICTATION_PENDING" ]]; then
    local age=$(( $(date +%s) - $(stat -f %m "$DICTATION_PENDING" 2>/dev/null || echo 0) ))
    [[ "$age" -lt 20 ]] && return 0
    rm -f "$DICTATION_PENDING"
  fi
  return 1
}
# Block until no dictation is active, then a short grace so the stop cue and paste finish.
wait_for_dictation_end() {
  local waited=0
  while dictation_active && [[ "$waited" -lt 1800 ]]; do sleep 0.5; waited=$((waited + 1)); done
  sleep 2
}
