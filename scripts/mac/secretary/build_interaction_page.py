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
    ("Dictating", "mic open, headset in call mode", "stop and send, at once. If you said nothing and it lasted under 15 seconds, it counts as cancelled instead", "not visible: the headset swallows a double press in call mode, the Mac receives nothing", "not tested yet"),
    ("Message playing", "a queued message or an answer", "pause", "stop and discard", "stop and play the next queued message"),
    ("Message paused", "", "resume", "stop and discard", "stop and play the next queued message"),
    ("Preparing (after 2 or 3 presses)", "two ticks played, voice being rendered or the secretary thinking, 2 to 15 s", "start a dictation (the prepared message plays afterwards)", "no effect until the audio starts", "no effect"),
    ("Press just received", "the second between a press and the recorder opening", "stops the dictation that is starting", "stops the dictation that is starting", "stops the dictation that is starting"),
    ("Headset disconnected", "earbuds off or out of range", "nothing reaches the Mac", "nothing", "nothing"),
]

EDGE_CASES = [
    ("You press to dictate but the headset has just dropped", "Nothing is recorded. Failure buzz on the Mac, a note is queued. Before, the Mac's own microphone recorded an empty room for as long as nobody stopped it."),
    ("The headset disconnects during a dictation", "The recorder stops within a second or two, transcribes what you said before the drop and delivers it. Failure buzz."),
    ("The microphone delivers frames but no sound for 60 seconds", "Treated as a lost headset: failure buzz, stop, deliver what was said. Pauses in real dictations never exceeded 14 seconds in the recordings measured."),
    ("A recording contains no speech at all", "Nothing is sent. The folder gets an explicit transcript saying no speech was detected, and a note is queued. Before, the recorder crashed and left nothing."),
    ("You close the recorder window", "That is a cancel: the recorder is killed, nothing is delivered, the audio stays on disk, and the earbuds are free again at once."),
    ("The recorder dies or never starts", "The busy marker is cleared immediately and you hear the failure buzz. A marker on its own is only trusted for 5 seconds (it was 20)."),
    ("The secretary was restarted in another window", "Its own hooks re-register the window on every turn, and every press checks that the window exists; a stale registration is healed from the secretary's running process."),
    ("The secretary window is really gone", "Failure buzz at the press, the dictation is still recorded, the text goes to the recordings folder and the clipboard, never into a random console, and a note is queued."),
    ("A press cannot be honoured", "You hear the short falling tone. Silence always means it worked, never that it broke."),
    ("The start cue may have been lost (edge of range)", "The recorder confirms from the Bluetooth log that the headset's audio link is up. If the link came up after the cue started, the cue is replayed once and the event is logged. Packet loss on a link that is already up cannot be detected."),
    ("The stop sound does not play after a dictation", "On some recordings, short or long, macOS accepts the sound's stream on the headset and never runs it, so you get no confirmation. The recorder now reads the audio daemon's log after each confirmation sound (recording ended, delivered, failure) and replays it, up to twice, when the stream never ran. Each replay is logged."),
    ("You started a dictation by mistake", "Say nothing and press once: a recording under 15 seconds with no speech in it is treated as cancelled. You hear the downward sweep, nothing is sent, no note is queued. A double press cannot do this: tested on 2026-09-19, the headset's firmware swallows a double press while it is in call mode and the Mac receives nothing at all, neither a second hang-up nor any other command. Closing the recorder window also cancels."),
    ("You want to cancel after you have spoken", "No earbud gesture for this yet. What the Mac can see in call mode is one press (hang-up) and press-and-hold (volume step); a triple press is untested. Until a gesture is chosen: stop normally and tell the secretary to ignore it, or close the recorder window."),
    ("You cancelled a dictation you wanted to keep", "Dictate to the secretary: recover my last cancelled message. It runs recover_cancelled.sh, which prints the text of the latest cancelled dictation and treats it as just dictated. Running it again goes back one more. A dictation cancelled by closing the recorder window is recovered the same way."),
    ("The headset reconnects", "The button app takes the buttons back and runs a self-check three seconds later: button app, secretary window, voice, microphone, recorder. One soft chord means ready. The failure buzz followed by a spoken reason means not ready."),
]

