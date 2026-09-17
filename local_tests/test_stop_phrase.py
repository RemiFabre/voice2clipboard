"""Spoken stop phrase: while streaming, a short isolated "roger stop" must end the recording
(touch the stop file), be dropped from the transcript, and nothing said after it is kept.
Builds the audio from a real dictation plus macOS `say`; needs the recording and the model."""
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(__file__))

REAL_WAV = os.path.join(ROOT, "recordings", "2026-09-17", "20-40-30", "audio.wav")


def silence(seconds, sr=16000):
    return np.zeros(int(seconds * sr), dtype=np.int16)


def synth(text, path):
    subprocess.run(["say", "-v", "Samantha", "-o", path, "--file-format=WAVE", "--data-format=LEI16@16000", text], check=True)


class StopPhraseMatching(unittest.TestCase):
    def test_phrase_matching_is_strict_but_punctuation_tolerant(self):
        import mlx_whisper_helper as helper

        s = helper.StreamSession("t", "/nonexistent", stop_file="/tmp/x")
        self.assertTrue(s._matches_stop_phrase("Roger, stop."))
        self.assertTrue(s._matches_stop_phrase("Okay, roger stop"))
        self.assertTrue(s._matches_stop_phrase("Over and out!"))
        self.assertFalse(s._matches_stop_phrase("I told Roger to stop the car before the bridge"))
        self.assertFalse(s._matches_stop_phrase(""))
        self.assertFalse(s._matches_stop_phrase("Stop."))


@unittest.skipUnless(os.path.exists(REAL_WAV), "real dictation not available")
class StopPhraseEndsStreaming(unittest.TestCase):
    def test_roger_stop_ends_recording_and_is_dropped(self):
        import soundfile as sf
        import mlx_whisper_helper as helper
        from test_streaming_transcription import feed_pcm, norm

        tmp = tempfile.mkdtemp()
        real, sr = sf.read(REAL_WAV, dtype="int16")
        self.assertEqual(sr, 16000)
        stop_wav = os.path.join(tmp, "stop.wav")
        synth("roger stop.", stop_wav)
        stop_audio, _ = sf.read(stop_wav, dtype="int16")
        before = real[5 * sr : 25 * sr]
        after = real[40 * sr : 48 * sr]
        composite = np.concatenate([before, silence(1.5), stop_audio, silence(1.5), after, silence(1.5)])
        wav_path = os.path.join(tmp, "composite.wav")
        sf.write(wav_path, composite, sr)

        pcm_path = os.path.join(tmp, "audio.pcm")
        open(pcm_path, "wb").close()
        stop_file = os.path.join(tmp, "stop.flag")
        session = helper.StreamSession("t", pcm_path, stop_file=stop_file)
        session.start()
        stop = threading.Event()
        writer = threading.Thread(target=feed_pcm, args=(wav_path, pcm_path, 1.0, 0.25, stop))
        t0 = time.time()
        writer.start()
        writer.join()
        deadline = time.time() + 15
        while not os.path.exists(stop_file) and time.time() < deadline:
            time.sleep(0.2)
        self.assertTrue(os.path.exists(stop_file), "helper never touched the stop file")
        self.assertTrue(session.stop_hit, "stop_hit not recorded")
        text, stats = session.end()

        words = norm(text)
        self.assertNotIn("roger", words, text)
        expected = norm(helper.decode_speech(before.astype(np.float32) / 32768.0))
        overlap = len(set(words) & set(expected)) / max(1, len(set(expected)))
        self.assertGreater(overlap, 0.7, (overlap, text))
        self.assertLessEqual(len(words), int(len(expected) * 1.3) + 3, "speech after the stop phrase leaked into the transcript")
        self.assertEqual(stats["stop_phrase_hit"], session.stop_hit)


if __name__ == "__main__":
    unittest.main()
