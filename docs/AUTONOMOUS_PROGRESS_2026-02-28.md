# Autonomous Progress Log (2026-02-28)

## Scope Delivered Tonight
1. Realtime benchmark framework for Voxtral (`voxmlx`) vs Whisper backends.
2. Production-style always-on transcript workflow:
   - always-on daemon writes transcript to file continuously
   - marker start/stop extracts interval to clipboard
3. Persistent docs and runbooks written to repo.

## New/Updated Files

### Benchmarking
- `tools/benchmark_realtime_backends.py`
- `tools/build_benchmark_manifest.py`
- `run_benchmark_realtime_backends.sh`
- `benchmarks/manifest_template.jsonl`
- `benchmarks/manifest_generated.jsonl`
- `benchmarks/realtime_backends_smoke_escalated.json`
- `benchmarks/realtime_backends_batch_20260228.json`
- `benchmarks/realtime_backends_retry_voxmlx_20260228.json`
- `benchmarks/realtime_backends_batch_20260228_complete.json`
- `benchmarks/realtime_backends_batch_20260228_summary.md`

### Always-on production path
- `tools/always_on_voxtral_daemon.py`
- `tools/always_on_capture.py`
- `run_always_on_voxtral_daemon.sh`
- `always_on_mark_start.sh`
- `always_on_mark_stop.sh`
- `always_on_status.sh`
- `install_always_on_launchagents.sh`
- `service_always_on.sh`

### Voxtral runtime/client improvements
- `run_voxmlx_server.sh` (PATH includes `~/.local/bin` for `uvx` discovery)
- `voxtral_realtime_client.py` (handles `response.audio_transcript.delta` + clean shutdown)

### Documentation
- `docs/AUTONOMOUS_PROGRESS_2026-02-28.md` (this file)
- `docs/ALWAYS_ON_VOXTRAL_RUNBOOK.md`
- `docs/BENCHMARKING_RUNBOOK.md`
- `VOXTRAL_DEBUG_STATUS_2026-02-27.md` (updated)
- `LOCALVOXTRAL_RESEARCH_2026-02-27.md`

## Validated Outcomes

### 1) Voxtral realtime works with `voxmlx`
- WS endpoint handshake confirmed: `ws://127.0.0.1:8000/v1/realtime`
- Received realtime event: `session.created`
- Client no longer throws traceback on normal quit.

### 2) Benchmark harness works
Smoke benchmark report generated successfully:
- `benchmarks/realtime_backends_smoke_escalated.json`

Measured on `recordings/2026-02-27/17-09-26/audio.wav` (~21.8s):
- `voxmlx`:
  - first token: `~0.94s`
  - total: `~9.60s`
  - first-token RTF: `~0.043x`
  - total RTF: `~0.440x`
- `faster-whisper medium`:
  - first token: `~10.30s` (one-shot)
  - total: `~10.30s`
  - total RTF: `~0.472x`

Interpretation:
- End-to-end completion is similar.
- Realtime UX is dramatically better with Voxtral because first visible text appears much earlier.

Extended batch benchmark generated (18 recordings):
- Complete report: `benchmarks/realtime_backends_batch_20260228_complete.json`
- Human summary: `benchmarks/realtime_backends_batch_20260228_summary.md`

Key aggregate deltas (batch):
- Avg first-token advantage of voxmlx vs faster-whisper: ~`16.88s` earlier
- Avg total-time delta (faster - voxmlx): `-4.69s` (on this batch, faster-whisper finished earlier on average)

### 3) Always-on marker workflow works
Validated commands:
- `./run_always_on_voxtral_daemon.sh` starts daemon and writes runtime state.
- `./always_on_mark_start.sh` creates selection marker.
- `./always_on_mark_stop.sh` extracts selected interval and copies to clipboard (or returns no-segment code if nothing said).
- `./always_on_status.sh` shows daemon state and marker state.

Runtime files used:
- `runtime/always_on/events.jsonl`
- `runtime/always_on/segments.jsonl`
- `runtime/always_on/live_text.txt`
- `runtime/always_on/state.json`
- `runtime/always_on/selection_marker.json` (ephemeral)
- `runtime/always_on/last_selection.txt`

LaunchAgent mode validated:
- `./install_always_on_launchagents.sh`
- `./service_always_on.sh reload`
- Both services running:
  - `com.voice2clipboard.voxmlx`
  - `com.voice2clipboard.alwayson`

## Important Known Limits
1. `mlx-whisper` still crashes in this environment (Metal init exception), so MLX benchmark backend may fail here.
2. `voxmlx` server does not expose `/v1/models`; health should be checked via websocket handshake, not REST models endpoint.
3. Always-on segmentation currently uses silence timeout + periodic commit; this is functional but not yet semantically perfect sentence segmentation.

## Approval/Autonomy Status
High-value command prefixes approved during this session include:
- `./run_voxmlx_server.sh`
- `./run_always_on_voxtral_daemon.sh`
- `./run_benchmark_realtime_backends.sh --help`
- benchmark python invocation prefix for realtime runner

This should reduce interruption frequency for iterative work.

## Next Steps (Concrete)
1. Improve always-on segment quality:
   - better flush policy (sentence-aware punctuation boundary heuristic)
   - dedup/smoothing pass for repeated deltas
2. Add automatic daemon supervision:
   - launch agent plist + restart policy (baseline scripts now added)
   - validate startup on login and permission behavior
3. Add benchmark quality mode:
   - manifest with real references (user-read scripted prompts)
   - WER/CER reporting table per backend/model config
4. Add optional overlay prototype:
   - read `runtime/always_on/live_text.txt`
   - display near cursor with lightweight GUI
5. Add optional LLM action stage:
   - tail transcript file
   - classify intent and produce action candidates (dry-run mode first)
