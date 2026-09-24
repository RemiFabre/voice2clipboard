"""Double press cancels a dictation: press arbitration, and the recovery command.
Run: python local_tests/test_cancel_dictation.py   (venv with the recorder's dependencies)"""
import os, subprocess, sys, tempfile
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "apps", "linux", "legacy_whisper"))
import voice_transcriber as vt

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name); fails += 0 if ok else 1

W = 0.7
a = vt.PressArbiter(window_s=W)
check("no press, no decision", a.decision(now=10.0) is None)
a.press("hangup", now=10.0)
check("one press: undecided inside the window", a.decision(now=10.0 + W - 0.05) is None)
check("one press: stop and send once the window closes", a.decision(now=10.0 + W + 0.01) == "stop")

a = vt.PressArbiter(window_s=W)
a.press("hangup", now=20.0); a.press("hangup", now=20.35)
check("two hang-ups inside the window: cancel, at once", a.decision(now=20.36) == "cancel")

a = vt.PressArbiter(window_s=W)
a.press("hangup", now=30.0); a.press("single", now=30.4)   # second press arrives as a media command
check("hang-up then a media press: cancel", a.decision(now=30.41) == "cancel")

a = vt.PressArbiter(window_s=W)
a.press("double", now=40.0)   # the headset classified the double press itself
check("a press already classified as double: cancel, no waiting", a.decision(now=40.0) == "cancel")

a = vt.PressArbiter(window_s=W)
a.press("hangup", now=50.0); a.press("hangup", now=50.02)  # the log repeats a line
check("the same press logged twice within 80 ms is one press", a.decision(now=50.1) is None and a.decision(now=50.8) == "stop")

a = vt.PressArbiter(window_s=0)
a.press("hangup", now=60.0)
check("window 0 disables the feature: immediate stop", a.decision(now=60.0) == "stop")
a = vt.PressArbiter(window_s=0)
a.press("double", now=70.0)
check("window 0: a press already classified as double still cancels", a.decision(now=70.0) == "cancel")
check("the default adds no delay to a normal stop", vt.DOUBLE_PRESS_WINDOW_S == 0)

# recovery command, on a synthetic recordings tree
rec = tempfile.mkdtemp()
def make(day, t, text, cancelled=True, recovered=False):
    d = os.path.join(rec, day, t); os.makedirs(d)
    open(os.path.join(d, "transcript.txt"), "w").write(text)
    if cancelled: open(os.path.join(d, "cancelled"), "w").write("double press\n")
    if recovered: open(os.path.join(d, "recovered"), "w").write("x")
    return d
make("2026-01-01", "09-00-00", "older cancelled message")
latest = make("2026-01-02", "10-00-00", "synthetic cancelled message number two")
make("2026-01-02", "11-00-00", "a delivered message", cancelled=False)
script = os.path.join(ROOT, "scripts", "mac", "secretary", "recover_cancelled.sh")
env = dict(os.environ, VOICE2CLIPBOARD_RECORDINGS_DIR=rec, SECRETARY_RUNTIME=tempfile.mkdtemp())
r = subprocess.run(["bash", script], capture_output=True, text=True, env=env)
check("prints the latest cancelled transcript", "synthetic cancelled message number two" in r.stdout and "delivered" not in r.stdout)
check("prints where it came from", latest in r.stdout)
check("marks it recovered", os.path.exists(os.path.join(latest, "recovered")))
r2 = subprocess.run(["bash", script], capture_output=True, text=True, env=env)
check("the next call goes back one more", "older cancelled message" in r2.stdout)
r3 = subprocess.run(["bash", script], capture_output=True, text=True, env=env)
check("nothing left: says so and exits 1", r3.returncode == 1 and "no cancelled" in r3.stdout.lower())
r4 = subprocess.run(["bash", script, "--list"], capture_output=True, text=True, env=env)
check("--list shows cancelled recordings without consuming them", "10-00-00" in r4.stdout and "09-00-00" in r4.stdout)

print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
