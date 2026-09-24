#!/bin/bash
# Memory guard. On 2026-09-21 at 22:20 the Mac froze and rebooted: memory was exhausted (14 MB
# free, no file cache left, 19 GB in the compressor on a 36 GB machine; one browser tab at 24 GB,
# two Python jobs at 18 and 11 GB). The kernel had been killing idle processes since 22:09, eleven
# minutes earlier, and nothing told Remi, who only saw the mouse get slower. This script tells him
# while there is still time to act, and names the biggest processes.
#   memory_guard.sh            check once: health flag "memory", one spoken warning per episode
#   memory_guard.sh --status   print one plain line and exit (for the self-check and by hand)
# Called in the background by the Stop hook of every session (cheap: two sysctl/vm_stat reads,
# 10 ms; `top` runs only when there is something to say). It never kills anything: what to close
# is Remi's decision. One exception inside our own system: the warm voice daemon is restarted
# when it has grown past POCKET_MAX_MB and nothing is speaking (it reloads in about a second).
source "$(dirname "$0")/lib.sh"
WARN_COMPRESSED_PCT="${SECRETARY_MEM_WARN_COMPRESSED_PCT:-35}"   # compressor size as % of RAM
REPEAT_S="${SECRETARY_MEM_REPEAT_S:-600}"
POCKET_MAX_MB="${SECRETARY_POCKET_MAX_MB:-4000}"
STAMP="$SECRETARY_RUNTIME/memory_warned"
# all readings can be replaced for tests: "<pressure level> <compressed % of RAM>"
# Absolute paths (sysctl lives in /usr/sbin, which not every caller has in PATH) and no defaults:
# on 2026-09-24 at 09:06 one sysctl call failed, the RAM size fell back to 1 byte, the compressor
# came out as 606969856000 % of RAM and Remi was told the Mac was short of memory while 83 % was
# free. A reading that is not four plain numbers is "unknown", and unknown decides nothing.
SYSCTL="${SECRETARY_SYSCTL:-/usr/sbin/sysctl}"; VM_STAT="${SECRETARY_VM_STAT:-/usr/bin/vm_stat}"
reading() {
  if [[ -n "${SECRETARY_MEM_READING:-}" ]]; then printf '%s' "$SECRETARY_MEM_READING"; return; fi
  local level pages ram pagesize
  level="$("$SYSCTL" -n kern.memorystatus_vm_pressure_level 2>/dev/null)"
  pages="$("$VM_STAT" 2>/dev/null | sed -nE 's/^Pages occupied by compressor: +([0-9]+)\..*/\1/p')"
  ram="$("$SYSCTL" -n hw.memsize 2>/dev/null)"
  pagesize="$("$SYSCTL" -n hw.pagesize 2>/dev/null)"
  if [[ ! ( "$level" =~ ^[0-9]+$ && "$pages" =~ ^[0-9]+$ && "$ram" =~ ^[1-9][0-9]*$ && "$pagesize" =~ ^[1-9][0-9]*$ ) ]]; then
    printf 'unknown level=%s pages=%s ram=%s pagesize=%s' "${level:-none}" "${pages:-none}" "${ram:-none}" "${pagesize:-none}"; return
  fi
  printf '%s %s' "$level" "$(( pages * pagesize * 100 / ram ))"
}
biggest() {   # "firefox 24 gigabytes, python 18 gigabytes, ..." (top counts compressed memory too)
  if [[ -n "${SECRETARY_MEM_TOP:-}" ]]; then printf '%s' "$SECRETARY_MEM_TOP"; return; fi
  top -l 1 -o mem -n 3 -stats command,mem 2>/dev/null | tail -n 3 | awk '
    { mem=$NF; $NF=""; name=$0; sub(/ +$/,"",name)
      if (mem ~ /G/) { sub(/G.*/,"",mem); unit="gigabytes" } else { sub(/M.*/,"",mem); unit="megabytes" }
      printf "%s%s %s %s", (n++ ? ", " : ""), name, mem, unit }'
}
read -r level pct <<<"$(reading)"
# a compressor larger than the RAM, or a level that is not a number, is a broken reading too
if [[ "$level" != unknown ]] && [[ ! ( "$level" =~ ^[0-9]+$ && "$pct" =~ ^[0-9]+$ ) || "$pct" -gt 100 ]]; then
  pct="level=$level compressed=$pct"; level=unknown
fi
if [[ "$level" == unknown ]]; then
  if [[ "${1:-}" == "--status" ]]; then echo "memory reading unavailable ($pct)"; exit 0; fi
  log "memory guard: reading unavailable this time ($pct), nothing decided"; exit 0
fi

# A record that survives a crash (2026-09-21: the two big Python jobs could not be named afterwards,
# the last log minutes were lost and the pids were dead). Every MEMLOG_EVERY_S one line goes to
# runtime/secretary/memory.log: pressure, compressed share, and the five biggest processes with pid
# and command line (top's MEM counts compressed memory too). The file is kept under 2000 lines.
MEMLOG="$SECRETARY_RUNTIME/memory.log"; MEMLOG_EVERY_S="${SECRETARY_MEMLOG_EVERY_S:-300}"
if [[ -z "${SECRETARY_MEM_READING:-}" && "${1:-}" != "--status" ]] &&
   [[ $(( $(date +%s) - $(stat -f %m "$MEMLOG" 2>/dev/null || echo 0) )) -ge "$MEMLOG_EVERY_S" ]]; then
  {
    printf '%s level=%s compressed=%s%%' "$(date '+%Y-%m-%d %H:%M:%S')" "$level" "$pct"
    top -l 1 -o mem -n 5 -stats pid,mem 2>/dev/null | tail -n 5 | while read -r tpid tmem; do
      printf ' | %s %s %s' "$tpid" "$tmem" "$(ps -o command= -p "$tpid" 2>/dev/null | cut -c1-110)"
    done
    printf '\n'
  } >>"$MEMLOG"
  if [[ "$(wc -l <"$MEMLOG")" -gt 2000 ]]; then tail -n 1500 "$MEMLOG" >"$MEMLOG.tmp" && mv "$MEMLOG.tmp" "$MEMLOG"; fi
