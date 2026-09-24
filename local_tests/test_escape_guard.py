"""An Escape key stops a headset dictation only when it was typed into the recorder's own window
(2026-09-23 10:23:49: an Escape aimed at another app stopped Remi's dictation mid-sentence; the
recorder's key listener sees every key event on the Mac). Frontmost window and mode are stubbed.
Run: python local_tests/test_escape_guard.py   (TEST_VT_DIR=<dir> tests an undeployed recorder)"""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.environ.get("TEST_VT_DIR") or os.path.join(ROOT, "apps", "linux", "legacy_whisper"))
import voice_transcriber as vt

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name); fails += 0 if ok else 1

calls = []
def front(front_app, current):
    def run(cmd, capture_output, text, timeout):
        calls.append(cmd)
        class R: pass
        r = R(); r.stdout = ("other:" + front_app) if front_app != "iTerm2" else current; r.returncode = 0
        return r
    vt.subprocess.run = run

os.environ["ITERM_SESSION_ID"] = "w0t0p0:RECORDER-WINDOW-ID"
check("own window id comes from the environment", vt.own_iterm_session_id() == "RECORDER-WINDOW-ID")

vt.VOICE_MODE = "headset"; vt.IS_MAC = True
front("Google Chrome", "")
check("default (Remi, 2026-09-23): Escape anywhere stops the dictation", vt.escape_counts())
os.environ["VOICE2CLIPBOARD_ESCAPE_ANYWHERE"] = "0"   # the window rule, kept for a day it is wanted
front("iTerm2", "RECORDER-WINDOW-ID")
check("headset mode, recorder window in front: Escape counts", vt.escape_counts())
front("iTerm2", "SOME-OTHER-ITERM-WINDOW")
check("headset mode, another iTerm window in front: ignored", not vt.escape_counts())
front("Google Chrome", "")
check("headset mode, a browser in front (the incident): ignored", not vt.escape_counts())
front("Finder", "")
check("headset mode, Finder in front: ignored", not vt.escape_counts())

def boom(*a, **k): raise RuntimeError("osascript failed")
vt.subprocess.run = boom
check("cannot tell who is in front: ignored (a lost dictation costs more)", not vt.escape_counts())
os.environ.pop("ITERM_SESSION_ID")
check("recorder without an iTerm window of its own: ignored", not vt.escape_counts())

vt.VOICE_MODE = "manual"
vt.subprocess.run = boom
os.environ.pop("VOICE2CLIPBOARD_ESCAPE_ANYWHERE")
check("manual mode keeps the old rule: Escape anywhere", vt.escape_counts())

print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
