# Verify B lifecycle rules against real daemons, command tools and minimal bodies.
import json
import os
from pathlib import Path
import signal
import sys
import time
import unittest

from support import Fixture, EVIDENCE, SCRATCH, dc, read, until, write


class Lifecycle(unittest.TestCase):
    def fixture(self, name):
        f = Fixture(name)
        self.addCleanup(f.close)
        return f

    def test_body_matrix(self):
        for kind in ('script', 'loop_array', 'loop_object', 'fsm'):
            for case in ('stop', 'sleep', 'zero', 'fail'):
                with self.subTest(body=kind, case=case):
                    f = self.fixture(kind + '_' + case).start()
                    f.add(f.body(kind, case))
                    if case == 'stop':
                        f.ctl('stop', 'job')
                        self.assertEqual(until(lambda: read(f.cell / 'ctl.json'))['cmd'], 'stop')
                        row = f.phase('stopped')
                        self.assertEqual(row['code'], 0)
                        f.ctl('stop', 'job', ok=1)
                        self.assertIn('PhaseBad', f.commands[-1]['stderr'])
                        f.record(kind, case, row)
                        f.ctl('start', 'job')
                        f.phase('running')
                    elif case == 'sleep':
                        f.ctl('sleep', 'job')
                        row = f.phase('sleeping')
                        self.assertFalse((f.cell / 'ctl.json').exists())
                        f.ctl('start', 'job', ok=1)
                        self.assertIn('PhaseBad', f.commands[-1]['stderr'])
                        f.ctl('wake', 'job')
                        f.phase('running')
                        f.record(kind, case, row)
                        EVIDENCE[-1]['after_wake'] = 'running'
                    elif case == 'zero':
                        until(lambda: not f.rows())
                        f.record(kind, case)
                        self.assertEqual(EVIDENCE[-1]['code'], 0)
                    else:
                        row = f.phase('stopped')
                        self.assertEqual(row['code'], 7)
                        self.assertIn('code 7', row['reason'])
                        f.record(kind, case, row)
                    f.close()

    def test_finish_wakes_mailbox_targets_with_arguments(self):
        for kind in ('script', 'loop_array', 'loop_object', 'fsm'):
            with self.subTest(body=kind):
                f = self.fixture('finish_' + kind).start()
                f.add(f.body(kind, 'stop', seconds=4))
                f.close()
                self.assertEqual(f.row()['phase'], 'sleeping')
                launch = f.row()['launch']
                self.assertIsInstance(launch, dict)
                f.start()
                f.phase('running')
                # These rows were added by mail: daemon.json has no startup specification.
                self.assertEqual(f.row()['launch'], launch)
                f.close()

    def test_no_term_when_stop_window_unwritable(self):
        f = self.fixture('write_failed').start()
        f.add(f.body('script', 'stop'))
        (f.cell / '.ctl.json').mkdir()  # Atomic window write fails even when run as root.
        f.ctl('stop', 'job')
        f.phase('stopping')
        row = f.phase('stopped')
        self.assertEqual(row['code'], 0)
        self.assertIsNone(row['signal'])
        self.assertIn('waiting for it to exit', (f.root / 'daemon.err').read_text())
        f.record('script', 'write_failed', row)

    def test_custom_ctl_and_null_ctl(self):
        for ctl in ('other.json', None, '', 12):
            with self.subTest(ctl=ctl):
                f = self.fixture('ctl_' + str(ctl)).start()
                # A valid loop config is used for custom/null; other values test default fallback
                # with an exec-style child and a parent-owned config fixture.
                f.add(f.body('script', 'stop'))
                write(f.cell / 'loop.json', {'ctl': ctl})
                f.ctl('stop', 'job')
                filename = ctl if isinstance(ctl, str) and ctl else 'ctl.json'
                until(lambda: read(f.cell / filename))
                self.assertEqual(dc.need_ctl(str(f.stack), 'job')[1], str(f.cell / filename))
                self.assertEqual(f.phase('stopped')['code'], 0)
                f.close()

    def test_procs_ctl_accepts_all_phase_keys_for_exec(self):
        f = self.fixture('procs_ctl').start()
        target = f.body('script', 'stop', seconds=4)
        for key, phase in (('procs_stopped', 'stopped'), ('procs_started', 'running'),
                           ('procs_slept', 'sleeping'), ('procs_woken', 'running')):
            write(f.stack / 'procs_ctl.json', {'procs_added': {'job': str(target)}, key: ['job']})
            f.phase(phase)
            self.assertIsNone(read(f.stack / 'procs_state.json')['ctl_warning'])
        write(f.stack / 'procs_ctl.json', {'procs_stopped': 4})
        until(lambda: read(f.stack / 'procs_state.json').get('ctl_warning'))

    def test_signal_exit_stays_stopped(self):
        f = self.fixture('signal').start()
        f.add(f.body('script', 'stop', seconds=4))
        os.kill(f.row()['pid'], signal.SIGKILL)
        row = f.phase('stopped')
        self.assertEqual(row['code'], 137)
        self.assertIn('signal 9', row['reason'])

    def test_launch_failure_is_one_stopped_row(self):
        f = self.fixture('launch_failed').start()
        target = f.body('script', 'stop')
        blocked = f.root / 'blocked'
        blocked.write_text('not a directory')
        f.ctl('add', '--name', 'job', '--stack', str(blocked / 'child'), str(target))
        row = f.phase('stopped')
        self.assertEqual(row['code'], 1)
        self.assertIn('MkdirFailed', row['reason'])
        self.assertIsNone(f.proc.poll())

    def test_auto_restart_still_stops_after_three_quick_exits(self):
        f = self.fixture('auto_restart')
        target = f.body('script', 'fail', seconds=.1)
        write(f.config, {'interval_ms': 20, 'procs': {'job': {'exec': str(target), 'auto_restart': True}}})
        f.start()
        self.assertIn('restarted 3 times', f.phase('stopped')['reason'])

    def test_adopt_stopping_keeps_stop_cooperative(self):
        f = self.fixture('adopt_stop').start()
        f.add(f.body('script', 'stop', seconds=3))
        f.ctl('stop', 'job')
        f.phase('stopping')
        f.proc.kill()
        f.proc.wait()
        f.close()
        f.start()
        self.assertEqual(f.phase('stopped')['signal'], None)
        self.assertEqual(f.row()['stop_mode'] if 'stop_mode' in f.row() else 'held', 'held')


    def test_pending_loop_can_wake_after_daemon_restart(self):
        f = self.fixture('pending_loop').start()
        body = f.body('script', 'stop', seconds=4)
        # add + sleep must not create a stack or depend on an existing loop.json.
        spec = {'exec': str(body), 'interval_ms': 30}
        reply = dc.ask(str(f.stack), {'procs_added': {'job': spec}, 'procs_slept': ['job']})
        self.assertTrue(reply['applied'])
        f.phase('sleeping')
        self.assertFalse(f.cell.exists())
        f.close()
        f.start()
        f.phase('running')
        until(lambda: (f.cell / 'ready').exists())

    def test_parent_written_loop_still_uses_custom_ctl(self):
        f = self.fixture('parent_loop').start()
        body = f.body('script', 'stop', seconds=.4)
        reply = dc.ask(str(f.stack), {'procs_added': {'job': {
            'exec': str(body), 'interval_ms': 30, 'ctl': 'control.json'}}})
        self.assertTrue(reply['applied'])
        f.phase('running')
        until(lambda: (f.cell / 'ready').exists())
        f.ctl('pause', '--timeout-s', '2', 'job')
        self.assertEqual(read(f.cell / 'control.json')['cmd'], 'pause')
        f.ctl('resume', '--timeout-s', '2', 'job')
        f.ctl('stop', 'job')
        self.assertEqual(f.phase('stopped')['code'], 0)
        self.assertEqual(read(f.cell / 'control.json')['cmd'], 'stop')
        self.assertFalse((f.cell / 'ctl.json').exists())

    def test_public_stuck_window_for_exec_can_restart(self):
        f = self.fixture('stuck_exec')
        target = f.body('script', 'stop', seconds=4)
        write(f.config, {'interval_ms': 20, 'procs': {'job': {
            'exec': str(target), 'stuck_after_ticks': 1, 'restart_on_stuck': True}}})
        f.start()
        f.phase('running')
        until(lambda: (f.cell / 'ready').exists())
        first = f.row()['pid']
        write(f.cell / 'state.json', {'responded_at': None})
        time.sleep(.03)
        write(f.cell / 'ctl.json', {'cmd': 'pause', 'seq': 1})
        until(lambda: f.row() and f.row()['phase'] == 'running' and f.row()['pid'] != first)
        self.assertIn('control window response timed out; restarting', (f.root / 'daemon.log').read_text())

    def test_pause_resume_without_parent_loop_config(self):
        f = self.fixture('real_pause').start()
        f.add(f.body('loop_object', 'stop'))
        self.assertFalse((f.cell / 'loop.json').exists())
        for cmd, phase in (('pause', 'paused'), ('resume', 'running')):
            f.ctl(cmd, '--timeout-s', '2', 'job')
            until(lambda: read(f.cell / 'state.json', {}).get('phase') == phase)
            self.assertFalse(f.commands[-1]['stderr'])

    def test_stopped_exec_survives_adopt_and_start(self):
        f = self.fixture('failed_adopt').start()
        target = f.body('script', 'fail', seconds=.2)
        f.add(target)
        reason = f.phase('stopped')['reason']
        f.close()
        f.start()
        self.assertEqual(f.phase('stopped')['reason'], reason)
        f.body('script', 'stop', seconds=4)
        f.ctl('start', 'job')
        f.phase('running')

    def test_unknown_adopted_exit_leaves_table(self):
        f = self.fixture('unknown_adopt').start()
        f.add(f.body('script', 'stop', seconds=2))
        first = f.row()['pid']
        f.proc.kill()
        f.proc.wait()
        f.close()
        f.start()
        self.assertEqual(f.phase('running')['pid'], first)
        until(lambda: not f.rows())
        self.assertIsNone(f.proc.poll())

    def test_saved_launch_moves_with_daemon_stack(self):
        import shutil
        f = self.fixture('move').start()
        dc.ask(str(f.stack), {'procs_added': {'job': [str(f.script), '4', '0']}})
        f.phase('running')
        until(lambda: (f.cell / 'ready').exists())
        f.close()
        old_root = f.root
        f.root = f.root.with_name(f.root.name + '_moved')
        shutil.move(str(old_root), f.root)
        f.stack, f.config = f.root / 'stack', f.root / 'daemon.json'
        f.cell = f.stack / 'procs' / 'job'
        f.start()
        f.phase('running')
        time.sleep(.15)
        self.assertEqual(f.row()['phase'], 'running', f.row())
        self.assertNotIn(str(old_root), json.dumps(f.row()['launch']))

    def test_agent_cli_controls_both_loop_entry_shapes(self):
        import subprocess
        from support import ENV
        for kind in ('loop_array', 'loop_object'):
            with self.subTest(body=kind):
                f = self.fixture('agent_' + kind).start()
                f.add(f.body(kind, 'stop'))
                for cmd, phase in (('stop', 'stopped'), ('start', 'running'),
                                   ('sleep', 'sleeping'), ('wake', 'running')):
                    p = subprocess.run(['aos-agent', '--daemon', str(f.stack), 'ctl', cmd,
                        '--target', 'job', '--timeout-s', '4'], env=ENV, cwd=f.root,
                        capture_output=True, text=True, timeout=6)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    f.phase(phase)
                f.close()


if __name__ == '__main__':
    try:
        unittest.main(verbosity=2)
    finally:
        (SCRATCH / 'matrix.json').write_text(json.dumps(EVIDENCE, indent=2) + '\n')
        print('Evidence: ' + str(SCRATCH))
