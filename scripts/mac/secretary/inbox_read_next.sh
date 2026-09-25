#!/bin/bash
# Speak the latest queued message whose voice is ready (newest first, per Remi; moves it to the
# spoken archive). Messages still being rendered are left alone: "Not ready yet.", then their ding.
# Uses the voice file rendered when the message was queued, so playback starts at once; renders
# on demand when that file is missing. Says so when the inbox is empty.
source "$(dirname "$0")/lib.sh"
if dictation_active; then refuse_cue "inbox_read_next: a dictation is active"; exit 0; fi
# A message whose voice is still being rendered is not there yet: never make him wait for it.
next="$(inbox_next_playable)"
if [[ -z "$next" && "$(inbox_rendering_count)" -gt 0 ]]; then
  log "inbox_read_next: only messages still being rendered: saying so, the ding will follow"
  : >"$DING_OWED"
  lang="$(rendering_lang)"; voice="$(voice_for "" "$lang")"; line="$(not_ready_text "$lang")"
  wait_clip="$(cached_clip "$lang" "$voice" "$line")"
  SAY_NOW_INTERRUPT=1 exec "$(dirname "$0")/say_now.sh" --lang "$lang" --voice "$voice" ${wait_clip:+--wav "$wait_clip"} "$line"
fi
if [[ -z "$next" ]]; then
  lang="$(last_heard_lang)"; voice="$(voice_for "" "$lang")"; line="$(no_messages_text "$lang")"
  empty="$(cached_clip "$lang" "$voice" "$line")"
  SAY_NOW_INTERRUPT=1 exec "$(dirname "$0")/say_now.sh" --lang "$lang" --voice "$voice" ${empty:+--wav "$empty"} "$line"
fi
lang="$(message_lang "$next")"; from="$(sed -n 's/^from=//p' "$next" | head -n 1)"
body="$(awk 'f{print} /^$/{f=1}' "$next")"
body_wav="${next%.txt}.wav"
mv "$next" "$SPOKEN_DIR/"
rm -f "${next%.txt}.rendering"   # only ever a stale one here (its render died)
export SAY_NOW_ARCHIVE="$SPOKEN_DIR/$(basename "$next")"
archive_prune
remaining=$(( $(ls "$INBOX_DIR"/*.txt 2>/dev/null | wc -l | tr -d ' ') - $(inbox_rendering_count) ))   # rendered ones only
# The secretary speaks in the first person with its own voice; agents introduce themselves in
# two words ("micro duck here.") and each keeps a consistent voice. Introduction and count are in
# the message's language ("Un message de la tour de contrôle.", "Encore deux messages en attente.").
voice="$(voice_for "$from" "$lang")"
intro="$(intro_text_for "$from" "$lang")"
count=""; [[ "$remaining" -gt 0 ]] && count="$(count_text "$lang" "$remaining")"
if [[ -s "$body_wav" ]]; then
  # Introduction and count are small cached clips; joining files takes milliseconds.
  clips=()
  # order (Remi, 2026-09-23): introduction, the message, and only then "N older waiting.", so a
  # message can be stopped before the count and the count never delays the message
  if [[ -n "$intro" ]]; then c="$(cached_clip "$lang" "$voice" "$intro")"; [[ -n "$c" ]] && clips+=("$c"); fi
  after=()
  if [[ -n "$count" ]]; then c="$(cached_clip "$lang" "$voice" "$count")"; [[ -n "$c" ]] && after+=("$c"); fi
  ready="$SECRETARY_RUNTIME/tts_ready.wav"
  if python3 "$SPEECH_RENDER" concat --out "$ready" "${clips[@]}" "$body_wav" "${after[@]}" >/dev/null 2>&1; then
    rm -f "$body_wav"
    SAY_NOW_INTERRUPT=1 exec "$(dirname "$0")/say_now.sh" --lang "$lang" --voice "$voice" --wav "$ready" "$intro $body $count"
  fi
  log "inbox_read_next: could not join the pre-rendered clips, rendering on demand"
fi
rm -f "$body_wav"
SAY_NOW_INTERRUPT=1 exec "$(dirname "$0")/say_now.sh" --lang "$lang" --voice "$voice" "$intro $body $count"
