#!/usr/bin/env python3
"""Build benchmark manifest from recordings tree.

By default includes recordings/*/*/audio.wav and tries to use transcript.txt as reference.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build JSONL manifest for benchmark_realtime_backends")
    ap.add_argument("--root", default="recordings")
    ap.add_argument("--output", default="benchmarks/manifest_generated.jsonl")
    ap.add_argument("--require-reference", action="store_true", help="Only keep entries with non-empty transcript reference")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    items = []
    audio_paths = sorted(glob.glob(os.path.join(args.root, "*", "*", "audio.wav")))

    for audio in audio_paths:
        folder = Path(audio).parent
        ref_path = folder / "transcript.txt"
        ref = ""
        if ref_path.exists():
            ref = ref_path.read_text(encoding="utf-8").strip()
        if args.require_reference and not ref:
            continue
        items.append({"audio": audio, "reference": ref})

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for obj in items:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(f"Wrote {len(items)} entries to {args.output}")


if __name__ == "__main__":
    main()
