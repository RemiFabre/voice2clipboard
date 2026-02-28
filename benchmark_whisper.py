#!/usr/bin/env python3
"""
Benchmark different Whisper configurations to find the best speed/quality tradeoff.
"""

import time
import sys
import platform
import subprocess
import json
from faster_whisper import WhisperModel

# Test file - use the most recent recording or pass as argument
DEFAULT_TEST_FILE = "recordings/2026-01-31/14-58-08/audio.wav"
IS_MAC = platform.system() == "Darwin"
DEVICE = "cpu" if IS_MAC else "cuda"
COMPUTE_TYPES = ["int8"] if IS_MAC else ["float16", "int8"]

# Configurations to test
CONFIGS = []
for compute_type in COMPUTE_TYPES:
    CONFIGS.extend([
        # (model_size, compute_type, beam_size, best_of)
        ("medium", compute_type, 5, 5),
        ("medium", compute_type, 1, 1),
        ("small", compute_type, 5, 5),
        ("small", compute_type, 1, 1),
        ("base", compute_type, 5, 5),
        ("base", compute_type, 1, 1),
        ("tiny", compute_type, 5, 5),
        ("tiny", compute_type, 1, 1),
    ])


def benchmark_config(test_file, model_size, compute_type, beam_size, best_of):
    """Run a single benchmark configuration."""

    # Measure model loading time
    load_start = time.time()
    model = WhisperModel(model_size, device=DEVICE, compute_type=compute_type)
    load_time = time.time() - load_start

    # Measure transcription time
    transcribe_start = time.time()
    segments, info = model.transcribe(
        test_file,
        beam_size=beam_size,
        best_of=best_of,
    )
    text = " ".join([seg.text for seg in segments])
    transcribe_time = time.time() - transcribe_start

    total_time = load_time + transcribe_time

    return {
        "model": model_size,
        "compute": compute_type,
        "beam": beam_size,
        "best_of": best_of,
        "load_time": load_time,
        "transcribe_time": transcribe_time,
        "total_time": total_time,
        "text": text,
        "text_len": len(text),
    }


def get_audio_duration_sec(test_file):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', test_file],
            capture_output=True, text=True
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def benchmark_mlx(test_file, model_size):
    repo = f"mlx-community/whisper-{model_size}-mlx"
    payload = r"""
import json
import sys
audio = sys.argv[1]
repo = sys.argv[2]
import mlx_whisper
try:
    result = mlx_whisper.transcribe(audio, path_or_hf_repo=repo)
except TypeError:
    result = mlx_whisper.transcribe(audio, repo)
text = result.get("text", "") if isinstance(result, dict) else str(result)
print(json.dumps({"text": text.strip()}))
""".strip()
    start = time.time()
    proc = subprocess.run([sys.executable, "-c", payload, test_file, repo], capture_output=True, text=True)
    elapsed = time.time() - start
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "mlx failed").strip())
    lines = (proc.stdout or "").strip().splitlines()
    if not lines:
        raise RuntimeError("mlx returned no output")
    text = json.loads(lines[-1]).get("text", "")
    return {
        "model": model_size,
        "compute": "mlx",
        "beam": 1,
        "best_of": 1,
        "load_time": 0.0,
        "transcribe_time": elapsed,
        "total_time": elapsed,
        "text": text,
        "text_len": len(text),
    }


def main():
    test_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEST_FILE
    include_mlx = "--include-mlx" in sys.argv

    print(f"Benchmarking Whisper configurations")
    print(f"Test file: {test_file}")
    print(f"Device: {DEVICE}")
    duration = get_audio_duration_sec(test_file)
    if duration:
        print(f"Audio duration: {duration:.2f}s")
    print("=" * 80)

    results = []
    baseline_text = None

    for i, (model_size, compute_type, beam_size, best_of) in enumerate(CONFIGS):
        config_name = f"{model_size}/{compute_type}/beam={beam_size}"
        print(f"\n[{i+1}/{len(CONFIGS)}] Testing: {config_name}")

        try:
            result = benchmark_config(test_file, model_size, compute_type, beam_size, best_of)
            results.append(result)

            if baseline_text is None:
                baseline_text = result["text"]

            print(f"  Load time:       {result['load_time']:.2f}s")
            print(f"  Transcribe time: {result['transcribe_time']:.2f}s")
            print(f"  Total time:      {result['total_time']:.2f}s")
            print(f"  Output length:   {result['text_len']} chars")

        except Exception as e:
            print(f"  ERROR: {e}")

    # Summary table
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'Config':<40} {'Load':>7} {'Trans':>7} {'Total':>7} {'RTF':>7} {'Chars':>6}")
    print("-" * 80)

    for r in results:
        config = f"{r['model']}/{r['compute']}/beam={r['beam']}"
        rtf = (r["transcribe_time"] / duration) if duration else 0.0
        print(f"{config:<40} {r['load_time']:>6.2f}s {r['transcribe_time']:>6.2f}s {r['total_time']:>6.2f}s {rtf:>6.2f}x {r['text_len']:>6}")

    if IS_MAC and include_mlx:
        print("\n" + "=" * 80)
        print("MLX BENCHMARKS")
        print("=" * 80)
        for model in ["medium", "small", "base", "tiny"]:
            print(f"\nTesting mlx/{model}...", end=" ", flush=True)
            try:
                r = benchmark_mlx(test_file, model)
                rtf = (r["transcribe_time"] / duration) if duration else 0.0
                print(f"done ({r['transcribe_time']:.2f}s, RTF {rtf:.2f}x)")
            except Exception as e:
                print(f"ERROR: {e}")

    # Show transcription samples for quality comparison
    print("\n" + "=" * 80)
    print("TRANSCRIPTION SAMPLES (first 200 chars)")
    print("=" * 80)

    for r in results:
        config = f"{r['model']}/{r['compute']}"
        print(f"\n[{config}]")
        print(r["text"][:200] + "..." if len(r["text"]) > 200 else r["text"])

    # Daemon value analysis
    print("\n" + "=" * 80)
    print("DAEMON VALUE ANALYSIS")
    print("=" * 80)
    if results:
        avg_load = sum(r["load_time"] for r in results) / len(results)
        medium_loads = [r["load_time"] for r in results if r["model"] == "medium"]
        if medium_loads:
            avg_medium_load = sum(medium_loads) / len(medium_loads)
            print(f"Average model load time (all): {avg_load:.2f}s")
            print(f"Average medium model load time: {avg_medium_load:.2f}s")
            print(f"A daemon would save ~{avg_medium_load:.1f}s per transcription for medium model")


if __name__ == "__main__":
    main()
