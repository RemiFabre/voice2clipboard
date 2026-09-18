"""Streaming transcription quality gate.

Simulates a live recording by growing a raw PCM file the way the recorder does,
drives the helper's StreamSession on it, and checks that chunked decoding is as
accurate as whole-file decoding while the final stream_end call stays fast.
Needs the recordings and the MLX model; skips otherwise (~3 min on M3 Pro).
"""
import collections
import difflib
import json
import os
import re
import sys
import tempfile
import threading
import time
import unicodedata
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))

LONG_WAV = os.path.join(ROOT, "recordings", "2026-09-17", "10-13-06", "audio.wav")
REAL_WAV = os.path.join(ROOT, "recordings", "2026-09-17", "20-40-30", "audio.wav")
MANIFEST = os.path.join(ROOT, "benchmarks", "private", "manifest_groundtruth_long_en_20260917.jsonl")  # private, gitignored


def norm(t):
    t = unicodedata.normalize("NFKC", t).lower()
    t = re.sub(r"[’‘]", "'", t)
    t = re.sub(r"[^\w\s']", " ", t)
    t = re.sub(r"\b(um|uh|hmm|mm)\b", " ", t)
    return t.split()


def wer(ref_words, hyp_words):
    prev = list(range(len(hyp_words) + 1))
    for x in ref_words:
        cur = [prev[0] + 1]
        for j, y in enumerate(hyp_words, 1):
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1] / max(1, len(ref_words))


def loop_stats(text):
    words = text.split()
    longest = run = 1
    for a, b in zip(words, words[1:]):
        run = run + 1 if a.lower() == b.lower() else 1
        longest = max(longest, run)
    sents = [s.strip().lower() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    consecutive = sum(1 for a, b in zip(sents, sents[1:]) if a == b)
    most_common = collections.Counter(sents).most_common(1)[0][1] if sents else 0
    return {"longest_word_run": longest, "consecutive_dup_sentences": consecutive, "max_sentence_count": most_common}


def feed_pcm(wav_path, pcm_path, audio_seconds_per_step, sleep_per_step, stop_event):
    """Write the WAV as int16 PCM into pcm_path in steps, like a live recorder."""
    import soundfile as sf

    audio, sr = sf.read(wav_path, dtype="int16")
    step = int(audio_seconds_per_step * sr)
    with open(pcm_path, "ab") as f:
        for i in range(0, len(audio), step):
            if stop_event.is_set():
                break
            f.write(audio[i : i + step].tobytes())
            f.flush()
            time.sleep(sleep_per_step)


def run_stream(helper, wav_path, audio_seconds_per_step=5.0, sleep_per_step=0.25):
    pcm_path = os.path.join(tempfile.mkdtemp(), "audio.pcm")
    open(pcm_path, "wb").close()
    stop = threading.Event()
    writer = threading.Thread(target=feed_pcm, args=(wav_path, pcm_path, audio_seconds_per_step, sleep_per_step, stop))
    session = helper.StreamSession("test", pcm_path)
    session.start()
    writer.start()
    writer.join()
    t_end = time.time()
    text, stats = session.end()
    stats["end_wall_seconds"] = round(time.time() - t_end, 3)
    return text, stats


@unittest.skipUnless(os.path.exists(LONG_WAV) and os.path.exists(MANIFEST), "benchmark recording not available")
class StreamingMatchesWholeFile(unittest.TestCase):
    def test_streamed_long_dictation_is_as_accurate_and_ends_fast(self):
        import mlx_whisper_helper as helper

        with open(MANIFEST) as f:
            reference = norm(json.loads(f.readline())["reference"])

        baseline_text, _elapsed, _vad = helper.transcribe(LONG_WAV)
        baseline_wer = wer(reference, norm(baseline_text))

        # 37 min of audio fed at 5 s per 0.25 s (20x real time): decoding must keep up.
        text, stats = run_stream(helper, LONG_WAV, audio_seconds_per_step=5.0, sleep_per_step=0.25)
        streamed_wer = wer(reference, norm(text))
        loops = loop_stats(text)
        print(f"\nbaseline WER={baseline_wer:.3f} streamed WER={streamed_wer:.3f} stats={stats}")

        self.assertLessEqual(loops["longest_word_run"], 3, (loops, text[:500]))
        self.assertEqual(loops["consecutive_dup_sentences"], 0, (loops, text[:500]))
        self.assertLessEqual(streamed_wer, baseline_wer + 0.005, (baseline_wer, streamed_wer))
        self.assertLess(stats["end_wall_seconds"], 5.0, stats)
        self.assertGreater(stats["chunks"], 5, stats)


@unittest.skipUnless(os.path.exists(REAL_WAV), "real dictation recording not available")
class StreamingRealDictationLatency(unittest.TestCase):
    def test_four_minute_dictation_ends_fast(self):
        import mlx_whisper_helper as helper

        text, stats = run_stream(helper, REAL_WAV, audio_seconds_per_step=5.0, sleep_per_step=0.5)
        print(f"\nreal dictation: {len(text.split())} words, stats={stats}")
        self.assertTrue(text.strip())
        self.assertLess(stats["end_wall_seconds"], 5.0, stats)


if __name__ == "__main__":
    unittest.main()
