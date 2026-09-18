#!/bin/bash
# Short attention sound in the current output device (the earbuds when connected). Never over
# speech or a dictation: waits in the background until the audio is free.
source "$(dirname "$0")/lib.sh"
if audio_busy; then
  nohup bash -c 'source "$1/lib.sh"; wait_for_audio_free; afplay "$2" >/dev/null 2>&1' _ "$(cd "$(dirname "$0")" && pwd)" "$DING_SOUND" >/dev/null 2>&1 &
else
  afplay "$DING_SOUND" >/dev/null 2>&1 &
fi
