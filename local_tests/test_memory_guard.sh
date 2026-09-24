#!/bin/bash
# Memory guard: warns while there is still time (2026-09-21: the Mac froze after eleven minutes of
# memory pressure that nobody was told about). Readings are injected, the voice is a stand-in,
# the runtime is a temp folder: no sound, nothing real is read or restarted.
# Run: bash local_tests/test_memory_guard.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
STAGE="$TMP/stage"; mkdir -p "$STAGE"
cp "$ROOT"/scripts/mac/secretary/*.sh "$ROOT"/scripts/mac/secretary/*.py "$STAGE/"
printf '#!/bin/bash\nprintf "%%s\\n" "$*" >>"%s/said.txt"\n' "$TMP" >"$STAGE/say_now.sh"; chmod +x "$STAGE/say_now.sh"
export SECRETARY_RUNTIME="$TMP/runtime" SECRETARY_CUES_MUTED=1 DICTATION_LOCK="$TMP/recorder.pid" \
       SECRETARY_MEM_TOP="firefox 24 gigabytes, python 18 gigabytes, python 11 gigabytes"
mkdir -p "$SECRETARY_RUNTIME"
source "$STAGE/lib.sh"
fails=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fails=$((fails + 1)); fi; }
flag() { cut -f2- "$HEALTH_DIR/memory" 2>/dev/null; }
said() { cat "$TMP/said.txt" 2>/dev/null | wc -l | tr -d ' '; }
guard() { SECRETARY_MEM_READING="$1" bash "$STAGE/memory_guard.sh"; /bin/sleep 0.3; }

guard "1 5"
check "normal: flag ok, nothing said" "[[ \"\$(flag)\" == ok && \$(said) == 0 ]]"
guard "1 40"
check "compressor at 40 % of RAM: warned although the OS still says normal" "grep -q 'running short of memory' <<<\"\$(flag)\" && [[ \$(said) == 1 ]]"
check "the warning names the biggest programs" "grep -q 'firefox 24 gigabytes' '$TMP/said.txt'"
guard "2 45"
check "same episode: not said again" "[[ \$(said) == 1 ]]"
guard "4 55"
check "critical: flag says critical, still one warning within ten minutes" "grep -q 'critically short' <<<\"\$(flag)\" && [[ \$(said) == 1 ]]"
touch -t "$(date -v-11M '+%Y%m%d%H%M.%S')" "$SECRETARY_RUNTIME/memory_warned"
guard "4 55"
check "still critical after ten minutes: said again" "[[ \$(said) == 2 ]]"
guard "1 8"
check "back to normal: flag ok" "[[ \"\$(flag)\" == ok ]]"
guard "2 20"
check "a new episode is announced at once" "[[ \$(said) == 3 ]]"
check "status line is plain" "SECRETARY_MEM_READING='2 20' bash '$STAGE/memory_guard.sh' --status | grep -q 'pressure level 2.*running short'"
check "the real readings work on this Mac" "bash '$STAGE/memory_guard.sh' --status | grep -Eq 'pressure level [124] .*compressed [0-9]+% of RAM'"

# A failed reading decides nothing (2026-09-24 09:06: one sysctl call failed, the RAM size fell back
# to 1 byte, "606969856000 % compressed" was spoken as a memory shortage while 83 % was free).
guard "2 20"; before="$(said)"; flag_before="$(flag)"
SECRETARY_SYSCTL=/usr/bin/false bash "$STAGE/memory_guard.sh"; /bin/sleep 0.3
check "sysctl failing: nothing said, flag untouched" "[[ \$(said) == \$before && \"\$(flag)\" == \"\$flag_before\" ]]"
check "sysctl failing: logged as unavailable" "grep -q 'memory guard: reading unavailable this time' '$SECRETARY_RUNTIME/secretary.log'"
check "sysctl failing: status says so instead of a number" "SECRETARY_SYSCTL=/usr/bin/false bash '$STAGE/memory_guard.sh' --status | grep -q 'reading unavailable'"
SECRETARY_VM_STAT=/usr/bin/true bash "$STAGE/memory_guard.sh"; /bin/sleep 0.3
check "vm_stat printing nothing: nothing said" "[[ \$(said) == \$before ]]"
guard "1 606969856000"
check "a compressor larger than the RAM is a broken reading, not an alarm" "[[ \$(said) == \$before ]]"
guard "x 20"
check "a pressure level that is not a number decides nothing" "[[ \$(said) == \$before ]]"
check "the real reading still works after all that" "bash '$STAGE/memory_guard.sh' --status | grep -Eq 'compressed [0-9]+% of RAM'"

echo; [[ "$fails" == 0 ]] && echo "all passed" || { echo "$fails failed"; exit 1; }
