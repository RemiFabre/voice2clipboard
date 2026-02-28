#!/usr/bin/env python3
"""Generate full-text comparison pack for manual ground-truth curation.

Runs several backend/model configurations on a selected manifest and writes:
- JSON merged results
- Markdown review doc with full transcripts
- JSONL annotation template (audio + empty reference)
- CSV matrix (audio + all candidate transcripts side by side)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime


def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_manifest(path: str) -> list[dict]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def run_benchmark(
    manifest: str,
    backend: str,
    whisper_model: str | None,
    voxmlx_model: str | None,
    out_file: str,
) -> tuple[bool, str]:
    cmd = [
        sys.executable,
        "tools/benchmark_realtime_backends.py",
        "--manifest",
        manifest,
        "--backend",
        backend,
        "--output",
        out_file,
    ]
    if whisper_model:
        cmd += ["--model-whisper", whisper_model]
    if voxmlx_model:
        cmd += ["--voxmlx-model", voxmlx_model]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return True, ""
    err = (proc.stderr or proc.stdout or "unknown benchmark error").strip()
    return False, err


def read_results(path: str) -> list[dict]:
    obj = json.load(open(path, "r", encoding="utf-8"))
    return obj.get("results", [])


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build manual groundtruth curation pack")
    ap.add_argument("--manifest", default="benchmarks/manifest_groundtruth_seed.jsonl")
    ap.add_argument("--output-prefix", default="benchmarks/groundtruth_pack")
    ap.add_argument("--voxmlx-model", default="voxtral-mini-latest")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    items = load_manifest(args.manifest)
    if not items:
        raise SystemExit("manifest has no items")

    configs = [
        {
            "backend": "voxmlx",
            "whisper_model": None,
            "voxmlx_model": args.voxmlx_model,
            "key": "voxmlx_voxtral",
            "label": f"voxmlx:{args.voxmlx_model}",
        },
        {
            "backend": "faster",
            "whisper_model": "medium",
            "voxmlx_model": None,
            "key": "faster_medium",
            "label": "faster:whisper-medium",
        },
        {
            "backend": "faster",
            "whisper_model": "small",
            "voxmlx_model": None,
            "key": "faster_small",
            "label": "faster:whisper-small",
        },
        {
            "backend": "faster",
            "whisper_model": "base",
            "voxmlx_model": None,
            "key": "faster_base",
            "label": "faster:whisper-base",
        },
    ]

    merged: dict[str, dict] = {item["audio"]: {"audio": item["audio"], "outputs": {}} for item in items}
    config_errors: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="gt_pack_") as td:
        for cfg in configs:
            out_file = os.path.join(td, f"{cfg['key']}.json")
            ok, err = run_benchmark(
                args.manifest,
                cfg["backend"],
                cfg["whisper_model"],
                cfg["voxmlx_model"],
                out_file,
            )
            if not ok:
                config_errors.append({"config": cfg["label"], "error": err})
                continue
            for row in read_results(out_file):
                audio = row["audio"]
                if audio not in merged:
                    continue
                merged[audio]["outputs"][cfg["key"]] = {
                    "backend": row.get("backend"),
                    "model": row.get("model"),
                    "config": row.get("config"),
                    "text": row.get("text", ""),
                    "timings": row.get("timings", {}),
                    "rtf_total": row.get("rtf_total"),
                }

    tag = now_tag()
    json_out = f"{args.output_prefix}_{tag}.json"
    md_out = f"{args.output_prefix}_{tag}.md"
    ann_out = f"{args.output_prefix}_{tag}_annotations.jsonl"
    matrix_out = f"{args.output_prefix}_{tag}_matrix.csv"

    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "manifest": args.manifest,
        "configs": [
            {"key": cfg["key"], "label": cfg["label"], "backend": cfg["backend"]}
            for cfg in configs
        ],
        "config_errors": config_errors,
        "samples": [merged[item["audio"]] for item in items],
    }
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines = ["# Ground Truth Curation Pack", ""]
    lines.append(f"- Source manifest: `{args.manifest}`")
    lines.append(f"- JSON bundle: `{json_out}`")
    lines.append(f"- Annotation template: `{ann_out}`")
    lines.append(f"- Editable matrix CSV: `{matrix_out}`")
    if config_errors:
        lines.append("- Config errors:")
        for e in config_errors:
            lines.append(f"  - `{e['config']}`: `{e['error']}`")
    lines.append("")
    lines.append("For each sample, choose the best candidate and manually correct into annotation template.")
    lines.append("")

    for i, item in enumerate(items, start=1):
        audio = item["audio"]
        sample = merged[audio]
        lines.append(f"## Sample {i}")
        lines.append("")
        lines.append(f"Audio: `{audio}`")
        lines.append("")
        for cfg in configs:
            key = cfg["key"]
            out = sample["outputs"].get(key, {})
            txt = (out.get("text") or "").strip()
            tt = out.get("timings", {}).get("total_s")
            ft = out.get("timings", {}).get("first_token_s")
            lines.append(f"### {cfg['label']}")
            lines.append("")
            if tt is not None:
                lines.append(f"- total_s: `{tt:.2f}`")
            if ft is not None:
                lines.append(f"- first_token_s: `{ft:.2f}`")
            lines.append("")
            lines.append(txt if txt else "<empty>")
            lines.append("")

    with open(md_out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    with open(ann_out, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps({"audio": item["audio"], "reference": ""}, ensure_ascii=False) + "\n")

    headers = ["audio", "reference_manual"] + [cfg["label"] for cfg in configs]
    with open(matrix_out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for item in items:
            audio = item["audio"]
            sample = merged[audio]
            row = {"audio": audio, "reference_manual": ""}
            for cfg in configs:
                row[cfg["label"]] = (sample["outputs"].get(cfg["key"], {}).get("text") or "").strip()
            writer.writerow(row)

    print(f"Wrote: {json_out}")
    print(f"Wrote: {md_out}")
    print(f"Wrote: {ann_out}")
    print(f"Wrote: {matrix_out}")


if __name__ == "__main__":
    main()