fi
problem=""
if [[ "${level:-1}" -ge 4 ]]; then problem="the Mac is critically short of memory"
elif [[ "${level:-1}" -ge 2 || "${pct:-0}" -ge "$WARN_COMPRESSED_PCT" ]]; then problem="the Mac is running short of memory"; fi

if [[ "${1:-}" == "--status" ]]; then
  echo "memory pressure level ${level:-?} (1 normal, 2 warning, 4 critical), compressed ${pct:-?}% of RAM${problem:+: $problem}"; exit 0
fi

# our own daemons first: a warm voice engine that has grown large is restarted while it is idle
# (Pocket starts at 0.85 GB, Kokoro at about 1.5 GB; both live in local-tts-lab)
if [[ -z "${SECRETARY_MEM_READING:-}" ]] && ! audio_busy && [[ -z "$(speech_lock_owner)" ]] && [[ "$(inbox_rendering_count)" == 0 ]]; then
  for daemon in "^/Users/remi/local-tts-lab/[.]venv-pocket/bin/python .*pocket_service[.]py daemon serve|$KOKORO_CTL" "^/Users/remi/local-tts-lab/[.]venv/bin/python -m local_tts_lab[.]kokoro_service serve|/Users/remi/local-tts-lab/.venv/bin/local-tts"; do
    dpid="$(pgrep -f "${daemon%%|*}" | head -n 1)"; [[ -n "$dpid" ]] || continue
    dmb=$(( $(ps -o rss= -p "$dpid" 2>/dev/null | tr -d ' ' || echo 0) / 1024 ))
    if [[ "$dmb" -ge "$POCKET_MAX_MB" ]]; then
      log "memory guard: voice daemon ${daemon%%|*} (pid $dpid) had grown to ${dmb} MB, restarting it while idle"
      PYTORCH_ENABLE_MPS_FALLBACK=1 "${daemon##*|}" kokoro-daemon restart >/dev/null 2>&1 || true
    fi
  done
fi

# Orphan voice daemons: a start that races another one leaves two daemons, and only the one named
# in the pid file is ever used or stopped again (2026-09-21: pairs of 2 GB Kokoro daemons piled up).
# Any extra one is ended, whether or not memory is short. Only our own two daemons are touched.
if [[ -z "${SECRETARY_MEM_READING:-}" ]]; then
  # The patterns are anchored on the daemons' own interpreter: a bare `pgrep -f name` also matches
  # any shell or editor whose command line merely contains that name (it ended the shell that
  # first ran this, 2026-09-21 22:59).
  for svc in "^/Users/remi/local-tts-lab/[.]venv/bin/python -m local_tts_lab[.]kokoro_service serve|/Users/remi/local-tts-lab/runtime/cache/kokoro-service/kokoro.pid" \
             "^/Users/remi/local-tts-lab/[.]venv-pocket/bin/python /Users/remi/local-tts-lab/src/local_tts_lab/pocket_service[.]py daemon serve|/Users/remi/local-tts-lab/runtime/cache/pocket-service/pocket.pid"; do
    keep="$(cat "${svc##*|}" 2>/dev/null | tr -dc '0-9')"
    pids="$(pgrep -f "${svc%%|*}" | tr '\n' ' ')"
    [[ "$(wc -w <<<"$pids")" -gt 1 ]] || continue
    for dp in $pids; do
      [[ "$dp" == "$keep" ]] && continue
      # without a usable pid file keep the oldest and end the rest
      [[ -z "$keep" || " $pids " != *" $keep "* ]] && { keep="$dp"; continue; }
      log "memory guard: ending orphan voice daemon $dp (${svc%%|*}), the registered one is $keep"
      kill -TERM "$dp" 2>/dev/null
    done
  done
fi

if [[ -z "$problem" ]]; then
  [[ "$(cut -f2- "$HEALTH_DIR/memory" 2>/dev/null)" == "ok" ]] || { health_set memory ok; rm -f "$STAMP"; }
  exit 0
fi
who="$(biggest)"
text="$problem (pressure level $level, $pct percent compressed); the biggest: ${who:-unknown}"
health_set memory "$text"
# one spoken warning per episode, repeated every REPEAT_S while it lasts
if [[ -f "$STAMP" && $(( $(date +%s) - $(stat -f %m "$STAMP" 2>/dev/null || echo 0) )) -lt "$REPEAT_S" ]]; then exit 0; fi
: >"$STAMP"
log "memory guard: $text"
play_cue "$FAIL_SOUND"; sleep 1.6
nohup "$(dirname "$0")/say_now.sh" "Warning: $problem. The biggest programs are ${who:-unknown}. Close something before it freezes." >/dev/null 2>&1 &
