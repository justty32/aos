"""llmcall delivery, failure and uncertain process exits at the brain boundary."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import aos7_up_brain as brain


class BrainLlmExitTests(unittest.TestCase):
    def call(self, node, rc):
        response = subprocess.CompletedProcess([], rc, json.dumps({'outcome': 'answered', 'text': '收到'}), '')
        with patch.object(brain, 'request', return_value=node / 'req.json'), \
                patch.object(brain, 'run', return_value=response), \
                patch.object(brain, 'test_point'):
            return brain.ask_ai(node, {}, 'c1', {'model': 'fake'})

    def test_brain_llm_exit_contract(self):
        with tempfile.TemporaryDirectory(prefix='fx1-b2-receipt-brain-') as directory:
            node = Path(directory)
            (node / 'brain').mkdir()
            for rc in (0, 4):
                with self.subTest(rc=rc):
                    (node / 'brain/unsure.json').write_text('{}')
                    reply = self.call(node, rc)
                    self.assertEqual(reply, '收到')
                    self.assertEqual(reply.usage_pending, rc == 4)
                    self.assertFalse((node / 'brain/unsure.json').exists())
            for rc in (1, 2):
                with self.subTest(rc=rc), self.assertRaises(brain.Trouble):
                    self.call(node, rc)

    def test_brain_unknown_llm_exit_keeps_uncertain_evidence(self):
        with tempfile.TemporaryDirectory(prefix='fx1-b2-receipt-brain-') as directory:
            node = Path(directory)
            (node / 'brain').mkdir()
            evidence = node / 'brain/unsure.json'
            evidence.write_text('{"cid":"c1"}')
            for rc in (3, -9, 5, 127):
                for raw_exists in (False, True):
                    with self.subTest(rc=rc, raw=raw_exists):
                        raw = node / 'llmcall/llm/c1/raw.json'
                        raw.parent.mkdir(parents=True, exist_ok=True)
                        if raw_exists:
                            raw.write_text('{}')
                        else:
                            raw.unlink(missing_ok=True)
                        with self.assertRaises(brain.Later) as caught:
                            self.call(node, rc)
                        self.assertEqual(caught.exception.unsure, not raw_exists)
                        self.assertEqual(evidence.read_text(), '{"cid":"c1"}')

    def test_brain_unsettled_failure_preserves_evidence(self):
        with tempfile.TemporaryDirectory(prefix='fx1-b2-receipt-brain-') as directory:
            node = Path(directory)
            (node / 'brain').mkdir()
            evidence = node / 'brain/unsure.json'
            evidence.write_text('{"cid":"c1"}')
            for billing in ('pending', 'overrun'):
                with self.subTest(billing=billing):
                    receipt = dict(outcome='failed', billing=billing, text='不可當回信的失敗文字')
                    response = subprocess.CompletedProcess([], 4, json.dumps(receipt), '')
                    with patch.object(brain, 'request', return_value=node / 'req.json'), \
                            patch.object(brain, 'run', return_value=response), \
                            patch.object(brain, 'test_point') as point, \
                            self.assertRaises(brain.Trouble) as caught:
                        brain.ask_ai(node, {}, 'c1', {'model': 'fake'})
                    self.assertEqual(caught.exception.why, 'AI 沒回應')
                    self.assertEqual(evidence.read_text(), '{"cid":"c1"}')
                    point.assert_not_called()
