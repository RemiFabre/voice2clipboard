# Always-On Voxtral Runbook

## Goal
Keep local dictation always running, write transcript continuously to file, and capture intervals to clipboard via start/stop markers.

## Prereqs
1. `voxmlx` server available locally.
2. Python venv at `/Users/remi/.virtualenvs/voice2clipboard`.

## Start Services

### Terminal A: start local server
```bash
cd /Users/remi/voice2clipboard
./run_voxmlx_server.sh
```

### Terminal B: start always-on daemon
```bash
cd /Users/remi/voice2clipboard
./run_always_on_voxtral_daemon.sh
```

## Marker Workflow

### Start selection window
```bash
cd /Users/remi/voice2clipboard
./always_on_mark_start.sh
```

### Stop selection window and copy to clipboard
```bash
cd /Users/remi/voice2clipboard
./always_on_mark_stop.sh
```

### Status
```bash
cd /Users/remi/voice2clipboard
./always_on_status.sh
```

## Runtime Artifacts
- Live transcript: `runtime/always_on/live_text.txt`
- Committed segments: `runtime/always_on/segments.jsonl`
- Human-readable timeline (daily files): `runtime/always_on/timeline/YYYY-MM-DD.txt` (one line per sentence with ISO timestamp)
- Marker latency log: `runtime/always_on/feedback_latency.jsonl`
- Raw events: `runtime/always_on/events.jsonl`
- Daemon state: `runtime/always_on/state.json`
- Last copied selection: `runtime/always_on/last_selection.txt`

## Optional notification toggle
- Default behavior keeps macOS notifications enabled.
- To reduce UI overhead while testing latency:
```bash
VOICE2CLIP_NOTIFY=0 /Users/remi/voice2clipboard/always_on_mark_start.sh
VOICE2CLIP_NOTIFY=0 /Users/remi/voice2clipboard/always_on_mark_stop.sh
```

## Suggested Hotkeys (skhd)
Add these to `~/.config/skhd/skhdrc`:

```txt
# Start interval marker
cmd + shift - 9 : /Users/remi/voice2clipboard/always_on_mark_start.sh

# Stop interval marker + copy to clipboard
cmd + shift - 0 : /Users/remi/voice2clipboard/always_on_mark_stop.sh
```

Reload skhd:
```bash
launchctl kickstart -k gui/$(id -u)/com.koekeishiya.skhd
```

## Notes
- The daemon currently runs foreground in terminal; closing terminal stops it.
- LaunchAgent mode is now scripted.

## LaunchAgent Service Mode (Auto-start)

Install plist files:
```bash
cd /Users/remi/voice2clipboard
./install_always_on_launchagents.sh
```

Manage services:
```bash
./service_always_on.sh reload
./service_always_on.sh status
./service_always_on.sh stop
./service_always_on.sh start
```

This manages two services:
- `com.voice2clipboard.voxmlx`
- `com.voice2clipboard.alwayson`
