"""The MLX helper drops Whisper repetition loops inside a window (2026-10-12: "I think" x111 and
"run" x223 came out of a two-minute pause and a 3 s pause that VAD let through; Whisper's own
fallback is skipped when no_speech_prob is high). No model, no audio: the decoder is a stand-in.
Run: /Users/remi/.virtualenvs/voice2clipboard/bin/python local_tests/test_helper_loop_filter.py"""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import numpy as np
import mlx_whisper_helper as h

fails = 0
def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name); fails += 0 if ok else 1

def seg(text, cr=1.4, nsp=0.0, lp=-0.3):
    return {"text": text, "compression_ratio": cr, "no_speech_prob": nsp, "avg_logprob": lp, "start": 0, "end": 1}

normal = "the first object should be the small box and the second one the lamp"
loop_i_think = " ".join(["I think"] * 111)
loop_run = " ".join(["run"] * 223)

check("a plain phrase is not a loop", not h.is_loop_text(normal))
check("a word said three times is not a loop", not h.is_loop_text("it was very very very slow"))
check("a short phrase repeated many times is a loop", h.is_loop_text(loop_i_think) and h.is_loop_text(loop_run))
check("a four-word phrase repeated is a loop", h.is_loop_text(" ".join(["we go back home"] * 6)))

res = {"text": normal + " " + loop_i_think + " " + normal, "segments": [seg(normal), seg(loop_i_think, cr=14.5, lp=-1.27), seg(normal)]}
text, dropped = h.filter_hallucinations(res)
check("the looping segment is dropped, the speech around it kept", text == normal + " " + normal and len(dropped) == 1 and dropped[0]["why"] == "loop")

res = {"text": "x", "segments": [seg(normal), seg("Different words every time here.", cr=3.1), seg(normal)]}
text, dropped = h.filter_hallucinations(res)
check("a segment over Whisper's compression threshold is dropped even without a visible repeat", "Different" not in text and len(dropped) == 1)

res = {"text": "x", "segments": [seg(normal)] + [seg("Bye.") for _ in range(9)] + [seg("Thank you.")]}
text, dropped = h.filter_hallucinations(res)
check("an identical short segment repeated nine times is kept twice", text.count("Bye.") == 2 and len(dropped) == 7)

res = {"text": "x", "segments": [seg("Yes."), seg("No."), seg("Yes."), seg("No.")]}
text, _ = h.filter_hallucinations(res)
check("alternating short segments are untouched", text == "Yes. No. Yes. No.")

check("a result without segments falls back to its text", h.filter_hallucinations({"text": " hello "}) == ("hello", []))
check("a non-dict result is stringified", h.filter_hallucinations("raw") == ("raw", []))

# decode_speech with a stand-in decoder: the loop never reaches the transcript, the drop is counted
calls = []
def fake_transcribe(audio, **kw):
    calls.append(kw)
    return {"text": "x", "segments": [seg("he knows so much and"), seg(loop_run, cr=20.0), seg("I don't know if we can say that")]}
h.mlx_whisper.transcribe = fake_transcribe
before = h.LOOPS_DROPPED["segments"]
out = h.decode_speech(np.zeros(h.SAMPLE_RATE * 3, dtype=np.float32))
check("decode_speech returns the speech without the loop", out == "he knows so much and I don't know if we can say that")
check("the drop is counted for the state file", h.LOOPS_DROPPED["segments"] == before + 1)
check("condition_on_previous_text stays off", calls and calls[0].get("condition_on_previous_text") is False)

print(); print("all passed" if not fails else f"{fails} failed"); sys.exit(1 if fails else 0)
