"""Press-and-hold on the headset cancels a dictation (the headset keeps a double press to itself
in call mode, so it is the only cancel gesture that can reach the Mac).
Fake audio stream and a fake Bluetooth log: no microphone, no sound, no paste, no real log stream.
Run: python local_tests/test_hold_cancel.py   (TEST_VT_DIR=<dir> tests an undeployed recorder)"""
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

# --- the decision itself
check("a hold after the first second cancels", vt.hold_cancels("gain_up", started_at=100.0, now=103.0))
check("volume down and an unknown direction cancel too", vt.hold_cancels("gain_down", 100.0, 103.0) and vt.hold_cancels("gain_change", 100.0, 103.0))
check("a gain report in the first second is ignored", not vt.hold_cancels("gain_change", 100.0, 100.4))
check("before the stream is open nothing cancels", not vt.hold_cancels("gain_up", None, 103.0))
check("a hang-up is not a hold", not vt.hold_cancels("hangup", 100.0, 103.0))
vt.HOLD_CANCELS = False
check("the switch turns it off", not vt.hold_cancels("gain_up", 100.0, 103.0))
vt.HOLD_CANCELS = True

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

def run(lines):
    script[:] = lines; sent.clear(); logged.clear()
    vt.press_arbiter = vt.PressArbiter(vt.DOUBLE_PRESS_WINDOW_S); vt.cancel_requested = False
    sys.argv = ["voice_transcriber.py", "--quick"]
    time.sleep(1.1)   # recordings folders are named by the second
    t0 = time.time(); vt.main()
    return os.path.dirname(vt.current_audio_path), time.time() - t0

folder, took = run([(2.0, GAIN % 9)])
check("hold at 2 s: marked cancelled", os.path.exists(os.path.join(folder, "cancelled")))
check("hold at 2 s: nothing sent", sent == [])
check("hold at 2 s: text kept for recovery", open(os.path.join(folder, "transcript.txt")).read() == "synthetic dictated sentence")
check("hold at 2 s: audio kept", os.path.getsize(os.path.join(folder, "audio.wav")) > 1000)
check("hold at 2 s: logged as a cancel", any("press-and-hold" in m and "cancelled" in m for m in logged))

folder, took = run([(0.3, GAIN % 9), (2.0, HANGUP)])
check("gain report at 0.3 s is ignored, the later press stops and sends", sent == ["synthetic dictated sentence"] and not os.path.exists(os.path.join(folder, "cancelled")))

folder, took = run([(1.5, HANGUP)])
check("a single press still stops and sends", sent == ["synthetic dictated sentence"] and not os.path.exists(os.path.join(folder, "cancelled")))

print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
