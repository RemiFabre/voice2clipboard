#!/usr/bin/env python3
"""
Compare transcription quality across different Whisper configurations.
"""

import time
import sys
from faster_whisper import WhisperModel

DEFAULT_TEST_FILE = "recordings/2026-01-31/14-58-08/audio.wav"
DEVICE = "cuda"

CONFIGS = [
    ("medium", "float16", 5, 5),
    ("medium", "float16", 1, 1),
    ("small", "float16", 5, 5),
    ("small", "int8", 1, 1),
    ("base", "int8", 1, 1),
    ("tiny", "int8", 1, 1),
]


def transcribe(test_file, model_size, compute_type, beam_size, best_of):
    model = WhisperModel(model_size, device=DEVICE, compute_type=compute_type)
    segments, info = model.transcribe(test_file, beam_size=beam_size, best_of=best_of)
    return " ".join([seg.text for seg in segments])


def find_differences(reference, comparison):
    """Find words that differ between reference and comparison."""
    ref_words = reference.lower().split()
    comp_words = comparison.lower().split()

    differences = []

    # Simple word-by-word comparison (not perfect but good enough)
    max_len = max(len(ref_words), len(comp_words))

    i, j = 0, 0
    while i < len(ref_words) and j < len(comp_words):
        if ref_words[i] != comp_words[j]:
            # Find the extent of the difference
            ref_word = ref_words[i] if i < len(ref_words) else ""
            comp_word = comp_words[j] if j < len(comp_words) else ""
            differences.append((ref_word, comp_word))
        i += 1
        j += 1

    return differences


def main():
    test_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEST_FILE

    print(f"Test file: {test_file}")
    print("=" * 80)

    results = []

    for model_size, compute_type, beam_size, best_of in CONFIGS:
        config_name = f"{model_size}/{compute_type}/beam={beam_size}"
        print(f"\nTranscribing with {config_name}...", end=" ", flush=True)

        start = time.time()
        text = transcribe(test_file, model_size, compute_type, beam_size, best_of)
        elapsed = time.time() - start

        print(f"done ({elapsed:.1f}s)")
        results.append((config_name, text, elapsed))

    # Output full transcriptions
    print("\n" + "=" * 80)
    print("FULL TRANSCRIPTIONS")
    print("=" * 80)

    for config_name, text, elapsed in results:
        print(f"\n### {config_name} ({elapsed:.1f}s) ###\n")
        print(text)
        print()

    # Compare against reference (first one = medium/float16/beam=5)
    reference_text = results[0][1]
    reference_name = results[0][0]

    print("\n" + "=" * 80)
    print(f"DIFFERENCES vs REFERENCE ({reference_name})")
    print("=" * 80)

    for config_name, text, elapsed in results[1:]:
        diffs = find_differences(reference_text, text)
        print(f"\n### {config_name} ###")
        if diffs:
            print(f"Found {len(diffs)} potential differences:")
            for ref_word, comp_word in diffs[:20]:  # Limit to first 20
                print(f"  '{ref_word}' -> '{comp_word}'")
            if len(diffs) > 20:
                print(f"  ... and {len(diffs) - 20} more")
        else:
            print("  No differences found (or very similar)")


if __name__ == "__main__":
    main()
