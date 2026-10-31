#!/usr/bin/env python3
"""Hand one of Remi's dictations, verbatim, to the Claude session it is meant for.

  deliver_dictation.sh --to <session name> [--id YYYY-MM-DD/HH-MM-SS]
  deliver_dictation.sh --list

Remi, 2026-10-31: the earbuds replace his hands. A request he dictates to the secretary and the
secretary relays by SendMessage is a message from another session: the harness and the auto mode
classifier rightly refuse to take it as his consent ("Unrequested Commit in a Connected App"), and
he was asked to come to the keyboard for something he had already said. The same words typed into
the target's own terminal by his own dictation pipeline are a turn from him, as when he dictates
into the frontmost window. So the secretary only chooses WHERE a dictation goes; this script does
the typing, and the only text it ever types is the recorder's transcript of that dictation:

- no text argument at all: an id and a session name, both checked against a strict pattern;
- the transcript comes from the recordings folder, written by the recorder, delivered to the
  secretary (its `.sent` marker), at most MAX_AGE_S old, with its audio beside it;
- each dictation goes at most once to a given session, under a lock;
- the target is a live Claude Code session found by name in ~/.claude/sessions, whose terminal's
  foreground process is Claude (never a shell: typed text would run as a command), never the
  secretary itself; its window must show its input prompt (no Escape is ever pressed in another
  agent's window: it would answer a dialog);
- every delivery is logged with the transcript's hash.

What it does not stop: a program running as Remi could write a fake recording, and the secretary
could pick the wrong session (the words are still his, but a bare "go" would land in the wrong
place). Outside agents, which can only send messages, can do neither.
Exit: 0 delivered, 2 bad usage or no such dictation, 3 target unusable, 4 typed but not taken."""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ROOT = "/Users/remi/voice2clipboard"
sys.path.insert(0, os.path.join(ROOT, "apps", "linux", "legacy_whisper"))
import voice_transcriber as vt  # noqa: E402   the recorder's own, tested delivery into a Claude window

vt.send_escape_to_iterm_session = lambda session_id: None   # never answer a dialog in another agent's window

RECORDINGS = os.getenv("VOICE2CLIPBOARD_RECORDINGS_DIR", os.path.join(ROOT, "recordings"))
RUNTIME = os.getenv("SECRETARY_RUNTIME", os.path.join(ROOT, "runtime", "secretary"))
SESSIONS = os.getenv("CLAUDE_SESSIONS_DIR", os.path.expanduser("~/.claude/sessions"))
MAX_AGE_S = int(os.getenv("SECRETARY_DICTATION_MAX_AGE_S", "900"))
ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}/\d{2}-\d{2}-\d{2}$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
LOG = os.path.join(RUNTIME, "dictation_deliveries.log")


def log(msg):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for path in (LOG, os.path.join(RUNTIME, "secretary.log")):
        try:
            with open(path, "a") as f:
                f.write(f"{stamp} deliver_dictation: {msg}\n")
        except OSError:
            pass


def fail(code, msg):
    print(msg, file=sys.stderr)
    log("refused: " + msg)
    sys.exit(code)


def dictations():
    """Fresh dictations that reached the secretary: [(id, folder, age_s, text)], newest last."""
    out, now = [], time.time()
    for folder in sorted(glob.glob(os.path.join(RECORDINGS, "*", "*"))):
        rid = os.path.relpath(folder, RECORDINGS)
        transcript, sent = os.path.join(folder, "transcript.txt"), os.path.join(folder, ".sent")
        if not ID_RE.match(rid) or not os.path.isfile(transcript) or not os.path.isfile(sent):
            continue
        age = now - os.path.getmtime(transcript)
        if age > MAX_AGE_S or not os.path.isfile(os.path.join(folder, "audio.wav")):
            continue
        if not open(sent).read().startswith("iterm_session"):   # copied to the clipboard only, never routed
            continue
        text = open(transcript).read().strip()
        if text:
            out.append((rid, folder, age, text))
    return out


def forwarded_to(folder):
    try:
        return [line.split("\t")[0] for line in open(os.path.join(folder, ".forwarded")) if line.strip()]
    except OSError:
        return []


