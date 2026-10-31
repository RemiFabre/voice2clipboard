"""A paste into the frontmost app that fails goes to the secretary instead of being lost
(2026-10-31: the Session Tower's process is "SessionTower" but its app name is "Session Tower", so
`tell application "SessionTower" to activate` failed and the dictation vanished). No iTerm, no
keystrokes, no audio: osascript and the secretary window are simulated.
Run: ~/.virtualenvs/voice2clipboard/bin/python local_tests/test_paste_fallback.py   (TEST_VT=<file> tests a staged copy)"""
import importlib.util, os, subprocess, sys, tempfile
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TMP = tempfile.mkdtemp()
os.environ["SECRETARY_SESSION_FILE"] = f"{TMP}/secretary_iterm_session"
src = os.environ.get("TEST_VT") or os.path.join(ROOT, "apps", "linux", "legacy_whisper", "voice_transcriber.py")
sys.path.insert(0, os.path.join(ROOT, "apps", "linux", "legacy_whisper"))
from importlib.machinery import SourceFileLoader
spec = importlib.util.spec_from_loader("vt", SourceFileLoader("vt", src))
vt = importlib.util.module_from_spec(spec); spec.loader.exec_module(vt)

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name); fails += 0 if ok else 1

scripts, typed = [], []
def osascript(cmd, *a, **k):
    scripts.append(cmd[-1])
    if osascript.fail: raise subprocess.CalledProcessError(1, cmd)
vt.subprocess.check_call = osascript
vt.pyperclip.copy = lambda t: None
vt.secretary_log = lambda m: None
vt.play_feedback = lambda *a: None
vt.iterm_session_runs_claude = lambda sid: sid == "SEC"
vt.deliver_to_claude_session = lambda text, sid, log=None: typed.append((sid, text)) or True
vt.QUICK_SEND_TRACE_PATH = f"{TMP}/trace.jsonl"

def dictate(n, fail, secretary):
    folder = f"{TMP}/rec{n}"; os.makedirs(folder)
    vt.current_audio_path = f"{folder}/audio.wav"; vt.current_transcript_path = f"{folder}/transcript.txt"
    if secretary: open(os.environ["SECRETARY_SESSION_FILE"], "w").write("SEC")
    elif os.path.exists(os.environ["SECRETARY_SESSION_FILE"]): os.remove(os.environ["SECRETARY_SESSION_FILE"])
    osascript.fail = fail; scripts.clear(); typed.clear(); raised = False
    try: vt.paste_at_cursor_and_send("Keep the question and the shake.", target_window="SessionTower")
    except Exception: raised = True
    marker = open(f"{folder}/.sent").read() if os.path.exists(f"{folder}/.sent") else ""
    return raised, marker

raised, marker = dictate(1, fail=False, secretary=True)
check("the app is raised by its process name, never `tell application <process name>`",
      'set frontmost of process "SessionTower" to true' in scripts[0] and 'tell application "SessionTower"' not in scripts[0])
check("a disabled Paste item (no text box focused) fails the paste instead of vanishing",
      'if not (enabled of menu item "Paste" of menu "Edit" of menu bar 1) then error' in scripts[0])
check("a working paste: pasted, nothing sent to the secretary", not raised and marker.startswith("clipboard_paste") and typed == [])
raised, marker = dictate(2, fail=True, secretary=True)
check("a failed paste goes to the secretary, his words verbatim after a note",
      not raised and len(typed) == 1 and typed[0][0] == "SEC" and typed[0][1].startswith("[Voice] (The recorder could not paste")
      and typed[0][1].endswith("Keep the question and the shake."))
check("marked as routed to the secretary, so it can be handed on", marker.startswith("iterm_session") and "fallback_from=SessionTower" in marker)
raised, marker = dictate(3, fail=True, secretary=False)
check("no secretary: the failure is raised as before (text stays in the clipboard)", raised and typed == [])
print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
