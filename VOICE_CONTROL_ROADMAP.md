# Voice Control Roadmap

## Goals
- Keep current Whisper quick-mode stable.
- Build a production-ready always-on local transcript pipeline.
- Compare Voxtral realtime vs Whisper paths with reproducible metrics.
- Preserve rollback and make every experiment persistent in repo files.

## Stable Baseline (Whisper Quick Mode)
- `cmd + shift - v` -> copy-only quick launcher
- `cmd + shift - b` -> auto-paste quick launcher
- Backed by `voice_transcriber.py` + MLX/faster fallback.

## Realtime Track Status

### Voxtral Realtime: Works via `voxmlx`
Validated path:
- server: `./run_voxmlx_server.sh`
- client: `./run_voxtral_realtime_client.sh`

Important:
- Do not use `vllm-metal` path for Voxtral right now in this repo; it remains blocked by upstream `mlx-vlm` architecture support mismatch (`voxtral_realtime`).

### Always-on production scaffold: Implemented
New scripts:
- `run_always_on_voxtral_daemon.sh`
- `tools/always_on_voxtral_daemon.py`
- `always_on_mark_start.sh`
- `always_on_mark_stop.sh`
- `always_on_status.sh`
- `tools/always_on_capture.py`

Behavior:
- daemon writes rolling transcript/segments to `runtime/always_on/`
- marker start sets interval start
- marker stop copies interval text to clipboard

### Service mode (auto-start): Implemented
- `install_always_on_launchagents.sh`
- `service_always_on.sh`

LaunchAgents:
- `com.voice2clipboard.voxmlx`
- `com.voice2clipboard.alwayson`

## Benchmarking Track Status
New benchmark assets:
- `tools/benchmark_realtime_backends.py`
- `run_benchmark_realtime_backends.sh`
- `tools/build_benchmark_manifest.py`
- `benchmarks/manifest_template.jsonl`
- `benchmarks/manifest_generated.jsonl`
- `benchmarks/realtime_backends_smoke_escalated.json`

Smoke benchmark (audio ~21.8s):
- `voxmlx` first token ~0.94s, total ~9.60s
- `faster-whisper medium` first token ~10.30s, total ~10.30s

Interpretation:
- similar final completion time
- Voxtral provides much better realtime UX (early text appearance)

## Known Constraints
1. `mlx-whisper` benchmark path may crash in this environment (Metal init exception).
2. `voxmlx` health check should use websocket handshake; `/v1/models` may return 404.
3. Always-on segmentation is functional but still heuristic-based (silence timeout + commit cadence).

## Next Steps (Ordered)
1. Improve always-on segment quality
   - dedup for repeated deltas
   - punctuation/sentence-aware flush heuristics
2. Benchmark quality at scale
   - run generated manifest with references
   - produce WER/CER summary tables by backend
3. Overlay prototype
   - render `runtime/always_on/live_text.txt` near cursor
4. LLM action prototype
   - tail selected transcript windows
   - classify intents + dry-run action suggestions
5. Hardening
   - long-run stability test (multi-hour)
   - log rotation / max file size policies

## Reference Docs
- `docs/AUTONOMOUS_PROGRESS_2026-02-28.md`
- `docs/ALWAYS_ON_VOXTRAL_RUNBOOK.md`
- `docs/BENCHMARKING_RUNBOOK.md`
- `VOXTRAL_DEBUG_STATUS_2026-02-27.md`
