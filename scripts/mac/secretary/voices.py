#!/usr/bin/env python3
"""Sticky voices: who speaks with which voice in the earbuds.

  voices.py voice <name>     -> the voice for that sender
  voices.py display <name>   -> the role's spoken name ("session tower" for "claude control center")
  voices.py display <name> fr -> its French name ("la tour de contrôle"), from "role_fr"; the
                                English one when the role has none
  voices.py list             -> every role, its voice and aliases

secretary/voices.json (tracked, edited by hand) maps roles and their aliases to voices. A name
found nowhere gets the least used voice of the pool and is written to
runtime/secretary/voices.learned.json (untracked: the repository is public and sender names can be
personal), so it is the same voice from then on. Environment: SECRETARY_VOICES_FILE,
SECRETARY_VOICES_LEARNED, SECRETARY_VOICE_POOL (space separated).
"""
import json, os, re, sys, tempfile, time

ROOT = "/Users/remi/voice2clipboard"
ROLES_FILE = os.environ.get("SECRETARY_VOICES_FILE") or ROOT + "/secretary/voices.json"
LEARNED_FILE = os.environ.get("SECRETARY_VOICES_LEARNED") or ROOT + "/runtime/secretary/voices.learned.json"
POOL = os.environ.get("SECRETARY_VOICE_POOL", "").split()


def norm(name):
    return re.sub(r"[\s_\-]+", " ", (name or "").strip().lower()).strip()


def keys(name):
    """Forms under which a name is looked up, most exact first: as given, without a session
    suffix ("secretary builder 3c", "reachy mini 2") or a trailing "agent", then without spaces."""
    n = norm(name)
    out = [n]
    short = re.sub(r" (?:[0-9a-f]{1,2}|\d+)$", "", n)
    short = re.sub(r" agent$", "", short)
    if short and short != n:
        out.append(short)
    return out + [k.replace(" ", "") for k in out]


def load(path):
    try:
        with open(path) as f:
            roles = json.load(f).get("roles", [])
        return [r for r in roles if isinstance(r, dict) and r.get("role") and r.get("voice")]
    except (OSError, ValueError, AttributeError):
        return []


def find(name, roles):
    index = {}
    for r in roles:
        for label in [r["role"]] + list(r.get("aliases") or []):
            index.setdefault(norm(label), r)
            index.setdefault(norm(label).replace(" ", ""), r)
    for k in keys(name):
        if k in index:
            return index[k]
    return None


def learn(name, roles):
    """Least used pool voice (pool order breaks ties), remembered in the learned file."""
    lock = LEARNED_FILE + ".lock"
    os.makedirs(os.path.dirname(LEARNED_FILE), exist_ok=True)
    for _ in range(50):
        try:
            os.mkdir(lock); break
        except FileExistsError:
            if time.time() - os.stat(lock).st_mtime > 10:
                try: os.rmdir(lock)
                except OSError: pass
            time.sleep(0.05)
    try:
        learned = load(LEARNED_FILE)
        again = find(name, learned)          # another process may have learned it meanwhile
        if again:
            return again
        used = [r["voice"] for r in roles + learned]
        voice = min(POOL, key=lambda v: (used.count(v), POOL.index(v)))
        entry = {"role": norm(name), "aliases": [], "voice": voice, "learned": time.strftime("%Y-%m-%d")}
        learned.append(entry)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(LEARNED_FILE), prefix=".voices.")
        with os.fdopen(fd, "w") as f:
            json.dump({"roles": learned}, f, indent=2, ensure_ascii=False); f.write("\n")
        os.replace(tmp, LEARNED_FILE)
        return entry
    finally:
        try: os.rmdir(lock)
        except OSError: pass


def resolve(name):
    tracked = load(ROLES_FILE)
    role = find(name, tracked) or find(name, load(LEARNED_FILE))
    if role is None and POOL and norm(name):
        role = learn(name, tracked)
    return role


def display(role, lang):
    """Spoken name of a role in a language. A French voice reading "session tower here." is what
    Remi heard as a bad start of French messages (2026-09-25): roles may carry "role_fr". A learned
    entry filed under a tracked role's name (an extra alias) takes that role's French name."""
    if lang == "fr":
        fr = role.get("role_fr") or (find(role["role"], load(ROLES_FILE)) or {}).get("role_fr")
        if fr:
            return fr
    return role["role"]


def main(argv):
    if len(argv) >= 2 and argv[1] == "list":
        for r in load(ROLES_FILE) + load(LEARNED_FILE):
            print("%-30s %-16s %s" % (r["role"], r["voice"], ", ".join(r.get("aliases") or [])))
        return 0
    if len(argv) < 3 or argv[1] not in ("voice", "display"):
        print(__doc__); return 2
    role = resolve(argv[2])
    if role is None:
        return 1
    print(role["voice"] if argv[1] == "voice" else display(role, argv[3] if len(argv) > 3 else "en"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
