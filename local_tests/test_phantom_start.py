"""A dictation that nobody ended and that holds no speech plays no cue, deletes nothing, and is
reported to Remi by a queued note (his rule: never lose data, never decide silently): putting an earbud
into its charger makes the headset send "pause", which starts a dictation exactly like a press.
No audio, no microphone: the recorder's functions are called directly with stubs.
Run: python local_tests/test_phantom_start.py   (TEST_VT_DIR=<dir> tests an undeployed recorder)"""
import os, sys, tempfile
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.environ.get("TEST_VT_DIR") or os.path.join(ROOT, "apps", "linux", "legacy_whisper"))
import voice_transcriber as vt

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name); fails += 0 if ok else 1

played, notes, logged = [], [], []
vt.play_feedback = lambda name, *a, **k: played.append(name)
vt.notify_secretary_inbox = notes.append
vt.secretary_log = logged.append
vt.audio_is_effectively_silent = lambda f: True          # "no speech" without any model
vt.IS_MAC = True
d = tempfile.mkdtemp()
vt.current_transcript_path = os.path.join(d, "transcript.txt"); vt.current_stats_path = os.path.join(d, "stats.json")
vt.current_audio_path = os.path.join(d, "audio.wav")

def run(mode, stop_source, seconds):
    played.clear(); notes.clear(); logged.clear()
    vt.VOICE_MODE = mode; vt.quick_stop_source = stop_source; vt.duration_sec = seconds
    return vt.transcribe_audio(vt.current_audio_path)

# the decision
vt.VOICE_MODE = "headset"
check("ended by silence, lost input or a vanished headset: nobody ended it", all(vt.phantom_start(s) for s in ("silence", "input_lost", "headset:disconnected")))
check("ended by a press, the keyboard or a cancel: somebody did", not any(vt.phantom_start(s) for s in ("press:stop", "hold:cancel", "external_stop", "escape", None)))
vt.VOICE_MODE = "manual"
check("outside headset mode nothing is a phantom", not vt.phantom_start("silence"))

# the phantom: 75 s, stopped by the silence rule, no speech
text = run("headset", "silence", 75.0)
check("phantom: nothing sent", text == "")
check("phantom: not a single sound", played == [])
check("phantom: he is told, with the time and that the audio is kept", len(notes) == 1 and "audio is kept" in notes[0] and "charger" in notes[0])
check("phantom: one log line says why", any("phantom start" in m for m in logged))
check("phantom: the explicit no-speech transcript is still written", os.path.exists(vt.current_transcript_path))
text = run("headset", "headset:disconnected", 9.0)
check("phantom cut short by the headset going away: no cue, one note", played == [] and len(notes) == 1)

# unchanged: he pressed to stop and there was no speech -> he must be told
run("headset", "press:stop", 40.0)
check("he pressed stop after 40 s of nothing: failure sound and a note, as before", "record_lost" in played and len(notes) == 1)
run("headset", "press:stop", 8.0)
check("he pressed stop within 15 s: the cancel sound, no note, as before", "record_cancel" in played and notes == [])
run("manual", "silence", 75.0)
check("manual mode keeps its sounds", "transcribe_start" in played)

# the silence tracker knows whether it ever heard anything
t = vt.SilenceTracker(0.002, 60)
for s in range(0, 61): tripped = t.update(0.0003, now=float(s))
check("docked microphone: trips after 60 s and never heard a sound", tripped and not t.heard_sound)
t = vt.SilenceTracker(0.002, 60); t.update(0.02, now=0.0)
for s in range(1, 62): tripped = t.update(0.0003, now=float(s))
check("speech then silence: trips and did hear sound", tripped and t.heard_sound)

print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
