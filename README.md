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

Voice-command mode is enabled by default in daemon service:
- say `roger start` to begin selection
- say `roger stop` to end selection and copy
- aliases: `copy start` / `copy stop`

5. Stop everything:
```bash
./voice_control.sh stop
```

Main runbook: `docs/runbooks/STABLE_OPERATIONS.md`

### Setup B: macOS manual tuning session (latency/commit experiments)
Use this when you want to tweak daemon params manually.

```bash
cd /Users/remi/voice2clipboard
./voice_control.sh stop
./scripts/mac/run_voxmlx_server.sh
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

Only `./voice_control.sh` is kept at repo root for daily usage.

Other command scripts moved to:
- `scripts/mac/` (production macOS operations)
- `scripts/experiments/` (benchmarking and vLLM experiment entrypoints)

## Runbooks

- Daily operations: `docs/runbooks/STABLE_OPERATIONS.md`
- Always-on details: `docs/runbooks/ALWAYS_ON_VOXTRAL_RUNBOOK.md`
- Benchmarking workflow: `docs/runbooks/BENCHMARKING_RUNBOOK.md`

## Notes

- Marker boundary compensation default is currently `1.5s` (symmetric start/stop) in `tools/always_on_capture.py`.
- `voice_control.sh start` already runs daemon + server; do not start a second manual daemon at the same time.
