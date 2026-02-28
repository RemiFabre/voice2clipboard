#!/usr/bin/env python3
"""Summarize macOS powermetrics text output.

Parses lines like:
- *** Sampled system activity (...)
- CPU Power: X mW
- GPU Power: X mW
- Combined Power (CPU + GPU + ANE): X mW
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path


SAMPLE_RE = re.compile(r"\*\*\* Sampled system activity \((.*?)\) \((.*?) elapsed\) \*\*\*")
CPU_RE = re.compile(r"^CPU Power:\s*([0-9]+) mW")
GPU_RE = re.compile(r"^GPU Power:\s*([0-9]+) mW")
ANE_RE = re.compile(r"^ANE Power:\s*([0-9]+) mW")
COMBINED_RE = re.compile(r"^Combined Power \(CPU \+ GPU \+ ANE\):\s*([0-9]+) mW")


def percentile(xs: list[int], p: float) -> int:
    if not xs:
        return 0
    i = int((len(xs) - 1) * p)
    return xs[i]


def summarize_series(values: list[int]) -> dict:
    if not values:
        return {}
    xs = sorted(values)
    return {
        "n": len(xs),
        "mean_mw": round(sum(xs) / len(xs), 1),
        "min_mw": xs[0],
        "p10_mw": percentile(xs, 0.10),
        "p50_mw": percentile(xs, 0.50),
        "p90_mw": percentile(xs, 0.90),
        "p95_mw": percentile(xs, 0.95),
        "max_mw": xs[-1],
        "stdev_mw": round(statistics.pstdev(xs), 1),
    }


def parse_file(path: Path) -> dict:
    sample_times: list[tuple[str, str]] = []
    cpu: list[int] = []
    gpu: list[int] = []
    ane: list[int] = []
    combined: list[int] = []
    current = {"cpu": None, "gpu": None, "ane": None, "combined": None}

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = SAMPLE_RE.search(line)
            if m:
                # flush previous sample if populated
                if current["cpu"] is not None:
                    cpu.append(current["cpu"])
                if current["gpu"] is not None:
                    gpu.append(current["gpu"])
                if current["ane"] is not None:
                    ane.append(current["ane"])
                if current["combined"] is not None:
                    combined.append(current["combined"])
                current = {"cpu": None, "gpu": None, "ane": None, "combined": None}
                sample_times.append((m.group(1), m.group(2)))
                continue
            m = CPU_RE.search(line)
            if m and current["cpu"] is None:
                current["cpu"] = int(m.group(1))
                continue
            m = GPU_RE.search(line)
            if m and current["gpu"] is None:
                current["gpu"] = int(m.group(1))
                continue
            m = ANE_RE.search(line)
            if m and current["ane"] is None:
                current["ane"] = int(m.group(1))
                continue
            m = COMBINED_RE.search(line)
            if m and current["combined"] is None:
                current["combined"] = int(m.group(1))
                continue

    # flush final sample
    if current["cpu"] is not None:
        cpu.append(current["cpu"])
    if current["gpu"] is not None:
        gpu.append(current["gpu"])
    if current["ane"] is not None:
        ane.append(current["ane"])
    if current["combined"] is not None:
        combined.append(current["combined"])

    result = {
        "file": str(path),
        "samples": len(sample_times),
        "first_sample": sample_times[0][0] if sample_times else None,
        "last_sample": sample_times[-1][0] if sample_times else None,
        "stats": {
            "cpu_mw": summarize_series(cpu),
            "gpu_mw": summarize_series(gpu),
            "ane_mw": summarize_series(ane),
            "combined_mw": summarize_series(combined),
        },
    }

    if combined:
        n = len(combined)
        lt_4500 = sum(1 for x in combined if x < 4500)
        b_4500_6000 = sum(1 for x in combined if 4500 <= x < 6000)
        ge_6000 = sum(1 for x in combined if x >= 6000)
        wh = sum(combined) / 1000 / 3600
        result["combined_buckets"] = {
            "lt_4500": {"count": lt_4500, "pct": round(lt_4500 * 100 / n, 1)},
            "b_4500_6000": {"count": b_4500_6000, "pct": round(b_4500_6000 * 100 / n, 1)},
            "ge_6000": {"count": ge_6000, "pct": round(ge_6000 * 100 / n, 1)},
        }
        result["energy_wh_estimate"] = round(wh, 4)

    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze powermetrics output file")
    ap.add_argument("--input", required=True, help="Path to powermetrics text file")
    ap.add_argument("--output", help="Optional JSON output path")
    args = ap.parse_args()

    report = parse_file(Path(args.input))
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
