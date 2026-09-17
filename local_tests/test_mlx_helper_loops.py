"""Regression test: the MLX helper must not emit Whisper repetition loops.

Reproduces the 2026-09-17 failure where a 60 s silent stretch after 60 s of speech
made whisper-medium repeat "So, I'm going to start with a brief introduction."
twenty times. Needs the local recording (recordings/ is gitignored) and the MLX
model in the HF cache; skips otherwise. Runs the real model on the full 37 min
file (~1 min on M3 Pro): a short slice does not reproduce the loop because
Whisper normalises the log-mel spectrogram against the loudest point of the
whole file, which changes what the silent windows look like to the decoder.
"""
import collections
import os
import re
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))

SOURCE_WAV = os.path.join(ROOT, "recordings", "2026-09-17", "10-13-06", "audio.wav")


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


@unittest.skipUnless(os.path.exists(SOURCE_WAV), "source recording not available")
class MlxHelperDoesNotLoop(unittest.TestCase):
    def test_silence_after_speech_does_not_trigger_repetition_loop(self):
        import mlx_whisper_helper as helper

        text, _elapsed, _vad = helper.transcribe(SOURCE_WAV)
        stats = loop_stats(text)
        self.assertLessEqual(stats["longest_word_run"], 3, (stats, text))
        self.assertEqual(stats["consecutive_dup_sentences"], 0, (stats, text))
        self.assertLessEqual(stats["max_sentence_count"], 2, (stats, text))
        self.assertIn("discord", text.lower(), text)


if __name__ == "__main__":
    unittest.main()
