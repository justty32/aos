# aos-daemon takes none of aos-loop's run points (on_before_run, on_after_run, their _if flags; 11-20 hook cut 5), and its own on_start / on_stop failing stops it like aos-loop (user 11-21: "daemon 也停").
import subprocess
import unittest

from support import ENV, Fixture, write


class RunPointsRefused(unittest.TestCase):
    def test_daemon_json_with_a_run_point_is_cfg_bad(self):
        for key, value in (('on_before_run', 'true'), ('on_after_run', ['true']), ('on_before_run_if', 'x.flag'),
                           ('on_after_run_if', None)):
            with self.subTest(key=key):
                f = Fixture('run_points_' + key)
                self.addCleanup(f.close)
                write(f.config, {'interval_ms': 20, 'procs': {}, key: value})
                p = subprocess.run(['aos-daemon', str(f.config)], cwd=f.root, env=dict(ENV, AOS_STACK=str(f.stack)),
                                   capture_output=True, text=True, timeout=10)
                self.assertEqual(p.returncode, 1)
                self.assertIn('aos-daemon: error: CfgBad %s is not taken by aos-daemon' % key, p.stderr)
                self.assertFalse((f.stack / 'procs_state.json').exists())

    def failing(self, f, code):
        sh = f.root / 'fail.sh'
        sh.write_text('#!/bin/sh\n# fails\nexit %d\n' % code)
        sh.chmod(0o755)
        return [str(sh)]

    def test_failing_on_start_stops_the_daemon(self):
        """The daemon does not come up: error line PointFailed, its exit code is on_start's, and no row of its table is started."""
        f = Fixture('run_points_on_start')
        self.addCleanup(f.close)
        target = f.body('script', 'ok')
        write(f.config, {'interval_ms': 20, 'procs': {'job': str(target)}, 'on_start': self.failing(f, 3)})
        p = subprocess.run(['aos-daemon', str(f.config)], cwd=f.root, env=dict(ENV, AOS_STACK=str(f.stack)),
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(p.returncode, 3, p.stderr)
        self.assertIn('aos-daemon: error: PointFailed on_start', p.stderr)
        self.assertNotIn('warning: on_start', p.stderr)
        self.assertFalse((f.cell / 'ready').exists())

    def test_failing_on_stop_sets_the_exit_code(self):
        """Shut down cleanly (would exit 0) with an on_stop that exits 4: the daemon exits 4 with PointFailed."""
        f = Fixture('run_points_on_stop')
        self.addCleanup(f.close)
        write(f.config, {'interval_ms': 20, 'procs': {}, 'on_stop': self.failing(f, 4)})
        f.start()
        self.assertIsNone(f.proc.poll())
        f.ctl('shutdown')
        self.assertEqual(f.proc.wait(timeout=15), 4)
        f.err.flush()
        err = (f.root / 'daemon.err').read_text()
        self.assertIn('aos-daemon: error: PointFailed on_stop', err)


if __name__ == '__main__':
    unittest.main()
