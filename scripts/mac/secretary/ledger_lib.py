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


SECRETARY_RUNTIME = os.getenv("SECRETARY_RUNTIME", "/Users/remi/voice2clipboard/runtime/secretary")
if os.getenv("SECRETARY_RUNTIME"):
    LEDGER_DIR = os.path.join(SECRETARY_RUNTIME, "ledger")   # tests keep their own ledger

# Keep-warm pings (2026-09-21). The Session Tower types a prompt starting with PING_PREFIX into an
# idle session so its prompt cache does not expire; the session answers with the single word
# "coconut". Such a turn is not activity: it must not replace the session's real last message in
# the ledger, clear a "waiting on Remi" flag, or be reported to the secretary. The prompt hook
# leaves a marker per session; the Stop hook takes it and, if the answer really is the ping's
# answer, records nothing. A marker without that answer (the session said something real) counts
# as a normal turn, and a marker older than PING_MARK_MAX_S is forgotten.
PING_PREFIX = "banana (automatic keep-warm ping"
PING_DIR = os.path.join(SECRETARY_RUNTIME, "pings")
PING_MARK_MAX_S = 900


def is_ping_prompt(prompt):
    return (prompt or "").lstrip().lower().startswith(PING_PREFIX)


def _ping_mark_path(session_id):
    return os.path.join(PING_DIR, re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown"))


def ping_mark(session_id):
    os.makedirs(PING_DIR, exist_ok=True)
    with open(_ping_mark_path(session_id), "w") as f:
        f.write(str(time.time()))


def is_ping_answer(msg):
    m = re.sub(r"[^a-z]", "", (msg or "").lower())
    return m == "coconut"


def ping_take(session_id, msg):
    """True when the turn that just ended was a keep-warm ping (marker left by the prompt hook and
    the expected one-word answer). The marker is removed either way."""
    path = _ping_mark_path(session_id)
    try:
        fresh = time.time() - os.stat(path).st_mtime < PING_MARK_MAX_S
        os.remove(path)
    except OSError:
        return False
    return fresh and is_ping_answer(msg)


def is_secretary(cwd, session_id=""):
    """The secretary is the session started in the secretary directory, or the Claude session
    that registered itself as the secretary (it may have been resumed by hand from anywhere:
    on 2026-09-19 it came back in /Users/remi and every check based on the directory missed it)."""
    if (cwd or "").rstrip("/").endswith("/secretary"):
        return True
    try:
        known = open(os.path.join(SECRETARY_RUNTIME, "secretary_claude_session")).read().strip()
    except OSError:
        known = ""
    return bool(known) and known == session_id


def register_secretary_window(scripts_dir, session_id):
    """Called on the secretary's own turns: keep the dictation target pointing at the window this
    session really runs in. Cheap, silent, and only logs when something changed."""
    import subprocess
    if not os.getenv("ITERM_SESSION_ID"):
        return
    subprocess.run([os.path.join(scripts_dir, "register_secretary.sh"), "--quiet",
                    "--claude-session", session_id], check=False, capture_output=True, timeout=10)


def project_name(cwd):
    base = os.path.basename((cwd or "").rstrip("/")) or "an agent"
    if base == "voice2clipboard":
        return "the secretary"  # Remi's mental model: this project IS the secretary
    if base == "secretary":
        return "the secretary"
    return base.replace("-", " ").replace("_", " ")


def spoken_text(msg, limit=70):
    # Everything after "Spoken:" is meant for the ears, however many paragraphs it takes (it used
    # to stop at the first blank line, which cut long reports short); a Notify line ends it.
    m = re.search(r"(?ms)^\**Spoken:?\**\s*(.+?)(?=^\**Notify:|\Z)", msg or "")
    if m:
        return re.sub(r"\s*\n\s*", " ", m.group(1)).strip()
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
    # The full spoken text also goes to a file: a long report typed into a terminal is easy to
    # lose part of, and the secretary can post it straight from the file (inbox_post.sh reads stdin).
    reports = os.path.join(SECRETARY_RUNTIME, "reports")
    os.makedirs(reports, exist_ok=True)
    path = os.path.join(reports, "%s-%d.txt" % (session_id[:8], int(time.time())))
    with open(path, "w") as f:
        f.write(text + "\n")
    for old_report in sorted(glob.glob(os.path.join(reports, "*.txt")))[:-200]:
        os.remove(old_report)
    body = ("[Agent report] project: %s | session: %s | why: %s | words: %d | full text: %s\n%s\n"
            "(Decide: if Remi should hear this, run inbox_post.sh --from \"%s\" < that file, or with the "
            "spoken text; otherwise stay silent. The ledger already has it.)"
            % (project, session_id[:8], reason, len(text.split()), path, text, project))
    if os.getenv("SECRETARY_FORWARD_DRY_RUN") == "1":
        print(body)
        return True
    env = dict(os.environ, ASK_SECRETARY_QUIET="1")
    r = subprocess.run([os.path.join(scripts_dir, "ask_secretary.sh"), body], capture_output=True, text=True, env=env)
    return r.returncode == 0
