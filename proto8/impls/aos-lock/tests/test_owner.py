# Check `aos-lock release` leaves someone else's lock alone (warning, exit 10) unless --force (設計-52).
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[3]
BIN = PROTO / 'impls' / 'aos-lock' / 'bin' / 'aos-lock'
BASE = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}


class Owner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-lock-owner-')
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.t = self.d / 'data.json'
        self.t.write_text('{}')
        for w in ('a', 'b'):
            (self.d / w).mkdir()

    def run_as(self, ws, *argv):
        return subprocess.run([str(BIN), *argv], env=dict(BASE, AOS_WS=str(self.d / ws)),
                              capture_output=True, text=True, timeout=10)

    def test_other_holder_is_not_released(self):
        self.assertEqual(self.run_as('a', 'acquire', str(self.t)).returncode, 0)
        p = self.run_as('b', 'release', str(self.t))
        self.assertEqual(p.returncode, 10)
        self.assertIn('aos-lock: warning: not releasing', p.stderr)
        self.assertTrue((self.d / 'data.json.lock').is_dir())
        p = self.run_as('a', 'release', str(self.t))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse((self.d / 'data.json.lock').exists())

    def test_force_releases_anyway(self):
        self.assertEqual(self.run_as('a', 'acquire', str(self.t)).returncode, 0)
        p = self.run_as('b', 'release', '--force', str(self.t))
        self.assertEqual((p.returncode, p.stderr), (0, ''))
        self.assertFalse((self.d / 'data.json.lock').exists())

    def test_holderless_lock_is_still_released(self):
        (self.d / 'data.json.lock').mkdir()   # 殘缺鎖（沒名牌）：照舊放得掉
        self.assertEqual(self.run_as('b', 'release', str(self.t)).returncode, 0)


if __name__ == '__main__':
    unittest.main()
