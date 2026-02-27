#!/bin/bash
# Quick mode: record → transcribe → paste at cursor + Enter
# Captures the currently focused app BEFORE opening iTerm

ORIGINAL_APP=$(osascript -e 'tell application "System Events" to get name of first process whose frontmost is true')

osascript << EOF
tell application "iTerm"
    create window with default profile
    tell current session of current window
        write text "source /Users/remi/.virtualenvs/voice2clipboard/bin/activate && cd /Users/remi/voice2clipboard && python voice_transcriber.py --quick --target-window '$ORIGINAL_APP'"
    end tell
end tell
EOF
