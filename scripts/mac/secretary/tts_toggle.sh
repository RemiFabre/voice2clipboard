#!/bin/bash
# Single earbud press: pause speech if speaking, resume if paused, otherwise read the next queued message.
source "$(dirname "$0")/lib.sh"
tts_finish_if_over
pid="$(tts_pid)"
if [[ -n "$pid" ]]; then
  if [[ "$(cat "$TTS_STATE_FILE" 2>/dev/null)" == "paused" ]]; then
    tts_resume "$pid"
  else
    tts_pause "$pid"
  fi
  exit 0
fi
nohup "$(dirname "$0")/inbox_read_next.sh" >/dev/null 2>&1 &
