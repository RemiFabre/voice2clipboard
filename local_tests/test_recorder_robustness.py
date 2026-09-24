"""Recorder robustness: headset disconnect lines, sustained near-silence, empty transcription.
Run: python local_tests/test_recorder_robustness.py   (venv with the recorder's dependencies)"""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "linux", "legacy_whisper"))
import voice_transcriber as vt

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name)
    fails += 0 if ok else 1

# Bluetooth log lines (device address is a placeholder)
ev = vt.headset_event_from_log_line
check("hang-up still detected", ev("[Server.Handsfree] Received call hangup event (AT+CHUP) from device 00:11:22:33:44:55") == "hangup")
check("hands-free disconnection detected", ev("[Server.Handsfree] Received handsfree disconnection event for device 00:11:22:33:44:55 with result 708") == "disconnected")
check("device handle disconnected detected", ev("[Server.Handsfree] Handsfree device handle 16 disconnected with status 708") == "disconnected")
check("audio link up detected", ev("[Server.Handsfree] Received voice audio connected event for device 00:11:22:33:44:55") == "audio_connected")
check("an unknown call command is noticed", vt.headset_other_command("[Server.Handsfree] Received call hold event (AT+CHLD) from device 00:11:22:33:44:55") == "call hold event (AT+CHLD)")
check("hang-up is not an unknown command", vt.headset_other_command("[Server.Handsfree] Received call hangup event (AT+CHUP) from device 00:11:22:33:44:55") is None)
check("volume is not an unknown command", vt.headset_other_command("[Server.Handsfree] Received speaker gain event from device 00:11:22:33:44:55, new gain is 9") is None)
check("unrelated line ignored", ev("[Server.Handsfree] calculateSleepIntervalInUs codec type:2") is None)

# Sustained near-silence: a run of quiet blocks longer than the limit trips, speech resets it
t = vt.SilenceTracker(rms_threshold=0.002, limit_seconds=60)
check("quiet for 59 s does not trip", not any(t.update(0.0003, now=float(s)) for s in range(0, 60)))
check("quiet for 61 s trips", t.update(0.0003, now=61.0))
t = vt.SilenceTracker(rms_threshold=0.002, limit_seconds=60)
for s in range(0, 50): t.update(0.0003, now=float(s))
t.update(0.05, now=50.0)
check("speech resets the run", not any(t.update(0.0003, now=float(s)) for s in range(51, 105)))
check("disabled tracker never trips", not vt.SilenceTracker(0.002, 0).update(0.0, now=9999.0))

# Log timestamps
check("log timestamp parsed", abs(vt.parse_log_timestamp("2026-01-02 03:04:05.250 Df bluetoothd") - vt.parse_log_timestamp("2026-01-02 03:04:05.000 Df x") - 0.25) < 1e-6)

# Empty transcription leaves an explicit transcript and stats instead of a crash
d = tempfile.mkdtemp()
vt.current_transcript_path = os.path.join(d, "transcript.txt"); vt.current_stats_path = os.path.join(d, "stats.json")
vt.current_audio_path = os.path.join(d, "audio.wav"); vt.duration_sec = 12.0
vt.write_no_speech_result("no speech detected")
check("explicit transcript written", "no speech detected" in open(vt.current_transcript_path).read())
check("stats mark no speech", '"no_speech": true' in open(vt.current_stats_path).read())

# Headset input check
check("headset input matches", vt.input_is_headset("OpenFit 2+ by Shokz"))
check("built-in mic is not the headset", not vt.input_is_headset("MacBook Pro Microphone"))

print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
