#!/bin/bash
# Checks the whole earbud chain and prints one line per problem (nothing when everything is fine).
# Used when the headset reconnects, and by hand: selfcheck.sh [--speak | --speak-problems]
#   --speak: ready cue when fine; failure buzz plus a spoken list of problems otherwise.
#   --speak-problems: same, but silent when fine. For checks Remi did not cause (the button app
#     restarting with the headset already on): on 2026-09-20 he took that ready cue for a message
#     ding and went looking for a message that did not exist.
# A problem is only announced after it survived SELFCHECK_RETRIES re-checks a few seconds apart:
# right after a reconnect or a redeploy, parts of the chain may still be coming up, and a false
# "not ready" is worse than a late one (2026-09-19, first live run).
source "$(dirname "$0")/lib.sh"
speak=0; ready_cue=1
case "${1:-}" in --speak) speak=1 ;; --speak-problems) speak=1; ready_cue=0 ;; esac
retries="${SELFCHECK_RETRIES:-3}"; gap="${SELFCHECK_RETRY_GAP_S:-3}"
# One self-check at a time (atomic claim; a claim older than 60 s is stale).
CLAIM="$SECRETARY_RUNTIME/selfcheck.lock"
if ! mkdir "$CLAIM" 2>/dev/null; then
  age=$(( $(date +%s) - $(stat -f %m "$CLAIM" 2>/dev/null || echo 0) ))
  if [[ "$age" -lt 60 ]]; then log "selfcheck: another one is running, skipped"; exit 0; fi
  rmdir "$CLAIM" 2>/dev/null; mkdir "$CLAIM" 2>/dev/null || exit 0
fi
trap 'rmdir "$CLAIM" 2>/dev/null' EXIT

run_checks() {
  problems=()
  # -a: pgrep skips its own ancestors, and this check is usually started by the button app itself
  pgrep -a -f "EarbudButtons.app/Contents/MacOS/EarbudButtons" >/dev/null || problems+=("the earbud button app is not running")
  local registered input
  registered="$(cat "$SESSION_FILE" 2>/dev/null || true)"
  if ! secretary_target_resolve >/dev/null; then
    if [[ -n "$registered" ]]; then problems+=("my window is missing, so dictations cannot reach me")
    else problems+=("no secretary session is registered"); fi
  fi
  "$KOKORO_CTL" kokoro-daemon status >/dev/null 2>&1 || "$KOKORO_CTL" kokoro-daemon start >/dev/null 2>&1 || problems+=("the voice is not available")
  input="$(/Users/remi/.virtualenvs/voice2clipboard/bin/python -c "import sounddevice as sd; print(sd.query_devices(kind='input')['name'])" 2>/dev/null)"
  is_headset_name "$input" || problems+=("the microphone is ${input:-unknown}, not the headset")
  [[ -x "$ROOT_DIR/scripts/mac/legacy_mlx_toggle_autopaste.sh" ]] || problems+=("the recorder script is missing")
  # Sound is the only feedback there is. With --speak (headset just put on) the volume is lifted
  # at once; a plain check only reports it.
  if [[ "$speak" == 1 ]]; then ensure_audible; else ensure_audible --report || problems+=("the headset volume is at zero or muted"); fi
  local topic note
  # call mode with no dictation (another program holds the headset microphone): evaluated now,
  # not read from the flag, so a missed event cannot leave a stale answer
  note="$(callmode_problem)"; [[ -n "$note" ]] && problems+=("$note")
  # the secretary's window must take typed input (a dialog left open in it swallows dictations)
  note="$("$(dirname "$0")/secretary_input_check.sh" 2>/dev/null)"; [[ -n "$note" ]] && problems+=("$note")
  for topic in "$HEALTH_DIR"/*; do
    [[ -f "$topic" && "$(basename "$topic")" != "output" && "$(basename "$topic")" != "callmode" && "$(basename "$topic")" != "secretary_input" ]] || continue
    note="$(health_problem "$(basename "$topic")")"; [[ -n "$note" ]] && problems+=("$note")
  done
}

attempt=0
while :; do
  run_checks
  [[ "${#problems[@]}" == 0 || "$attempt" -ge "$retries" ]] && break
  attempt=$((attempt + 1))
  log "selfcheck: attempt $attempt found: $(IFS=';'; echo "${problems[*]}") — re-checking in ${gap}s"
  sleep "$gap"
done
if [[ "${#problems[@]}" == 0 ]]; then
  log "selfcheck: ready"
  if [[ "$speak" == 1 && "$ready_cue" == 1 ]] && ! dictation_active; then play_cue "$READY_SOUND"; fi
  exit 0
fi
printf '%s\n' "${problems[@]}"
log "selfcheck: NOT ready after $((attempt + 1)) checks: $(IFS=';'; echo "${problems[*]}")"
if [[ "$speak" == 1 ]]; then
  play_cue "$FAIL_SOUND"; sleep 1.6
  SAY_NOW_INTERRUPT=1 nohup "$(dirname "$0")/say_now.sh" "Not ready. $(printf '%s. ' "${problems[@]}")" >/dev/null 2>&1 &
fi
exit 1
