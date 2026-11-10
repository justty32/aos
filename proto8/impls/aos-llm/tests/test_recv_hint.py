# Check recv's exit 10 says why when something is wrong: kernel not running, or the reply never reached BOX (坑-102).
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-llm'


class RecvHint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-llm-hint-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.kernel = self.root / 'kernel'
        self.box = self.root / 'box'
        for d in (self.kernel / 'requests', self.box):
            for part in ('new', 'cur', 'tmp'):
                (d / part).mkdir(parents=True)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        self.env['AOS_LLM_KERNEL'] = str(self.kernel)

    def recv(self, name='L1', env=None):
        p = subprocess.run([str(BIN), 'recv', str(self.box), name], env=env or self.env,
                           capture_output=True, text=True, timeout=10)
        return p.returncode, p.stderr.strip()

    def running(self):
        (self.kernel / 'state.json').write_text(json.dumps({'phase': 'running', 'pid': os.getpid()}))

    def test_waiting_normally_is_quiet(self):
        self.running()
        (self.kernel / 'requests/new/L1').mkdir()
        self.assertEqual(self.recv(), (10, ''))
        (self.kernel / 'requests/new/L1').rename(self.kernel / 'requests/cur/L1')
        self.assertEqual(self.recv(), (10, ''))

    def test_kernel_not_running(self):
        (self.kernel / 'requests/new/L1').mkdir()
        code, err = self.recv()
        self.assertEqual(code, 10)
        self.assertIn('aos-llm: warning: no reply for L1 yet', err)
        self.assertIn('no llm daemon here', err)
        (self.kernel / 'state.json').write_text(json.dumps({'phase': 'stopped', 'pid': None}))
        code, err = self.recv()
        self.assertIn('llm daemon is not running', err)

    def test_kernel_cannot_write_box(self):
        self.running()
        (self.kernel / 'requests/cur/L1').mkdir()
        (self.box / 'new').chmod(0o555)
        self.addCleanup((self.box / 'new').chmod, 0o755)
        code, err = self.recv()
        self.assertEqual(code, 10)
        self.assertIn('the llm kernel cannot deliver into', err)
        self.assertIn('is mode 555', err)

    def test_letter_gone_and_no_reply_is_quiet(self):
        self.running()   # 信已不在 kernel、BOX 也沒有：可能是回信已經收過一次，分不出來，不報
        self.assertEqual(self.recv(), (10, ''))

    def test_without_kernel_env_stays_quiet(self):
        env = dict(self.env)
        env.pop('AOS_LLM_KERNEL')
        self.assertEqual(self.recv(env=env), (10, ''))


if __name__ == '__main__':
    unittest.main()
