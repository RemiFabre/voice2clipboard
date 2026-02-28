# Stable Operations Guide

This is the single operational guide for daily usage.

## Mental model (what runs)
- `voxmlx server`:
  - process that hosts the realtime model endpoint at `ws://127.0.0.1:8000/v1/realtime`.
- `always-on daemon`:
  - this is your persistent microphone capture + transcription worker.
  - it acts as the realtime client to the server and writes transcript files.
- `manual realtime client` (`run_voxtral_realtime_client.sh`):
  - optional testing tool only; not required for daily always-on workflow.

For your default workflow, you need:
1. server ON
2. always-on daemon ON

You do **not** need to run the manual client.

## Current production path
- Realtime backend: `voxmlx` server (local).
- Always-on capture daemon: `tools/always_on_voxtral_daemon.py`.
- Marker-based clipboard capture: `always_on_mark_start.sh` / `always_on_mark_stop.sh`.
- Unified control entrypoint: `voice_control.sh`.

## One command set (use these)
From `/Users/remi/voice2clipboard`:

```bash
./voice_control.sh status
./voice_control.sh start
./voice_control.sh stop
./voice_control.sh restart
./voice_control.sh enable-autostart
./voice_control.sh mark-start
./voice_control.sh mark-stop
./voice_control.sh mark-status
./voice_control.sh mark-clear
./voice_control.sh logs
./voice_control.sh files
./voice_control.sh live
./voice_control.sh live-ts
./voice_control.sh live-tail
./voice_control.sh preview
```

## Does it auto-start on boot/login?
Yes, if LaunchAgents are installed and loaded:

```bash
./voice_control.sh enable-autostart
```

This installs:
- `~/Library/LaunchAgents/com.voice2clipboard.voxmlx.plist`
- `~/Library/LaunchAgents/com.voice2clipboard.alwayson.plist`

Both are configured with:
- `RunAtLoad = true`
- `KeepAlive = true`

Desired behavior for your setup:
- Turn on computer
- login
- server + daemon auto-start
- transcript files start updating without manual launch
- only use `mark-start` / `mark-stop` when you want clipboard capture windows

## How to check if server is running
Use:

```bash
./voice_control.sh status
```

Look for:
- LaunchAgent loaded/running (`com.voice2clipboard.voxmlx`)
- TCP check (best-effort): `voxmlx 127.0.0.1:8000 (best-effort): up`

## What `start` and `stop` do
- `./voice_control.sh start`
  - starts LaunchAgent for server (`com.voice2clipboard.voxmlx`)
  - starts LaunchAgent for daemon (`com.voice2clipboard.alwayson`)
- `./voice_control.sh stop`
  - stops both LaunchAgents above
- `./voice_control.sh restart`
  - reloads both (stop + start)

So `start/stop` control the **background services**, not marker windows.

## How to stop everything
Use:

```bash
./voice_control.sh stop
```

This stops:
- realtime server LaunchAgent
- always-on daemon LaunchAgent

## How to view transcript live (default verification)
Use:

```bash
./voice_control.sh live
```

This opens in VS Code:
- `runtime/always_on/live_text.txt` (rolling current text)
- `runtime/always_on/timeline/YYYY-MM-DD.txt` (daily append-only timeline)

If you want terminal tail mode:
```bash
./voice_control.sh live-tail
```

If you only want timestamps:
```bash
./voice_control.sh live-ts
```

## Temporary tuning UI (selection preview)
For boundary tuning sessions, use:

```bash
./voice_control.sh preview
```

Behavior:
- Gray text = outside current selection.
- Green text = inside current active marker window.
- This does not modify production pipeline behavior; it is read-only visualization.
- If `tkinter` is unavailable on your Python build, it auto-falls back to a local web UI.

Alternative in VS Code:
- open `runtime/always_on/live_text.txt`
- open `runtime/always_on/timeline/<today>.txt`

## Why `mark-stop` may “not work”
Common causes:
- No marker was started (`mark-start` missing)
- No transcript segments were produced between start and stop
- Daemon not running
- Hotkey not sending `F12` keycode (media-key mode / app capture)

Debug quickly:

```bash
./voice_control.sh mark-status
./voice_control.sh files
./voice_control.sh logs
tail -n 50 /Users/remi/voice2clipboard/runtime/always_on/toggle.log
```

## Important runtime files
- State: `runtime/always_on/state.json`
- Live text (current rolling text): `runtime/always_on/live_text.txt`
- Raw delta stream (fine-grained): `runtime/always_on/deltas.jsonl`
- Segments (JSONL): `runtime/always_on/segments.jsonl`
- Last copied text: `runtime/always_on/last_selection.txt`
- Marker state: `runtime/always_on/selection_marker.json`
- Marker latency metrics: `runtime/always_on/feedback_latency.jsonl`
- Daily timeline files: `runtime/always_on/timeline/YYYY-MM-DD.txt`

Clipboard marker selection note:
- Marker copy now prefers `deltas.jsonl` (fine-grained stream) for better boundary accuracy.
- Falls back to `segments.jsonl` if delta data is unavailable.
- Marker boundaries use symmetric lag compensation:
  - start boundary uses `press_start + boundary_pad`
  - stop boundary uses `press_stop + boundary_pad`
  - default: `boundary_pad=0.66s`
  - override via env var:
    - `VOICE2CLIP_BOUNDARY_PAD_S`

## Transcript partitioning (stability update)
- Transcript timeline is now one file per day:
  - `runtime/always_on/timeline/2026-02-28.txt`
  - `runtime/always_on/timeline/2026-03-01.txt`
- This avoids one giant file and simplifies navigation/search.

## Code modules: stable vs exploration
Stable operational modules:
- `voice_control.sh`
- `service_always_on.sh`
- `install_always_on_launchagents.sh`
- `run_voxmlx_server.sh`
- `run_always_on_voxtral_daemon.sh`
- `tools/always_on_voxtral_daemon.py`
- `tools/always_on_capture.py`
- `always_on_mark_start.sh`
- `always_on_mark_stop.sh`
- `always_on_status.sh`

Exploration/benchmark/research area:
- `benchmarks/`
- `docs/` files not named as runbook/operations
- `VOXTRAL_*`, `RESEARCH_*`, `LOCALVOXTRAL_*`
- benchmark scripts in `tools/benchmark_*` and related manifests

## Recommended daily flow
1. `./voice_control.sh status`
2. If down: `./voice_control.sh start`
3. Speak capture window:
   - `./voice_control.sh mark-start` (or hotkey `ctrl + slash`, right hand supported)
   - talk
   - `./voice_control.sh mark-stop` (or hotkey `ctrl + slash` again)
4. If issue: `./voice_control.sh logs`
