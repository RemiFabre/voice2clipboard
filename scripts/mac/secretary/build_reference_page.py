#!/usr/bin/env python3
"""Builds a self-contained HTML reference of the earbud sounds and button mapping, with every
sound embedded as WAV so it plays in any browser, then prints the page path.
Run with the voice2clipboard venv python (needs soundfile)."""
import base64
import io
import os
import subprocess
import tempfile

import soundfile as sf

ROOT = "/Users/remi/voice2clipboard"
OUT = os.path.join(ROOT, "runtime", "secretary", "earbuds_reference.html")


def wav_b64(path):
    if path.endswith(".aiff") and path.startswith("/System"):
        tmp = os.path.join(tempfile.mkdtemp(), "s.wav")
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16", path, tmp], check=True)
        path = tmp
    audio, sr = sf.read(path)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return base64.b64encode(buf.getvalue()).decode()


def voice_sample():
    tmp = os.path.join(tempfile.mkdtemp(), "voice.wav")
    env = dict(os.environ, PYTORCH_ENABLE_MPS_FALLBACK="1")
    r = subprocess.run(["/Users/remi/local-tts-lab/.venv/bin/kokoro-say", "--no-play", "--output", tmp,
                        "reachy mini says: the antenna script is fixed and pushed."], env=env, capture_output=True)
    return wav_b64(tmp) if r.returncode == 0 and os.path.exists(tmp) else None


SOUNDS = [
    ("Start cue", "rising two notes", f"{ROOT}/sounds/cue_start.aiff",
     "The microphone is live: start talking. Plays about one second after you press."),
    ("Stop cue", "descending three notes", f"{ROOT}/sounds/cue_stop.aiff",
     "The recording has ended (button, Escape or shortcut). The text is being finalized and sent."),
    ("Transcribing", "system Tink", "/System/Library/Sounds/Tink.aiff",
     "The transcriber has started working on the file. Usually right after the stop cue, very short."),
    ("Delivered", "system Glass", "/System/Library/Sounds/Glass.aiff",
     "The text has been delivered: pasted into the target, or sent to the secretary."),
    ("Working on it", "two soft mid ticks", f"{ROOT}/sounds/cue_ack.aiff",
     "Plays immediately after a double or triple press: your request was received and the voice is being prepared."),
    ("Message waiting", "two high notes", f"{ROOT}/sounds/cue_ding.aiff",
     "The secretary decided you should hear something (an agent is waiting on you, answers a voice request, or reports a problem). Press twice to hear it; nothing is read to you unless you ask."),
]

STATES = [
    ("Nothing happening", "start a dictation", "hear the latest notification", "ask what needs your attention"),
    ("Dictating (mic open)", "stop the dictation", "stop the dictation", "stop the dictation"),
    ("A message is playing", "pause it", "stop and discard it", "stop it and play the next queued"),
    ("A message is paused", "resume it", "stop and discard it", "stop it and play the next queued"),
]

CSS = """
:root{--bg:#f6f4ee;--fg:#1d1d1b;--muted:#6b6963;--card:#fff;--line:#e2dfd6;--accent:#1f6f5b}
@media(prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe6;--muted:#a09e96;--card:#1f1f1d;--line:#333;--accent:#5fc2a4}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 -apple-system,Helvetica,Arial,sans-serif;padding:24px 16px 60px}
main{max-width:880px;margin:0 auto}h1{font-size:28px;margin:0 0 4px}h2{font-size:20px;margin:36px 0 12px}p.lead{color:var(--muted);margin:0 0 24px}
.sound{display:grid;grid-template-columns:52px 1fr;gap:14px;align-items:start;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:10px 0}
.sound button{width:52px;height:52px;border-radius:50%;border:0;background:var(--accent);color:#fff;font-size:22px;cursor:pointer}
.sound b{display:block;font-size:17px}.sound small{color:var(--muted)}.sound p{margin:4px 0 0}
table{border-collapse:collapse;width:100%;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:15px}
th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:rgba(127,127,127,.08);font-weight:600}
tr:last-child td{border-bottom:0}td:first-child{font-weight:600;white-space:nowrap}
ul{padding-left:20px}li{margin:6px 0}.note{background:var(--card);border-left:4px solid var(--accent);padding:10px 14px;border-radius:8px;margin:12px 0}
@media(max-width:600px){table{font-size:13px}th,td{padding:8px 6px}td:first-child{white-space:normal}}
"""


