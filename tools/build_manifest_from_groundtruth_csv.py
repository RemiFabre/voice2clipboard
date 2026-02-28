#!/usr/bin/env python3
"""Build benchmark manifest JSONL from corrected ground-truth CSV.

Input CSV columns:
- audio
- reference_manual
(plus any candidate transcript columns)
"""

from __future__ import annotations

import argparse
import csv
import json


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Convert corrected ground-truth CSV to manifest JSONL")
    ap.add_argument("--csv", required=True, help="Ground-truth CSV (from build_groundtruth_pack.py)")
    ap.add_argument("--output", required=True, help="Output JSONL manifest path")
    ap.add_argument("--allow-empty", action="store_true", help="Keep rows with empty reference_manual")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    kept = 0
    skipped = 0
    with open(args.csv, "r", encoding="utf-8", newline="") as fin, open(args.output, "w", encoding="utf-8") as fout:
        reader = csv.DictReader(fin)
        for row in reader:
            audio = (row.get("audio") or "").strip()
            ref = (row.get("reference_manual") or "").strip()
            if not audio:
                skipped += 1
                continue
            if not ref and not args.allow_empty:
                skipped += 1
                continue
            fout.write(json.dumps({"audio": audio, "reference": ref}, ensure_ascii=False) + "\n")
            kept += 1

    print(f"Wrote {kept} rows to {args.output} (skipped {skipped})")


if __name__ == "__main__":
    main()
