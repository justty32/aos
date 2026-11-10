# Check send's warning, when no llm daemon runs at AOS_LLM_KERNEL, names the letter and where it was written (two-machines B10).
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-llm'


class SendHint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-llm-send-hint-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        self.kernel = self.root / 'someone_else'
        self.kernel.mkdir()
        self.box = self.root / 'box'
        for part in ('new', 'cur', 'tmp'):
            (self.box / part).mkdir(parents=True)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        self.env['AOS_LLM_KERNEL'] = str(self.kernel)

    def send(self):
        return subprocess.run([str(BIN), 'send', '--reply-to', str(self.box)], env=self.env, capture_output=True, text=True,
                              input=json.dumps({'request': {'messages': []}}), timeout=10)

    def test_warning_names_the_letter_and_its_path(self):
        p = self.send()
        self.assertEqual(p.returncode, 0, p.stderr)
        name = p.stdout.strip()
        letter = self.kernel / 'requests' / 'new' / name
        self.assertTrue((letter / 'letter.json').is_file())
        self.assertIn('aos-llm: warning: %s: no llm daemon here' % self.kernel, p.stderr)
        self.assertIn('letter %s was written anyway to %s,' % (name, letter), p.stderr)
        self.assertIn('if AOS_LLM_KERNEL points to the wrong place, fix it and delete that letter', p.stderr)

    def test_running_kernel_is_quiet(self):
        (self.kernel / 'state.json').write_text(json.dumps({'phase': 'waiting', 'pid': os.getpid()}))
        p = self.send()
        self.assertEqual((p.returncode, p.stderr), (0, ''))


if __name__ == '__main__':
    unittest.main()
