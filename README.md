# voice2clipboard

Local voice-to-text workflows with a production macOS always-on path and separated experiment tracks.

## Start Here

### Setup A: macOS daily workflow (recommended)
This is the setup you use every day.

1. Check state:
```bash
cd /Users/remi/voice2clipboard
./voice_control.sh status
```

2. Start services:
```bash
./voice_control.sh start
```

3. Open live transcript in VS Code:
```bash
./voice_control.sh live
```

4. Capture a clipboard window:
```bash
./voice_control.sh mark-start
# speak
./voice_control.sh mark-stop
```

5. Stop everything:
```bash
./voice_control.sh stop
```

Main runbook: `docs/runbooks/STABLE_OPERATIONS.md`

### Setup B: macOS manual tuning session (latency/commit experiments)
Use this when you want to tweak daemon params manually.

```bash
cd /Users/remi/voice2clipboard
./service_always_on.sh stop
./run_voxmlx_server.sh
```

In a second terminal:
```bash
cd /Users/remi/voice2clipboard
source /Users/remi/.virtualenvs/voice2clipboard/bin/activate
python tools/always_on_voxtral_daemon.py \
  --runtime-dir /Users/remi/voice2clipboard/runtime/always_on \
  --samplerate 16000 \
  --blocksize 1280 \
  --commit-every 0.2 \
  --segment-silence 0.8
```

### Setup C: legacy Whisper hotkey flow (Linux-oriented)
Legacy scripts are now under:
- `apps/linux/legacy_whisper/`

## Repo Layout

- `voice_control.sh`
  - single daily entrypoint for macOS operation (start/stop/status/markers/live/logs)
- `tools/`
  - runtime core (`always_on_voxtral_daemon.py`, `always_on_capture.py`) and utility scripts
- `docs/runbooks/`
  - operational docs you should follow
- `docs/research/`
  - dated notes, diagnostics, analysis, papers-derived writeups
- `experiments/benchmarks/`
  - benchmark runners and analysis scripts
- `experiments/vllm_voxtral/`
  - vLLM/vllm-metal based Voxtral runtime experiments
- `apps/linux/legacy_whisper/`
  - previous Whisper-first pipeline and launch scripts

## Compatibility wrappers kept at repo root

To avoid breaking older commands, these still work and forward to their new locations:
- `./run_benchmark_realtime_backends.sh`
- `./run_benchmark_full_mac.sh`
- `./run_voxtral_realtime_server.sh`
- `./run_voxtral_realtime_client.sh`
- `./setup_voxtral_runtime.sh`
- `./fix_voxtral_runtime.sh`
- `./stop_voxtral_realtime_server.sh`
- `./wait_voxtral_server_ready.sh`

## Runbooks

- Daily operations: `docs/runbooks/STABLE_OPERATIONS.md`
- Always-on details: `docs/runbooks/ALWAYS_ON_VOXTRAL_RUNBOOK.md`
- Benchmarking workflow: `docs/runbooks/BENCHMARKING_RUNBOOK.md`

## Notes

- Marker boundary compensation default is currently `1.5s` (symmetric start/stop) in `tools/always_on_capture.py`.
- `voice_control.sh start` already runs daemon + server; do not start a second manual daemon at the same time.
