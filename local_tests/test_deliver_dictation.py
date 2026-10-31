"""Remi's dictations handed verbatim to the session they are for (2026-10-31): only the recorder's
own fresh transcript is ever typed, once per session, into a live Claude window showing its prompt,
never into a shell, a dialog or the secretary. Fake recordings, fake session table, simulated
window: no iTerm, no Claude, no audio.
Run: ~/.virtualenvs/voice2clipboard/bin/python local_tests/test_deliver_dictation.py"""
import io, json, os, subprocess, sys, tempfile, time
from contextlib import redirect_stderr, redirect_stdout
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TMP = tempfile.mkdtemp()
os.environ.update(VOICE2CLIPBOARD_RECORDINGS_DIR=f"{TMP}/recordings", SECRETARY_RUNTIME=f"{TMP}/runtime",
                  CLAUDE_SESSIONS_DIR=f"{TMP}/sessions", SECRETARY_DICTATION_PROMPT_WAIT_S="1")
for d in ("recordings", "runtime", "sessions"):
    os.makedirs(f"{TMP}/{d}")
sys.path.insert(0, os.path.join(ROOT, "scripts", "mac", "secretary"))
import deliver_dictation as dd

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name); fails += 0 if ok else 1

def recording(rid, text, age_s=30, sent="iterm_session\nsend_id=x\n", audio=True):
    folder = f"{TMP}/recordings/{rid}"; os.makedirs(folder, exist_ok=True)
    open(f"{folder}/transcript.txt", "w").write(text)
    if sent is not None: open(f"{folder}/.sent", "w").write(sent)
    if audio: open(f"{folder}/audio.wav", "w").write("x")
    t = time.time() - age_s; os.utime(f"{folder}/transcript.txt", (t, t))
    return folder

live = subprocess.Popen(["sleep", "300"])
def session(name, pid=None, cwd="/Users/remi/agentic-socials"):
    json.dump({"pid": pid or live.pid, "name": name, "cwd": cwd}, open(f"{TMP}/sessions/{pid or live.pid}-{name}.json", "w"))

# the simulated window
class Window:
    def __init__(self): self.reset()
    def reset(self, claude=True, prompt=True, takes=True, iterm="W1"):
        self.claude, self.prompt, self.takes, self.iterm, self.typed, self.escapes = claude, prompt, takes, iterm, [], 0
win = Window()
dd.tty_of = lambda pid: "/dev/ttys042"
dd.iterm_session_for_tty = lambda tty: win.iterm
dd.vt.iterm_session_runs_claude = lambda sid: win.claude
dd.vt.claude_input_ready = lambda sid: win.prompt
dd.vt.apply_word_dictionary = lambda text: text.replace("reachy many", "Reachy Mini")
def deliver(text, sid, log=None):
    win.typed.append(text); return win.takes
dd.vt.deliver_to_claude_session = deliver

def run(*args):
    sys.argv = ["deliver_dictation.py", *args]; out, err = io.StringIO(), io.StringIO()
    code = 0
    with redirect_stdout(out), redirect_stderr(err):
        try: dd.main()
        except SystemExit as e: code = e.code or 0
    return code, out.getvalue() + err.getvalue()

session("agentic-socials-c9")
session("secretary-53", cwd="/Users/remi/voice2clipboard/secretary")
A = recording("2026-10-31/16-51-02", "Tell the socials agent to switch off the ads on reachy many episode three.")

# 1. the normal case: verbatim, with the header, logged, once
code, out = run("--to", "agentic-socials-c9")
check("delivered (exit 0)", code == 0 and "delivered 2026-10-31/16-51-02" in out)
check("typed: the header, then his words verbatim (dictionary applied)",
      win.typed == ["[Dictated by Remi at 16:51, routed here by the secretary] Tell the socials agent to switch off the ads on Reachy Mini episode three."])
check("recorded in the dictation's folder and the delivery log",
      open(f"{A}/.forwarded").read().startswith("agentic-socials-c9\t") and "-> agentic-socials-c9" in open(f"{TMP}/runtime/dictation_deliveries.log").read())
win.reset(); code, out = run("--to", "agentic-socials-c9")
check("never twice to the same session", code == 2 and win.typed == [])
check("--list shows it and where it went", "agentic-socials-c9" in run("--list")[1])

