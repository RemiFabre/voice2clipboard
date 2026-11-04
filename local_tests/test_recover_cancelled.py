"""The recovery command for cancelled dictations (closing the recorder window cancels one).
Run: python local_tests/test_recover_cancelled.py   (venv with the recorder's dependencies)"""
import os, subprocess, sys, tempfile
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name); fails += 0 if ok else 1

# recovery command, on a synthetic recordings tree
rec = tempfile.mkdtemp()
def make(day, t, text, cancelled=True, recovered=False):
    d = os.path.join(rec, day, t); os.makedirs(d)
    open(os.path.join(d, "transcript.txt"), "w").write(text)
    if cancelled: open(os.path.join(d, "cancelled"), "w").write("recorder window closed\n")
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
