#!/bin/bash
# The recorder window is closed during a dictation: that is a cancel, by Remi's decision (2026-09-24
# 09:42, he uses the close button as one; the audio may be kept, the text must not reach anyone).
# iTerm sends HUP to the recorder's process group five seconds after the click: the recorder dies of
# it, the worker survives, plays the cancel cue, writes the `cancelled` marker and one log line, and
# delivers nothing. A plain crash keeps the recovery path (buzz, transcription, delivery).
# Everything here is a stand-in (recorder, recovery, inbox, model helper, sounds, state files): no
# iTerm, no microphone, no sound, and nothing under /tmp that the real recorder uses.
# Run: bash local_tests/test_window_closed_delivery.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKER="$ROOT/scripts/mac/legacy_mlx_toggle_autopaste_worker.sh"
TMP="$(mktemp -d)"; [[ -n "${KEEP_TMP:-}" ]] && echo "keeping $TMP" || trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/runtime"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }

# stand-ins: the recorder (dies of HUP like the real one, which handles only INT and TERM), the
# recovery script, the inbox, the model helper, afplay
cat >"$TMP/bin/python" <<'EOF'
#!/bin/bash
mkdir -p "$FAKE_REC"; head -c 64000 /dev/zero >"$FAKE_REC/audio.wav"
printf '%s' "$FAKE_REC/audio.wav" >"$VOICE2CLIPBOARD_AUDIO_STATE_FILE"
echo "fake recorder: recording"
while true; do sleep 0.2; done
EOF
cat >"$TMP/bin/recover.sh" <<'EOF'
#!/bin/bash
echo "recover $*" >>"$FAKE_LOG/recovered.txt"
[[ -f "$FAKE_LOG/recovery_fails" ]] && exit 1
echo " - Saved to             : recordings/x/transcript.txt"
EOF
printf '#!/bin/bash\necho "$*" >>"$FAKE_LOG/inbox.txt"\n' >"$TMP/bin/inbox.sh"
printf '#!/bin/bash\necho "$*" >>"$FAKE_LOG/helper.txt"\n' >"$TMP/bin/helper.sh"
printf '#!/bin/bash\necho "$*" >>"$FAKE_LOG/afplay.txt"\n' >"$TMP/bin/afplay"
printf 'export PATH="%s/bin:$PATH"\n' "$TMP" >"$TMP/activate"
chmod +x "$TMP"/bin/*
export FAKE_LOG="$TMP" SECRETARY_RUNTIME="$TMP/runtime" VOICE2CLIPBOARD_TEST_NO_PKILL=1 \
       VOICE2CLIPBOARD_VENV="$TMP/activate" VOICE2CLIPBOARD_HELPER_CTL="$TMP/bin/helper.sh" \
       VOICE2CLIPBOARD_RECOVER_SCRIPT="$TMP/bin/recover.sh" VOICE2CLIPBOARD_INBOX_POST="$TMP/bin/inbox.sh"

start_worker() {   # start_worker <name>: state prefix, meta file, recorder folder for this run
  export VOICE2CLIPBOARD_STATE_PREFIX="$TMP/$1.state" FAKE_REC="$TMP/$1.rec"
  cat >"$TMP/$1.state.meta" <<EOF
session_id=test-$1
started_at=now
target_app=iTerm2
target_iterm_session=FAKE-SESSION-ID
helper_launch_state=started
voice_mode=headset
copy_only=0
EOF
  touch "$SECRETARY_RUNTIME/dictation_pending"
  # its own process group, as under iTerm (the HUP goes to the whole group)
  python3 -c 'import os, sys; os.setsid(); os.execv("/bin/bash", ["bash", sys.argv[1]])' "$WORKER" >"$TMP/$1.out" 2>&1 &
  WPID=$!
  for _ in $(seq 1 60); do [[ -s "$TMP/$1.state.pid" && -s "$TMP/$1.state.audio" ]] && break; sleep 0.1; done
  RPID="$(cat "$TMP/$1.state.pid" 2>/dev/null)"
}
wait_worker() { for _ in $(seq 1 150); do kill -0 "$WPID" 2>/dev/null || return 0; sleep 0.1; done; return 1; }

# 1. the window is closed: HUP to the group, like iTerm five seconds after the click
start_worker closed
check "recorder up: lock and audio state written, pending marker gone" \
  "[[ -n \"\$RPID\" ]] && kill -0 \"\$RPID\" 2>/dev/null && [[ ! -f '$SECRETARY_RUNTIME/dictation_pending' ]]"
kill -HUP -- "-$WPID"
check "the worker survives the HUP and finishes by itself" "wait_worker"
check "the recorder is gone" "! kill -0 \"\$RPID\" 2>/dev/null"
check "nothing is transcribed or delivered" "[[ ! -f '$TMP/recovered.txt' ]]"
check "no note is queued" "[[ ! -f '$TMP/inbox.txt' ]]"
check "the cancel cue plays, not the failure buzz" "grep -q cue_cancel '$TMP/afplay.txt' && ! grep -q cue_fail '$TMP/afplay.txt'"
check "the audio is kept and marked cancelled" "[[ -s '$TMP/closed.rec/audio.wav' ]] && grep -q 'recorder window closed' '$TMP/closed.rec/cancelled'"
check "lock and state files cleaned up" "[[ ! -f '$TMP/closed.state.pid' && ! -f '$TMP/closed.state.meta' && ! -f '$TMP/closed.state.audio' ]]"
check "secretary log: one line, cancelled, audio kept, how to recover" "grep -q 'recorder window closed: dictation cancelled, audio kept in $TMP/closed.rec (recover_cancelled.sh)' '$SECRETARY_RUNTIME/secretary.log'"
check "the worker's own log has the story too" "grep -q 'recorder window closed while recording: cancelled' '$TMP/closed.state.log'"
check "the model helper is stopped at the end" "grep -q stop '$TMP/helper.txt'"

# 2. a crash without the window closing keeps the recovery path: buzz, transcription, delivery
rm -f "$TMP/recovered.txt" "$TMP/inbox.txt" "$TMP/afplay.txt"
start_worker crash
kill -KILL "$RPID"
check "crash: the worker finishes" "wait_worker"
check "crash: recovered and sent to the dictation's target" "grep -q 'recover $TMP/crash.rec/audio.wav .*--target-iterm-session FAKE-SESSION-ID' '$TMP/recovered.txt'"
for _ in $(seq 1 20); do [[ -f "$TMP/afplay.txt" ]] && break; sleep 0.1; done   # played in the background
check "crash: the failure buzz plays" "grep -q cue_fail '$TMP/afplay.txt'"
check "crash: not marked cancelled, no note" "[[ ! -f '$TMP/crash.rec/cancelled' && ! -f '$TMP/inbox.txt' ]]"

# 3. a crash whose recovery fails announces the loss
rm -f "$TMP/recovered.txt" "$TMP/inbox.txt" "$TMP/afplay.txt"; touch "$TMP/recovery_fails"
start_worker lost
kill -KILL "$RPID"
check "lost: the worker finishes" "wait_worker"
check "lost: the loss is announced" "grep -q 'A dictation was lost' '$TMP/inbox.txt'"

echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
