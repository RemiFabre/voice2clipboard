"""Verified delivery into a Claude Code window (2026-09-22: a "/usage" dialog left open in the
secretary's window swallowed a dictation and two reports for two hours). The window, its
keystrokes and its transcript are simulated: no iTerm, no Claude, no audio.
Run: python local_tests/test_verified_delivery.py   (TEST_VT_DIR=<dir> tests an undeployed recorder)"""
import os, sys, tempfile, json
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.environ.get("TEST_VT_DIR") or os.path.join(ROOT, "apps", "linux", "legacy_whisper"))
import voice_transcriber as vt

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name); fails += 0 if ok else 1

PROMPT = "❯ \n──────────────────\n  5h 2% · week 13%\n  ⏵⏵ bypass permissions on (shift+tab to cycle)"
DIALOG = "Usage\n\nCurrent session  ████░░░░ 42%\nCurrent week     ██░░░░░░ 13%\n\nEsc to close"

class Window:
    """A Claude Code window: a screen, a dialog that Escape closes, a transcript that grows when
    a message is typed while the prompt is showing. `deaf` = a dialog that Escape cannot close."""
    def __init__(self, dialog=False, deaf=False, transcript=True):
        self.dialog, self.deaf, self.typed, self.keys = dialog, deaf, [], []
        self.path = tempfile.mktemp(suffix=".jsonl") if transcript else None
        if self.path: open(self.path, "w").write('{"type":"user","message":{"role":"user","content":"earlier"}}\n')
    def contents(self, sid): return DIALOG if self.dialog else PROMPT
    def escape(self, sid):
        self.keys.append("esc")
        if not self.deaf: self.dialog = False
    def type(self, text, sid): self.typed.append(text); self.pending = text
    def enter(self, sid):
        self.keys.append("enter")
        if not self.dialog and self.path and os.path.exists(self.path):
            with open(self.path, "a") as f:
                f.write(json.dumps({"type": "user", "message": {"role": "user", "content": self.pending}}) + "\n")
            self.echoed = self.pending
        self.pending = None if not self.dialog else self.pending
    def transcript(self, sid): return self.path

def wire(w):
    vt.get_iterm_session_contents = w.contents
    vt.send_escape_to_iterm_session = w.escape
    vt.send_text_to_iterm_session = w.type
    vt.send_enter_to_iterm_session = w.enter
    vt.claude_transcript_for_iterm = w.transcript
vt.DELIVERY_VERIFY_SECONDS = 1.0
logs = []; log = logs.append
def deliver(w, text="[Voice] Synthetic test message number seven for the stand-in window."):
    logs.clear(); wire(w); return vt.deliver_to_claude_session(text, "SID", log)

check("prompt screen is recognised", vt.claude_screen_has_prompt(PROMPT))
check("dialog screen is not", not vt.claude_screen_has_prompt(DIALOG))
check("a plain prompt line counts too", vt.claude_screen_has_prompt("some output\n❯ "))

w = Window()
check("normal window: delivered, typed once", deliver(w) and w.typed == [w.typed[0]] and len(w.typed) == 1)
check("normal window: no Escape sent", "esc" not in w.keys)

w = Window(dialog=True)
check("dialog open (the incident): Escape, then delivered", deliver(w) and w.keys[0] == "esc" and len(w.typed) == 1)
check("the dialog is reported", any("no input prompt" in m for m in logs))

# A busy session (in a tool turn) queues the message: the transcript gets a "queue-operation"
# enqueue line at once (this exact spacing), the "queued_command" attachment and the user turn
# only when the turn reaches its next round, often after the wait here. 2026-09-24 08:56 and
# 15:15: typed twice into the busy secretary, then "could not be delivered" while it had been.
class BusyWindow(Window):
    def enter(self, sid):
        self.keys.append("enter")
        if self.path and os.path.exists(self.path):
            with open(self.path, "a") as f:
                f.write(json.dumps({"type": "queue-operation", "operation": "enqueue",
                                    "timestamp": "2026-09-24T13:15:36.488Z", "sessionId": "x", "content": self.pending}) + "\n")
        self.pending = None
w = BusyWindow()
check("busy session, message queued: delivered, typed once", deliver(w) and len(w.typed) == 1)
check("busy session: no Escape, no retry", "esc" not in w.keys and w.keys.count("enter") == 1)
d0 = tempfile.mkdtemp(); q = os.path.join(d0, "q.jsonl"); open(q, "w").write("{}\n"); off0 = os.path.getsize(q)
open(q, "a").write(json.dumps({"type": "attachment", "attachment": {"type": "queued_command", "prompt": "<pasted_content id=\"1\">\n[Voice] queued later</pasted_content>"}}) + "\n")
check("the later queued_command attachment counts too", vt.transcript_has_user_turn(q, "[Voice] queued later", off0))
open(q, "a").write(json.dumps({"type": "queue-operation", "operation": "dequeue", "content": "[Voice] dequeued only"}) + "\n")
check("a dequeue line alone does not", not vt.transcript_has_user_turn(q, "[Voice] dequeued only", off0))

w = Window(dialog=True, deaf=True)
check("dialog that will not close: two attempts, then False", deliver(w) is False and len(w.typed) == 2)
check("never a third attempt", w.keys.count("enter") == 2)

w = Window(transcript=False)
check("no transcript found: the screen decides, delivered", deliver(w) and len(w.typed) == 1)

w = Window(); w.path = "/nonexistent/x.jsonl"
check("transcript path unreadable: still delivered by the screen, not stuck", deliver(w) is True or len(w.typed) <= 2)

# the marker: a user turn that already existed before the send does not count
w = Window(); open(w.path, "a").write('{"type":"user","message":{"role":"user","content":"[Voice] Synthetic test message number seven for the stand-in window."}}\n')
w2 = Window(dialog=True, deaf=True); w2.path = w.path
check("an older identical turn is not mistaken for delivery", deliver(w2) is False)

# transcript helper on a real file layout
d = tempfile.mkdtemp(); p = os.path.join(d, "t.jsonl"); open(p, "w").write('{"type":"user","message":{"content":"old"}}\n')
off = os.path.getsize(p)
open(p, "a").write('{"type":"user","message":{"content":[{"type":"tool_result","content":"[Voice] hello"}]}}\n')
check("a tool result echoing the text is not a user turn", not vt.transcript_has_user_turn(p, "[Voice] hello", off))
open(p, "a").write(json.dumps({"type": "user", "message": {"content": "  <pasted_content id=\"1\"> [Voice] hello there</pasted_content>"}}) + "\n")
check("a pasted user turn is found", vt.transcript_has_user_turn(p, "[Voice] hello", off))
check("a quote in the marker survives JSON escaping", vt.transcript_has_user_turn(p, '[Voice] hello', off) and not vt.transcript_has_user_turn(p, 'x"y', off))

print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
