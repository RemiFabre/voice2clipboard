#!/bin/bash
# Quick dictation mode: record -> transcribe -> paste at cursor + Enter
# Bind this to a global hotkey (e.g., Super+Shift+V)

# Capture the currently focused window BEFORE opening terminal
ORIGINAL_WINDOW=$(xdotool getactivewindow)

terminator -e "bash -c 'source /home/remi/.virtualenvs/whisper/bin/activate && cd /home/remi/voice2chatgpt && python voice_transcriber.py --quick --target-window $ORIGINAL_WINDOW'"
