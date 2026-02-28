# Powermetrics Comparison (2026-02-28)

## Inputs
- A-like baseline: `benchmarks/raw_powermetrics/power_idle_20260228.txt`
- B-like (client on, mostly silent): `benchmarks/raw_powermetrics/power_client_silent_20260228.txt`
- C-like (client on, speaking): `benchmarks/raw_powermetrics/power_client_active_20260228.txt`

## Windows
- A: 600 samples, `13:57:57` -> `14:08:07` (~10m10s)
- B: 600 samples, `17:08:34` -> `17:18:42` (~10m08s)
- C: 443 samples, `17:26:18` -> `17:33:47` (~7m29s)

## Summary table
| Run | Combined mean (W) | Combined p95 (W) | CPU mean (W) | GPU mean (W) |
|---|---:|---:|---:|---:|
| A baseline | 5.36 | 9.55 | 2.05 | 3.31 |
| B client-silent | 8.57 | 13.48 | 0.50 | 8.07 |
| C client-active | 12.47 | 14.42 | 0.56 | 11.91 |

## Deltas
- B - A: `+3.20 W` (`+59.7%`, `1.60x`)
- C - A: `+7.11 W` (`+132.5%`, `2.33x`)
- C - B: `+3.90 W` (`+45.5%`, `1.46x`)

## Notes
- Main incremental load appears on GPU power for this setup.
- C run is shorter than target 10 minutes but still clearly above B.
- Absolute values include display/HDMI and normal desktop activity; deltas are more reliable than absolute watts.
