# Check the envelope sender of a brain request is the proc's stack ($AOS_STACK) even when $AOS_WS is set (11-13 線修 T31/T38),
# for both send (via aos-post) and ask (send_held); without $AOS_STACK it falls back to aos::identity() ($AOS_WS first).
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-llm'


class SenderIsStack(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-llm-sender-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.kernel = self.root / 'kernel'
        self.kernel.mkdir()
        (self.kernel / 'state.json').write_text(json.dumps({'phase': 'waiting', 'pid': os.getpid()}))   # 不印「沒有 daemon」提醒
        self.ws = self.root / 'ws'
        self.stack = self.ws / '.stack' / 'procs' / 'lead'
        self.stack.mkdir(parents=True)
        self.box = self.stack / 'think' / 'reply'
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        self.env.update(AOS_LLM_KERNEL=str(self.kernel), AOS_WS=str(self.ws), AOS_STACK=str(self.stack))

    def sent(self, args, timeout=10):
        p = subprocess.run([str(BIN)] + args, env=self.env, capture_output=True, text=True, cwd=str(self.root),
                           input=json.dumps({'request': {'messages': []}}), timeout=timeout)
        return p

    def only_letter(self):
        found = list((self.kernel / 'requests').glob('*/*/letter.json')) + list((self.kernel / 'requests').glob('tmp/.*/letter.json'))
        self.assertEqual(len(found), 1, found)
        return json.loads(found[0].read_text())

    def test_send_uses_the_stack_not_the_workspace(self):
        p = self.sent(['send', '--reply-to', str(self.box)])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.only_letter()['sender'], str(self.stack))

    def test_relative_stack_counts_from_cwd(self):
        self.env['AOS_STACK'] = 'ws/.stack/procs/lead'
        p = self.sent(['send', '--reply-to', str(self.box)])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.only_letter()['sender'], str(self.stack))

    def test_without_stack_falls_back_to_the_workspace(self):
        del self.env['AOS_STACK']
        p = self.sent(['send', '--reply-to', str(self.box)])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.only_letter()['sender'], str(self.ws))

    def test_ask_uses_the_stack(self):
        # ask 寄了就等；沒有 kernel 回信，等到逾時被收掉前先看 new/ 裡那封的信封
        proc = subprocess.Popen([str(BIN), 'ask'], env=self.env, cwd=str(self.root), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            proc.stdin.write(json.dumps({'request': {'messages': []}}))
            proc.stdin.close()
            letters = []
            for _ in range(100):
                letters = list((self.kernel / 'requests' / 'new').glob('*/letter.json'))
                if letters:
                    break
                subprocess.run(['sleep', '0.05'])
            self.assertEqual(len(letters), 1)
            self.assertEqual(json.loads(letters[0].read_text())['sender'], str(self.stack))
        finally:
            proc.kill()
            proc.wait()
            proc.stdout.close()
            proc.stderr.close()


if __name__ == '__main__':
    unittest.main()
