#!/usr/bin/env python3
"""Builds the interaction model page (states x presses, sounds, collision rules, modes, open
questions) into runtime/secretary/interaction_model.html and prints its path."""
import os

OUT = "/Users/remi/voice2clipboard/runtime/secretary/interaction_model.html"
CSS = """
:root{--bg:#f6f4ee;--fg:#1d1d1b;--muted:#6b6963;--card:#fff;--line:#e2dfd6;--accent:#1f6f5b;--warn:#b5541b}
@media(prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe6;--muted:#a09e96;--card:#1f1f1d;--line:#333;--accent:#5fc2a4;--warn:#e08a4a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 -apple-system,Helvetica,Arial,sans-serif;padding:24px 16px 60px}
main{max-width:960px;margin:0 auto}h1{font-size:28px;margin:0 0 4px}h2{font-size:20px;margin:36px 0 12px}p.lead{color:var(--muted);margin:0 0 20px}
table{border-collapse:collapse;width:100%;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:15px;margin:8px 0 16px}
th,td{padding:9px 11px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:rgba(127,127,127,.08);font-weight:600}
tr:last-child td{border-bottom:0}td:first-child{font-weight:600}
ul{padding-left:20px}li{margin:6px 0}.q{background:var(--card);border-left:4px solid var(--warn);padding:10px 14px;border-radius:8px;margin:10px 0}
.q b{color:var(--warn)}.rule{background:var(--card);border-left:4px solid var(--accent);padding:10px 14px;border-radius:8px;margin:10px 0}
@media(max-width:640px){table{font-size:13px}th,td{padding:7px 6px}}
"""

STATES = [
    ("Idle", "nothing plays, no dictation", "start a dictation", "hear the latest queued message", "ask what needs your attention"),
    ("Dictating", "mic open, headset in call mode", "stop and send", "stop and send", "stop and send"),
    ("Message playing", "a queued message or an answer", "pause", "stop and discard", "stop and play the next queued message"),
    ("Message paused", "", "resume", "stop and discard", "stop and play the next queued message"),
    ("Preparing (after 2 or 3 presses)", "two ticks played, voice being rendered or the secretary thinking, 2 to 15 s", "start a dictation (the prepared message plays afterwards)", "no effect until the audio starts", "no effect"),
    ("Headset disconnected", "earbuds off or out of range", "nothing reaches the Mac", "nothing", "nothing"),
]

SOUNDS = [
    ("Rising two notes", "microphone is live, start talking"),
    ("Descending three notes", "recording ended, text is being sent"),
    ("Two soft ticks", "your double or triple press was received, wait for the voice"),
    ("Two high notes (ding)", "a message was queued for you; two presses to hear it"),
    ("Low double buzz", "something went wrong: the microphone stopped delivering or a recording had to be recovered"),
    ("Tink, then Glass", "transcriber working, then text delivered (keyboard flow mostly)"),
    ("Default voice, first person", "the secretary"),
    ("Another voice, opening with a name", "an agent, always the same voice for the same agent"),
]

RULES = [
    "Hard guard: exactly one voice message at a time. Every speech path goes through one atomic lock taken before synthesis and released when playback ends or a press stops it. A second message cannot start while the first is playing; it queues and plays right after.",
    "Press-driven playback (two or three presses) is the only thing that interrupts speech. Two presses stop and discard; three presses stop and continue with the next queued message.",
    "The secretary's direct speech never overlaps you or another message: if you are dictating or listening, it waits and plays right after the current event ends. It is queued after the event, not dropped.",
    "Nothing speaks while a dictation is running, or in the second between the press and the recorder opening.",
    "Dings are the exception: a notification ding may sound at any time, even while you talk or listen, so you know something arrived. Dings are rate-limited to one per 20 seconds; the next playback tells you how many are waiting.",
    "Every played or discarded message is archived on disk (pruned only past 300 MB). Nothing is replayed automatically; ask the secretary to search the archive when you want to check what you were told.",
    "If the microphone stops delivering for 3 seconds, the recorder finishes with what it has after a failure buzz. If a recorder dies outright, the launcher recovers the saved audio and sends the text, or queues a note saying a dictation was lost and where the audio is.",
]

QUESTIONS = [
    ("Ding rate", "One ding per 20 seconds at most, and a ding for every finished agent turn in headset mode. If that is still too many, the next step is one ding per agent per few minutes, or only for messages flagged as needing you."),
]


def build():
    h = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>Interaction model</title><style>{CSS}</style></head><body><main>"
         "<h1>Interaction model</h1><p class='lead'>Every state the earbud system can be in, what each press does there, every sound, and the rules that prevent collisions. Built 2026-09-18 for review; open questions are marked.</p>"
         "<h2>States and presses</h2><table><tr><th>State</th><th>What it is</th><th>1 press</th><th>2 presses</th><th>3 presses</th></tr>"]
    for row in STATES:
        h.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
    h.append("</table><p class='lead'>Both earbuds send the same signals. In call mode (while dictating) every press arrives as a hang-up, which is why any press stops a dictation. Long presses only change the headset volume and are not part of the model. Keyboard-driven use without the headset is unchanged.</p>")
    h.append("<h2>Sounds</h2><table><tr><th>Sound</th><th>Meaning</th></tr>")
    for a, b in SOUNDS:
        h.append(f"<tr><td>{a}</td><td>{b}</td></tr>")
    h.append("</table><p class='lead'>Every cue starts with a third of a second of silence so the earbuds do not swallow it. Play them on the <a href='earbuds_reference.html'>sounds reference page</a>.</p>")
    h.append("<h2>Rules against collisions</h2>")
    for r in RULES:
        h.append(f"<div class='rule'>{r}</div>")
    h.append("<h2>Two dictation modes</h2><table><tr><th></th><th>Headset mode</th><th>Manual mode</th></tr>"
             "<tr><td>Flips when</td><td>a dictation starts from an earbud press</td><td>a dictation starts from the keyboard shortcut</td></tr>"
             "<tr><td>Text goes to</td><td>the secretary</td><td>the console you were in</td></tr>"
             "<tr><td>Dings and queued messages</td><td>yes</td><td>none</td></tr>"
             "<tr><td>Attention ledger</td><td colspan='2'>kept in both modes; three presses or asking the secretary reads it</td></tr>"
             "<tr><td>Shown</td><td colspan='2'>the recorder window prints Mode: HEADSET or Mode: MANUAL at every start; the mode stays until a dictation of the other kind</td></tr></table>")
    h.append("<h2>Decided on 2026-09-18</h2><ul><li>Long press: not an action anywhere.</li><li>Headset disconnected: nothing changes; keyboard use without the headset works as before.</li><li>Two presses during a message: stop and discard (archive kept for voluntary lookup).</li><li>Three presses: attention summary only when idle; otherwise stop and next.</li><li>One voice message at a time, enforced by a lock; direct speech that would collide is queued after the event.</li><li>Dings may sound at any time, rate-limited.</li></ul>")
    h.append("<h2>Open question</h2>")
    for t, q in QUESTIONS:
        h.append(f"<div class='q'><b>{t}.</b> {q}</div>")
    h.append("</main></body></html>")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write("".join(h))
    print(OUT)


if __name__ == "__main__":
    build()
