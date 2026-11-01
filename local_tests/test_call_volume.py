"""Cues in call mode as loud as the media (Remi, 2026-11-01): while the microphone is open the
headset is a separate audio device with its own volume, so the recorder copies the media volume to
it. osascript is simulated: nothing is read from or set on the real output.
Run: ~/.virtualenvs/voice2clipboard/bin/python local_tests/test_call_volume.py   (TEST_VT=<file> tests a staged copy)"""
import importlib.util, os, sys, time, types
from importlib.machinery import SourceFileLoader
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src = os.environ.get("TEST_VT") or os.path.join(ROOT, "apps", "linux", "legacy_whisper", "voice_transcriber.py")
sys.path.insert(0, os.path.join(ROOT, "apps", "linux", "legacy_whisper"))
spec = importlib.util.spec_from_loader("vt", SourceFileLoader("vt", src))
vt = importlib.util.module_from_spec(spec); spec.loader.exec_module(vt)

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name); fails += 0 if ok else 1

calls, logs = [], []
def fake_run(cmd, *a, **k):
    calls.append(cmd[-1]); return types.SimpleNamespace(stdout=fake_run.settings, returncode=0)
vt.subprocess.run = fake_run
vt.secretary_log = logs.append
vt.CALL_VOLUME_AT_S = (0.05, 0.1)
vt.IS_MAC = True

def go(settings, recording=True, wait=0.4):
    calls.clear(); logs.clear(); fake_run.settings = settings; vt.recording = recording
    vt.match_call_volume(); time.sleep(wait)

go("output volume:19, input volume:100, alert volume:100, output muted:false")
check("the media volume is read first, then given to the call link, twice",
      calls == ["get volume settings", "set volume output volume 19", "set volume output volume 19"])
check("logged once", logs == ["call mode volume set to the media volume (19 %)"])
go("output volume:0, input volume:100, alert volume:100, output muted:true")
check("a muted output is never unmuted or raised here", calls == ["get volume settings"])
go("output volume:40, input volume:100, alert volume:100, output muted:false", recording=False)
check("a recording already over: nothing set", calls == ["get volume settings"])
go("garbage")
check("an unreadable answer: nothing set", calls == ["get volume settings"])
t = time.time(); vt.recording = True; fake_run.settings = "output volume:19, output muted:false"; vt.match_call_volume()
check("never blocks the start of the recording", time.time() - t < 0.05)
time.sleep(0.3)
vt.MATCH_CALL_VOLUME = False; calls.clear(); vt.match_call_volume(); time.sleep(0.2)
check("can be switched off (VOICE2CLIPBOARD_MATCH_CALL_VOLUME=0)", calls == [])
print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
