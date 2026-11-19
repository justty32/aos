# Check that take and take-all skip a letter they cannot claim (rename refused), claim the rest, and say so in a warning (11-19 audit P2).
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[3]
ENV = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
ENV['PATH'] = str(PROTO / 'bin') + ':' + ENV['PATH']


def run(*argv, stdin=''):
    return subprocess.run(list(argv), input=stdin, env=ENV, capture_output=True, text=True, timeout=60)


@unittest.skipIf(os.geteuid() == 0, 'root renames a read-only folder anyway')
class TakeSkip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-post-skip-')
        self.addCleanup(self.tmp.cleanup)
        self.box = Path(self.tmp.name) / 'box'
        self.assertEqual(run('aos-post', 'init', str(self.box)).returncode, 0)

    def stuck(self, name):
        """A letter folder that cannot be renamed to cur/: moving a folder to another parent needs write on the folder itself."""
        d = self.box / 'new' / name
        d.mkdir()
        (d / 'letter.json').write_text(json.dumps({'sender': '/x', 'sent_at': 'x', 'body': {}}))
        d.chmod(0o555)
        self.addCleanup(d.chmod, 0o755)
        return d

    def send(self):
        p = run('aos-post', 'send', str(self.box), stdin='{}')
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def test_take_all_skips_and_warns(self):
        self.stuck('000000000001.stuck')   # ordered: sorts first, so it is met before the good ones
        good = [self.send(), self.send()]
        p = run('aos-post', 'take-all', str(self.box))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.split(), good)
        self.assertIn('aos-post: warning: skipped letter 000000000001.stuck (cannot claim it, left in new/): WriteFailed', p.stderr)
        self.assertNotIn('error:', p.stderr)
        self.assertEqual(sorted(x.name for x in (self.box / 'new').iterdir()), ['000000000001.stuck'])

    def test_take_skips_to_next(self):
        self.stuck('000000000001.stuck')
        good = self.send()
        p = run('aos-post', 'take', str(self.box))
        self.assertEqual((p.returncode, p.stdout.strip()), (0, good), p.stderr)
        self.assertIn('warning: skipped letter 000000000001.stuck', p.stderr)

    def test_only_stuck_is_no_letter_with_warning(self):
        self.stuck('000000000001.stuck')
        for sub in ('take', 'take-all'):
            with self.subTest(sub=sub):
                p = run('aos-post', sub, str(self.box))
                self.assertEqual(p.returncode, 10, p.stderr)
                self.assertEqual(p.stdout, '')
                self.assertIn('warning: skipped letter 000000000001.stuck', p.stderr)

    def test_quiet_when_nothing_is_stuck(self):
        self.send()
        p = run('aos-post', 'take-all', str(self.box))
        self.assertEqual((p.returncode, p.stderr), (0, ''))


if __name__ == '__main__':
    unittest.main()
