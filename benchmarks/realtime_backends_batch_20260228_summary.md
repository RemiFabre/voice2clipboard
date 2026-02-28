# Benchmark Summary (2026-02-28)

- Source: `benchmarks/realtime_backends_batch_20260228_complete.json`
- Samples: 18
- Backends: voxmlx, faster-whisper (medium/int8/cpu)

## Backend Averages

| Backend | Avg total (s) | Avg first token (s) | Avg RTF total | Avg text len |
|---|---:|---:|---:|---:|
| voxmlx | 20.97 | 1.63 | 1.516 | 210.4 |
| faster | 16.28 | 16.28 | 1.223 | 391.3 |

## Comparative Deltas (faster - voxmlx)

- Avg first-token advantage of voxmlx: `16.88s` earlier
- Avg total-time delta: `-4.69s` (positive => voxmlx faster)

## Notes
- `voxmlx` gives much earlier visible text on most non-silent clips.
- Total completion time is similar and depends on clip length/content.
- Silent clips can show empty output for both backends.
