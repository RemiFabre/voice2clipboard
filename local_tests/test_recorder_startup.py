"""Recorder startup must stay light: heavy modules are imported lazily and the
"GO" banner tells the user the microphone is live."""
import os
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "apps", "linux", "legacy_whisper"))

import voice_transcriber as vt  # noqa: E402


class LazyImports(unittest.TestCase):
    def test_importing_transcriber_does_not_load_heavy_modules(self):
        code = (
            "import sys; sys.path.insert(0, 'apps/linux/legacy_whisper'); import voice_transcriber; "
            "print(sorted(m for m in ('faster_whisper', 'pyautogui', 'requests') if m in sys.modules))"
        )
        out = subprocess.check_output([sys.executable, "-c", code], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)
        self.assertEqual(out.strip(), "[]")


class GoBanner(unittest.TestCase):
    def test_banner_is_big_and_says_go(self):
        banner = vt.go_banner()
        self.assertGreaterEqual(banner.count("\n"), 5)
        self.assertIn("SPEAK NOW", banner)
        self.assertIn("█", banner)


if __name__ == "__main__":
    unittest.main()


class HeadsetLogParsing(unittest.TestCase):
    def test_hands_free_lines_map_to_events(self):
        vt.headset_event_from_log_line.last_gain = None
        self.assertEqual(vt.headset_event_from_log_line(
            "2026-09-17 21:47:21.744 Df bluetoothd[43329:a8aad08] [com.apple.bluetooth:Server.Handsfree] Received call hangup event (AT+CHUP) from device A0:0C:E2:E9:6D:45"), "hangup")
        self.assertEqual(vt.headset_event_from_log_line(
            "2026-09-17 21:47:32.844 Df bluetoothd[43329:a8ab644] [com.apple.bluetooth:Server.Handsfree] Received speaker gain event from device A0:0C:E2:E9:6D:45 - new gain is 3"), "gain_change")
        self.assertEqual(vt.headset_event_from_log_line(
            "... [com.apple.bluetooth:Server.Handsfree] Received speaker gain event from device A0:0C:E2:E9:6D:45 - new gain is 4"), "gain_up")
        self.assertEqual(vt.headset_event_from_log_line(
            "... [com.apple.bluetooth:Server.Handsfree] Received speaker gain event from device A0:0C:E2:E9:6D:45 - new gain is 2"), "gain_down")
        self.assertIsNone(vt.headset_event_from_log_line(
            "2026-09-17 21:47:14.059 I  bluetoothd[43329:a8ab681] [com.apple.bluetooth:Server.Handsfree] Filling done, not enough data.  shared 624, fill 0"))


class WordDictionary(unittest.TestCase):
    def test_transcription_fixes_product_name_and_claude(self):
        self.assertEqual(vt.apply_word_dictionary("the community of rich many users and the Ricci Mini app"),
                         "the community of Reachy Mini users and the Reachy Mini app")
        self.assertEqual(vt.apply_word_dictionary("send it to the cloud session"), "send it to Claude")
        self.assertEqual(vt.apply_word_dictionary("a cloudy day"), "a cloudy day")

    def test_pronunciation_rewrite(self):
        out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "mac", "secretary", "dictionary.py"), "pronounce"],
                             input="Reachy Mini is fixed", capture_output=True, text=True).stdout
        self.assertEqual(out, "Reechy Mini is fixed")
