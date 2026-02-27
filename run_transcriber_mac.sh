#!/bin/bash
# Standard mode: record → transcribe → choose action
osascript << 'EOF'
tell application "iTerm"
    create window with default profile
    tell current session of current window
        write text "source /Users/remi/.virtualenvs/voice2clipboard/bin/activate && cd /Users/remi/voice2clipboard && python voice_transcriber.py; echo 'Press Enter to close...'; read"
    end tell
end tell
EOF
