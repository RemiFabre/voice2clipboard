#!/bin/bash
# Search the archive of every message that was played or discarded. Usage: messages_search.sh [pattern] [--last N]
# Voluntary lookup only (the secretary runs it when Remi asks); never automatic.
source "$(dirname "$0")/lib.sh"
pattern=""; last=20
while [[ $# -gt 0 ]]; do case "$1" in --last) last="$2"; shift 2 ;; *) pattern="$1"; shift ;; esac; done
files="$(ls "$SPOKEN_DIR"/*.txt 2>/dev/null | sort -r)"
[[ -n "$pattern" ]] && files="$(grep -il -- "$pattern" $files 2>/dev/null)"
n=0
for f in $files; do
  [[ $n -ge $last ]] && break; n=$((n+1))
  stamp="$(basename "$f" | cut -d- -f1)"; when="$(date -r $((stamp/1000)) '+%Y-%m-%d %H:%M')"
  from="$(sed -n 's/^from=//p' "$f" | head -n 1)"; status="$(sed -n 's/^status=//p' "$f" | tail -n 1)"
  body="$(awk 'f&&!/^status=/{print} /^$/{f=1}' "$f" | tr '\n' ' ' | cut -c1-240)"
  printf '%s  %s  [%s]  %s\n' "$when" "$from" "${status:-queued, not yet heard}" "$body"
done
[[ $n -eq 0 ]] && echo "no archived message matches"