# 2. nothing but a recorder transcript can be typed
check("no text argument exists", run("--to", "agentic-socials-c9", "do something else")[0] == 2)
check("an id that is not a recording id is refused", run("--to", "agentic-socials-c9", "--id", "../../etc/passwd")[0] == 2)
check("a strange session name is refused", run("--to", "a; rm -rf ~")[0] == 2)
win.reset(); session("other-agent-1")
recording("2026-10-31/15-00-00", "old words", age_s=2000)
check("a dictation older than the limit is refused", run("--to", "other-agent-1", "--id", "2026-10-31/15-00-00")[0] == 2 and win.typed == [])
recording("2026-10-31/16-52-00", "clipboard only", sent="clipboard\n")
check("a dictation never routed (clipboard only) is refused", run("--to", "other-agent-1", "--id", "2026-10-31/16-52-00")[0] == 2)
recording("2026-10-31/16-53-00", "no audio beside it", audio=False)
check("a transcript without its audio is refused", run("--to", "other-agent-1", "--id", "2026-10-31/16-53-00")[0] == 2)
os.makedirs(f"{TMP}/recordings/2026-10-31/16-54-00"); open(f"{TMP}/recordings/2026-10-31/16-54-00/transcript.txt", "w").write("hand made")
check("a folder without the recorder's .sent marker is refused", run("--to", "other-agent-1", "--id", "2026-10-31/16-54-00")[0] == 2)

# 3. two fresh dictations: the secretary must name one
B = recording("2026-10-31/16-55-00", "Second dictation.")
win.reset(); code, out = run("--to", "other-agent-1")
check("two fresh dictations and no --id: refused, both listed", code == 2 and "16-51-02" in out and "16-55-00" in out and win.typed == [])
code, out = run("--to", "other-agent-1", "--id", "2026-10-31/16-55-00")
check("with --id: that one", code == 0 and win.typed[-1].endswith("Second dictation."))
win.reset(); code, out = run("--to", "other-agent-1", "--id", "2026-10-31/16-51-02")
check("one dictation may go to a second session (he spoke to two agents)", code == 0)

# 4. only a live Claude window showing its prompt, never the secretary
win.reset(); check("no such session", run("--to", "nobody-here", "--id", "2026-10-31/16-55-00")[0] == 3)
session("dead-agent-2", pid=999999); check("a dead session", run("--to", "dead-agent-2", "--id", "2026-10-31/16-55-00")[0] == 3)
check("never the secretary by name", run("--to", "secretary-53", "--id", "2026-10-31/16-55-00")[0] == 3)
session("renamed-sec", cwd="/Users/remi/voice2clipboard/secretary")
check("never the secretary by its folder", run("--to", "renamed-sec", "--id", "2026-10-31/16-55-00")[0] == 3)
session("shell-agent-3"); win.reset(claude=False)
check("a window whose foreground is a shell: nothing typed", run("--to", "shell-agent-3", "--id", "2026-10-31/16-55-00")[0] == 3 and win.typed == [])
session("dialog-agent-4"); win.reset(prompt=False)
check("a window with a dialog that stays open: nothing typed", run("--to", "dialog-agent-4", "--id", "2026-10-31/16-55-00")[0] == 3 and win.typed == [])
ready_at = time.time() + 0.5; dd.vt.claude_input_ready = lambda sid: time.time() > ready_at
check("a dialog that closes within the wait: delivered", run("--to", "dialog-agent-4", "--id", "2026-10-31/16-55-00")[0] == 0)
dd.vt.claude_input_ready = lambda sid: win.prompt
session("lost-agent-5"); win.reset(iterm="")
check("no iTerm window found: refused", run("--to", "lost-agent-5", "--id", "2026-10-31/16-55-00")[0] == 3)
check("the recorder's Escape is switched off here", dd.vt.send_escape_to_iterm_session("W1") is None)

# 5. typed but not seen taken: said so, and not offered again
session("busy-agent-6"); win.reset(takes=False)
code, out = run("--to", "busy-agent-6", "--id", "2026-10-31/16-55-00")
check("not seen taken: exit 4, recorded as such", code == 4 and "busy-agent-6\t" in open(f"{B}/.forwarded").read())
check("every refusal is logged", open(f"{TMP}/runtime/dictation_deliveries.log").read().count("refused:") >= 10)

live.kill()
print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
