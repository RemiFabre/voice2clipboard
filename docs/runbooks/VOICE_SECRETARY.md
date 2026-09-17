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

| Press | Headset sends | Action |
|---|---|---|
| single | pause/play | pause speech; press again to resume; if nothing is playing, read the next queued message |
| double | next track | start a dictation to the secretary; double again to stop and send |
| triple | previous track | stop and repeat the last spoken message |
| long | volume up/down | changes headset volume only, never reaches the Mac as a command |

While another app is actually playing audio, macOS routes the buttons to that app. The button
app takes them back at start, after each gesture, or with `scripts/mac/earbuds/ctl.sh reassert`.

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
