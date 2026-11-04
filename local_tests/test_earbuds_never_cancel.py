"""The earbuds never cancel a dictation (Remi, 2026-11-04): a press-and-hold is only the headset's
own volume step, and a volume change made on the Mac reaches the recorder as the same gain event.
Every press, single or double, stops and sends.
Fake audio stream and a fake Bluetooth log: no microphone, no sound, no paste, no real log stream.
Run: python local_tests/test_earbuds_never_cancel.py   (TEST_VT_DIR=<dir> tests an undeployed recorder)"""
import os, sys, tempfile, threading, time
import numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.environ.get("TEST_VT_DIR") or os.path.join(ROOT, "apps", "linux", "legacy_whisper"))
work = tempfile.mkdtemp(); os.chdir(work)
os.environ.update(VOICE2CLIPBOARD_PRESS_FILE=os.path.join(work, "press"), VOICE2CLIPBOARD_HEADSET_STOP="1",
                  VOICE2CLIPBOARD_STOP_REQUEST_FILE=os.path.join(work, "stop"), VOICE2CLIPBOARD_STREAMING="0",
                  VOICE2CLIPBOARD_AUDIO_STATE_FILE=os.path.join(work, "audio"), VOICE2CLIPBOARD_PHASE_FILE=os.path.join(work, "phase"),
                  VOICE2CLIPBOARD_ROTATION_DIR=os.path.join(work, "rotation"))
import voice_transcriber as vt

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name); fails += 0 if ok else 1

# --- the press decision
a = vt.PressArbiter()
check("no press, no decision", a.decision() is None)
a.press("hangup", now=10.0)
check("one press: stop", a.decision() == "stop")
for kind in ("double", "triple", "other"):
    a = vt.PressArbiter(); a.press(kind, now=20.0)
    check(f"a '{kind}' press: stop, not cancel", a.decision() == "stop")
a = vt.PressArbiter()
a.press("hangup", now=55.0, source="headset hang-up"); a.press("hangup", now=55.02, source="repeat")
a.press("single", now=55.3, source="press file (single)")
check("each counted press keeps its source (a repeated log line is not counted)",
      a.sources == ["headset hang-up", "press file (single)"] and a.count == 2)
check("no cancel switch is left", not hasattr(vt, "hold_cancels") and not hasattr(vt, "cancel_requested"))

# --- the whole path, with a fake Bluetooth log (device address is a placeholder)
GAIN = "2026-01-02 03:04:05.000 Df bluetoothd[1:2] [Server.Handsfree] Received speaker gain event from device 00:11:22:33:44:55, new gain is %d\n"
HANGUP = "2026-01-02 03:04:05.000 Df bluetoothd[1:2] [Server.Handsfree] Received call hangup event (AT+CHUP) from device 00:11:22:33:44:55\n"

class FakeInputStream:
    def __init__(self, samplerate, channels, callback):
        self.cb, self.ch, self.alive = callback, channels, False
    def __enter__(self):
        self.alive = True
        def feed():
            while self.alive:
                self.cb((np.random.randn(1600, self.ch) * 0.01).astype(np.float32), 1600, None, None); time.sleep(0.1)
        threading.Thread(target=feed, daemon=True).start(); return self
    def __exit__(self, *a):
        self.alive = False

class FakeLogStream:
    """Stands in for `log stream`: yields the scheduled lines, then idles until terminated."""
    def __init__(self, script):
        self.script, self.done, self.t0 = list(script), False, time.time()
        self.stdout = self._lines()
    def _lines(self):
        for at, line in self.script:
            while time.time() - self.t0 < at and not self.done:
                time.sleep(0.02)
            if self.done: return
            yield line
        while not self.done:
            time.sleep(0.05)
    def poll(self): return 0 if self.done else None
    def terminate(self): self.done = True

script = []
real_popen = vt.subprocess.Popen
def popen(cmd, *a, **k):
    if isinstance(cmd, list) and cmd and cmd[0] == "/usr/bin/log":
        return FakeLogStream(script)
    return real_popen(cmd, *a, **k)
vt.subprocess.Popen = popen

sent, logged = [], []
vt.sd.InputStream = FakeInputStream
vt.play_feedback = lambda *a, **k: None
vt.audio_callback = lambda *a, **k: None
vt.pyperclip.copy = lambda t: None
vt.handle_escape_during_recording = lambda: None
vt.confirm_headset_route = lambda *a, **k: None if hasattr(vt, "confirm_headset_route") else None
vt.transcribe_with_best_backend = lambda f: "synthetic dictated sentence"
vt.paste_at_cursor_and_send = lambda text, *a, **k: sent.append(text)
vt.secretary_log = logged.append

def run(lines, presses=()):
    script[:] = lines; sent.clear(); logged.clear()
    def presser():   # presses that reach the Mac as media commands (on_gesture.sh's press file)
        t0 = time.time()
        for kind, at in presses:
            time.sleep(max(0, at - (time.time() - t0)))
            with open(os.environ["VOICE2CLIPBOARD_PRESS_FILE"], "a") as f: f.write(kind + "\n")
    threading.Thread(target=presser, daemon=True).start()
    vt.press_arbiter = vt.PressArbiter()
    sys.argv = ["voice_transcriber.py", "--quick"]
    time.sleep(1.1)   # recordings folders are named by the second
    t0 = time.time(); vt.main()
    return os.path.dirname(vt.current_audio_path), time.time() - t0

VOLUME_ECHO = "2026-01-02 03:04:05.000 Df bluetoothd[1:2] [Server.Handsfree] Volume did update to 4\n"
folder, took = run([(1.5, VOLUME_ECHO), (1.6, GAIN % 4), (2.0, GAIN % 6), (2.5, GAIN % 3), (3.0, HANGUP)])
check("Mac volume echo and holds at 1.6-2.5 s: still recording, the press at 3 s stops it", took >= 2.9)
check("... and sends", sent == ["synthetic dictated sentence"] and not os.path.exists(os.path.join(folder, "cancelled")))

folder, took = run([(1.5, HANGUP)])
check("a single press stops and sends", sent == ["synthetic dictated sentence"] and not os.path.exists(os.path.join(folder, "cancelled")))

folder, took = run([], presses=[("double", 1.5)])
check("a double press that reaches the Mac stops and sends", sent == ["synthetic dictated sentence"] and not os.path.exists(os.path.join(folder, "cancelled")))

print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
