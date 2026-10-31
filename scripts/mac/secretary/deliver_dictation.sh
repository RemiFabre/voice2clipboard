#!/bin/bash
# Give one of Remi's dictations, verbatim, to the session it is for (see deliver_dictation.py).
#   deliver_dictation.sh --to <session name> [--id YYYY-MM-DD/HH-MM-SS]  |  --list
exec "${VOICE2CLIPBOARD_PYTHON:-/Users/remi/.virtualenvs/voice2clipboard/bin/python}" "$(dirname "$0")/deliver_dictation.py" "$@"
