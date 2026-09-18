"""Attention ledger shared by the hooks: one JSON file per Claude Code session under
runtime/secretary/ledger/, holding its latest activity and whether it is waiting on Remi."""
import glob
import json
import os
import re
import time

LEDGER_DIR = "/Users/remi/voice2clipboard/runtime/secretary/ledger"
ATTENTION_PATTERNS = re.compile(
    r"\?\s*$|\b(let me know|tell me|your call|should i|do you want|would you like|can you confirm|"
    r"waiting for you|need(s)? (your|a) (decision|answer|input|go-ahead)|please (confirm|decide|choose|review)|"
    r"which (one|option)|say (yes|the word))\b",
    re.I,
)


def project_name(cwd):
    base = os.path.basename((cwd or "").rstrip("/")) or "an agent"
    if base == "voice2clipboard":
        return "the secretary"  # Remi's mental model: this project IS the secretary
    if base == "secretary":
        return "the secretary"
    return base.replace("-", " ").replace("_", " ")


def spoken_text(msg, limit=70):
    m = re.search(r"(?ms)^\**Spoken:?\**\s*(.+?)(?:\n\s*\n|\Z)", msg or "")
    if m:
        return m.group(1).strip()
    plain = re.sub(r"```.*?```", " ", msg or "", flags=re.S)
    plain = re.sub(r"[`*_#>|]", "", plain)
    plain = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", plain)
    words = re.sub(r"\s+", " ", plain).strip().split()
    return " ".join(words[:limit]) + (" ... more on screen." if len(words) > limit else "")


def needs_attention(msg):
    text = (msg or "").strip()
    if not text:
        return False
    tail = " ".join(text.split()[-60:])
    return bool(ATTENTION_PATTERNS.search(tail))


def _path(session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")[:80]
    return os.path.join(LEDGER_DIR, safe + ".json")


def load(session_id):
    try:
        return json.load(open(_path(session_id)))
    except Exception:
        return {}


def write(session_id, **fields):
    os.makedirs(LEDGER_DIR, exist_ok=True)
    entry = load(session_id)
    entry.update(fields)
    entry["session_id"] = session_id
    entry["updated"] = time.time()
    tmp = _path(session_id) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(entry, f, indent=1)
    os.replace(tmp, _path(session_id))
    return entry


def entries(max_age_hours=24):
    out = []
    cutoff = time.time() - max_age_hours * 3600
    for p in glob.glob(os.path.join(LEDGER_DIR, "*.json")):
        try:
            e = json.load(open(p))
        except Exception:
            continue
        if e.get("updated", 0) >= cutoff:
            out.append(e)
    out.sort(key=lambda e: (not e.get("needs_attention"), -e.get("updated", 0)))
    return out


def age_text(ts):
    s = int(time.time() - ts)
    if s < 90:
        return "just now"
    if s < 3600:
        return f"{s // 60} minutes ago"
    if s < 86400:
        return f"{s // 3600} hours ago"
    return f"{s // 86400} days ago"


# ---- notification policy ------------------------------------------------------------------
OVERRIDES_PATH = "/Users/remi/voice2clipboard/secretary/notify_overrides.json"
PROBLEM_PATTERNS = re.compile(r"\b(failed|failure|error|crash|cannot|can.t|couldn.t|blocked|broken|security|vulnerab|leak|data loss|lost)\b", re.I)
NOTIFY_MARKER = re.compile(r"(?m)^\**Notify( Remi)?:?\**\s*(.+)$", re.I)


def policy_for(project):
    try:
        table = json.load(open(OVERRIDES_PATH)).get("projects", {})
    except Exception:
        table = {}
    return table.get(project, "secretary-decides")


def classify(msg):
    """Why this turn might deserve Remi's attention: 'asked to notify', 'waiting on Remi', 'possible problem' or ''."""
    if NOTIFY_MARKER.search(msg or ""):
        return "asked to notify"
    if needs_attention(msg):
        return "waiting on Remi"
    if PROBLEM_PATTERNS.search(spoken_text(msg, 120)):
        return "possible problem"
    return ""


def forward_to_secretary(scripts_dir, project, session_id, reason, text):
    """Hand a flagged turn to the secretary session as a typed message. Returns True if delivered."""
    import subprocess
    body = ("[Agent report] project: %s | session: %s | why: %s\n%s\n"
            "(Decide: if Remi should hear this, run inbox_post.sh --from \"%s\" with the spoken text; "
            "otherwise stay silent. The ledger already has it.)" % (project, session_id[:8], reason, text, project))
    if os.getenv("SECRETARY_FORWARD_DRY_RUN") == "1":
        print(body)
        return True
    env = dict(os.environ, ASK_SECRETARY_QUIET="1")
    r = subprocess.run([os.path.join(scripts_dir, "ask_secretary.sh"), body], capture_output=True, text=True, env=env)
    return r.returncode == 0
