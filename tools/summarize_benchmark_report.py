#!/usr/bin/env python3
"""Build a human-readable benchmark summary from one or more benchmark JSON files."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def normalize_ws(s: str) -> str:
    return " ".join((s or "").split())


def tokenize_words(s: str) -> list[str]:
    return normalize_ws(s).split(" ") if normalize_ws(s) else []


def levenshtein(a: list[str], b: list[str]) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, start=1):
        cur = [i]
        for j, y in enumerate(b, start=1):
            cost = 0 if x == y else 1
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def avg(vals: list[float]) -> float | None:
    return (sum(vals) / len(vals)) if vals else None


def fmt(x: float | None, nd: int = 3) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{nd}f}"


def wer_label(v: float | None) -> str:
    if v is None:
        return "n/a"
    if v <= 0.05:
        return "excellent"
    if v <= 0.15:
        return "good"
    if v <= 0.30:
        return "usable with edits"
    return "poor"


@dataclass
class Row:
    config: str
    backend: str
    model: str
    audio: str
    ref: str
    hyp: str
    wer: float | None
    cer: float | None
    total_s: float | None
    first_s: float | None
    rtf: float | None


def extract_rows(paths: list[str]) -> list[Row]:
    rows: list[Row] = []
    for p in paths:
        obj = json.loads(Path(p).read_text(encoding="utf-8"))
        args = obj.get("args", {})
        default_vox_model = args.get("voxmlx_model", "voxtral-mini-latest")
        default_whisper_model = args.get("model_whisper", "medium")
        mode = "clientlike" if args.get("voxmlx_clientlike") else "standard"
        voxmlx_tag = (
            f"mode={mode}"
            f"|chunk={args.get('chunk_ms', 'n/a')}"
            f"|commit={args.get('commit_every', 'n/a')}"
            f"|idle={args.get('post_commit_idle', 'n/a')}"
        )
        for r in obj.get("results", []):
            backend = r.get("backend", "")
            model = r.get("model") or (default_vox_model if backend == "voxmlx" else f"whisper-{default_whisper_model}")
            if backend == "voxmlx":
                config = f"{backend}:{model}|{voxmlx_tag}"
            else:
                config = r.get("config") or f"{backend}:{model}"
            m = r.get("metrics") or {}
            t = r.get("timings") or {}
            ref = r.get("reference") or ""
            rows.append(
                Row(
                    config=config,
                    backend=backend,
                    model=model,
                    audio=r.get("audio", ""),
                    ref=ref,
                    hyp=r.get("text", ""),
                    wer=m.get("wer"),
                    cer=m.get("cer"),
                    total_s=t.get("total_s"),
                    first_s=t.get("first_token_s"),
                    rtf=r.get("rtf_total"),
                )
            )
    return rows


def word_error_breakdown(ref: str, hyp: str) -> tuple[int, int, int]:
    a = tokenize_words(ref.lower())
    b = tokenize_words(hyp.lower())
    matcher = SequenceMatcher(a=a, b=b)
    sub = ins = dele = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            ra = i2 - i1
            rb = j2 - j1
            common = min(ra, rb)
            sub += common
            if ra > rb:
                dele += ra - rb
            elif rb > ra:
                ins += rb - ra
        elif tag == "insert":
            ins += j2 - j1
        elif tag == "delete":
            dele += i2 - i1
    return sub, ins, dele


def main() -> None:
    ap = argparse.ArgumentParser(description="Create markdown summary for benchmark JSON reports")
    ap.add_argument("--input", action="append", required=True, help="Benchmark JSON path (repeatable)")
    ap.add_argument("--output", required=True, help="Markdown output path")
    args = ap.parse_args()

    raw_rows = extract_rows(args.input)
    dedup: dict[tuple[str, str], Row] = {}
    for r in raw_rows:
        dedup[(r.audio, r.config)] = r
    rows = list(dedup.values())
    if not rows:
        raise SystemExit("No rows found in input report(s)")

    by_cfg: dict[str, list[Row]] = defaultdict(list)
    by_audio: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        by_cfg[r.config].append(r)
        by_audio[r.audio].append(r)

    lines: list[str] = []
    lines.append("# Benchmark Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## Inputs")
    for p in args.input:
        lines.append(f"- `{p}`")
    lines.append("")
    lines.append("## How To Read WER")
    lines.append("- WER = word error rate (0.0 is perfect, 1.0 means roughly one error per reference word).")
    lines.append("- Rough guide: <=0.05 excellent, <=0.15 good, <=0.30 usable with edits, >0.30 poor.")
    lines.append("")

    lines.append("## Aggregate By Config")
    lines.append("")
    lines.append("| Config | Samples | Avg WER | Avg CER | Avg Total(s) | Avg First Token(s) | Avg RTF | Quality |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for cfg in sorted(by_cfg):
        rs = by_cfg[cfg]
        w = avg([x.wer for x in rs if x.wer is not None])
        c = avg([x.cer for x in rs if x.cer is not None])
        tt = avg([x.total_s for x in rs if x.total_s is not None])
        ft = avg([x.first_s for x in rs if x.first_s is not None])
        rtf = avg([x.rtf for x in rs if x.rtf is not None])
        lines.append(f"| {cfg} | {len(rs)} | {fmt(w)} | {fmt(c)} | {fmt(tt)} | {fmt(ft)} | {fmt(rtf)} | {wer_label(w)} |")
    lines.append("")

    lines.append("## Per-Sample Mistakes")
    lines.append("")
    for audio in sorted(by_audio):
        lines.append(f"### {audio}")
        sample_rows = sorted(by_audio[audio], key=lambda x: x.config)
        ref = sample_rows[0].ref
        lines.append("")
        lines.append("Reference:")
        lines.append("")
        lines.append(ref if ref else "<missing reference>")
        lines.append("")
        for r in sample_rows:
            sub, ins, dele = word_error_breakdown(r.ref, r.hyp) if r.ref else (0, 0, 0)
            dist = levenshtein(tokenize_words(r.ref.lower()), tokenize_words(r.hyp.lower())) if r.ref else 0
            lines.append(f"- Config: `{r.config}`")
            lines.append(f"  WER={fmt(r.wer)} CER={fmt(r.cer)} | total={fmt(r.total_s,2)}s first={fmt(r.first_s,2)}s | edits(sub/ins/del)={sub}/{ins}/{dele} (distance={dist})")
            lines.append("  Hypothesis:")
            lines.append(f"  {normalize_ws(r.hyp)}")
            lines.append("")

    Path(args.output).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
