#!/usr/bin/env python3
"""
Benchmark different Whisper configurations to find the best speed/quality tradeoff.
"""

import time
import sys
from faster_whisper import WhisperModel

# Test file - use the most recent recording or pass as argument
DEFAULT_TEST_FILE = "recordings/2026-01-31/14-58-08/audio.wav"

DEVICE = "cuda"

# Configurations to test
CONFIGS = [
    # (model_size, compute_type, beam_size, best_of)
    ("medium", "float16", 5, 5),   # Current config (baseline)
    ("medium", "float16", 1, 1),   # Reduced beam
    ("medium", "int8", 5, 5),      # int8 quantization
    ("medium", "int8", 1, 1),      # int8 + reduced beam
    ("small", "float16", 5, 5),    # Smaller model
    ("small", "int8", 1, 1),       # Small optimized
    ("base", "float16", 5, 5),     # Even smaller
    ("base", "int8", 1, 1),        # Base optimized
    ("tiny", "float16", 5, 5),     # Smallest
    ("tiny", "int8", 1, 1),        # Tiny optimized
]


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


def main():
    test_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEST_FILE

    print(f"Benchmarking Whisper configurations")
    print(f"Test file: {test_file}")
    print(f"Device: {DEVICE}")
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
    print(f"{'Config':<40} {'Load':>7} {'Trans':>7} {'Total':>7} {'Chars':>6}")
    print("-" * 80)

    for r in results:
        config = f"{r['model']}/{r['compute']}/beam={r['beam']}"
        print(f"{config:<40} {r['load_time']:>6.2f}s {r['transcribe_time']:>6.2f}s {r['total_time']:>6.2f}s {r['text_len']:>6}")

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
