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
