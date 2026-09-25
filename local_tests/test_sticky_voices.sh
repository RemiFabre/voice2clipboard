#!/bin/bash
# Tests of the sticky voices: roles and aliases from secretary/voices.json, unknown names learned
# into a scratch file (never the tracked one), fallbacks. No audio, no real runtime.
# Run: bash local_tests/test_sticky_voices.sh      (TEST_LIB=<path to a lib.sh> tests an undeployed copy)
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
export SECRETARY_RUNTIME="$TMP/runtime" SECRETARY_CUES_MUTED=1
mkdir -p "$SECRETARY_RUNTIME"
source "${TEST_LIB:-$ROOT/scripts/mac/secretary/lib.sh}"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
before="$(cksum <"$ROOT/secretary/voices.json")"

check "the secretary keeps its voice" "[[ \$(voice_for secretary) == \$SECRETARY_VOICE && \$(voice_for 'the secretary') == \$SECRETARY_VOICE && \$(voice_for '') == \$SECRETARY_VOICE ]]"
check "this repository is the secretary" "[[ \$(voice_for voice2clipboard) == \$SECRETARY_VOICE ]] && is_secretary_name 'voice to clipboard'"
check "a rotated secretary session is still the secretary" "[[ \$(voice_for secretary-a4) == \$SECRETARY_VOICE ]]"
check "the secretary has no introduction" "[[ -z \"\$(intro_text_for 'the secretary')\" ]]"
check "French is the French voice for anyone" "[[ \$(voice_for 'session tower' fr) == estelle ]]"
tower="$(voice_for 'session tower')"
check "aliases share the role's voice" "[[ \$(voice_for 'claude control center') == $tower && \$(voice_for 'Tower builder') == $tower && \$(voice_for 'claude-control-center') == $tower ]]"
check "introduction uses the role's name" "[[ \"\$(intro_text_for 'claude control center')\" == 'session tower here.' ]]"
check "a trailing 'agent' or session suffix is ignored" "[[ \$(voice_for 'OpenWarlock agent') == \$(voice_for 'open warlock') && \$(voice_for 'reachy mini 3c') == \$(voice_for 'reachy_mini') ]]"
check "the secretary's voice is nobody else's" "[[ \$(grep -c \"\\\"voice\\\": \\\"\$SECRETARY_VOICE\\\"\" '$ROOT/secretary/voices.json') == 1 && ' $VOICE_POOL_EN ' != *\" \$SECRETARY_VOICE \"* ]]"
check "every tracked voice is a pool voice" "python3 - <<PY
import json,sys
pool='$VOICE_POOL_EN'.split()+['$SECRETARY_VOICE']
sys.exit(0 if all(r['voice'] in pool for r in json.load(open('$ROOT/secretary/voices.json'))['roles']) else 1)
PY"
check "no two tracked roles share a voice" "python3 - <<PY
import json,sys
v=[r['voice'] for r in json.load(open('$ROOT/secretary/voices.json'))['roles']]
sys.exit(0 if len(v)==len(set(v)) else 1)
PY"

# unknown names: least used voice, remembered, in the scratch file only
first="$(voice_for 'brand new project')"
check "an unknown name gets a pool voice" "[[ ' $VOICE_POOL_EN ' == *' $first '* ]]"
check "it gets a voice no tracked role uses while one is free" "! grep -q '\"$first\"' '$ROOT/secretary/voices.json'"
check "it is the same voice the next time" "[[ \$(voice_for 'brand new project') == $first && \$(voice_for 'Brand-New Project 2') == $first ]]"
check "it was remembered in the runtime file" "grep -q 'brand new project' '$SECRETARY_RUNTIME/voices.learned.json'"
second="$(voice_for 'second newcomer')"
check "the next newcomer gets another voice" "[[ '$second' != '$first' ]]"
check "unknown names introduce themselves as given" "[[ \"\$(intro_text_for 'second newcomer')\" == 'second newcomer here.' ]]"
for i in 1 2 3 4 5 6; do voice_for "parallel $i" >/dev/null & done; wait
check "parallel learning loses nothing" "[[ \$(grep -c '\"role\": \"parallel' '$SECRETARY_RUNTIME/voices.learned.json') == 6 ]]"
check "the tracked file was not written" "[[ \"\$(cksum <'$ROOT/secretary/voices.json')\" == '$before' ]]"

# French messages: introduction in French, with the role's French name when it has one (2026-09-25)
check "French introduction uses the French name" "[[ \"\$(intro_text_for 'claude control center' fr)\" == 'Un message de la tour de contrôle.' ]]"
check "English introduction unchanged" "[[ \"\$(intro_text_for 'claude control center' en)\" == 'session tower here.' ]]"
check "a product name stays as it is in French" "[[ \"\$(intro_text_for 'micro duck' fr)\" == 'Un message de micro duck.' ]]"
check "the secretary has no introduction in French either" "[[ -z \"\$(intro_text_for 'the secretary' fr)\" ]]"
check "repeat: 'again' in the message's language" "[[ \"\$(intro_text_for secretary en again)\" == 'Again.' && \"\$(intro_text_for secretary fr again)\" == 'Encore une fois.' && \"\$(intro_text_for tower en again)\" == 'session tower here, again.' && \"\$(intro_text_for tower fr again)\" == 'Un message de la tour de contrôle, encore une fois.' ]]"
check "every tracked French name is a non-empty string" "python3 - <<PY
import json,sys
roles=json.load(open('$ROOT/secretary/voices.json'))['roles']
sys.exit(0 if all(isinstance(r.get('role_fr', 'x'), str) and r.get('role_fr', 'x').strip() for r in roles) else 1)
PY"
python3 - "$SECRETARY_RUNTIME/voices.learned.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["roles"] += [{"role": "family and one-off questions", "aliases": ["kitchen table"], "voice": "vera"},
               {"role": "garden study", "role_fr": "l'étude du jardin", "aliases": [], "voice": "alba"}]
json.dump(d, open(sys.argv[1], "w"))
PY
check "a learned alias of a tracked role takes its French name" "[[ \"\$(intro_text_for 'kitchen table' fr)\" == 'Un message des questions diverses.' ]]"
check "a learned role can carry its own French name" "[[ \"\$(intro_text_for 'garden study' fr)\" == \"Un message de l'étude du jardin.\" && \"\$(intro_text_for 'garden study')\" == 'garden study here.' ]]"
check "counts: English digits, French words" "[[ \"\$(count_text en 2)\" == '2 older waiting.' && \"\$(count_text fr 1)\" == 'Encore un message en attente.' && \"\$(count_text fr 3)\" == 'Encore trois messages en attente.' ]]"

# fallbacks: a broken or missing roles file, or a voice that does not exist, must still speak
printf '{ broken' >"$TMP/bad.json"
check "broken roles file: still a pool voice" "v=\$(SECRETARY_VOICES_FILE='$TMP/bad.json' voice_for 'ludometer'); [[ ' $VOICE_POOL_EN ' == *\" \$v \"* ]]"
printf '{"roles":[{"role":"typo","aliases":[],"voice":"no_such_voice"}]}' >"$TMP/typo.json"
check "unknown voice in the file: hash fallback, logged" "v=\$(SECRETARY_VOICES_FILE='$TMP/typo.json' voice_for typo); [[ ' $VOICE_POOL_EN ' == *\" \$v \"* ]] && grep -q 'not a known voice' '$LOG_FILE'"
check "helper missing: hash fallback" "v=\$(VOICES_PY=/nonexistent voice_for 'ludometer'); [[ ' $VOICE_POOL_EN ' == *\" \$v \"* ]]"

echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
