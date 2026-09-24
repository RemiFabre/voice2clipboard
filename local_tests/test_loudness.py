"""Every voice at the same speech level: speech_render.normalize on synthetic "speech" (bursts of
tone separated by pauses) at very different levels. No audio is played.
Run: python3 local_tests/test_loudness.py   (TEST_SEC=<dir> tests an undeployed speech_render.py)"""
import array, math, os, shutil, sys, tempfile, time, wave
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SEC = os.environ.get("TEST_SEC") or os.path.join(ROOT, "scripts", "mac", "secretary")
sys.path.insert(0, SEC); sys.path.insert(1, os.path.join(ROOT, "scripts", "mac", "secretary"))   # dictionary.py
import speech_render as sr

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name); fails += 0 if ok else 1

tmp = tempfile.mkdtemp(); RATE = 24000
def make(path, amp, seconds=4.0, crest=1.0):
    """0.4 s bursts of a 220 Hz tone with 0.3 s pauses; crest > 1 adds a short loud peak per burst."""
    a = array.array("h")
    for i in range(int(RATE * seconds)):
        t = i / RATE; in_burst = (t % 0.7) < 0.4
        v = amp * math.sin(2 * math.pi * 220 * t) if in_burst else 0.0
        if in_burst and (t % 0.7) < 0.004: v *= crest
        a.append(int(max(-1, min(1, v)) * 32767))
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(a.tobytes())
def read(path):
    with wave.open(path) as w:
        a = array.array("h"); a.frombytes(w.readframes(w.getnframes())); return a
def level(path): return sr.speech_level_dbfs(read(path), RATE)
def peak(path): return max(abs(x) for x in read(path)) / 32768.0

quiet, normal, loud = (os.path.join(tmp, n) for n in ("quiet.wav", "normal.wav", "loud.wav"))
make(quiet, 0.05); make(normal, 0.14); make(loud, 0.5)
before = [level(p) for p in (quiet, normal, loud)]
check("the test voices really differ (%.0f dB apart)" % (max(before) - min(before)), max(before) - min(before) > 15)
for p in (quiet, normal, loud): sr.normalize(p)
after = [level(p) for p in (quiet, normal, loud)]
check("after: all within 1 dB of the target (%s)" % ", ".join("%.1f" % x for x in after), all(abs(x - sr.TARGET_DBFS) < 1.0 for x in after))
check("pauses stay silent", min(abs(x) for x in read(quiet)) == 0)

peaky = os.path.join(tmp, "peaky.wav"); make(peaky, 0.06, crest=9.0)
sr.normalize(peaky)
check("a quiet voice with sharp peaks is raised without clipping (peak %.2f)" % peak(peaky), peak(peaky) <= 0.985 and abs(level(peaky) - sr.TARGET_DBFS) < 1.5)

silent = os.path.join(tmp, "silent.wav"); make(silent, 0.0)
check("silence is left alone", sr.normalize(silent) == 0.0)
twice = os.path.join(tmp, "twice.wav"); make(twice, 0.05); sr.normalize(twice)
check("normalising twice changes nothing more", sr.normalize(twice) == 0.0)

long = os.path.join(tmp, "long.wav"); make(long, 0.05, seconds=60)
t0 = time.time(); sr.normalize(long); took = time.time() - t0
check("a one minute message takes under 3 s (%.1f s)" % took, took < 3.0)

shutil.rmtree(tmp)
print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
