# test_screen_hook checks that slash_of routes screen-only commands to slash_turn and leaves look-alikes as plain text.
import os
import sys
import unittest

PROTO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))
sys.path[:0] = [os.path.join(PROTO, "py"), os.path.join(PROTO, "py")]
from aos.apps.eca.slash import slash_of  # noqa: E402


class ScreenHook(unittest.TestCase):
    def test_context_alone_is_a_slash(self):
        self.assertEqual(slash_of([{"content": " /context \n"}], None), "/context")

    def test_context_with_text_or_batch_is_plain(self):
        self.assertIsNone(slash_of([{"content": "/context please"}], None))
        self.assertIsNone(slash_of([{"content": "/context"}, {"content": "hi"}], None))

    def test_existing_commands_unchanged(self):
        self.assertEqual(slash_of([{"content": "/status"}], None), "/status")
        self.assertIsNone(slash_of([{"content": "/contexts"}], None))


if __name__ == "__main__":
    unittest.main()
