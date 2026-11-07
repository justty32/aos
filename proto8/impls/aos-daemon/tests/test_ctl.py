# Exercise entry preservation, public control paths, phase checks, help and agent hints.
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

from support import ENV, PROTO, dc, write
sys.path.insert(0, str(PROTO / 'cmd' / 'aos-agent'))
from aos_agent import common, hints


class Control(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-ctl-b-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_arrays_and_argv_objects_do_not_read_loop_config(self):
        for body in (['aos-loop', 'missing.json'], {'argv': ['aos-loop', 'missing.json'],
                                                   'cwd': '.', 'envs': {'X': 'Y'}}):
            with self.subTest(body=body):
                target = self.root / 'body.json'
                write(target, body)
                self.assertIsNone(dc.find_loop(str(target)))
                name, letter = dc.add_letter(str(target))
                self.assertEqual(letter['procs_added'][name]['exec'], str(target))

    def test_direct_loop_config_keeps_startup_interval(self):
        target = self.root / 'loop.json'
        write(target, {'exec': '/bin/true'})
        _, body = dc.add_letter(str(target))
        self.assertEqual(body['procs_added']['loop.json']['interval_ms'], 0)

    def test_all_stopped_and_sleeping_rows_reject_wrong_phase(self):
        for cmd, valid in (('stop', 'running'), ('sleep', 'running'), ('start', 'stopped'), ('wake', 'sleeping')):
            dc.need_phase(cmd, 'job', {'phase': valid})
            for invalid in {'running', 'stopping', 'stopped', 'sleeping'} - {valid}:
                with self.assertRaises(dc.Fail) as got:
                    dc.need_phase(cmd, 'job', {'phase': invalid})
                self.assertEqual(got.exception.code, 'PhaseBad')

    def test_pause_resume_default_ctl_without_parent_config(self):
        import daemon_ctl.ctl as ctl
        row = {'phase': 'running', 'stack': str(self.root)}
        with patch.object(ctl, 'row_of', return_value=row), patch.object(ctl, 'wait_applied'):
            for cmd in ('pause', 'resume'):
                dc.write_ctl(str(self.root), 'job', cmd)
                import json
                self.assertEqual(json.loads((self.root / 'ctl.json').read_text())['cmd'], cmd)
        row['phase'] = 'stopped'
        with patch.object(ctl, 'row_of', return_value=row), self.assertRaises(dc.Fail) as got:
            dc.write_ctl(str(self.root), 'job', 'pause')
        self.assertEqual(got.exception.code, 'PhaseBad')

    def test_agent_phase_body_accepts_exec_rows(self):
        for cmd, phase, key in (('stop', 'running', 'stopped'), ('sleep', 'running', 'slept'),
                                ('start', 'stopped', 'started'), ('wake', 'sleeping', 'woken')):
            with patch.object(common, 'daemon_path', return_value=str(self.root)), \
                 patch.object(dc, 'row_of', return_value={'phase': phase}):
                self.assertEqual(common.phase_body(cmd, 'job'), {'procs_' + key: ['job']})

    def test_agent_off_table_does_not_claim_a_known_failure_disappears(self):
        a = SimpleNamespace(name='job', stack=str(self.root))
        with patch.object(hints, 'row_named', return_value=None), \
             patch.object(hints, 'daemon_path', return_value=str(self.root)), \
             patch.object(dc, 'names_of', return_value={'procs_stderr': 'stderr.txt'}):
            text = hints.off_table(a)
            self.assertIn('known nonzero exits stay stopped with a reason', text)
            self.assertNotIn('whatever its exit code', text)
        with patch.object(hints, 'row_named', return_value={'phase': 'stopped'}):
            self.assertIsNone(hints.off_table(a))

    def test_help_for_all_control_commands(self):
        import subprocess
        for cmd in ('aos-daemon-ctl', 'aos-agent'):
            for sub in ((), ('ctl',) if cmd == 'aos-agent' else ('stop',),
                        ('ctl', 'sleep') if cmd == 'aos-agent' else ('sleep',)):
                p = subprocess.run([cmd, *sub, '--help'], env=ENV, text=True, capture_output=True)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertNotIn('CtlMissing', p.stdout)
                self.assertNotIn('exec types have no', p.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
