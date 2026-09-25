# Voice secretary runbook (earbuds ↔ Claude Code sessions)

Built 2026-09-17. Lets Remi drive Claude Code sessions from the Shokz OpenFit 2+ buttons
without being at the screen: dictate to a router session, hear replies through Kokoro TTS.

## Pieces

| Piece | Where | Role |
|---|---|---|
| EarbudButtons.app | `scripts/mac/earbuds/` (built into `runtime/earbuds/`) | Registers as the macOS Now Playing app so headset presses reach it (and takes that role back from any other app); runs `on_gesture.sh`; watches headset connections and who holds the headset microphone (`on_headset.sh`). launchd agent `com.voice2clipboard.earbuds`. |
| Gesture router | `scripts/mac/secretary/on_gesture.sh` | single → `tts_toggle.sh`, double → `dictate_toggle.sh`, triple → `tts_repeat_last.sh` |
| Spoken inbox | `inbox_post.sh`, `inbox_read_next.sh`, `say_now.sh`, `ding.sh` | Queue in `runtime/secretary/inbox/`, archive in `spoken/`. Speech = kokoro-say → wav → afplay (pid in `tts.pid`, pausable with SIGSTOP). |
| Hooks | `stop_hook.sh`, `notification_hook.sh`, `user_prompt_hook.sh` in `~/.claude/settings.json` | Every session's final message goes to the attention ledger. Flagged turns (question, decision, permission prompt, `Notify:` line, possible problem) are typed into the secretary session as an `[Agent report]`; the secretary decides whether Remi hears it, in the agent's voice. `secretary/notify_overrides.json` can force `always` or `never` per project. |
| Secretary session | `secretary/CLAUDE.md`, `start_secretary.sh`, `stop_secretary.sh` | A Claude Code session (permissions skipped, always `--model claude-fable-5-1 --effort xhigh`: since 2026-09-24 new sessions default to Opus 5.5, the secretary keeps its Fable voice by Remi's rule) whose only job is routing `[Voice]` dictations to the right project session with SendMessage and speaking back. |
| Dictation target | `legacy_mlx_toggle_autopaste.sh` honours `VOICE2CLIPBOARD_TARGET_ITERM_SESSION` | Earbud dictations paste into the secretary's iTerm session instead of the frontmost app. Keyboard shortcut behaviour unchanged. |

## Button map (Shokz OpenFit 2+, both earbuds identical)

The headset sends the same commands from either side: single press = play/pause, double = next
track, triple = previous track. Long press is volume on the headset only. What they do depends
on the state (`scripts/mac/secretary/on_gesture.sh`):

| State | single | double | triple |
|---|---|---|---|
| idle | start a dictation | hear the latest notification | ask what needs your attention |
| dictating | stop and send (nothing said in under 15 s: cancelled); **press and hold: cancel** | never reaches the Mac | untested |
| message playing | pause | stop and discard | stop, play the next queued |
| message paused | resume | stop and discard | stop, play the next queued |

**While a dictation is recording, the headset is in hands-free mode** (macOS sets up a "virtual
call" with it, seen in the Bluetooth log at 21:47:06 on 2026-09-17). Its buttons then send call
commands instead of media commands, so the Now Playing app never sees them. The recorder
therefore watches the unified log (`/usr/bin/log stream`, process bluetoothd, category
Server.Handsfree) while recording: a press arrives as `Received call hangup event (AT+CHUP)`,
a long press as `Received speaker gain event` (right = up, left = down). Any of them stops the
dictation (verified live 21:53, single press). Escape in the recorder window also works. A
spoken stop phrase exists but is OFF by default at Remi's request (brittle); enable with
`VOICE2CLIPBOARD_STOP_PHRASES="roger stop"` in the helper's environment.

Voices (sticky since 2026-09-20): a voice belongs to a role, which is a project or a durable job,
not to the name a session happens to announce. `secretary/voices.json` (tracked, edited by hand)
lists each role with its aliases and its voice; `voice_for` in `lib.sh` asks
`scripts/mac/secretary/voices.py`, which matches the name against roles and aliases (case, dashes
and underscores ignored, as are a trailing "agent" and a session suffix such as "-3c"). A name
found nowhere gets the least used voice of the pool and is remembered in
`runtime/secretary/voices.learned.json`, untracked because the repository is public and sender
names can be personal; move an entry to the tracked file to make it permanent, or edit its voice
(clips are cached by voice and text, so a changed mapping re-renders by itself). The introduction
speaks the role's name ("session tower here."; in French messages its `role_fr`, "Un message de la
tour de contrôle.", see 2026-09-25 below), so aliases also sound the same. The secretary is
always `anna` (Remi's choice on 2026-09-20 late evening after hearing it; it was `alba` until
then, which moved to the end of the pool, last to be handed out) and has no introduction, French is always `estelle`, and if the file or the helper
is broken the old hash of the name over the pool still answers. To keep voices rotating, roles
are narrow (one per project or job) except one shared role for throwaway questions.
`voices.py list` prints the table. Test: `bash local_tests/test_sticky_voices.sh`.

Sounds, all with a 350 ms silent lead-in because the earbuds swallow the head of short sounds:
`sounds/cue_start.aiff` (rising, mic is live), `cue_stop.aiff` (descending, recording ended),
`cue_ding.aiff` (two high notes, a spoken message is waiting), `cue_ack.aiff` (two soft ticks,
your double or triple press was received and the voice is being prepared), `cue_refuse.aiff` (one
short falling tone, the press cannot be honoured now), `cue_ready.aiff` (one soft chord, the
headset reconnected and the self-check passed), `cue_fail.aiff` (low double buzz, a problem), `cue_cancel.aiff` (quick downward sweep, dictation
cancelled). The transcriber's "done" sound is
still the system Glass sound.

## Cancelling a dictation (2026-09-19)

Remi asked for a double press to cancel a dictation. Tested with him the same day: it cannot work
with this headset. During the test recording the Mac received nothing between the start and
the final single press, in any bluetoothd category: no second `AT+CHUP`, no other AT command
(`AT+BLDN`, `AT+BVRA`, `AT+CHLD`), no AVRCP command (those show up as `Server.Remote: Received
AVRCP ... command`). The Shokz firmware keeps a double press to itself while in call mode. What
is visible then: one press (`AT+CHUP`) and press-and-hold (`Received speaker gain event`, one
volume step as a side effect); a triple press is untested. The recorder logs volume events and
unknown call commands seen while recording to `secretary.log` to settle such questions.

What exists:
- **Press and hold cancels (2026-09-21).** Remi reached for the double press again on a
  dictation started by mistake: a limit he has to remember is a design gap. Press-and-hold is
  the only other gesture the headset lets through in call mode (`Received speaker gain event`),
  so the recorder now treats it as cancel: cancel cue, nothing sent, `cancelled` marker, audio
  kept and transcribed quietly, `recover_cancelled.sh` brings it back. Evidence against false
  cancels: in 66 logged dictations the headset sent exactly one gain event, the deliberate test
  of 2026-09-20; a gain report in the first second of a recording is ignored anyway
  (`VOICE2CLIPBOARD_HOLD_CANCEL_GRACE_S`). Side effect: each hold moves the headset's call
  volume (the loudness of dictation cues) one step, up on the right earbud, down on the left,
  so cancelling on the right side is the better habit. `VOICE2CLIPBOARD_HOLD_CANCELS=0` turns
  it off. Test: `python local_tests/test_hold_cancel.py` (fake Bluetooth log, silent). Confirmed on the
  real headset on 2026-09-21 at 18:18.
- A recording of at most `VOICE2CLIPBOARD_ACCIDENTAL_MAX_S` (15 s) with no speech is treated as
  a cancelled accident: `sounds/cue_cancel.aiff`, nothing sent, no note.
- `PressArbiter` in the recorder: a press that reaches the Mac already classified as `double`
  (through `on_gesture.sh` and `/tmp/voice2clipboard_quick_autopaste.press`, only possible when
  the recording does not use the headset microphone) cancels: nothing sent, `cancelled` marker
  in the folder, quiet transcription. `VOICE2CLIPBOARD_DOUBLE_PRESS_WINDOW_S` (default 0) can make
  the recorder wait for a second hang-up, at the price of that delay on every stop; it is 0
  because the second hang-up never comes.
- Closing the recorder window cancels, by Remi's decision (2026-09-24 09:42: he uses the close
  button as a cancel; the audio may be kept, the text must not reach the secretary). iTerm sends
  HUP to the recorder's process group five seconds after the click (its "undo close" grace,
  measured); the recorder dies of it, the worker traps it, moves its output to the log, plays the
  cancel cue, writes the `cancelled` marker and one log line, delivers nothing and queues no note.
  The window is named "🎤 Dictation running: closing this window cancels it (audio kept)".
  Test: `bash local_tests/test_window_closed_delivery.sh` (stand-ins, no iTerm, no microphone).
