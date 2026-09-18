#!/bin/bash
# Prints the attention ledger as plain spoken-style text: sessions waiting on Remi first, then the
# rest with what they last did. Usage: ledger.sh [--hours N]
hours=24; [[ "${1:-}" == "--hours" ]] && hours="$2"
python3 - "$(dirname "$0")" "$hours" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import ledger_lib as L
es = L.entries(float(sys.argv[2]))
if not es:
    print("Nothing recorded in the last %s hours." % sys.argv[2]); sys.exit(0)
waiting = [e for e in es if e.get("needs_attention")]
print("NEEDS YOU (%d):" % len(waiting) if waiting else "Nothing is waiting on you.")
for e in waiting:
    print("- %s, %s: %s. Last said: %s" % (e["project"], L.age_text(e["updated"]), e.get("reason") or "asked you something", (e.get("summary") or "")[:300]))
others = [e for e in es if not e.get("needs_attention")]
if others:
    print("\nOTHERS (%d):" % len(others))
    for e in others:
        print("- %s, %s, %s: %s" % (e["project"], L.age_text(e["updated"]), e.get("state") or "", (e.get("summary") or "")[:160]))
PY
