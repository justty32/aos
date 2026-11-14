# Verify zero-second listen waits without a deadline and still rejects invalid timeout combinations.
import contextlib
import io
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PROTO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(PROTO / 'cmd/aos-agent'), str(PROTO / 'py'), str(PROTO / 'lib')]
from aos_agent import listen


class ListenTimeout(unittest.TestCase):
    def test_zero_seconds_waits_for_delayed_answer(self):
        ready = threading.Event()
        agent = SimpleNamespace(stack='/unused', name='kid', phase='running')
        timer = threading.Timer(1, ready.set)
        self.addCleanup(timer.cancel)
        output = io.StringIO()
        with patch.object(listen, 'target', return_value=agent), \
                patch.object(listen, 'latest', return_value='letter'), \
                patch.object(listen.aos_ws, 'answers', side_effect=lambda _: ['answer'] if ready.is_set() else []), \
                patch.object(listen.aos_ws, 'where', side_effect=lambda *_: [] if ready.is_set() else ['new']), \
                patch.object(listen, 'handed_unanswered', return_value=False), \
                patch.object(listen, 'on_table', return_value=True), \
                patch.object(listen, 'label', return_value='running'), \
                contextlib.redirect_stdout(output):
            timer.start()
            listen.cmd(['--target', 'kid', '--timeout-s', '0'])
        self.assertTrue(ready.is_set())
        self.assertEqual(output.getvalue(), 'answer\n')

    def test_invalid_seconds_and_zero_with_last_are_rejected(self):
        for value in ('-1', 'nan', 'inf'):
            with self.subTest(value=value), self.assertRaises(listen.Fail):
                listen.seconds(value)
        with self.assertRaises(listen.Fail):
            listen.cmd(['--timeout-s', '0', '--last', '1'])


if __name__ == '__main__':
    unittest.main()
