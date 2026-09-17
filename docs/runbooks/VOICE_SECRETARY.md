# Voice secretary runbook (earbuds ↔ Claude Code sessions)

Built 2026-09-17. Lets Remi drive Claude Code sessions from the Shokz OpenFit 2+ buttons
without being at the screen: dictate to a router session, hear replies through Kokoro TTS.

## Pieces

| Piece | Where | Role |
|---|---|---|
| EarbudButtons.app | `scripts/mac/earbuds/` (built into `runtime/earbuds/`) | Registers as the macOS Now Playing app so headset presses reach it; runs `on_gesture.sh`. launchd agent `com.voice2clipboard.earbuds`. |
| Gesture router | `scripts/mac/secretary/on_gesture.sh` | single → `tts_toggle.sh`, double → `dictate_toggle.sh`, triple → `tts_repeat_last.sh` |
| Spoken inbox | `inbox_post.sh`, `inbox_read_next.sh`, `say_now.sh`, `ding.sh` | Queue in `runtime/secretary/inbox/`, archive in `spoken/`. Speech = kokoro-say → wav → afplay (pid in `tts.pid`, pausable with SIGSTOP). |
| Hooks | `stop_hook.sh`, `notification_hook.sh` registered in `~/.claude/settings.json` | While `voice_mode.on` exists, every session's final message (its `Spoken:` paragraph if present) is queued with a ding; permission prompts and input requests too. Subagents and the secretary are skipped. |
| Secretary session | `secretary/CLAUDE.md`, `start_secretary.sh`, `stop_secretary.sh` | A Claude Code session (permissions skipped) whose only job is routing `[Voice]` dictations to the right project session with SendMessage and speaking back. |
| Dictation target | `legacy_mlx_toggle_autopaste.sh` honours `VOICE2CLIPBOARD_TARGET_ITERM_SESSION` | Earbud dictations paste into the secretary's iTerm session instead of the frontmost app. Keyboard shortcut behaviour unchanged. |

## Button map (Shokz OpenFit 2+, both earbuds identical)

The headset sends the same commands from either side: single press = play/pause, double = next
track, triple = previous track. Long press is volume on the headset only. What they do depends
on the state (`scripts/mac/secretary/on_gesture.sh`):

| State | single | double | triple |
|---|---|---|---|
| idle | start a dictation | hear the latest notification | ask the secretary for a status |
| dictating | (stop, keyboard path only) | (stop, keyboard path only) | ignored |
| message playing | pause | stop the message | stop + status |
| message paused | resume | stop the message | stop + status |

**While a dictation is recording, the headset is in hands-free mode** (macOS sets up a "virtual
call" with it, seen in the Bluetooth log at 21:47:06 on 2026-09-17). Its buttons then send call
commands instead of media commands, so the Now Playing app never sees them. The recorder
therefore watches the unified log (`/usr/bin/log stream`, process bluetoothd, category
Server.Handsfree) while recording: a press arrives as `Received call hangup event (AT+CHUP)`,
a long press as `Received speaker gain event` (right = up, left = down). Any of them stops the
dictation (verified live 21:53, single press). Escape in the recorder window also works. A
spoken stop phrase exists but is OFF by default at Remi's request (brittle); enable with
`VOICE2CLIPBOARD_STOP_PHRASES="roger stop"` in the helper's environment.

Sounds, all with a 350 ms silent lead-in because the earbuds swallow the head of short sounds:
`sounds/cue_start.aiff` (rising, mic is live), `cue_stop.aiff` (descending, recording ended),
`cue_ding.aiff` (two high notes, a spoken message is waiting). The transcriber's "done" sound is
still the system Glass sound.

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