SOUNDS = [
    ("Rising two notes", "microphone is live, start talking"),
    ("Descending three notes", "recording ended, text is being sent"),
    ("Two soft ticks", "your double or triple press was received and the voice still has to be prepared; not played when the message is ready and starts at once"),
    ("Two high notes (ding)", "a message was queued for you; two presses to hear it"),
    ("Low double buzz", "something went wrong: the headset dropped, the microphone went silent, a recording held no speech or could not be delivered, or the self-check failed"),
    ("One quick downward sweep", "dictation cancelled: nothing was sent, everything is kept"),
    ("One short falling tone", "your press was received but cannot be honoured right now"),
    ("One soft chord", "the headset reconnected and the whole chain checks out: ready"),
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
    "Who decides a notification: the secretary. Agents never ding by themselves. A flagged turn (a question for you, a permission prompt, an explicit Notify line, a possible problem) is handed to the secretary, which notifies only if you are being waited on, if it answers something you routed by voice, or if it matters. Routine completions of work you started at the keyboard stay in the ledger for the triple press. A per-project file can force always or never.",
    "A queued message is rendered to audio when it is queued, in the sender's voice, and the ding only plays once that audio is ready. Two presses then start the message at once; the two ticks are only played when the voice still has to be rendered. Long reports are rendered in chunks of a few sentences so an urgent sentence never waits behind them.",
    "Every played or discarded message is archived on disk (pruned only past 300 MB). Nothing is replayed automatically; ask the secretary to search the archive when you want to check what you were told.",
    "If the microphone stops delivering for 3 seconds, the recorder finishes with what it has after a failure buzz. If a recorder dies outright, the launcher recovers the saved audio and sends the text, or queues a note saying a dictation was lost and where the audio is.",
    "One source of truth for 'a dictation is running': the recorder's lock, owned by the recorder. The press marker only bridges the second before the lock exists; the recorder removes it when the lock appears and again when it exits, however it exits.",
    "Every press produces a sound. A refused or ignored press plays the short falling tone and the reason is written to the log.",
    "Earbud dictations are only ever delivered to the secretary's window. If it cannot be reached, the text is kept and a note is queued; it is never pasted into whatever console happens to be in front.",
]

QUESTIONS = [
    ("Ding rate", "The secretary now decides; expect a handful a day. If a project is still too chatty, mute it in the per-project file, or tell the secretary to."),
]


def build():
    h = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>Interaction model</title><style>{CSS}</style></head><body><main>"
         "<h1>Interaction model</h1><p class='lead'>Every state the earbud system can be in, what each press does there, every sound, and the rules that prevent collisions. Built 2026-09-18, edge cases added 2026-09-19; open questions are marked.</p>"
         "<h2>States and presses</h2><table><tr><th>State</th><th>What it is</th><th>1 press</th><th>2 presses</th><th>3 presses</th></tr>"]
    for row in STATES:
        h.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
    h.append("</table><p class='lead'>Both earbuds send the same signals. In call mode (while dictating) every press arrives as a hang-up, which is the only press the Mac sees then: a double press never arrives, the headset keeps it to itself. Long presses only change the headset volume and are not part of the model. Keyboard-driven use without the headset is unchanged.</p>")
    h.append("<h2>Sounds</h2><table><tr><th>Sound</th><th>Meaning</th></tr>")
    for a, b in SOUNDS:
        h.append(f"<tr><td>{a}</td><td>{b}</td></tr>")
    h.append("</table><p class='lead'>Every cue starts with a third of a second of silence so the earbuds do not swallow it. Play them on the <a href='earbuds_reference.html'>sounds reference page</a>.</p>")
    h.append("<h2>Rules against collisions</h2>")
    for r in RULES:
        h.append(f"<div class='rule'>{r}</div>")
    h.append("<h2>Edge cases (robustness pass, 2026-09-19)</h2><table><tr><th>Situation</th><th>What happens now</th></tr>")
    for a, b in EDGE_CASES:
        h.append(f"<tr><td>{a}</td><td>{b}</td></tr>")
    h.append("</table>")
    h.append("<h2>Two dictation modes</h2><table><tr><th></th><th>Headset mode</th><th>Manual mode</th></tr>"
             "<tr><td>Flips when</td><td>a dictation starts from an earbud press</td><td>a dictation starts from the keyboard shortcut</td></tr>"
             "<tr><td>Text goes to</td><td>the secretary</td><td>the console you were in</td></tr>"
             "<tr><td>Notifications</td><td colspan='2'>identical in both modes: the secretary decides from agent reports</td></tr>"
             "<tr><td>Attention ledger</td><td colspan='2'>kept in both modes; three presses or asking the secretary reads it</td></tr>"
             "<tr><td>Shown</td><td colspan='2'>the recorder window prints Mode: HEADSET or Mode: MANUAL at every start; the mode stays until a dictation of the other kind</td></tr></table>")
    h.append("<h2>Decided on 2026-09-18</h2><ul><li>Long press: not an action anywhere.</li><li>Headset disconnected: nothing changes; keyboard use without the headset works as before.</li><li>Two presses during a message: stop and discard (archive kept for voluntary lookup).</li><li>Three presses: attention summary only when idle; otherwise stop and next.</li><li>One voice message at a time, enforced by a lock; direct speech that would collide is queued after the event.</li><li>Dings may sound at any time, rate-limited.</li></ul>")
    h.append("<h2>Decided on 2026-09-19</h2><ul><li>Cancelling a dictation never erases it: the audio and text are kept and the secretary can recover them on request. A double press cannot be the gesture, the headset hides it in call mode; a short dictation with no speech is cancelled automatically.</li><li>Queued messages are rendered before the ding, so they play at once.</li><li>Every press produces a sound; a refused press has its own.</li></ul>")
    h.append("<h2>Open question</h2>")
    for t, q in QUESTIONS:
        h.append(f"<div class='q'><b>{t}.</b> {q}</div>")
    h.append("</main></body></html>")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write("".join(h))
    print(OUT)


if __name__ == "__main__":
    build()
