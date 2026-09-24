#!/bin/bash
# The Session Tower's keep-warm pings ("banana (automatic keep-warm ping ..." answered by
# "coconut") are not activity: the hooks must leave the attention ledger exactly as it was.
# Temp runtime, stub voice, no audio, no real secretary: nothing live is read or written.
# Run: bash local_tests/test_ping_ignored.sh      (TEST_OVERLAY=<dir> tests undeployed copies)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
STAGE="$TMP/stage"; mkdir -p "$STAGE"
cp "$ROOT"/scripts/mac/secretary/*.sh "$ROOT"/scripts/mac/secretary/*.py "$STAGE/"
[[ -n "${TEST_OVERLAY:-}" ]] && cp "$TEST_OVERLAY"/* "$STAGE/"
export SECRETARY_RUNTIME="$TMP/runtime" SECRETARY_CUES_MUTED=1 KOKORO_SAY=/usr/bin/true FALLBACK_SAY=/usr/bin/true KOKORO_CTL=/usr/bin/true \
       DICTATION_LOCK="$TMP/recorder.pid"
mkdir -p "$SECRETARY_RUNTIME"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
SID="11111111-2222-3333-4444-555555555555"; ENTRY="$SECRETARY_RUNTIME/ledger/$SID.json"
prompt() { printf '{"session_id":"%s","cwd":"/Users/x/some-project","prompt":%s}' "$SID" "$1" | bash "$STAGE/user_prompt_hook.sh"; }
stop()   { printf '{"session_id":"%s","cwd":"/Users/x/some-project","last_assistant_message":%s}' "$SID" "$1" | bash "$STAGE/stop_hook.sh"; }
field()  { python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2]))" "$ENTRY" "$1"; }

# a real turn that ends with a question: the session is waiting on Remi
prompt '"please look at the build"'; stop '"The build is fixed. Should I also update the changelog?"'
check "a real turn is recorded" "[[ -f '$ENTRY' ]]"
check "it is waiting on Remi" "[[ \"\$(field needs_attention)\" == True ]]"
before="$(cksum <"$ENTRY")"

# the ping turn: nothing may change
prompt '"banana (automatic keep-warm ping from the Session Tower, answer with the single word coconut)"'
check "the ping prompt does not clear the waiting flag" "[[ \"\$(cksum <'$ENTRY')\" == '$before' ]]"
stop '"coconut"'
check "the ping answer does not touch the ledger entry" "[[ \"\$(cksum <'$ENTRY')\" == '$before' ]]"
check "the marker is gone" "[[ -z \"\$(ls '$SECRETARY_RUNTIME/pings' 2>/dev/null)\" ]]"
check "nothing was queued for the ears by the ping" "[[ \$(ls '$SECRETARY_RUNTIME'/inbox/*.txt 2>/dev/null | wc -l) -le 1 ]]"
prompt '"  Banana (automatic keep-warm ping, second wording)"'; stop '"Coconut."'
check "case, spaces and a full stop do not matter" "[[ \"\$(cksum <'$ENTRY')\" == '$before' ]]"

# a ping that woke something real is a normal turn
prompt '"banana (automatic keep-warm ping)"'; stop '"coconut. By the way the deploy failed, do you want me to retry?"'
check "a ping answered with real news is recorded" "[[ \"\$(cksum <'$ENTRY')\" != '$before' ]] && grep -q 'deploy failed' '$ENTRY'"

# "coconut" with no ping before it is an ordinary message
before="$(cksum <"$ENTRY")"
prompt '"what is the word"'
check "a normal prompt clears the waiting flag as before" "[[ \"\$(field needs_attention)\" == False ]]"
stop '"coconut"'
check "coconut without a ping is recorded like any message" "grep -q 'coconut' '$ENTRY'"

# a stale marker (the ping turn never ended properly) does not swallow a later real turn
prompt '"banana (automatic keep-warm ping)"'
touch -t "$(date -v-30M '+%Y%m%d%H%M.%S')" "$SECRETARY_RUNTIME/pings/$SID"
stop '"coconut"'
check "a 30 minute old marker is not honoured" "[[ -z \"\$(ls '$SECRETARY_RUNTIME/pings' 2>/dev/null)\" ]]"

# the secretary itself can be pinged: no registration attempt, no rotation check, no error
printf '{"session_id":"s1","cwd":"/Users/remi/voice2clipboard/secretary","prompt":"banana (automatic keep-warm ping)"}' | bash "$STAGE/user_prompt_hook.sh"
printf '{"session_id":"s1","cwd":"/Users/remi/voice2clipboard/secretary","last_assistant_message":"coconut"}' | bash "$STAGE/stop_hook.sh"
check "a pinged secretary leaves no marker and no ledger entry" "[[ -z \"\$(ls '$SECRETARY_RUNTIME/pings' 2>/dev/null)\" && ! -f '$SECRETARY_RUNTIME/ledger/s1.json' ]]"
check "the live ledger was never touched" "[[ ! -f '/Users/remi/voice2clipboard/runtime/secretary/ledger/$SID.json' ]]"

echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
