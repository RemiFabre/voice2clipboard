# Voxtral Realtime: Paper + Pipeline + Presets (2026-03-01)

## Scope
This note consolidates:
- local paper copy review (`docs/papers/voxtral_realtime_2602.11298.pdf`)
- current repo runtime behavior (daemon/client/benchmark)
- practical presets for tuning latency vs quality

## Local paper artifact
- PDF: `docs/papers/voxtral_realtime_2602.11298.pdf`
- Extracted text: `docs/papers/voxtral_realtime_2602.11298.txt`

## What the Voxtral paper says (relevant operational points)
1. Native streaming cadence is **80 ms** per decoder step (12.5 Hz).
2. Training/inference delay target `tau` is an explicit controllable variable in multiples of 80 ms, from 80 ms to 2400 ms.
3. Reported reference operating points in the paper are 240 / 480 / 960 / 2400 ms; 480 ms is the key “sub-second, near-offline” point.
4. Serving design expects:
- incremental audio appends
- periodic commits
- full-duplex input/output streaming over websocket
5. Architecture handles emission timing internally (the paper explicitly says no external VAD is required for core emission timing).

## Current repo defaults (double-check)

### Always-on daemon (clipboard workflow)
File: `tools/always_on_voxtral_daemon.py`
- sample rate: `16000`
- block size: `2048` samples
  - at 16 kHz: `2048 / 16000 = 0.128 s` (128 ms input callback granularity)
  - payload size per block (mono int16): `2048 * 2 = 4096` bytes before base64
- commit interval: `0.8 s` (`--commit-every`)
- segment flush silence gate: `0.9 s`

This is workable but **coarser/slower than the model’s native 80 ms rhythm**.

### Manual realtime client
File: `voxtral_realtime_client.py`
- sample rate: `16000`
- block size: `2048` samples (128 ms)
- commit behavior: start commit (`final:false`) and stop commit (`final:true`), no periodic commit loop

### Benchmark voxmlx path
File: `tools/benchmark_realtime_backends.py`
- default chunk: `80 ms`
- default commit interval: `0.7 s`
- optional client-like mode available

### Marker boundary compensation (start/stop copy window)
File: `tools/always_on_capture.py`
- currently in working tree, start default fallback is `1.5 s` (uncommitted local tweak)
- stop path reads pad from marker and otherwise falls back to `0.66 s`
- this means start/stop can feel offset if pad is not explicitly set and should be treated as an active tuning zone

## Why observed latency can exceed advertised model delay
Even if model delay target is ~480 ms, end-to-end visible delay includes:
1. microphone block accumulation (currently up to ~128 ms)
2. websocket scheduling + commit cadence (currently up to ~800 ms between commits in daemon)
3. server decode/emit + client UI/file flush

So “~480 ms model delay” does not mean “~480 ms wall-clock text paint” unless pipeline cadence is tightened.

## Recommended preset profiles (for this repo)

### Preset A: Balanced (recommended first)
Goal: close to paper default feel with stable quality.
- daemon blocksize: `1280` (80 ms)
- daemon commit-every: `0.4 s`
- marker boundary pad: `0.66 s`

Run manually:
```bash
cd /Users/remi/voice2clipboard
source /Users/remi/.virtualenvs/voice2clipboard/bin/activate
VOICE2CLIP_BOUNDARY_PAD_S=0.66 \
python tools/always_on_voxtral_daemon.py \
  --runtime-dir runtime/always_on \
  --blocksize 1280 \
  --commit-every 0.4 \
  --segment-silence 0.8
```

### Preset B: Low-latency aggressive
Goal: fastest updates, possible quality/stability tradeoff.
- blocksize: `640` (40 ms)
- commit-every: `0.2 s`
- segment-silence: `0.6 s`

### Preset C: Quality-biased
Goal: smoother/higher confidence text at cost of lag.
- blocksize: `1600` (100 ms)
- commit-every: `0.8 s`
- segment-silence: `1.0 s`

## Exact places to tune
1. Daemon defaults: `tools/always_on_voxtral_daemon.py` (`parse_args()`)
2. Daemon launch script: `run_always_on_voxtral_daemon.sh`
3. Marker boundary pad: env var `VOICE2CLIP_BOUNDARY_PAD_S`
4. Benchmark chunk/commit: `tools/benchmark_realtime_backends.py`

## Practical next experiment order
1. Move daemon to 80 ms block + 0.4 s commits.
2. Keep marker pad fixed at 0.66 s and run 10 quick start/stop utterances.
3. If still clipping edges, increase pad symmetrically in +0.1 s steps (0.76, 0.86).
4. If live text still feels late, reduce commit interval to 0.3 then 0.2.

## Notes on source of truth
- Paper: `arXiv:2602.11298` local copy above.
- Model card/serving examples were cross-checked from accessible Hugging Face/Voxtral pages during this session; the paper is the strongest, versioned source for 80 ms/480 ms framing.