- `scripts/mac/secretary/recover_cancelled.sh` prints the text of the latest cancelled dictation
  not yet recovered and marks it `recovered`; `--list` shows them all.
Tests: `python local_tests/test_cancel_dictation.py`, `python local_tests/test_cancel_integration.py`.

## Pre-rendered inbox (2026-09-19)

`inbox_post.sh` queues the text and returns at once; in the background `speech_render.py`
renders the body in the sender's voice to `inbox/<stem>.wav`, the introduction and the
"N older waiting." counts go to `runtime/secretary/clip_cache/`, and only then does `ding.sh`
play. `inbox_read_next.sh` joins the cached clips and the body (350 ms silent lead-in) and hands
the file to `say_now.sh --wav`, which keeps the speech lock, the pause and stop handling and the
no-speech-during-dictation rule; without a voice file it renders on demand as before.
`on_gesture.sh` skips the "working on it" ticks when the next message is ready. Measured: a
two-sentence message is ready 3 s after posting; a 600 word report takes about 26 s, and because
the Kokoro daemon serves one request at a time it is rendered in chunks of about 60 words so
direct speech slips in between. Agent reports typed into the secretary now carry the whole
`Spoken:` text (it used to stop at the first blank line) and the path of a file holding it under
`runtime/secretary/reports/`. Test: `bash local_tests/test_prerendered_inbox.sh`.

**A message exists only once its voice is ready (2026-09-20).** The ding was already after the
render, but a double press in between took the unrendered message: press confirmation, then up
to 22 s of nothing while it rendered on demand. Now `inbox_post.sh` marks a message
`<stem>.rendering` until its voice is done, and `inbox_next_playable` in `lib.sh` skips marked
messages: an older ready message is played as before; if only unrendered ones wait he hears the
cached clip "Not ready yet." at once, nothing is consumed, and `ding_owed` makes the following
ding ignore its 20 s cooldown, since he is waiting for it. A marker older than 180 s
(`SECRETARY_RENDERING_MAX_S`) belongs to a render that died and no longer hides the message.
The "N older waiting" count ignores unrendered messages.

## French messages are French from the first word to the last (2026-09-25)

Reported by Remi at night: in French messages the middle was fine but the start and the end
sounded bad. Cause: the message's language (`lang=` in the inbox file) chose the voice of the
body only. The introduction ("<role> here.") and the count ("N older waiting.") were always the
English sentences, rendered by the French voice, with English role names.