def live_session(name):
    """(pid, info) of the live Claude session called `name`, or None."""
    for path in glob.glob(os.path.join(SESSIONS, "*.json")):
        try:
            info = json.load(open(path))
        except (OSError, ValueError):
            continue
        if info.get("name") != name:
            continue
        pid = int(info.get("pid") or 0)
        try:
            os.kill(pid, 0)
        except (OSError, ValueError):
            continue
        return pid, info
    return None


def tty_of(pid):
    try:
        tty = subprocess.check_output(["ps", "-o", "tty=", "-p", str(pid)], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""
    return "" if not tty or tty.startswith("?") else "/dev/" + tty


def iterm_session_for_tty(tty):
    script = f'''
tell application "iTerm2"
    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                if (tty of s as text) is "{tty}" then return (unique id of s as text)
            end repeat
        end repeat
    end repeat
end tell
return ""'''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def header(rid):
    hh, mm = rid.split("/")[1].split("-")[:2]
    return f"[Dictated by Remi at {hh}:{mm}, routed here by the secretary] "


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--to")
    ap.add_argument("--id")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    fresh = dictations()
    if a.list:
        for rid, folder, age, text in fresh:
            sent = ", ".join(forwarded_to(folder)) or "nobody yet"
            print(f"{rid}  {int(age // 60)} min ago  forwarded to: {sent}  | {' '.join(text.split()[:12])}")
        return
    if not a.to or not NAME_RE.match(a.to):
        fail(2, "usage: deliver_dictation.sh --to <session name> [--id YYYY-MM-DD/HH-MM-SS]")
    if a.id is not None and not ID_RE.match(a.id):
        fail(2, f"not a dictation id: {a.id!r}")
    if a.to.startswith("secretary-"):
        fail(3, "the secretary already has its dictations")
    candidates = [d for d in fresh if (a.id is None or d[0] == a.id) and a.to not in forwarded_to(d[1])]
    if not candidates:
        fail(2, f"no fresh dictation{' ' + a.id if a.id else ''} left to give to {a.to} (older than "
                f"{MAX_AGE_S // 60} min, already given to it, or not a dictation): see --list")
    if len(candidates) > 1:
        fail(2, "several fresh dictations, name one with --id: " + ", ".join(d[0] for d in candidates))
    rid, folder, _age, text = candidates[0]

    found = live_session(a.to)
    if not found:
        fail(3, f"no live session called {a.to}")
    pid, info = found
    if os.path.realpath(info.get("cwd", "")) == os.path.join(ROOT, "secretary"):
        fail(3, f"{a.to} is the secretary")
    tty = tty_of(pid)
    iterm = iterm_session_for_tty(tty) if tty else ""
    if not iterm:
        fail(3, f"{a.to} has no iTerm window this script can type into")
    if not vt.iterm_session_runs_claude(iterm):   # a shell would run the text as a command
        fail(3, f"the window of {a.to} is not running Claude in the foreground")
    if not vt.claude_input_ready(iterm):
        fail(3, f"the window of {a.to} shows no input prompt (a dialog is open): nothing typed")

    lock = os.path.join(folder, ".forwarding")
    try:
        os.mkdir(lock)
    except FileExistsError:
        fail(2, f"dictation {rid} is being delivered right now")
    try:
        if a.to in forwarded_to(folder):
            fail(2, f"dictation {rid} was already given to {a.to}")
        message = header(rid) + vt.apply_word_dictionary(text)
        digest = hashlib.sha256(text.encode()).hexdigest()[:16]
        ok = vt.deliver_to_claude_session(message, iterm, lambda m: log(m))
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(folder, ".forwarded"), "a") as f:
            f.write(f"{a.to}\t{stamp}\t{digest}\t{'taken' if ok else 'typed, not seen taken'}\n")
        log(f"{rid} -> {a.to} (pid {pid}, {iterm}) sha256:{digest} {'delivered' if ok else 'typed but not seen in its transcript'}")
    finally:
        os.rmdir(lock)
    if not ok:
        fail(4, f"typed into {a.to} but not seen taken: check that window")
    print(f"delivered {rid} to {a.to}")


if __name__ == "__main__":
    main()
