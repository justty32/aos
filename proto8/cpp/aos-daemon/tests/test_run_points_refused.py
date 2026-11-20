# aos-daemon takes none of aos-loop's run points (on_before_run, on_after_run, their _if flags), and its own on_start failing stays a warning (11-20 hook cut 5).
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

    def test_failing_on_start_only_warns(self):
        f = Fixture('run_points_on_start')
        self.addCleanup(f.close)
        sh = f.root / 'fail.sh'
        sh.write_text('#!/bin/sh\n# fails\nexit 3\n')
        sh.chmod(0o755)
        write(f.config, {'interval_ms': 20, 'procs': {}, 'on_start': [str(sh)]})
        f.start()
        self.assertIsNone(f.proc.poll())
        f.ctl('shutdown')
        self.assertEqual(f.proc.wait(timeout=15), 0)
        f.err.flush()
        err = (f.root / 'daemon.err').read_text()
        self.assertIn('aos-daemon: warning: on_start', err)
        self.assertNotIn('PointFailed', err)


if __name__ == '__main__':
    unittest.main()
