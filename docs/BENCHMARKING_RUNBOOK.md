# Benchmarking Runbook (Voxtral vs Whisper)

## Purpose
Compare realtime and one-shot transcription paths on your machine with reproducible output files.

## Main Script
- `tools/benchmark_realtime_backends.py`
- Wrapper: `run_benchmark_realtime_backends.sh`

## Quick Run (discovered local recordings)
```bash
cd /Users/remi/voice2clipboard
./run_benchmark_realtime_backends.sh --backend voxmlx --backend faster
```

## Run with explicit manifest
1. Edit `benchmarks/manifest_template.jsonl` with entries:
```json
{"audio":"recordings/.../audio.wav","reference":"expected text"}
```
2. Run:
```bash
cd /Users/remi/voice2clipboard
./run_benchmark_realtime_backends.sh \
  --manifest benchmarks/manifest_template.jsonl \
  --backend voxmlx \
  --backend faster \
  --backend mlx
```

## Ground truth workflow (manual correction)
1. Build a pack with full candidate transcripts:
```bash
source /Users/remi/.virtualenvs/voice2clipboard/bin/activate
cd /Users/remi/voice2clipboard
python tools/build_groundtruth_pack.py \
  --manifest benchmarks/manifest_groundtruth_seed_short.jsonl \
  --output-prefix benchmarks/groundtruth_pack_short
```
2. Edit `reference_manual` in the generated `*_matrix.csv`.
3. Convert corrected CSV to benchmark manifest:
```bash
python tools/build_manifest_from_groundtruth_csv.py \
  --csv benchmarks/groundtruth_pack_short_YYYYMMDD_HHMMSS_matrix.csv \
  --output benchmarks/manifest_groundtruth_short_corrected.jsonl
```
4. Rerun benchmark and compute WER/CER against your corrected references:
```bash
python tools/benchmark_realtime_backends.py \
  --manifest benchmarks/manifest_groundtruth_short_corrected.jsonl \
  --backend voxmlx \
  --backend faster \
  --model-whisper medium \
  --output benchmarks/realtime_backends_groundtruth_short_medium.json
```

## Auto-build manifest from existing recordings

Generate from `recordings/*/*/audio.wav` and matching `transcript.txt`:
```bash
cd /Users/remi/voice2clipboard
source /Users/remi/.virtualenvs/voice2clipboard/bin/activate
python tools/build_benchmark_manifest.py --output benchmarks/manifest_generated.jsonl
```

Only include samples that already have reference transcripts:
```bash
python tools/build_benchmark_manifest.py \
  --output benchmarks/manifest_with_refs.jsonl \
  --require-reference
```

## Metrics
Per backend/audio item:
- `total_s`: end-to-end transcription time
- `first_token_s`: time to first visible token
- `rtf_total`: total real-time factor
- `rtf_first_token`: first-token real-time factor
- `wer`, `cer` (if reference text provided)

## Important
- `voxmlx` benchmark requires running local websocket server at `ws://127.0.0.1:8000/v1/realtime`.
- In this environment, `mlx` backend may fail due MLX Metal runtime crash.

## Output Files
Saved to `benchmarks/` as JSON, for example:
- `benchmarks/realtime_backends_YYYYMMDD_HHMMSS.json`
- `benchmarks/realtime_backends_smoke_escalated.json`

Current batch artifacts:
- `benchmarks/realtime_backends_batch_20260228_complete.json`
- `benchmarks/realtime_backends_batch_20260228_summary.md`

## Operational Tip
For heavy long-file batch runs, temporarily pausing always-on daemon can reduce websocket timeout risk:
```bash
launchctl bootout gui/$(id -u)/com.voice2clipboard.alwayson || true
# run batch benchmark
launchctl bootstrap gui/$(id -u) $HOME/Library/LaunchAgents/com.voice2clipboard.alwayson.plist || true
launchctl kickstart -k gui/$(id -u)/com.voice2clipboard.alwayson || true
```
