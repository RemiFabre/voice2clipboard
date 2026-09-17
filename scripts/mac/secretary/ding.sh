#!/bin/bash
# Short attention sound in the current output device (the earbuds when connected).
source "$(dirname "$0")/lib.sh"
afplay "$DING_SOUND" >/dev/null 2>&1 &
