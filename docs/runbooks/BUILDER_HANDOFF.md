# Secretary builder: handoff for a fresh session (any account)

Written 2026-09-23 by the builder session, on Remi's order that every agent be ready to be
restarted from another account. Everything a successor needs is in this repository; the
per-account memory notes under `~/.claude/projects/-Users-remi-voice2clipboard/memory/` are a
convenience, not a requirement. Read in this order, nothing more than needed:

1. `CLAUDE.md` at the repo root: this repo is public; never commit a transcript or a dictated
   sentence; recordings and adjudicated files stay under `recordings/` and `benchmarks/private/`.
2. `docs/runbooks/VOICE_SECRETARY.md`: the whole earbud system, one dated section per change,
   each with the incident that caused it, the mechanism, and the test. Newest sections are near
   the top half (2026-09-20 to 2026-09-23).
3. `secretary/CLAUDE.md`: the secretary session's own rules (routing, voice, notifications).

## What is live and where

| Piece | Files |
|---|---|
| Earbud buttons (Now Playing app, resting in "paused") | `scripts/mac/earbuds/EarbudButtons.swift`, `ctl.sh`, built into `runtime/earbuds/`; previous binary `runtime/earbuds/EarbudButtons.prev` |
| Gesture router, dictation start, lazy rotation | `scripts/mac/secretary/on_gesture.sh`, `dictate_toggle.sh`, `lazy_rotate.sh` (asks `~/claude_control_center/bin/tower rotate-advice`) |
| Recorder (headset mode, verified delivery, hold-to-cancel, phantom starts, Escape guard) | `apps/linux/legacy_whisper/voice_transcriber.py`, launched by `scripts/mac/legacy_mlx_toggle_autopaste*.sh` |
| Speech: inbox, pre-render, loudness, pause/resume, sticky voices | `inbox_post.sh`, `inbox_read_next.sh`, `say_now.sh`, `speech_render.py`, `voices.py`, `secretary/voices.json` (+ untracked `runtime/secretary/voices.learned.json`) |
| Hooks (ledger, reports to the secretary, keep-warm pings ignored, memory guard) | `stop_hook.sh`, `user_prompt_hook.sh`, `notification_hook.sh`, `ledger_lib.py`, `memory_guard.sh` (also run every minute by the Tower) |
| Health flags read by the Session Tower | `runtime/secretary/health/<topic>`: `nowplaying`, `callmode`, `output`, `memory`, `secretary_input` |
| Self-check and window checks | `selfcheck.sh`, `secretary_input_check.sh`, `on_headset.sh` |

Voice engine: Kyutai Pocket TTS daemon in `/Users/remi/local-tts-lab` (`bin/pocket-say`,
`bin/pocket-ctl`), Kokoro as fallback. The variable names in `lib.sh` still say KOKORO.

## Rules that are not derivable from the code

- Everything under `scripts/mac/secretary/` and the recorder is LIVE while Remi wears the
  earbuds: replace files atomically (temp file next to it, `bash -n`, `mv`), never in place, never
  while `audio_busy` (lib.sh) is true. A rebuild of the button app makes macOS ask the Bluetooth
  question again and the buttons are dead until Remi clicks Allow: only with him at the screen.
- Never use the live microphone or play sound into the earbuds for a test. Every suite in
  `local_tests/` is silent and uses a scratch runtime (`SECRETARY_RUNTIME`), stand-in players and
  voices; `render_speech` refuses real voice engines outside the live runtime. Exception:
  `test_nowplaying_watchdog.sh --borrow-the-buttons` takes the buttons for 30 s: only with the
  secretary's go.
- Never lose data, never decide silently about a recording (Remi, 2026-09-21): audio and
  transcripts are always kept; suspicious cases are reported to him, not erased.
- The secretary is never rotated proactively; only at a dictation press when the Tower says the
  wake would cost more than a fresh start.
- Committing is Remi's decision. Do not stash, reset or checkout. About fifty files are
  uncommitted, deliberately.
- Heavy work (long log scans, big rewrites, research) goes to Opus subagents (Remi, 2026-09-23:
  his weekly Fable limit is near). Fable stays for judgement and the live system.
- Report to the current secretary session by SendMessage (name `secretary-XX`, find it with
  ListAgents; it changes at each rotation) with a paragraph starting `Spoken:` for his ears.

## Tests (all silent): run them all after any change

```
for t in local_tests/*.sh; do bash "$t"; done          # bash suites (skip test_nowplaying_watchdog.sh)
for t in local_tests/*.py; do /Users/remi/.virtualenvs/voice2clipboard/bin/python "$t"; done
bash scripts/mac/secretary/selfcheck.sh                # live, silent
```
Known flake: `test_prerendered_inbox.sh` fails one timing check about once in ten runs.

## Backups and rollback

`runtime/backups/<date>-<topic>/` holds the previous versions of files swapped that day (the
2026-09-23 set is under `2026-09-23-delivery`). `/tmp` is wiped at reboot: never keep backups there.

## Open items (2026-09-23)

- Root fix for call mode: keep the Mac's default input on the built-in microphone, recorder picks
  the headset by name. Proposed in the runbook, needs Remi's yes and a supervised dictation.
- Resting in "paused" loses the buttons to an app that really plays; the app then holds "playing"
  for two minutes. Acceptable to Remi so far.
- Bluetooth disconnect notifications of the button app almost never fire (needs a rebuild).
- The 10:23:49 Escape of 2026-09-23 could not be attributed; the guard makes it harmless.
