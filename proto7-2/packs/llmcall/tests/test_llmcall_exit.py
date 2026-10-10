import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aos7_llmcall_exit import answered, delivered, meaning


class LlmcallExitTests(unittest.TestCase):
    def test_call_exit_contract(self):
        for rc, expected in ((0, "delivered"), (1, "failed"), (2, "bad_request"),
                             (3, "unsure"), (4, "delivered_unsettled"),
                             (-9, "unknown"), (5, "unknown"), (127, "unknown")):
            with self.subTest(rc=rc):
                self.assertEqual(meaning(rc), expected)
                self.assertEqual(delivered(rc), rc in (0, 4))

    def test_answered_requires_receipt_outcome_and_string_text(self):
        for rc in (0, 1, 2, 3, 4, -9, 5, 127):
            for receipt, valid in ((None, False), ([], False), ({}, False),
                                   ({'outcome': 'answered', 'text': None}, False),
                                   ({'outcome': 'failed', 'billing': 'pending', 'text': '失敗文字'}, False),
                                   ({'outcome': 'failed', 'billing': 'overrun', 'text': '失敗文字'}, False),
                                   ({'outcome': 'rejected', 'text': '拒答文字'}, False),
                                   ({'outcome': 'answered', 'text': ''}, True),
                                   ({'outcome': 'answered', 'text': '回答'}, True)):
                with self.subTest(rc=rc, receipt=receipt):
                    self.assertEqual(answered(rc, receipt), valid if rc in (0, 4) else False)
