# Voice secretary runbook (earbuds ↔ Claude Code sessions)

Built 2026-09-17. Lets Remi drive Claude Code sessions from the Shokz OpenFit 2+ buttons
without being at the screen: dictate to a router session, hear replies through Kokoro TTS.

## Pieces

| Piece | Where | Role |
|---|---|---|
| EarbudButtons.app | `scripts/mac/earbuds/` (built into `runtime/earbuds/`) | Registers as the macOS Now Playing app so headset presses reach it; runs `on_gesture.sh`. launchd agent `com.voice2clipboard.earbuds`. |
| Gesture router | `scripts/mac/secretary/on_gesture.sh` | single → `tts_toggle.sh`, double → `dictate_toggle.sh`, triple → `tts_repeat_last.sh` |
| Spoken inbox | `inbox_post.sh`, `inbox_read_next.sh`, `say_now.sh`, `ding.sh` | Queue in `runtime/secretary/inbox/`, archive in `spoken/`. Speech = kokoro-say → wav → afplay (pid in `tts.pid`, pausable with SIGSTOP). |
| Hooks | `stop_hook.sh`, `notification_hook.sh`, `user_prompt_hook.sh` in `~/.claude/settings.json` | Every session's final message goes to the attention ledger. Flagged turns (question, decision, permission prompt, `Notify:` line, possible problem) are typed into the secretary session as an `[Agent report]`; the secretary decides whether Remi hears it, in the agent's voice. `secretary/notify_overrides.json` can force `always` or `never` per project. |
| Secretary session | `secretary/CLAUDE.md`, `start_secretary.sh`, `stop_secretary.sh` | A Claude Code session (permissions skipped) whose only job is routing `[Voice]` dictations to the right project session with SendMessage and speaking back. |
| Dictation target | `legacy_mlx_toggle_autopaste.sh` honours `VOICE2CLIPBOARD_TARGET_ITERM_SESSION` | Earbud dictations paste into the secretary's iTerm session instead of the frontmost app. Keyboard shortcut behaviour unchanged. |

## Button map (Shokz OpenFit 2+, both earbuds identical)

The headset sends the same commands from either side: single press = play/pause, double = next
track, triple = previous track. Long press is volume on the headset only. What they do depends
on the state (`scripts/mac/secretary/on_gesture.sh`):

| State | single | double | triple |
|---|---|---|---|
| idle | start a dictation | hear the latest notification | ask what needs your attention |
| dictating | (stop, keyboard path only) | (stop, keyboard path only) | ignored |
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

Voices: the secretary speaks first person in the default Kokoro voice (af_heart); each agent gets
a consistent voice from a stable hash of its name (`voice_for` in lib.sh) and introduces itself
in two words ("micro duck here."). French uses the single Kokoro French voice.

Sounds, all with a 350 ms silent lead-in because the earbuds swallow the head of short sounds:
`sounds/cue_start.aiff` (rising, mic is live), `cue_stop.aiff` (descending, recording ended),
`cue_ding.aiff` (two high notes, a spoken message is waiting), `cue_ack.aiff` (two soft ticks,
your double or triple press was received and the voice is being prepared). The transcriber's "done" sound is
still the system Glass sound.

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
