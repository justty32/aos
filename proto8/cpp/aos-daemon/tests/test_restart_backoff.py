# Check auto_restart backs off (wait grows on each restart in a row), shows it on the row (reason, counter_restarts), and resets after a long run (11-19 audit P12).
from datetime import datetime
import json
import unittest

from support import Fixture, until, write


class RestartBackoff(unittest.TestCase):
    def fixture(self, name, seconds):
        f = Fixture(name)
        target = f.body('script', 'fail', seconds=seconds)   # runs `seconds`, then exits 7: longer than the 3 s quick window
        write(f.config, {'interval_ms': 20, 'procs': {}})
        f.start()
        self.addCleanup(f.close)
        f.ctl('add', '--auto-restart', '--name', 'job', str(target))
        return f

    def starts(self, f):
        lines = [json.loads(s) for s in (f.root / 'daemon.log').read_text().splitlines()]
        return [v for v in lines if v.get('name') == 'job' and v.get('phase') == 'running']

    def test_waits_grow_and_show_on_the_row(self):
        f = self.fixture('backoff', 3.2)
        # 1st exit: restarted at once; 2nd exit: waits 1 s; 3rd exit: waits 2 s
        row = until(lambda: (r if (r := f.row()) and r.get('counter_restarts') == 1 and r['phase'] == 'running' else None), 10)
        self.assertRegex(row['reason'], r'^auto_restart: restarted 1 times; last: failed while running: exited with code 7')
        row = until(lambda: (r if (r := f.row()) and r['phase'] == 'sleeping' and r.get('counter_restarts') == 2 else None), 10)
        self.assertRegex(row['reason'], r'^auto_restart: restart 2 in 1s \(2 in a row; last: failed while running: exited with code 7')
        row = until(lambda: (r if (r := f.row()) and r['phase'] == 'sleeping' and r.get('counter_restarts') == 3 else None), 12)
        self.assertIn('auto_restart: restart 3 in 2s (3 in a row;', row['reason'])
        until(lambda: len(self.starts(f)) >= 4, 10)
        at = [datetime.fromisoformat(s['at'].replace('Z', '+00:00')).timestamp() for s in self.starts(f)]
        gaps = [b - a for a, b in zip(at, at[1:])]   # run 3.2 s + wait 0, 1, 2 s
        self.assertLess(gaps[0], 3.2 + .8)
        self.assertGreater(gaps[1], 3.2 + .9)
        self.assertGreater(gaps[2], 3.2 + 1.9)
        self.assertIn('\tauto_restart: restarted 3 times; last: ', f.ctl('ls').stdout)   # the REASON column of ls

    def test_human_start_resets_the_count(self):
        f = self.fixture('backoff_reset', 3.2)
        until(lambda: (r if (r := f.row()) and r.get('counter_restarts') == 1 else None), 10)
        f.ctl('stop', 'job')
        f.phase('stopped')
        f.ctl('start', 'job')
        row = f.phase('running')
        self.assertNotIn('counter_restarts', row)
        self.assertIsNone(row['reason'])


if __name__ == '__main__':
    unittest.main()
