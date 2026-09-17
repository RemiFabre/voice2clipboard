#!/bin/bash
# Single earbud press: pause speech if speaking, resume if paused, otherwise read the next queued message.
source "$(dirname "$0")/lib.sh"
pid="$(tts_pid)"
if [[ -n "$pid" ]]; then
  if [[ "$(cat "$TTS_STATE_FILE" 2>/dev/null)" == "paused" ]]; then
    kill -CONT "$pid" && echo playing >"$TTS_STATE_FILE" && log "tts resumed"
  else
    kill -STOP "$pid" && echo paused >"$TTS_STATE_FILE" && log "tts paused"
  fi
  exit 0
fi
nohup "$(dirname "$0")/inbox_read_next.sh" >/dev/null 2>&1 &
