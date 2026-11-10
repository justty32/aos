# Check EntryMissing says where a relative entry was counted from and what absolute path it became (two-machines B08).
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BIN = Path(__file__).resolve().parents[1] / 'bin' / 'aos-exec'
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


def run(*argv, cwd):
    p = subprocess.run([str(BIN), *argv], cwd=cwd, env=ENV, capture_output=True, text=True, timeout=10)
    return p.returncode, p.stderr.strip()


class EntryMissing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-exec-missing-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(os.path.realpath(self.tmp.name))

    def test_relative_from_cwd(self):
        code, err = run('agents/../nope', cwd=self.d)
        self.assertEqual(code, 1)
        self.assertEqual(err, 'aos-exec: error: EntryMissing entry not found: agents/../nope (relative paths count from %s: %s/nope)'
                         % (self.d, self.d))

    def test_redirect_counts_from_the_file_that_holds_it(self):
        sub = self.d / 'another'
        sub.mkdir()
        (sub / 'x.json').write_text(json.dumps({'_entry': 'agents/a'}))
        code, err = run('another/x.json', cwd=self.d)
        self.assertEqual(code, 1)
        self.assertIn('entry not found: agents/a (relative paths count from %s: %s/agents/a)' % (sub, sub), err)

    def test_absolute_is_printed_as_is(self):
        code, err = run(str(self.d / 'gone'), cwd=self.d)
        self.assertEqual(code, 1)
        self.assertEqual(err, 'aos-exec: error: EntryMissing entry not found: %s' % (self.d / 'gone'))


if __name__ == '__main__':
    unittest.main()
