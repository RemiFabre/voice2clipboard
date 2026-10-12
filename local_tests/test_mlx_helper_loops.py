"""Regression test: the MLX helper must not emit Whisper repetition loops.

Reproduces the 2026-09-17 failure where a 60 s silent stretch after 60 s of speech
made whisper-medium repeat one hallucinated sentence twenty times. Needs the local recording (recordings/ is gitignored) and the MLX
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
# 2026-10-12: a 15 min dictation with a two-minute pause and a 3 s pause that VAD let through;
# the streaming helper filled whole windows with one phrase ("I think" x111, "run" x223).
PAUSE_PCM = os.path.join(ROOT, "recordings", "2026-10-12", "21-19-59", "audio.pcm")


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


def replay_stream(helper, pcm_path):
    """The live chunking of StreamSession replayed offline: the file grows by one second per
    step, closed VAD regions accumulate to STREAM_MIN_CHUNK_SPEECH_S (or wait
    STREAM_MAX_CHUNK_WAIT_S) and are decoded through decode_speech, as in a real dictation."""
    import numpy as np
    from faster_whisper.vad import collect_chunks, get_speech_timestamps

    sr = helper.SAMPLE_RATE
    with open(pcm_path, "rb") as f:
        raw = np.frombuffer(f.read(), dtype=np.int16).astype(np.float32) / 32768.0
    committed = have = t = 0
    pending_t = None
    texts = []
    while have < len(raw):
        have = min(len(raw), have + sr)
        t += 1
        tail = raw[committed:have]
        if len(tail) < sr:
            continue
        regions = get_speech_timestamps(tail, helper.vad_options())
        limit = len(tail) - int(helper.STREAM_CLOSE_MARGIN_S * sr)
        closed = [{"start": r["start"] + committed, "end": r["end"] + committed} for r in regions if r["end"] <= limit]
        if not closed:
            continue
        speech_s = sum(r["end"] - r["start"] for r in closed) / sr
        pending_t = t if pending_t is None else pending_t
        if speech_s >= helper.STREAM_MIN_CHUNK_SPEECH_S or t - pending_t >= helper.STREAM_MAX_CHUNK_WAIT_S:
            pieces, _meta = collect_chunks(raw, [dict(r) for r in closed], sr)
            texts.append(helper.decode_speech(np.concatenate(pieces)))
            committed = closed[-1]["end"]
            pending_t = None
    return " ".join(x for x in texts if x), len(texts)


@unittest.skipUnless(os.path.exists(PAUSE_PCM), "2026-10-12 recording not available")
class StreamedPausesDoNotLoop(unittest.TestCase):
    def test_pauses_inside_a_streamed_dictation_do_not_loop(self):
        import mlx_whisper_helper as helper

        text, chunks = replay_stream(helper, PAUSE_PCM)
        stats = loop_stats(text)
        self.assertLessEqual(stats["longest_word_run"], 3, (stats, text[:300]))
        self.assertLessEqual(stats["max_sentence_count"], 3, (stats, text[:300]))
        self.assertGreaterEqual(chunks, 25, "the replay did not chunk like the live stream")
        self.assertGreater(len(text.split()), 600, "transcript unexpectedly short")
        self.assertLess(len(text), 5000, "a loop slipped through")
        self.assertGreater(helper.LOOPS_DROPPED["segments"], 0, "the looping windows were not dropped")


@unittest.skipUnless(os.path.exists(SOURCE_WAV), "source recording not available")
class MlxHelperDoesNotLoop(unittest.TestCase):
    def test_silence_after_speech_does_not_trigger_repetition_loop(self):
        import mlx_whisper_helper as helper

        text, _elapsed, _vad = helper.transcribe(SOURCE_WAV)
        stats = loop_stats(text)
        self.assertLessEqual(stats["longest_word_run"], 3, (stats, text))
        self.assertEqual(stats["consecutive_dup_sentences"], 0, (stats, text))
        self.assertLessEqual(stats["max_sentence_count"], 2, (stats, text))
        self.assertGreater(len(text.split()), 500, "transcript unexpectedly short")


if __name__ == "__main__":
    unittest.main()