def build():
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>Earbud cues and buttons</title><style>{CSS}</style></head><body><main>"
             "<h1>Earbud cues and buttons</h1><p class='lead'>What each sound means and what each press does, as implemented on 2026-09-17. "
             "Regenerate with <code>scripts/mac/secretary/build_reference_page.py</code>.</p>"
             "<h2>Sounds</h2>"]
    for name, desc, path, meaning in SOUNDS:
        b64 = wav_b64(path)
        parts.append(f"<div class='sound'><button onclick=\"new Audio('data:audio/wav;base64,{b64}').play()\" aria-label='play {name}'>&#9654;</button>"
                     f"<div><b>{name} <small>({desc})</small></b><p>{meaning}</p></div></div>")
    v = voice_sample()
    if v:
        parts.append(f"<div class='sound'><button onclick=\"new Audio('data:audio/wav;base64,{v}').play()\" aria-label='play voice sample'>&#9654;</button>"
                     "<div><b>Spoken message <small>(Kokoro voice)</small></b><p>The secretary speaks in this default voice, in the first person, with no prefix. Each agent has its own consistent voice (chosen from the agent's name) and introduces itself in two words, for example: micro duck here. One press pauses, one press resumes, two presses stop.</p></div></div>")
    parts.append("<h2>Buttons</h2><p class='lead'>Both earbuds send the same signals; left and right cannot be told apart, except that a long press is volume up on the right and volume down on the left.</p>"
                 "<table><tr><th>Situation</th><th>1 press</th><th>2 presses</th><th>3 presses</th></tr>")
    for row in STATES:
        parts.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
    parts.append("</table>")
    parts.append("<h2>Two modes</h2><table><tr><th></th><th>Headset mode</th><th>Manual mode</th></tr>"
                 "<tr><td>Starts when</td><td>you start a dictation with an earbud press</td><td>you start a dictation with the keyboard shortcut</td></tr>"
                 "<tr><td>Text goes to</td><td>the secretary, which routes it</td><td>the console or app you were in</td></tr>"
                 "<tr><td>Notifications</td><td colspan='2'>the same in both modes: the secretary decides what you hear; two presses to hear it</td></tr>"
                 "<tr><td>Attention ledger</td><td colspan='2'>in both modes every agent silently records what it last did and whether it is waiting on you; three presses ask the secretary what needs your attention</td></tr>"
                 "<tr><td>Shown</td><td colspan='2'>the recorder window prints Mode: HEADSET or Mode: MANUAL at each start; the mode stays until a dictation of the other kind</td></tr></table>")
    parts.append("<h2>Stopping a dictation</h2><ul><li>Any press on either earbud (single, double, triple or long). While the mic is open the earbuds are in phone-call mode, and the recorder catches their hang-up and volume signals from the Bluetooth log.</li>"
                 "<li>Escape in the recorder window, or the keyboard shortcut again.</li>"
                 "<li>Spoken stop phrases are switched off.</li></ul>")
    parts.append("<h2>Where it differs from what you asked</h2><ul>"
                 "<li>Right = talk, left = pause was not possible: the earbuds send identical presses from both sides.</li>"
                 "<li>While dictating, every kind of press stops the recording, not only the single press: in phone-call mode the earbuds send the same hang-up for one, two or three presses.</li>"
                 "<li>Two presses when nothing is happening plays the latest notification, as you asked; further double presses go back through older ones.</li>"
                 "<li>Long presses only change the headset volume; by your decision they are not an action anywhere.</li></ul>")
    parts.append("<div class='note'>Sound tip: every cue starts with a third of a second of silence because Bluetooth earbuds swallow the beginning of short sounds while the link wakes up. If a cue still gets lost, that lead-in can be lengthened.</div>")
    parts.append("</main></body></html>")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("".join(parts))
    print(OUT)


if __name__ == "__main__":
    build()
