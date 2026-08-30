import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "linux", "legacy_whisper"))

import voice_transcriber as vt  # noqa: E402


class ItermWriteTextAction(unittest.TestCase):
    def test_plain_action_types_text_without_newline(self):
        self.assertEqual(
            vt.iterm_write_text_action('say "hi"', bracketed=False),
            'write text "say \\"hi\\"" newline NO',
        )

    def test_bracketed_action_wraps_text_in_bracketed_paste_markers(self):
        self.assertEqual(
            vt.iterm_write_text_action("hello", bracketed=True),
            'write text (ASCII character 27) & "[200~" & "hello" & (ASCII character 27) & "[201~" newline NO',
        )


class TtyForegroundDetection(unittest.TestCase):
    PS_OUTPUT = "S    -zsh\nS+   /Users/remi/.local/share/claude/versions/2.1.251\nS+   tee\n"

    def test_foreground_commands_are_basenames_of_plus_state_processes(self):
        self.assertEqual(
            vt.foreground_commands_from_ps(self.PS_OUTPUT),
            ["2.1.251", "tee"],
        )

    def test_claude_is_detected_by_comm_or_versions_path(self):
        self.assertTrue(vt.tty_foreground_is_claude("S+   claude\n"))
        self.assertTrue(vt.tty_foreground_is_claude(self.PS_OUTPUT))

    def test_shell_only_tty_is_not_claude(self):
        self.assertFalse(vt.tty_foreground_is_claude("S+   -zsh\nS    vim\n"))
        self.assertFalse(vt.tty_foreground_is_claude(""))


if __name__ == "__main__":
    unittest.main()