Now `lib.sh` builds every sentence around a message in its language: `intro_text_for <name>
<lang>` ("Un message de la tour de contrôle."), `count_text <lang> <n>` ("Encore deux messages en
attente.", numbers in words), and the two short answers of a double press: "Il n'y a pas de
nouveau message." when the last message heard was French, "Le message n'est pas encore prêt."
when the one being rendered is French. Clips are cached per language, voice and text;
`inbox_post.sh` pre-renders the French ones with a French message. Roles carry a French name,
article included (`role_fr` in `secretary/voices.json`, and in the untracked learned file for
learned roles); product names keep their English name; "de" contracts (du, des, d').
`tts_repeat_last.sh` says "encore une fois" in French.

Wording chosen by measurement, never by playing into the earbuds: each candidate rendered three
times by the real French voice to files, transcribed by Whisper large-v3-turbo. The engine
garbles very short sentences about one time in three, and a clip is cached from one render, so
only sentences right three times out of three were kept. "Ici Reachy Mini." lost "Mini" in
every render and "Ici micro duck." was never understood, while "Un message de ..." was right
every time; "Pas encore prêt." and "Aucun nouveau message." each failed once in three.

Two more causes of English sounds in French messages, fixed at the same time:
- `inbox_post.sh` without `--lang` (the hooks relaying an agent's "Spoken:" paragraph) was always
  English. The language is now guessed (`speech_render.py lang`): English unless there are at
  least two French marks (common words, elisions such as "l'" or "c'", accents) and more of them
  than English common words. The log says `lang=fr (guessed)`.
- The pronunciation respellings of `secretary/dictionary.json` ("Claude" read as "Clawed") were
  applied to French too. `pronounce` is now English only; an entry may add `pronounce_fr` for the
  French voice.

Tests: `bash local_tests/test_sticky_voices.sh`, `bash local_tests/test_prerendered_inbox.sh`
(stand-in voice, sections 5 and 6).

## Pause and resume of a message (2026-09-21)

Reported: after pausing and resuming a message, the speech rushed ahead and a piece was missing.
Not the voice engine (the audio is a finished file by then). A pause was `SIGSTOP` on `afplay`
and a resume `SIGCONT`, and `afplay` keeps to the wall clock: measured silently (volume zero,
timing only), a 12 s file paused for 4 s still ends 13 s after its start, exactly like an
unpaused one. Whatever "should" have played during the pause is dropped or rushed through, so a
2 s pause cost him about 2 s of speech, and longer pauses cost more.

Now a pause is real: `tts_pause` (lib.sh) notes the seconds of sound left in `tts.paused`, hands
the pid file to the `say_now.sh` that owns the message (`tts.owner`) and ends the player. On
resume (`tts.resume`) `say_now.sh` cuts the rest of the audio with `speech_render.py tail`,
starting 1 s before the point of the pause (`SECRETARY_TTS_REWIND_S`) behind the usual 350 ms
silent lead-in, and plays that; the sound clock, the end tone, discarding while paused and the
"message is over" rule work as before. If the cut fails the message restarts from the beginning,
and a message started by an older `say_now.sh` (no owner file) is still paused the old way.
Test: `bash local_tests/test_pause_resume.sh` (stand-in player, silent). Not verified by ear.

## Unheard speech is never dropped, and keep-warm pings (2026-09-21 evening)

- **Speech still being prepared.** A direct answer of the secretary that had waited behind a
  playing message was killed by a double press two seconds into its preparation (the press was
  meant for the next inbox message): never spoken, no trace. Now a double or triple press on a
  message in state `preparing` leaves it alone and plays the "coming" ticks (after 45 s a
  preparation counts as stuck and is stopped as before), and whatever else stops direct speech
  before it sounds (a dictation starting, an interrupting message) moves its text to the inbox:
  `say_now.sh` keeps the text in `tts.text` until playback starts, `tts_requeue_if_unheard` in
  `lib.sh` posts it from the secretary. Only the secretary's voice is re-queued; inbox playback
  is not concerned, its text is already in the archive; once a message sounds, a stop is a stop.
  Test: `bash local_tests/test_unheard_speech.sh`.
- **Keep-warm pings.** The Session Tower types a prompt starting with `banana (automatic
  keep-warm ping` into idle sessions so their prompt cache survives; the answer is the single
  word `coconut`. The hooks treat such a turn as no activity: the prompt hook leaves a marker
  under `runtime/secretary/pings/` instead of clearing "waiting on Remi", and the Stop hook, on
  that marker plus that answer, writes no ledger entry, sends no report and skips the rotation
  check (`is_ping_prompt`, `ping_take` in `ledger_lib.py`). A ping answered with anything more is
  recorded as a real turn; a marker older than 15 minutes is forgotten. The two strings are a
  contract with the Tower agent. Test: `bash local_tests/test_ping_ignored.sh`.
- The cancel marker and log line now name the gesture ("press and hold", "double press", or
  the stop source) instead of always saying "double press". Press and hold was confirmed on the
  real headset at 18:18 that day.

## Same loudness for every voice, and the phantom dictation at the charger (2026-09-21 night)

- **Loudness.** Measured on the cached clips: the speech level of the voices in use spread over
  10 dB (about -28 dBFS for the quietest pool voice, -18 for the loudest). `speech_render.py`
  now brings every rendered file to one speech level (`SPEECH_TARGET_DBFS`, default -20): RMS of
  the 50 ms frames that carry speech, gain within 15 dB either way, peaks rounded off softly
  instead of clipped; standard library only, 0.2 s for a one minute message.
  `speech_render.py normalize <files>` does the same in place (used once on the 67 cached clips).
  Fresh renders of the quietest voice and of the secretary's now differ by about 1 dB.
  `SPEECH_NORMALIZE=0` switches it off. Test: `python3 local_tests/test_loudness.py`. Cues and
  the ding are not touched. Not judged by ear yet.
- **Phantom dictation when an earbud goes into the charger** (confirmed by Remi on 2026-09-21 at
  21:46, on purpose). Putting the FIRST earbud into its slot makes the headset send an ordinary
  `AVRCP Pause` (21:46:22.856), presumably to stop music, and a pause is exactly what a single
  press sends, so a dictation starts. Compared in the Bluetooth daemon's log with two real
  presses: nothing tells them apart (no battery, charging or in-case report, no disconnection;
  the headset stays connected with the second earbud). Earlier cases: 2026-09-21 18:39:23 and
  2026-09-19 16:00:38. It cannot be prevented on arrival, so it is made harmless:
  a dictation that nobody ends (it stops by the 60 s silence rule, lost input or the headset
  going away) and that holds no speech is a silent non-event: no sound at all (with the headset
  in its charger a cue would come out of the Mac's speakers), no spoken note, one log line
  (`phantom start`); `phantom_start` in the recorder, test `python local_tests/test_phantom_start.py`.
  Unchanged on purpose: when HE presses stop and there was no speech, he is told. While one
  earbud is still worn he hears the start cue: press and hold cancels, or one press without a
  word within 15 s. Candidate for a real cure, to try with him (two minutes, buttons dead
  meanwhile): the headset may only send that pause because we report "playing" all the time;
  stop the button app, run `local_tests/nowplaying_client.swift` in state paused, let him dock an
  earbud and then press once, and read the Bluetooth log. If no pause arrives when we are
  "paused" and a press arrives as "play", the button app could rest in "paused" and claim only
  when needed. That is a change of the app, so a rebuild and the Bluetooth question.
- **False call mode alarm, fixed.** In that same 18:39 episode the call mode watch looked once,
  in the two seconds between the dying recorder releasing its lock and its microphone closing,
  and announced "another program is using its microphone". `on_headset.sh mic-open` now looks
  twice, 4 s apart (`SECRETARY_CALLMODE_CONFIRM_S`), and raises the flag only at the second look.
- Known gap, needs a rebuild of the button app (so: with Remi at the screen): its Bluetooth
  disconnect notifications almost never fire (2 logged against a dozen connects), so
  `on_headset.sh disconnected` rarely runs. The recorder's own log watcher covers dictations.

## Resting in "paused", the freeze of 2026-09-21, and the memory guard

- **Two tests with Remi (22:12 and 22:15).** The headset keeps its own idea of whether music
  plays. With the Now Playing owner reporting "paused" and ten seconds of silence, two dockings
  sent nothing and two presses arrived as `Play`; four seconds after speech a docking still sent
  `Pause`. So the cause of the phantom was the button app saying "playing" all day.
- **The button app since 22:50** says "playing" only to take the buttons (`claimNowPlaying`), then
  rests in "paused" 0.4 s later (`settle`), and repeats playing-then-paused after every command
  and on `SIGUSR2` (`ctl.sh settle`, sent by `say_now.sh` when a message ends). `Play` is a press
  (`single`); `Pause` is handed to `on_gesture.sh` as `pause`, which decides: something playing
  or recording, or a message ended less than 8 s ago (`SECRETARY_PAUSE_IS_PRESS_S`): a press;
  otherwise the headset was put away: refuse tone, no dictation. Measured with the watchdog
  test: resting in "paused" loses the buttons at once to an app that is really playing, so after
  two such losses the app holds "playing" for 120 s (`EARBUDS_HOLD_PLAYING_S`), the behaviour of
  before, and tries to rest again later. `EARBUDS_REST_PAUSED=0` restores the old behaviour.
  `ctl.sh settle` does nothing unless `runtime/earbuds/supports_settle` exists: an older build
  does not handle `SIGUSR2` and would be killed by it. The previous binary is kept as
  `runtime/earbuds/EarbudButtons.prev`. Test: `bash local_tests/test_pause_gesture.sh`.
- **Rule from Remi the same evening: never lose data, never decide silently.** The "phantom
  start" handling deletes nothing (audio and the explicit no-speech transcript are always kept)
  and queues a note telling him; only the cues are skipped.
- **The freeze at 22:20.** Panic report: `no checkins from watchdogd in 91 seconds`; memory
  snapshot: 14 MB free, 1.4 MB of file cache, 19.3 GB in the compressor on a 36 GB machine. The
  kernel had been killing idle processes since 22:09:30. Holders: one Firefox content process
  at 24 GB (17 s of CPU: one page that ballooned), two `python3.12` jobs at 18.3 and 11.5 GB
  (never identified: the last minutes of the system log were not persisted), Docker's VM at
  5 GB. **Correction found an hour later, from the first line of the new memory log:** the
  builder's own test suite was a contributor. `test_ping_ignored.sh` used `/usr/bin/true` as the
  voice command; it produces no file, so `render_speech` fell through to the REAL Kokoro fallback,
  and every run (from 18:35 on, about ten runs that evening) started real Kokoro daemons, in
  racing pairs, 2 GB each at birth, never stopped, and rendered on them (Kokoro's pid file was
  rewritten at 18:35 and 22:46, both times within seconds of that test). At least five of the
  ten `python3.12` processes in the snapshot fit that pattern, and the 18 GB one may be such a
  daemon grown by renders (not proven). Fixed at the root: in any runtime other than the live
  one `render_speech` refuses the real engines and has no fallback (`SECRETARY_ALLOW_REAL_VOICE=1`
  overrides); after a full run of the suites no daemon is started and Kokoro's files are
  untouched. `memory_guard.sh` also ends orphan voice daemons (any beyond the one in the pid
  file) and caps both daemons at 4 GB. Its process matching is anchored on the daemons' own
  interpreter path: a bare `pgrep -f name` matches any shell whose command line contains the
  name, and the first version ended the shell that ran it. The button app and scripts
  themselves held only a few MB; Kokoro's daemon was at 2 GB and
  the Pocket daemon at 4.7 GB at most (it starts at 0.85 GB, so it grows). To read such a report:
  the `.panic` file is a JSON header line plus a JSON body with `panicString`, `memoryStatus`
  and `processByPid` (`residentMemoryBytes`, `procname`, CPU times). Lesson for this layer:
  scratch files under `/tmp` do not survive a reboot, so backups of live files belong in
  `runtime/`.
- **Memory guard** (`scripts/mac/secretary/memory_guard.sh`, started in the background by the
  Stop hook at the end of every session turn): reads `kern.memorystatus_vm_pressure_level` and
  the compressor size; at warning level or past 35 % of RAM compressed it raises health flag
  `memory`, plays the failure buzz and says once per episode (again every 10 minutes) which
  three programs are the biggest. It never kills anything. Exception inside our own system: the
  Pocket voice daemon is restarted when it has grown past 4 GB and nothing speaks or renders.
  `memory_guard.sh --status` prints one line. Test: `bash local_tests/test_memory_guard.sh`.
  Readings use `/usr/sbin/sysctl` and `/usr/bin/vm_stat` by absolute path and a reading that is not
  four plain numbers (or a compressor larger than the RAM) is "unknown" and decides nothing
  (2026-09-24 09:06: one failed sysctl made the RAM size 1 byte and a false "short of memory").
  Limit: no check while every session is idle.

## A dictation stopped by itself: an Escape from elsewhere (2026-09-23)

At 10:23:49 a keyboard-started headset dictation stopped mid-sentence with no button pressed.
The Bluetooth log shows no hang-up; the recorder's own log says `Stop requested via escape`,
and the audio "routing request" from a Python process that the secretary noticed was the
recorder itself closing its stream. The recorder's Escape listener (`pynput`) sees every key
event on the Mac, wherever it was aimed: a human Escape in another window or a script's
synthetic keystroke (`System Events`) stops the dictation. An `osascript` launched from an iTerm
shell asked for input-monitoring rights 1.6 s before, which is what keystroke automation needs;
no session transcript shows the command, so the sender is not known (excluded: the secretary, whose only
keystrokes that morning were an iTerm `write text` at 10:17, which never reaches the key listener;
the Tower; and every script of this repository).

- **Escape guard, OFF by Remi's decision the same day** (he wants Escape anywhere: he starts talking, goes back to something else and presses the key from there; `VOICE2CLIPBOARD_ESCAPE_ANYWHERE=0`
  turns the rule on). `escape_counts` in the recorder: in headset mode an Escape counts only when
  iTerm is the frontmost app and its current session is the recorder's own window
  (`ITERM_SESSION_ID` of the worker window); anything else, or a failure to tell, is logged as
  `Escape key seen while the recorder window is not in front ... ignored` and the recording goes
  on. Manual mode keeps "Escape anywhere". Test: `python local_tests/test_escape_guard.py`.
- **Dings wait for a dictation to end** (`ding.sh`, `DING_DEFERRED`): the 2026-09-18 rule "dings
  may sound at any time" now excludes a running recording (the ding at 10:22:51 played into this
  one). Speech never did. Test in `test_secretary_robustness.sh`.
- `press decision: stop (1 press)` in `secretary.log` also covers an Escape: the arbiter counts
  it as a press. Read the worker log (`/tmp/voice2clipboard_quick_autopaste.log`, `Stop
  requested via ...`) for the real source.

## A dialog in the secretary's window swallowed two hours of input (2026-09-22)

Between 21:33 and 23:16 the secretary took no typed input: a 54 s dictation (21:36), two agent
reports (21:51, 22:48) and three socket messages never became turns. Cause, from Claude Code's
prompt history (`~/.claude/history.jsonl`): `/usage` was submitted in the secretary's own window
at 21:35:04, 41 s before the dictation was typed. `/usage` (like `/help`, `/model`, `/config`,
`/memory`...) opens a full-screen dialog that stays until Escape; while it is open Claude Code
reports the session as `waiting` (its session file and the peer listing), every keystroke goes to
the dialog, and messages received over the socket are queued but not started. The recorder's
trace shows the paste and Enter were sent normally; the dialog ate them. The text was never lost:
`recordings/<date>/<time>/transcript.txt` has it, and the secretary re-sent it.

Guards, all live since 2026-09-23 10:30:
- **Verified delivery** (`deliver_to_claude_session` in `voice_transcriber.py`, used by the
  recorder in headset mode and by `ask_secretary.sh`): before typing, the window's screen must
  show the input prompt (`bypass permissions` footer or a `❯` line); if not, one Escape, which
  closes such a dialog. After typing and Enter, the message must appear as a user turn in the
  session's transcript (found through tty -> claude pid -> `~/.claude/sessions/<pid>.json` ->
  `~/.claude/projects/*/<id>.jsonl`, so a fresh secretary needs no registration); without a
  transcript, the text must have left the input box. Not consumed within 8 s
  (`VOICE2CLIPBOARD_DELIVERY_VERIFY_S`): Escape and one more attempt, never a third; then the
  existing undelivered path (failure buzz, text kept in the recordings folder and the clipboard,
  spoken note), and for reports `ask_secretary.sh` exits 4 so the hook posts to the inbox
  instead. Checked in a throwaway window with a real `/usage` dialog: Escape, delivered, 2.1 s.
- **At the press** `dictate_toggle.sh` runs `secretary_input_check.sh --clear` in the background:
  if the window shows no prompt or the session file says `waiting`, one Escape, logged.
- `secretary_input_check.sh` also feeds the health flag `secretary_input` and `selfcheck.sh`
  ("the secretary's window is not taking typed messages").
- Playback order (Remi, 2026-09-23): "N older waiting." is now said after the message, so a
  message can be stopped before the count and never waits behind it.
Tests: `python local_tests/test_verified_delivery.py` (window, keys and transcript simulated).
Known limit: a dialog that Escape does not close (a permission prompt in a non-bypass session,
an AskUserQuestion) still blocks; the failure is then loud instead of silent.

## Robustness (2026-09-19 pass)

Post-mortem of a morning with three lost or refused interactions, and what guards each now:

- **Secretary resumed by hand in another window.** `secretary_iterm_session` kept the closed
  window's id and the recorder's fallback pasted into whatever iTerm console was frontmost.
  Now: `register_secretary.sh` records the iTerm id, the Claude session id and the claude pid;
  the Stop and UserPromptSubmit hooks call it on every secretary turn (`ledger_lib.is_secretary`
  recognises the secretary by directory or by registered session id); `secretary_target_resolve`
  in `lib.sh` verifies the window before every press and heals a stale id from the environment of
  the secretary's running process. If the window is really gone: failure buzz, recording in
  `--copy-only`, queued note. In headset mode the recorder never falls back to a blind paste.
- **Headset dropped at the instant of the press.** The Bluetooth log shows the disconnect in the
  same 100 ms as the press; the Mac's own microphone then recorded an empty room for 14 minutes
  and the empty transcription crashed the recorder (and, through `set -e`, the worker before its
  recovery code). Now, in headset mode: the recorder refuses to start when the default input is
  not the headset (`VOICE2CLIPBOARD_HEADSET_PATTERN`, default `Shokz|OpenFit`); a hands-free
  disconnection line in the Bluetooth log stops a running recording and delivers what was said;
  60 s under 0.002 rms does the same (`VOICE2CLIPBOARD_SILENCE_STOP_SECONDS`, `_RMS`; measured
  pauses in real dictations: 14 s at most, silent recordings: about 0.0003 rms throughout); a
  recording without speech writes `[no speech detected]` to `transcript.txt` plus `stats.json`
  and queues a note instead of crashing.
- **Recorder window closed, next press refused in silence.** The 20 s pending marker outlived
  the recorder. Now the recorder worker owns the state: it removes the marker when its lock
  exists and in its exit trap (closing the window is a cancel: recorder killed, audio kept), the
  marker alone is trusted for 5 s (`SECRETARY_PENDING_MAX_S`), `dictate_toggle.sh` clears it when
  the launcher fails, `on_gesture.sh` uses the same `dictation_active` as everything else, and
  any refused press plays `sounds/cue_refuse.aiff` (`refuse_cue`, reason in `secretary.log`).
- **Start cue lost at the edge of range.** The cue plays when the stream opens, but the headset
  hears it only once its hands-free audio link is up. `confirm_headset_route` reads the Bluetooth
  log (`Received voice audio connected event`) and replays the cue once when the link came up
  more than 350 ms after the cue started; both outcomes are logged. Packet loss on a link that
  is already up is not detectable this way (the headset reports no usable signal strength).
- **Stop cue not heard.** Not a matter of length. When a recording's microphone opens,
  coreaudiod's Bluetooth layer sometimes logs `StartIO bypass, waiting i/o codec synchronzied`;
  the start cue's StopIO then skips the decrement of the hands-free profile's stream count
  (`StopIO on profile tsco, activeIO:2` when the microphone closes, instead of 1). For those
  recordings (7 of about 17 on 2026-09-19) the stop cue's stream is accepted but never runs:
  `IO Stopped Context N after 320 frames`, one buffer, where a heard cue shows 30 000. In headset
  mode the recorder's confirmation cues (`record_stop`, `done`, `record_lost`) now go through
  `play_cue_verified.sh`, which looks up its own afplay in the coreaudiod log and replays the cue
  (twice at most) when the stream never ran; replays are written to `secretary.log` as `cue ...`.
- **Reconnect.** EarbudButtons also registers IOBluetooth connect and disconnect notifications
  and calls `on_headset.sh`: on disconnect it stops a running dictation and any speech; on
  connect it re-asserts Now Playing, waits 3 s, and runs `selfcheck.sh --speak` (button app,
  secretary window, Kokoro, default input, recorder): `cue_ready.aiff`, or the failure buzz and a
  spoken list of problems. `selfcheck.sh` can be run by hand. macOS may ask once whether
  EarbudButtons may use Bluetooth.

Tests: `bash local_tests/test_secretary_robustness.sh` and
`python local_tests/test_recorder_robustness.py`.

## "The buttons are dead" (2026-09-20): it was the volume

Reported as two hours without working buttons. The unified log said otherwise (use
`/usr/bin/log`: in zsh, `log` is a builtin and prints nothing useful). bluetoothd logs one
`Received AVRCP <command>` line per press and mediaremoted names the app it forwards it to: all
three presses of that period arrived and were executed. What was broken was sound. The evening
before, the keyboard's volume-down key had taken the headset's music (A2DP) volume to zero and
muted it (coreaudiod, category `BTAudio`: `Scalar volume ... -> 0.000000`, `Set muteControl
... to 1`, from loginwindow). Messages, dings and cues then played into silence, while dictation
cues were heard: in call mode the headset is another audio device with its own volume. Every
piece of feedback being sound, a silent output looks exactly like dead buttons.

- **Volume guard** (`ensure_audible` in `lib.sh`). When the default output is the headset and
  it is muted or at most 3 %, it is unmuted and lifted to 30 %
  (`SECRETARY_OUTPUT_RESTORE_LEVEL`); nothing is ever lowered and other outputs are left alone.
  Called on every press (`on_gesture.sh`), before any speech (`say_now.sh`) and by the reconnect
  self-check. A ding only reports (`ensure_audible --report`): a deliberate zero is not undone by
  an unsolicited sound, but the log and the health flag `output` say that dings are not heard.
  Cost when all is well: one `osascript` call, 0.13 s. `SECRETARY_VOLUME_GUARD=0` disables it.
- **Health flags**: `runtime/secretary/health/<topic>` holds a timestamp, a tab, then `ok` or a
  one-line problem (`output` from the volume guard, `nowplaying` from the button app).
  `selfcheck.sh` reports every topic that is not `ok`; outside tools (the Session Tower) can read
  the directory.
- **Discard is confirmed**: a double press on a playing or paused message now plays
  `cue_cancel.aiff`. On a paused message it used to be a press with no audible effect at all.
- **Now Playing, while looking.** Not the cause, but tested with two silent clients
  (`local_tests/nowplaying_client.swift`): the app that last started playing owns the buttons and
  keeps them while paused, until it quits; re-sending the Now Playing info or setting
  `.playing` again takes nothing back, only a paused -> playing transition does. The old
  re-assert therefore never reclaimed anything. EarbudButtons now claims that way (start,
  headset connect, SIGUSR1) and follows mediaremoted's `ActiveNowPlayingClient changed from X
  to Y` line through a `log stream` child (the private MediaRemote queries return nothing to
  unentitled apps since macOS 15.4). What it does with a change of owner was redesigned the same
  evening: see "The buttons are always ours" below.

### No silent press, and the end of a message (same day)

Audit of every press path, asked by Remi (no press may stay silent: he must always know which
state the system is in). Measured first: from a single press to the start cue takes 1.0 s (median of
9 dictations, 1.6 s at worst; press time from `earbuds.log`, cue time from bluetoothd's
`Received voice audio connected event`). The `start cue route confirmed` line in `secretary.log`
is written a second or more after the cue and is no measure of it. What was silent:

- **The tail of a message.** afplay outlives its sound by more than a second (a 1.1 s cue keeps
  it alive 2.3 s). During that tail a message still counted as playing, so a single press meant
  "pause", in silence, and the next one "resume", in silence: that is the feeling of having to
  wait a few seconds after a message, and half of all pauses in the log were followed by another
  press within 6 s. Now `say_now.sh` starts a sound clock (`tts.clock`: seconds of sound left,
  frozen while paused; `tts_pause`, `tts_resume`, `tts_sound_over` in `lib.sh`), and a press
  with under 0.3 s of sound left (`SECRETARY_TTS_TAIL_S`) ends the player and is handled as if
  idle: a single press starts a dictation.
- **End tone.** Every spoken message ends with `sounds/cue_message_end.wav` (0.2 s of silence,
  then a 90 ms soft tone), joined to the audio so that it plays only at the natural end, never
  after a stop or discard. A pause inside a message no longer sounds like its end; the tone is
  the moment from which a single press dictates. `SECRETARY_END_TONE=0` disables it.
- **Press while the voice is still being rendered** (state `preparing`): a single press used to
  freeze the renderer's shell. It now plays the refuse cue.
- **Voice failure after a press** (`say_now: kokoro failed`): now plays the failure buzz.
- **Discarding** a message: cancel cue (above). **Volume at zero**: volume guard (above).
- `say_now.sh` only removes pid, state and clock files that are still its own: an interrupted
  message could erase the next message's files when it exited, leaving it invisible to the buttons.
- **A sound he did not cause.** Restarting the button app with the headset on played the ready
  cue, and he went looking for a message. The app now tells `on_headset.sh` `present` instead of
  `connected` for devices reported during its Bluetooth registration (that call can take 10 s on
  the first launch of a new build, so time since process start is useless), and the self-check
  then runs with `--speak-problems`: silent when ready.
- Still not answerable with a sound: a press that never reaches the Mac (another app owns the
  buttons, headset out of range). The watchdog and the reconnect check cover those.

Rule for anyone editing these scripts: they are live. Bash reads a script as it runs, so write to
a temporary file and rename it over the original; never rewrite in place (a running `say_now.sh`
died of exactly that on 2026-09-20).

Tests: `bash local_tests/test_message_tail.sh` (stand-in player and recorder, silent),
`bash local_tests/test_volume_guard.sh` (stubbed volume control, silent) and
`bash local_tests/test_nowplaying_watchdog.sh --borrow-the-buttons` (silent, but the buttons go
to test processes for 30 s: never while the earbuds are in use).

## The buttons are always ours (2026-09-20 evening)

Three different causes produced the same symptom on 2026-09-20, earbud buttons that do nothing:
the volume at zero (morning, above), another program holding the headset microphone (18:10, next
section) and another app owning Now Playing (20:00). Triage, in this order, with `/usr/bin/log`:

1. No `Received AVRCP ... command` lines from bluetoothd while he presses, and
   `runtime/secretary/headset_mic` says `open` with no dictation: call mode (next section).
2. AVRCP lines present but no `gesture` line in `earbuds.log`: another app owns Now Playing
   (`health/nowplaying`, and the `Now Playing taken by` lines in `earbuds.log`).
3. Both fine: the sound (`health/output`, `osascript -e 'get volume settings'`).

**What happened at 20:00.** QuickTime, with a paused video, owned Now Playing for 3.5 minutes; six
presses went to it. The take-back of that morning waited for 30 s of silent output
(`kAudioDevicePropertyDeviceIsRunningSomewhere` on the default output), and that silence never
came: a Firefox tab kept an output stream open on the headset for hours (coreaudiod showed
`Play: 2` when QuickTime stopped; the CoreAudio process list names the holder). Any rule that
depends on "nothing is playing" is at the mercy of every program on the Mac.

**Policy now** (Remi: he never uses the earbud buttons for media, so "during a video a press
pauses the video" is withdrawn). While the headset is connected:

- another app takes the buttons: they are taken back 0.5 s later (`EARBUDS_RECLAIM_DELAY_S`),
  whatever is playing. An app that insists (five thefts within a minute, as when scrubbing a
  video) is answered with a growing delay, 10 s at most, and the log switches from one line per
  theft to a count every ten minutes;
- every 60 s (`EARBUDS_ASSERT_EVERY_S`) the claim is repeated even when all looks well, in case
  the log stream missed a line. Measured with a second "playing" client: this causes no change
  of owner and no log line;
- a claim that does not take is retried every 5 s, and after 15 s (`EARBUDS_STUCK_AFTER_S`) the
  health flag `nowplaying` says so; it is `ok` otherwise, and only rewritten when it changes.

A claim is two property writes in our own process (paused, then playing). Nothing is sent to the
other app: the test client that loses the buttons receives no command and stays "playing", and
macOS has no audio interruption tied to Now Playing, so a video keeps playing at its volume.
Dictations and our own speech are not concerned: in call mode no media command exists anyway, and
`afplay` is not a Now Playing client. Without the headset nothing is taken back, so the
keyboard's play key keeps resuming his video. Side effect to know: with the headset on, the
keyboard's play key also goes to the secretary (a dictation starts).

Test: `bash local_tests/test_nowplaying_watchdog.sh --borrow-the-buttons` (silent; the buttons
go to test processes for 30 s, so only with the secretary's go).

## Call mode without a dictation (2026-09-20 evening)

At 18:10 a robot daemon opened the Mac's default microphone, which was the headset. The headset
then sat in call mode with no dictation running: it keeps double presses to itself, sends a
single press as a hang-up, and no media command reaches the Mac. Signature in the system log:
bluetoothd `Number of SCO Connections: 1` and coreaudiod `HFPInputShimDevice: StartIO` while
`secretary.log` shows no dictation.

- **Detection.** EarbudButtons polls CoreAudio every 5 s (no permission needed, a few property
  reads): is the headset's input device running, and which processes run input on it
  (`kAudioHardwarePropertyProcessObjectList`, `kAudioProcessPropertyIsRunningInput`, macOS
  14.2+). On a change it writes `runtime/secretary/headset_mic` (`<time> TAB open TAB
  <pid>:<exe>,...` or `closed` or `absent`), logs `headset microphone open: ...` to
  `earbuds.log` and calls `on_headset.sh mic-open` or `mic-closed`.
- **Judgement** is in `lib.sh` (`callmode_problem`): open microphone and `dictation_active`
  false is the problem. The holder is named the way Remi would say it (`process_friendly_name`:
  the app bundle, or for an interpreter the script or module it runs, so "reachy mini daemon"
  rather than "python3.12"). Health flag `callmode`: `ok`, or one line with the name.
- **Telling him** (`on_headset.sh mic-open`, after 8 s of grace, `SECRETARY_CALLMODE_GRACE_S`,
  because the recorder opens the microphone before its lock exists and some programs only probe
  it): failure buzz and one short sentence, "Buttons off: Firefox has the microphone." (Remi,
  2026-09-23, after hearing the long first version while talking to a web page through Firefox:
  keep it, but the program's name and the fact only). Browser helpers are named by their app. Sound does
  reach him in call mode, as the dictation cues show. Once per episode; the same program again
  within 10 minutes is flagged but not spoken (`SECRETARY_CALLMODE_REPEAT_S`); programs that look
  like a real call (`SECRETARY_CALLMODE_QUIET_APPS`: Zoom, FaceTime, Teams, ...) are flagged,
  never spoken into. When the microphone closes after an announced episode: ready cue.
- `selfcheck.sh` evaluates this on the spot (not from the flag), and the triple-press status
  query now asks the secretary to run `selfcheck.sh` first and say its problems in plain words.
  In call mode a triple press cannot arrive, so that path serves dictated or typed questions.
- Do not take the end of a dictation from the `press decision: stop` line of `secretary.log`
  (it is only written when a press ended the recording; a keyboard stop, the silence rule or a
  lost input leave none): use the lock (`recorder_alive`).

Test: `bash local_tests/test_callmode_watch.sh` (silent: state file written by hand, stand-in
voice, stubbed `ps`). Verified live only for the harmless half: a real dictation is reported as
`open <pid>:Python` and judged fine. The foreign-program half cannot be tested without opening
the real microphone, which is not done without Remi.

**Root fix, proposed, not applied.** The recorder opens the *default* input
(`sd.InputStream` without a device), and refuses to start in headset mode when the default
input is not the headset. Any program that opens the default microphone therefore puts the
headset in call mode. The fix would be: the recorder selects the headset input by name, the
default input is put back on the MacBook microphone at every headset connect (macOS moves it to
the headset each time, so this needs a small CoreAudio setter in the button app or a helper),
and `selfcheck.sh` checks "headset input present" instead of "default input is the headset".
Not done on 2026-09-20 because it changes the recorder, which cannot be tested without the live
microphone, and because it changes which microphone his video calls use by default: it needs
Remi's yes and one supervised test dictation.

**Rebuilding the button app costs a click.** The bundle is ad-hoc signed, so every new build is
new code for macOS privacy: it asks again whether EarbudButtons may use Bluetooth, and the app
blocks on that question before it serves any button (55 s of dead buttons on 2026-09-20 20:56
until Remi clicked Allow). Never rebuild when he is away from the screen; batch changes into one
build. A stable self-signed code-signing identity (none exists in the keychain today) would stop
the repeated question; moving the Bluetooth registration off the start-up path would stop the
blocking. Replace the binary with copy, rename, `codesign`, then `ctl.sh restart`.

## Boot, rotation, dictionary

- **Login:** `scripts/mac/secretary/secretary_ctl.sh install-boot` installs a LaunchAgent that,
  20 s after login, warms Kokoro, starts the earbud app and opens the secretary in iTerm.
- **Rotation:** the secretary's own Stop hook sums the last turn's `input + cache_read +
  cache_creation` tokens from its transcript; past `SECRETARY_ROTATE_TOKENS` (700k of the 1M
  window) it queues a note, runs `start_secretary.sh --rotate` (new session registered first,
  old window closed 20 s later). The secretary keeps `runtime/secretary/handover.md` for its
  successor and reads it plus the ledger on start.
- **Dictionary:** `secretary/dictionary.json`; `dictionary.py transcribe` fixes dictations
  (applied in the recorder before pasting), `dictionary.py pronounce` rewrites words for Kokoro
  (applied in say_now.sh). Add entries as mistakes recur.

## Lazy rotation at the press (2026-09-20)

Remi declined a nightly rotation: he values one secretary with a long memory. The decision is
taken at the moment he presses to dictate, the one moment it is certain he is about to talk to
the secretary, and the recording itself buys the time to boot a successor.

- **Who decides.** The Session Tower owns the cost maths:
  `/Users/remi/claude_control_center/bin/tower rotate-advice` prints one line, `rotate <reason>`
  or `keep <reason>` (20 ms, from its cached snapshot; `--json` gives the numbers). Its policy,
  in his words: warm means keep, whatever the size; cold means rotate only when waking the old
  context costs more than onboarding a fresh one (its `cold_tick`). `lazy_rotate.sh` waits 1.5 s
  at most and treats anything else (Tower down, slow, nonsense) as keep.
- **What happens on rotate** (`scripts/mac/secretary/lazy_rotate.sh`, started in the background
  by `dictate_toggle.sh`, so the start cue never waits): a fresh secretary is opened with
  `bin/spawn-session` (own window, on the workspace `bin/pick-space` chooses: the first of 3, 4, 5,
  6 with fewer than 6 terminal windows, Remi's cap of 2026-09-24; tiled, danger mode), the script waits for its
  input box (screen contains `bypass permissions on`) plus 3 s, then publishes the hand-over and
  switches `secretary_iterm_session`. Measured with a real window: 6 s from the press. The old
  window is closed 20 s after the dictation is over. The successor reads
  `runtime/secretary/handover.md` on its first message, as after any rotation.
- **No dictation can be lost.** Hand-over files live in `runtime/secretary/lazy_rotation/`:
  `pending` (old id) while the successor boots, `ready` (old and new id) once usable. The
  recorder (`rotation_redirect` in `voice_transcriber.py`) sends to the new session when `ready`
  names its target and that window is alive; if the transcript is there first it waits up to
  30 s (`VOICE2CLIPBOARD_ROTATION_WAIT_S`), then renames `pending` to `aborted` and delivers to
  the old secretary as always, and the rotator closes the new window. The rotator publishes
  with rename `pending` to `publishing`, then `ready.tmp` to `ready`: whoever renames `pending`
  first wins, so both sides always agree. Spawn failure, a successor that never gets ready, an
  error in the redirect, leftovers of a dead rotator: all end with the old secretary registered
  and untouched.
- What he hears: nothing new. Only when the dictation is shorter than the boot, the pause
  between the stop cue and the sent sound is longer, and the first answer comes from a secretary
  that has just read the handover.
- `SECRETARY_LAZY_ROTATION=0` switches it off. The 700k end-of-turn rotation in `stop_hook.sh`
  stays as the safety net. Every decision is one line in `secretary.log` (`lazy rotation: ...`);
  the Tower agent uses the "ready and registered" line to measure the successor's onboarding.
- Known limit: agents that answer the old secretary by session name after it was closed reach
  nobody; the handover file has to carry what was pending.

Tests: `bash local_tests/test_lazy_rotation.sh` (stand-ins for the Tower, the spawner and iTerm)
and `python local_tests/test_rotation_redirect.py`. Verified with real windows on 2026-09-20:
spawn, ready detection, typed input accepted, close. Not verified until a real cold morning:
the whole chain with a real dictation.

## Daily use

```bash
scripts/mac/earbuds/ctl.sh status            # button app (launchd, starts at login)
scripts/mac/secretary/start_secretary.sh     # opens the secretary window, voice mode on
scripts/mac/secretary/voice_mode.sh status   # on = hooks queue spoken messages
scripts/mac/secretary/stop_secretary.sh      # unregister, voice mode off
tail -f runtime/secretary/secretary.log       # what was said, queued, pressed
scripts/mac/earbuds/ctl.sh logs              # raw commands received from the headset
```

First use: macOS asks once whether EarbudButtons may control iTerm2 and System Events (the
dictation path uses AppleScript). Accept both. Hooks only apply to Claude Code sessions started
after they were registered; open `/hooks` in an older session to reload them.

## Two modes: headset and manual

| | Headset mode | Manual mode |
|---|---|---|
| how it starts | a dictation started from an earbud press | a dictation started from the keyboard shortcut |
| where text goes | the secretary session | the app or console that was frontmost |
| notifications | decided by the secretary from agent reports (both modes) | same: the mode no longer changes notifications |
| switch | `voice_mode.on` exists (`voice_mode.sh on`) | flag absent (`voice_mode.sh off`) |

The mode flips automatically with the next dictation of the other kind and persists in between,
so an earbud dictation followed by keyboard work leaves headset mode the moment the first
keyboard dictation starts. The recorder window prints `Mode: HEADSET` or `Mode: MANUAL` at
every start; `voice_mode.sh status` prints it too. `start_secretary.sh` switches to headset
mode, `stop_secretary.sh` to manual.

## Attention ledger (both modes)

Every session's Stop hook writes its latest message to `runtime/secretary/ledger/<session>.json`
(project name, summary, `needs_attention` when the message ends with a question or asks for a
decision); the Notification hook flags permission prompts and input requests; the
UserPromptSubmit hook clears the flag as soon as Remi talks to that session. This runs silently
in both modes; only headset mode adds the ding and the spoken queue. `ledger.sh` prints it,
sessions waiting on Remi first. Triple press, or asking the secretary "what needs my
attention?", reads it aloud. The project `voice2clipboard` is reported as "the secretary".

## Collision rules (Remi, 2026-09-18)

One voice message at a time, enforced by an atomic lock in `say_now.sh` (taken before synthesis,
released at the end or when a press stops it). Press-driven playback interrupts; direct speech
that would collide waits and plays right after the current event. Dings may sound at any time,
rate-limited (`SECRETARY_DING_COOLDOWN_S`, 20 s). Every played or discarded message stays in
`runtime/secretary/spoken/` with a status line (pruned past `SECRETARY_ARCHIVE_MAX_MB`);
`messages_search.sh` searches it on request. Long presses are not an action: the recorder stops
on the hang-up only.

## Notifications (Remi, 2026-09-18): the secretary decides

Hooks never ding on their own. A flagged turn is handed to the secretary, which notifies only
when the session is waiting on Remi, the report answers a voice-routed request, or the content
is important. Routine completions of keyboard-driven work stay in the ledger for the triple
press. Overrides per project: `secretary/notify_overrides.json`. If no secretary session is
running, a session waiting on Remi posts directly so it is not lost.

## Notification rule (Remi, 2026-09-17)

Silence means success. Nothing speaks to Remi on its own: agent reports and the secretary's
news go to the inbox with a ding, and he double-presses to hear the latest one. Direct speech
(`say_now.sh`) is reserved for problems, genuinely important items, or a session that
explicitly asks to talk to him.

## Agent side

`~/.claude/CLAUDE.md` tells every agent: when `voice_mode.on` exists, end the final message with
a `Spoken:` paragraph sized to the situation. The Stop hook reads that paragraph, else the first
70 words of the message. `crossSessionInbound` is set to `accept` in user settings so the
secretary's messages are delivered without approval.

## Verified 2026-09-17

- Probe: single/double/triple presses arrive as pause/nextTrack/previousTrack.
- Relay: `[Voice]` dictation → secretary → SendMessage to a project session → reply → spoken
  back, 12 s end to end.
- Hook: Spoken paragraph extracted, markdown fallback, subagent payloads ignored.
- Pause/resume of speech with SIGSTOP/SIGCONT on afplay.

Not yet verified with a human: a real earbud dictation through the launchd-started app (TCC
prompts), and whether presses still arrive while the headset mic is in hands-free mode during
a recording. If they do not, stop the dictation with the keyboard shortcut.
