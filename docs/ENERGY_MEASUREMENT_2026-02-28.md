# Energy Measurement Report (2026-02-28)

## Input analyzed
- Raw file: `/private/tmp/power_idle.txt`
- Parsed summary JSON: `benchmarks/powermetrics_power_idle_20260228_summary.json`
- Parser script: `tools/analyze_powermetrics.py`
- Additional raw files (round 2):
  - `benchmarks/raw_powermetrics/power_client_silent_20260228.txt`
  - `benchmarks/raw_powermetrics/power_client_active_20260228.txt`
- Additional summaries (round 2):
  - `benchmarks/powermetrics_power_client_silent_20260228_summary.json`
  - `benchmarks/powermetrics_power_client_active_20260228_summary.json`

## Measurement context (as provided)
- Screen ON
- HDMI connected
- Lid open
- Some Chrome browsing activity
- Client mostly OFF during run; server ON in background

Note: this means values include display/external-monitor and normal desktop overhead, not pure ASR-only power.

## Window and sample count
- First sample: `Sat Feb 28 13:57:57 2026 +0100`
- Last sample: `Sat Feb 28 14:08:07 2026 +0100`
- Samples: `600` (~10 minutes at 1s interval)

## Key power stats
- Combined power (CPU+GPU+ANE)
  - Mean: `5363.3 mW` (5.36 W)
  - Median (p50): `4518 mW`
  - p90: `7990 mW`
  - p95: `9549 mW`
  - Min/Max: `2851 / 16304 mW`
  - Stddev: `2280.9 mW`
- CPU power
  - Mean: `2054.7 mW`
  - p50/p95: `1153 / 6048 mW`
- GPU power
  - Mean: `3308.7 mW`
  - p50/p95: `3288 / 3819 mW`
- ANE power: always `0 mW`

## Variability interpretation
- There are strong power swings.
- Buckets on combined power:
  - `< 4.5W`: `49.7%` of samples
  - `4.5W–6.0W`: `18.8%`
  - `>= 6.0W`: `31.5%`
- This indicates mixed behavior: quiet desktop periods plus frequent activity spikes (likely interactive usage/browser/render bursts).

## Energy estimate for this run
- Estimated energy over capture: `0.8939 Wh` (for ~10 minutes)
- If sustained at this average for 24h: `~128.7 Wh/day` (`~0.129 kWh/day`)

## Server/client state note
- `logs/voxmlx_server.log` shows a websocket disconnect at `2026-02-28 13:58:11`, inside the measurement window.
- So a client session appears to have been active at the very beginning, then disconnected.
- Practical interpretation: this run is already a near-`A` baseline (server ON, client mostly OFF), with only brief contamination at the start.

## Next experiment plan (short and controlled)
Goal: isolate incremental ASR cost.

### A0 (already captured): Reuse current baseline
- You can treat `/private/tmp/power_idle.txt` as baseline for "server ON, client mostly OFF".
- A fresh `A` rerun is optional, only if you want a perfectly clean window with no early websocket activity.

### Test A: Server ON, client OFF (baseline with your current desktop setup)
```bash
sudo powermetrics -i 1000 -n 180 --samplers cpu_power,gpu_power > /private/tmp/power_A_server_only.txt
python /Users/remi/voice2clipboard/tools/analyze_powermetrics.py \
  --input /private/tmp/power_A_server_only.txt \
  --output /Users/remi/voice2clipboard/benchmarks/powermetrics_A_server_only.json
```

### Test B: Client ON + capture ON + mostly silent
1. Start client:
```bash
cd /Users/remi/voice2clipboard
./run_voxtral_realtime_client.sh
```
2. Press `Enter` once to start capture, stay mostly silent.
3. In another terminal:
```bash
sudo powermetrics -i 1000 -n 180 --samplers cpu_power,gpu_power > /private/tmp/power_B_client_silent.txt
python /Users/remi/voice2clipboard/tools/analyze_powermetrics.py \
  --input /private/tmp/power_B_client_silent.txt \
  --output /Users/remi/voice2clipboard/benchmarks/powermetrics_B_client_silent.json
```

### Test C: Client ON + capture ON + continuous speaking
- Keep same setup as B, but speak continuously for 3 minutes.
```bash
sudo powermetrics -i 1000 -n 180 --samplers cpu_power,gpu_power > /private/tmp/power_C_client_speaking.txt
python /Users/remi/voice2clipboard/tools/analyze_powermetrics.py \
  --input /private/tmp/power_C_client_speaking.txt \
  --output /Users/remi/voice2clipboard/benchmarks/powermetrics_C_client_speaking.json
```

## What to compare after A/B/C
- Combined mean and p95
- CPU mean and p95
- GPU mean and p95
- Delta vs A (B-A and C-A)

This will tell us:
- incremental cost of just keeping client capture open (B vs A)
- incremental cost of active speech decoding (C vs B)

---

## Round 2: Completed A/B/C-style comparison

### Run windows
- A-like baseline (`power_idle`): 600 samples, `13:57:57` -> `14:08:07` (~10m10s)
- B-like (`power_client_silent`): 600 samples, `17:08:34` -> `17:18:42` (~10m08s)
- C-like (`power_client_active`): 443 samples, `17:26:18` -> `17:33:47` (~7m29s)

Note: C is shorter than 10 minutes but still long enough to show a strong signal.

### Core comparison (mean combined power)
- A baseline: `5363.3 mW` (5.36W)
- B client-on, mostly silent: `8567.8 mW` (8.57W)
- C client-on, speaking: `12470.1 mW` (12.47W)

### Deltas
- B - A: `+3204.5 mW` (`+59.7%`, `1.60x`)
- C - A: `+7106.8 mW` (`+132.5%`, `2.33x`)
- C - B: `+3902.3 mW` (`+45.5%`, `1.46x`)

### CPU/GPU split (means)
- A: CPU `2054.7 mW`, GPU `3308.7 mW`
- B: CPU `497.9 mW`, GPU `8069.9 mW`
- C: CPU `559.8 mW`, GPU `11910.2 mW`

Interpretation:
- In these runs, incremental load appears mostly on GPU power, not CPU.
- Speaking continuously clearly increases power versus client-silent.
- Absolute numbers include desktop/display/HDMI/background activity, so use deltas as the main signal.
