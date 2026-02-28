#!/usr/bin/env python3
"""
Full macOS benchmark for voice2clipboard.

Compares:
- faster-whisper (CPU/int8) with cold vs warm timings
- mlx-whisper (Metal) with cold vs warm timings in an isolated subprocess

Outputs:
- Console summary
- JSON report saved under benchmarks/
"""

import argparse
import glob
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime

from faster_whisper import WhisperModel


MLX_MODEL_REPOS = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v2": "mlx-community/whisper-large-v2-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
}


def latest_audio_file():
    files = sorted(glob.glob("recordings/*/*/audio.wav"))
    return files[-1] if files else None


def audio_duration_sec(path):
    try:
        res = subprocess.run(
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
            capture_output=True,
            text=True,
            check=True,
        )
        return float(res.stdout.strip())
    except Exception:
        return None


def bench_faster_whisper(audio_path, model_size, beam_size):
    load_t0 = time.time()
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    load_s = time.time() - load_t0

    run1_t0 = time.time()
    seg1, _ = model.transcribe(audio_path, beam_size=beam_size, best_of=beam_size)
    run1_s = time.time() - run1_t0
    text1 = " ".join(s.text for s in seg1).strip()

    run2_t0 = time.time()
    seg2, _ = model.transcribe(audio_path, beam_size=beam_size, best_of=beam_size)
    run2_s = time.time() - run2_t0
    text2 = " ".join(s.text for s in seg2).strip()

    return {
        "backend": "faster-whisper",
        "model": model_size,
        "beam": beam_size,
        "compute": "int8/cpu",
        "load_s": load_s,
        "cold_transcribe_s": run1_s,
        "warm_transcribe_s": run2_s,
        "cold_total_s": load_s + run1_s,
        "warm_total_s": run2_s,
        "text_len_cold": len(text1),
        "text_len_warm": len(text2),
    }


def bench_mlx(audio_path, model_size):
    repo = MLX_MODEL_REPOS.get(model_size)
    if not repo:
        raise ValueError(f"No MLX repo mapping for model {model_size}")

    payload = r"""
import json
import sys
import time

audio = sys.argv[1]
repo = sys.argv[2]

import mlx_whisper

def do_transcribe():
    t0 = time.time()
    try:
        out = mlx_whisper.transcribe(audio, path_or_hf_repo=repo)
    except TypeError:
        out = mlx_whisper.transcribe(audio, repo)
    elapsed = time.time() - t0
    if isinstance(out, dict):
        text = out.get("text", "")
    else:
        text = str(out)
    return elapsed, text.strip()

cold_s, cold_text = do_transcribe()
warm_s, warm_text = do_transcribe()
print(json.dumps({
    "cold_transcribe_s": cold_s,
    "warm_transcribe_s": warm_s,
    "text_len_cold": len(cold_text),
    "text_len_warm": len(warm_text),
}))
""".strip()

    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, "-c", payload, audio_path, repo],
        capture_output=True,
        text=True,
    )
    wall_s = time.time() - t0

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "mlx benchmark failed").strip()
        raise RuntimeError(err)

    lines = (proc.stdout or "").strip().splitlines()
    if not lines:
        raise RuntimeError("mlx benchmark returned no output")
    data = json.loads(lines[-1])

    return {
        "backend": "mlx-whisper",
        "model": model_size,
        "beam": 1,
        "compute": "metal",
        "load_s": None,  # Included in cold run inside mlx call
        "cold_transcribe_s": data["cold_transcribe_s"],
        "warm_transcribe_s": data["warm_transcribe_s"],
        "cold_total_s": data["cold_transcribe_s"],
        "warm_total_s": data["warm_transcribe_s"],
        "text_len_cold": data["text_len_cold"],
        "text_len_warm": data["text_len_warm"],
        "subprocess_wall_s": wall_s,
    }


def format_num(x):
    if x is None:
        return "-"
    return f"{x:.2f}"


def main():
    parser = argparse.ArgumentParser(description="Run full benchmark on macOS.")
    parser.add_argument("audio", nargs="?", help="Path to audio file to benchmark.")
    parser.add_argument(
        "--models",
        default="medium,small,base,tiny",
        help="Comma-separated model list (default: medium,small,base,tiny)",
    )
    args = parser.parse_args()

    audio = args.audio or latest_audio_file()
    if not audio:
        print("No audio provided and no recordings/*/*/audio.wav found.", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(audio):
        print(f"Audio file not found: {audio}", file=sys.stderr)
        sys.exit(1)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    duration = audio_duration_sec(audio)

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "system": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "python_executable": sys.executable,
        },
        "audio_path": audio,
        "audio_duration_s": duration,
        "results": [],
        "errors": [],
    }

    print("Full macOS Whisper benchmark")
    print(f"Audio: {audio}")
    if duration:
        print(f"Duration: {duration:.2f}s")
    print("-" * 80)

    for model in models:
        # faster-whisper beam=1 always, plus beam=5 for medium to show quality/speed tradeoff
        beams = [1, 5] if model == "medium" else [1]
        for beam in beams:
            label = f"faster-whisper/{model}/beam={beam}"
            print(f"Running {label} ...", end=" ", flush=True)
            try:
                result = bench_faster_whisper(audio, model, beam)
                if duration:
                    result["cold_rtf"] = result["cold_transcribe_s"] / duration
                    result["warm_rtf"] = result["warm_transcribe_s"] / duration
                report["results"].append(result)
                print("OK")
            except Exception as e:
                msg = f"{label}: {e}"
                report["errors"].append(msg)
                print(f"ERROR ({e})")

        label = f"mlx-whisper/{model}"
        print(f"Running {label} ...", end=" ", flush=True)
        try:
            result = bench_mlx(audio, model)
            if duration:
                result["cold_rtf"] = result["cold_transcribe_s"] / duration
                result["warm_rtf"] = result["warm_transcribe_s"] / duration
            report["results"].append(result)
            print("OK")
        except Exception as e:
            msg = f"{label}: {e}"
            report["errors"].append(msg)
            print(f"ERROR ({e})")

    print("\nSummary")
    print(
        f"{'Backend':<16} {'Model':<8} {'Beam':<4} {'Cold(s)':>8} {'Warm(s)':>8} {'Cold RTF':>8} {'Warm RTF':>8}"
    )
    print("-" * 80)
    for r in report["results"]:
        print(
            f"{r['backend']:<16} "
            f"{r['model']:<8} "
            f"{str(r['beam']):<4} "
            f"{format_num(r['cold_transcribe_s']):>8} "
            f"{format_num(r['warm_transcribe_s']):>8} "
            f"{format_num(r.get('cold_rtf')):>8} "
            f"{format_num(r.get('warm_rtf')):>8}"
        )

    os.makedirs("benchmarks", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join("benchmarks", f"mac_full_benchmark_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nSaved report: {out_path}")
    if report["errors"]:
        print("\nErrors:")
        for e in report["errors"]:
            print(f"- {e}")


if __name__ == "__main__":
    main()

