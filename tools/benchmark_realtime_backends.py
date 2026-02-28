#!/usr/bin/env python3
"""Benchmark Voxtral(voxmlx realtime) vs Whisper backends.

Inputs come from a manifest JSONL (one item per line):
  {"audio": "recordings/.../audio.wav", "reference": "optional text"}

If reference is provided, computes WER/CER (simple Levenshtein metrics).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import contextlib
import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import websockets


@dataclass
class AudioItem:
    audio: str
    reference: str | None


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_text(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def tokenize(s: str) -> list[str]:
    s = normalize_text(s)
    return [t for t in re.split(r"[^\w']+", s) if t]


def levenshtein(seq_a: list[Any], seq_b: list[Any]) -> int:
    if not seq_a:
        return len(seq_b)
    if not seq_b:
        return len(seq_a)
    prev = list(range(len(seq_b) + 1))
    for i, a in enumerate(seq_a, start=1):
        cur = [i]
        for j, b in enumerate(seq_b, start=1):
            cost = 0 if a == b else 1
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def wer_cer(reference: str, hypothesis: str) -> dict[str, float]:
    ref_w = tokenize(reference)
    hyp_w = tokenize(hypothesis)
    ref_c = list(normalize_text(reference).replace(" ", ""))
    hyp_c = list(normalize_text(hypothesis).replace(" ", ""))

    w_dist = levenshtein(ref_w, hyp_w)
    c_dist = levenshtein(ref_c, hyp_c)

    wer = w_dist / max(1, len(ref_w))
    cer = c_dist / max(1, len(ref_c))
    return {"wer": wer, "cer": cer}


def load_manifest(path: str) -> list[AudioItem]:
    items: list[AudioItem] = []
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            audio = obj.get("audio")
            if not audio:
                raise ValueError(f"Manifest line {idx}: missing 'audio'")
            ref = obj.get("reference")
            items.append(AudioItem(audio=audio, reference=ref))
    return items


def discover_audio() -> list[AudioItem]:
    paths = sorted(Path("recordings").glob("*/*/audio.wav"))
    return [AudioItem(audio=str(p), reference=None) for p in paths]


def audio_duration_sec(path: str) -> float | None:
    try:
        p = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return float((p.stdout or "").strip())
    except Exception:
        return None


def read_audio_16k_mono(path: str) -> np.ndarray:
    data, sr = sf.read(path, dtype="float32", always_2d=False)
    if data.ndim == 2:
        data = data.mean(axis=1)
    if sr != 16000:
        # Lightweight linear resample to avoid extra dependency.
        src_idx = np.arange(len(data), dtype=np.float64)
        dst_len = int(round(len(data) * 16000 / sr))
        dst_idx = np.linspace(0, max(0, len(data) - 1), dst_len, dtype=np.float64)
        data = np.interp(dst_idx, src_idx, data).astype(np.float32)
    return np.clip(data, -1.0, 1.0)


def transcribe_faster(audio: str, model: str) -> tuple[str, dict[str, float]]:
    t0 = time.time()
    from faster_whisper import WhisperModel  # lazy import

    model_obj = WhisperModel(model, device="cpu", compute_type="int8")
    t_model = time.time()
    segments, _ = model_obj.transcribe(audio, beam_size=1, best_of=1)
    text = " ".join(s.text for s in segments).strip()
    t1 = time.time()
    return text, {
        "load_s": t_model - t0,
        "transcribe_s": t1 - t_model,
        "total_s": t1 - t0,
        "first_token_s": t1 - t0,  # one-shot backend
    }


def transcribe_mlx(audio: str, model: str) -> tuple[str, dict[str, float]]:
    repo_map = {
        "tiny": "mlx-community/whisper-tiny-mlx",
        "base": "mlx-community/whisper-base-mlx",
        "small": "mlx-community/whisper-small-mlx",
        "medium": "mlx-community/whisper-medium-mlx",
    }
    repo = repo_map.get(model, "mlx-community/whisper-medium-mlx")
    payload = r'''
import json
import sys
import time
import mlx_whisper

audio = sys.argv[1]
repo = sys.argv[2]
t0 = time.time()
try:
    out = mlx_whisper.transcribe(audio, path_or_hf_repo=repo)
except TypeError:
    out = mlx_whisper.transcribe(audio, repo)
t1 = time.time()
text = out.get("text", "") if isinstance(out, dict) else str(out)
print(json.dumps({"text": text.strip(), "total_s": t1 - t0}))
'''.strip()
    t0 = time.time()
    proc = subprocess.run(["python3", "-c", payload, audio, repo], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "mlx transcribe failed").strip())
    lines = (proc.stdout or "").strip().splitlines()
    data = json.loads(lines[-1])
    total = float(data.get("total_s", time.time() - t0))
    text = data.get("text", "").strip()
    return text, {
        "load_s": 0.0,
        "transcribe_s": total,
        "total_s": total,
        "first_token_s": total,
    }


async def transcribe_voxmlx(
    audio: str,
    url: str,
    model: str,
    chunk_ms: int,
    commit_every_s: float,
    realtime_pace: bool,
    client_like_mode: bool,
    post_commit_idle_s: float,
    max_wait_s: float,
) -> tuple[str, dict[str, float]]:
    samples = read_audio_16k_mono(audio)
    chunk_samples = max(1, int(16000 * chunk_ms / 1000))

    current_text: list[str] = []
    finalized_text: str | None = None
    first_token_at: float | None = None
    last_delta_at: float | None = None

    t_start = time.time()
    t_connected: float | None = None
    t_audio_done: float | None = None

    async with websockets.connect(
        url,
        max_size=10 * 1024 * 1024,
        ping_interval=None,
        ping_timeout=None,
    ) as ws:
        t_connected = time.time()
        await ws.send(json.dumps({"type": "session.update", "model": model, "temperature": 0.0}))
        # Match interactive client semantics: open a new segment before streaming audio.
        await ws.send(json.dumps({"type": "input_audio_buffer.commit", "final": False}))

        async def recv_loop() -> None:
            nonlocal first_token_at, last_delta_at, finalized_text
            while True:
                raw = await ws.recv()
                obj = json.loads(raw)
                evt = obj.get("type", "")
                if evt in {"response.audio_transcript.delta", "transcription.delta"}:
                    delta = obj.get("delta", "")
                    if delta:
                        current_text.append(delta)
                        now = time.time()
                        if first_token_at is None:
                            first_token_at = now
                        last_delta_at = now
                elif evt in {"transcription.done", "transcription.final", "response.audio_transcript.done"}:
                    # Prefer final server text when available (can include corrections not present in deltas).
                    full = (obj.get("text") or obj.get("transcript") or "").strip()
                    if full:
                        finalized_text = full
                    last_delta_at = time.time()
                elif evt == "error":
                    raise RuntimeError(f"server error: {obj}")

        recv_task = asyncio.create_task(recv_loop())
        try:
            last_commit = time.time()
            for i in range(0, len(samples), chunk_samples):
                chunk = samples[i:i + chunk_samples]
                pcm16 = (chunk * 32767.0).astype(np.int16)
                b64 = base64.b64encode(pcm16.tobytes()).decode("ascii")
                await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": b64}))

                now = time.time()
                if (not client_like_mode) and commit_every_s > 0 and (now - last_commit >= commit_every_s):
                    await ws.send(json.dumps({"type": "input_audio_buffer.commit", "final": False}))
                    last_commit = now

                if realtime_pace:
                    await asyncio.sleep(len(chunk) / 16000.0)

            await ws.send(json.dumps({"type": "input_audio_buffer.commit", "final": True}))
            t_audio_done = time.time()

            wait_start = time.time()
            while True:
                now = time.time()
                if finalized_text and last_delta_at is not None and (now - last_delta_at) >= post_commit_idle_s:
                    break
                if last_delta_at is not None and (now - last_delta_at) >= post_commit_idle_s and finalized_text is None:
                    break
                if (now - wait_start) >= max_wait_s:
                    break
                await asyncio.sleep(0.05)
        finally:
            recv_task.cancel()
            with contextlib.suppress(BaseException):
                await recv_task

    t_end = time.time()
    text = finalized_text or "".join(current_text).strip()
    first_token_s = (first_token_at - t_start) if first_token_at is not None else None
    return text, {
        "connect_s": (t_connected - t_start) if t_connected else None,
        "send_audio_s": (t_audio_done - t_connected) if (t_audio_done and t_connected) else None,
        "total_s": t_end - t_start,
        "first_token_s": first_token_s,
        "load_s": 0.0,
        "transcribe_s": t_end - t_start,
    }


def build_result(
    backend: str,
    model_name: str,
    audio: str,
    text: str,
    timings: dict[str, float],
    ref: str | None,
) -> dict[str, Any]:
    duration = audio_duration_sec(audio)
    row: dict[str, Any] = {
        "backend": backend,
        "model": model_name,
        "config": f"{backend}:{model_name}",
        "audio": audio,
        "audio_duration_s": duration,
        "text": text,
        "text_len": len(text),
        "timings": timings,
    }
    if duration and timings.get("total_s") is not None:
        row["rtf_total"] = timings["total_s"] / duration
    if duration and timings.get("first_token_s") is not None:
        row["rtf_first_token"] = timings["first_token_s"] / duration
    if ref:
        row["reference"] = ref
        row["metrics"] = wer_cer(ref, text)
    return row


def ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Benchmark Voxtral/Whisper backends")
    ap.add_argument("--manifest", help="JSONL manifest with audio/reference entries")
    ap.add_argument("--backend", action="append", choices=["voxmlx", "faster", "mlx"], help="Backend(s) to run")
    ap.add_argument("--model-whisper", default="medium", help="Whisper model size for faster/mlx")
    ap.add_argument("--voxmlx-url", default="ws://127.0.0.1:8000/v1/realtime")
    ap.add_argument("--voxmlx-model", default="mistralai/Voxtral-Mini-4B-Realtime-2602")
    ap.add_argument("--chunk-ms", type=int, default=80)
    ap.add_argument("--commit-every", type=float, default=0.7)
    ap.add_argument("--realtime-pace", action="store_true", help="Replay audio in real-time pace")
    ap.add_argument(
        "--voxmlx-clientlike",
        action="store_true",
        help="Emulate live client: realtime pacing + start/end commits only (no periodic commits)",
    )
    ap.add_argument("--post-commit-idle", type=float, default=1.2)
    ap.add_argument("--max-wait", type=float, default=10.0)
    ap.add_argument("--output", default="benchmarks/realtime_backend_benchmark_latest.json")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    backends = args.backend or ["voxmlx", "mlx", "faster"]

    if args.manifest:
        items = load_manifest(args.manifest)
    else:
        items = discover_audio()

    if not items:
        raise SystemExit("No audio items found. Provide --manifest or add recordings/*/*/audio.wav")

    report: dict[str, Any] = {
        "timestamp": now_iso(),
        "args": vars(args),
        "items": [item.__dict__ for item in items],
        "results": [],
        "errors": [],
    }

    for item in items:
        if not os.path.isfile(item.audio):
            report["errors"].append(f"missing audio: {item.audio}")
            continue

        for backend in backends:
            label = f"{backend}:{item.audio}"
            print(f"Running {label} ...", flush=True)
            try:
                model_name = ""
                if backend == "faster":
                    model_name = f"whisper-{args.model_whisper}"
                    text, timings = transcribe_faster(item.audio, args.model_whisper)
                elif backend == "mlx":
                    model_name = f"whisper-{args.model_whisper}"
                    text, timings = transcribe_mlx(item.audio, args.model_whisper)
                else:
                    model_name = args.voxmlx_model
                    text, timings = asyncio.run(
                        transcribe_voxmlx(
                            audio=item.audio,
                            url=args.voxmlx_url,
                            model=args.voxmlx_model,
                            chunk_ms=args.chunk_ms,
                            commit_every_s=args.commit_every,
                            realtime_pace=(args.realtime_pace or args.voxmlx_clientlike),
                            client_like_mode=args.voxmlx_clientlike,
                            post_commit_idle_s=args.post_commit_idle,
                            max_wait_s=args.max_wait,
                        )
                    )

                result = build_result(backend, model_name, item.audio, text, timings, item.reference)
                report["results"].append(result)
                t = result["timings"].get("total_s")
                ft = result["timings"].get("first_token_s")
                print(f"  OK total={t:.2f}s first_token={ft if ft is None else round(ft, 2)} text_len={len(text)}")
            except Exception as exc:
                msg = f"{label}: {exc}"
                report["errors"].append(msg)
                print(f"  ERROR {exc}")

    ensure_parent(args.output)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\nSaved report: {args.output}")
    print(f"Results: {len(report['results'])}, Errors: {len(report['errors'])}")


if __name__ == "__main__":
    main()
