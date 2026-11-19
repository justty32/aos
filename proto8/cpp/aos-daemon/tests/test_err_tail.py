# Verify a failing proc with a huge stderr.txt (sparse) leaves the daemon alive, its memory flat, and the reason taken from the file's tail.
import json
from pathlib import Path
import unittest

from support import Fixture, until, write

BIG = 512 << 20   # sparse: no disk is used; before the tail read this made the daemon allocate about 1 GB
BODY = '''#!/usr/bin/env python3
# Test body: write ready, then grow stderr.txt (sparse) to argv[1] bytes, print argv[2] (if any) to stderr, exit 3.
import os, pathlib, sys, time
s = pathlib.Path(os.environ['AOS_STACK'])
(s / 'ready').write_text('ready')
time.sleep(.3)
size = int(sys.argv[1])
if size:
    os.truncate(s / 'stderr.txt', size)
if len(sys.argv) > 2:
    sys.stderr.write('noise line\\n' + sys.argv[2] + '\\n\\n')
    sys.stderr.flush()
sys.exit(3)
'''


def hwm_kb(pid):
    for line in Path('/proc/%d/status' % pid).read_text().splitlines():
        if line.startswith('VmHWM:'):
            return int(line.split()[1])
    raise AssertionError('no VmHWM for pid %d' % pid)


class ErrTail(unittest.TestCase):
    def fixture(self, name):
        f = Fixture('errtail_' + name)
        self.addCleanup(f.close)
        body = f.root / 'tail_body.py'
        body.write_text(BODY)
        body.chmod(0o755)
        self.body = body
        f.start()
        ok = f.root / 'ok.json'
        write(ok, ['/bin/sleep', '600'])
        f.ctl('add', '--name', 'ok', str(ok))
        until(lambda: (f.rows().get('ok') or {}).get('phase') == 'running')
        return f

    def run_failing(self, f, size, *last):
        target = f.root / 'job.json'
        write(target, [str(self.body), str(size), *last])
        before = hwm_kb(f.proc.pid)
        f.add(target)
        row = f.phase('stopped')
        return row, before

    def assert_daemon_fine(self, f, before):
        self.assertIsNone(f.proc.poll(), 'the daemon exited')
        grew = hwm_kb(f.proc.pid) - before
        self.assertLess(grew, 32 << 10, 'daemon peak memory grew by %d kB' % grew)
        ok = f.rows().get('ok') or {}
        self.assertEqual(ok.get('phase'), 'running')
        self.assertTrue(Path('/proc/%d' % ok['pid']).exists())
        f.ctl('ping')

    def test_huge_stderr_reason_is_the_tail(self):
        f = self.fixture('huge')
        row, before = self.run_failing(f, BIG, 'fixture: error: tail marker')
        self.assertIn('code 3', row['reason'])
        self.assertTrue(row['reason'].endswith(': fixture: error: tail marker'), row['reason'])
        self.assertGreaterEqual((f.cell / 'stderr.txt').stat().st_size, BIG)
        self.assert_daemon_fine(f, before)

    def test_huge_earlier_life_is_not_the_reason(self):
        f = self.fixture('earlier')
        err = f.cell / 'stderr.txt'
        err.parent.mkdir(parents=True, exist_ok=True)
        with open(err, 'wb') as out:   # a previous life left a huge log ending in a line that must not show
            out.truncate(BIG)
            out.seek(0, 2)
            out.write(b'earlier life line\n')
        row, before = self.run_failing(f, 0)
        self.assertIn('code 3', row['reason'])
        self.assertNotIn('earlier life line', row['reason'])
        self.assertTrue(row['reason'].endswith('code 3') or row['reason'].endswith('code 3)'), row['reason'])
        self.assert_daemon_fine(f, before)


if __name__ == '__main__':
    unittest.main()
