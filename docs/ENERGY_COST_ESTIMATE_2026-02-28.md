# Energy Cost Estimate (24/7) - 2026-02-28

## Scope
This estimate uses measured `combined_mw = cpu_power + gpu_power + ane_power` from powermetrics runs.

Important: this is **ASR stack silicon power only**, not full wall power of the whole laptop (display, SSD, RAM, external monitor, charger losses, etc.).

## Inputs
- Baseline (server on, client mostly off): `5.363 W`
- Client on, mostly silent: `8.568 W`
- Client on, active speaking: `12.470 W`

Formula:
- `kWh/day = (W * 24) / 1000`
- `monthly_cost = kWh/day * 30 * electricity_price`
- `yearly_cost = kWh/day * 365 * electricity_price`

## Cost at $0.18/kWh
| Mode | kWh/day | Cost/day | Cost/month (30d) | Cost/year |
|---|---:|---:|---:|---:|
| Baseline | 0.1287 | $0.023 | $0.70 | $8.46 |
| Client silent | 0.2056 | $0.037 | $1.11 | $13.51 |
| Client speaking | 0.2993 | $0.054 | $1.62 | $19.66 |

## Monthly cost sensitivity by electricity price
| Mode | $0.12/kWh | $0.18/kWh | $0.25/kWh | $0.30/kWh | $0.40/kWh |
|---|---:|---:|---:|---:|---:|
| Baseline | $0.46 | $0.70 | $0.97 | $1.16 | $1.54 |
| Client silent | $0.74 | $1.11 | $1.54 | $1.85 | $2.47 |
| Client speaking | $1.08 | $1.62 | $2.24 | $2.69 | $3.59 |

## Interpretation
- Incremental ASR compute cost is small in absolute dollar terms.
- Real household electricity cost of the **entire machine + monitor** will be higher than values here.
- For full-system cost, collect wall-power or battery-discharge-based measurements and recompute with the same formulas.
