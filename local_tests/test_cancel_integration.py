"""The recorder's whole cancel path, with a fake audio stream: no microphone, no sound, no paste.
Run: python local_tests/test_cancel_integration.py   (venv with the recorder's dependencies)"""
import os, sys, tempfile, threading, time
import numpy as np
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "apps", "linux", "legacy_whisper"))
work = tempfile.mkdtemp(); os.chdir(work)
os.environ.update(VOICE2CLIPBOARD_PRESS_FILE=os.path.join(work, "press"), VOICE2CLIPBOARD_HEADSET_STOP="0",
                  VOICE2CLIPBOARD_STOP_REQUEST_FILE=os.path.join(work, "stop"), VOICE2CLIPBOARD_STREAMING="0",
                  VOICE2CLIPBOARD_AUDIO_STATE_FILE=os.path.join(work, "audio"), VOICE2CLIPBOARD_PHASE_FILE=os.path.join(work, "phase"),
                  VOICE2CLIPBOARD_DOUBLE_PRESS_WINDOW_S="0.7")
import voice_transcriber as vt


class FakeInputStream:
    """Stands in for sounddevice.InputStream: feeds quiet noise to the callback from a thread."""
    def __init__(self, samplerate, channels, callback):
        self.cb, self.sr, self.ch, self.alive = callback, samplerate, channels, False
    def __enter__(self):
        self.alive = True
        def feed():
            while self.alive:
                self.cb((np.random.randn(1600, self.ch) * 0.01).astype(np.float32), 1600, None, None); time.sleep(0.1)
        threading.Thread(target=feed, daemon=True).start(); return self
    def __exit__(self, *a):
        self.alive = False


sent = []
vt.sd.InputStream = FakeInputStream
vt.play_feedback = lambda *a, **k: None
vt.audio_callback = lambda *a, **k: None
vt.pyperclip.copy = lambda t: None
vt.handle_escape_during_recording = lambda: None
vt.transcribe_with_best_backend = lambda f: "synthetic dictated sentence"
vt.paste_at_cursor_and_send = lambda text, *a, **k: sent.append(text)
vt.secretary_log = lambda m: None

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name); fails += 0 if ok else 1

def run(presses):
    """presses: [(kind, seconds after start)]; returns (folder, seconds from first press to the end of recording)."""
    vt.press_arbiter = vt.PressArbiter(vt.DOUBLE_PRESS_WINDOW_S); vt.cancel_requested = False; sent.clear()
    marks = {}
    def presser():
        t0 = time.time()
        for kind, at in presses:
            time.sleep(max(0, at - (time.time() - t0)))
            marks.setdefault("first", time.time())
            with open(os.environ["VOICE2CLIPBOARD_PRESS_FILE"], "a") as f: f.write(kind + "\n")
    orig = vt.request_recording_stop
    def stop(source=None): marks.setdefault("stopped", time.time()); orig(source)
    vt.request_recording_stop = stop
    sys.argv = ["voice_transcriber.py", "--quick"]
    time.sleep(1.1)   # recordings folders are named by the second
    threading.Thread(target=presser, daemon=True).start(); vt.main()
    vt.request_recording_stop = orig
    return os.path.dirname(vt.current_audio_path), marks["stopped"] - marks["first"]

folder, delay = run([("single", 1.0), ("single", 1.3)])
check("two presses: marked cancelled", os.path.exists(os.path.join(folder, "cancelled")))
check("two presses: nothing sent", sent == [])
check("two presses: text kept for recovery", open(os.path.join(folder, "transcript.txt")).read() == "synthetic dictated sentence")
check("two presses: audio kept", os.path.getsize(os.path.join(folder, "audio.wav")) > 1000)
check("two presses: decided at the second press, not at the end of the window (%.2f s)" % delay, delay < 0.55)

folder, delay = run([("single", 1.0)])
check("one press: sent", sent == ["synthetic dictated sentence"])
check("one press: not marked cancelled", not os.path.exists(os.path.join(folder, "cancelled")))
check("one press: stop waits for the window and no longer (%.2f s)" % delay, 0.65 <= delay <= 0.95)

vt.DOUBLE_PRESS_WINDOW_S = 0   # the shipped default
folder, delay = run([("single", 1.0)])
check("default window 0: one press stops at once (%.2f s) and sends" % delay, delay < 0.15 and sent == ["synthetic dictated sentence"])
folder, delay = run([("double", 1.0)])
check("default window 0: a classified double press still cancels", os.path.exists(os.path.join(folder, "cancelled")) and sent == [])

folder, delay = run([("double", 1.0)])
check("headset-classified double: cancelled at once (%.2f s)" % delay, os.path.exists(os.path.join(folder, "cancelled")) and delay < 0.2 and sent == [])

print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
