# Verify proc lifecycle and damaged-state adoption against real daemons and minimal bodies.
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from support import ENV, Fixture, EVIDENCE, SCRATCH, dc, read, until, write


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

    def test_sleep_escalates_cooperative_stop_and_keeps_stopped(self):
        f = self.fixture('sleep_stopping').start()
        f.add(f.body('script', 'stop', seconds=30))
        launch = f.row()['launch']
        f.ctl('stop', 'job')
        f.phase('stopping')
        f.ctl('sleep', 'job')
        row = f.phase('stopped')
        self.assertEqual(row['code'], 143)
        self.assertEqual(row['signal'], 15)
        self.assertEqual(row['launch'], launch)
        self.assertTrue(f.cell.exists())
        f.ctl('start', 'job')
        f.phase('running')
        time.sleep(.2)
        self.assertEqual(f.row()['phase'], 'running')
        f.ctl('stop', 'job')
        f.phase('stopping')
        f.ctl('sleep', 'job')
        f.phase('stopped')
        f.close()
        self.start_after_finish(f)
        self.assertEqual(f.row()['phase'], 'stopped')
        f.ctl('start', 'job')
        f.phase('running')

    def test_declared_sleep_escalates_stop_and_start_stays_running(self):
        f = self.fixture('declared_sleep_stopping').start()
        target = f.body('script', 'stop', seconds=30)
        spec = {'procs_added': {'job': str(target)}, 'procs_stopped': ['job']}
        f.add(target)
        write(f.stack / 'procs_ctl.json', spec)
        f.phase('stopping')
        write(f.stack / 'procs_ctl.json', dict(spec, procs_slept=['job']))
        self.assertEqual(f.phase('stopped')['signal'], 15)
        write(f.stack / 'procs_ctl.json', {'procs_added': {'job': str(target)}, 'procs_started': ['job']})
        f.phase('running')
        time.sleep(.2)
        self.assertEqual(f.row()['phase'], 'running')

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
            self.assertIsNone(read(f.stack / 'state_flux.json')['procs_ctl_warning'])
        write(f.stack / 'procs_ctl.json', {'procs_stopped': 4})
        until(lambda: read(f.stack / 'state_flux.json').get('procs_ctl_warning'))

    def test_response_only_changes_leave_stable_windows_untouched(self):
        f = self.fixture('flux_only').start()
        stable = [f.stack / name for name in ('state.json', 'procs_state.json')]
        before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in stable]
        flux = f.stack / 'state_flux.json'
        self.assertNotIn('updated_at', read(flux))
        for seq in (1, 2):
            write(f.stack / 'ctl.json', {'cmd': 'resume', 'seq': seq})
            until(lambda: read(flux, {}).get('ctl_seq') == seq)
        write(f.stack / 'procs_ctl.json', {'seq': 7})
        until(lambda: read(flux, {}).get('procs_ctl_seq') == 7)
        write(f.stack / 'procs_ctl.json', {'procs_stopped': 4})
        until(lambda: read(flux, {}).get('procs_ctl_warning'))
        previous_response = read(flux)['responded_at']
        dc.ask(str(f.stack), {'ping': True})
        until(lambda: read(flux)['responded_at'] != previous_response)
        self.assertEqual(before, [(p.read_bytes(), p.stat().st_mtime_ns) for p in stable])
        for p in stable:
            self.assertTrue({'ctl_seq', 'ctl_warning', 'responded_at', 'mailbox_warning'}.isdisjoint(read(p)))
        snapshot = (flux.read_bytes(), flux.stat().st_mtime_ns)
        time.sleep(.12)
        self.assertEqual(snapshot, (flux.read_bytes(), flux.stat().st_mtime_ns))

    def test_flux_ack_follows_stable_state_and_restart_deduplicates_stop(self):
        f = self.fixture('flux_restart').start()
        flux = f.stack / 'state_flux.json'
        write(f.stack / 'ctl.json', {'cmd': 'pause', 'seq': 11})
        until(lambda: read(flux, {}).get('ctl_seq') == 11)
        self.assertTrue(read(f.stack / 'state.json')['paused'])
        write(f.stack / 'ctl.json', {'cmd': 'stop', 'seq': 12})
        f.proc.wait(timeout=7)
        self.assertEqual(read(flux)['ctl_seq'], 12)
        self.assertEqual(read(f.stack / 'state.json')['phase'], 'stopped')
        f.close()
        f.start()
        until(lambda: read(f.stack / 'state.json', {}).get('pid') == f.proc.pid)
        self.assertIsNone(f.proc.poll())
        self.assertEqual(read(flux)['ctl_seq'], 12)
        self.assertTrue(read(f.stack / 'state.json')['paused'])

    def test_own_control_settings_are_stable_before_ack(self):
        f = self.fixture('flux_settings').start()
        flux = f.stack / 'state_flux.json'
        write(f.stack / 'ctl.json', {'cmd': 'resume', 'max': 100000,
                                     'interval_ms': 25, 'seq': 101})
        until(lambda: read(flux, {}).get('ctl_seq') == 101)
        state = read(f.stack / 'state.json')
        self.assertEqual(state['max'], 100000)
        self.assertEqual(state['interval_ms'], 25)
        self.assertFalse(state['paused'])

    def test_failed_stable_write_prevents_early_ack(self):
        f = self.fixture('flux_write_order').start()
        state = f.stack / 'state.json'
        backup = f.stack / 'saved_state.json'
        flux = f.stack / 'state_flux.json'
        state.rename(backup)
        state.mkdir()  # rename of the stable window fails deterministically, including as root.
        try:
            write(f.stack / 'ctl.json', {'cmd': 'resume', 'max': 100000,
                                         'interval_ms': 25, 'seq': 101})
            until(lambda: 'cannot write the state windows' in (f.root / 'daemon.err').read_text())
            time.sleep(.12)
            self.assertNotEqual(read(flux)['ctl_seq'], 101)
            self.assertEqual(read(backup)['interval_ms'], 20)
        finally:
            state.rmdir()
            backup.replace(state)
        until(lambda: read(flux, {}).get('ctl_seq') == 101)
        self.assertEqual(read(state)['max'], 100000)
        self.assertEqual(read(state)['interval_ms'], 25)
        self.assertIsNone(f.proc.poll())

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

    def stopped_adopt_fixture(self, name):
        f = self.fixture(name).start()
        f.add(f.body('loop_object', 'stop', seconds=.2))
        f.ctl('stop', 'job')
        f.phase('stopped')
        f.close()
        return f

    def assert_adopt_warning(self, f, prefix, suffix):
        warning = until(lambda: read(f.stack / 'state_flux.json', {}).get('adopt_warning'))
        self.assertIsInstance(warning, str)
        self.assertTrue(warning)
        lines = (f.root / 'daemon.err').read_text().splitlines()
        matches = [line for line in lines if line.startswith('aos-daemon: warning: ' + prefix)]
        self.assertEqual(len(matches), 1, lines)
        self.assertTrue(matches[0].endswith(suffix), matches[0])
        self.assertIn(warning, matches[0])
        logs = [json.loads(line) for line in (f.root / 'daemon.log').read_text().splitlines()]
        self.assertTrue(any(warning in value for entry in logs for value in entry.values()
                            if isinstance(value, str)), logs)
        dc.ask(str(f.stack), {'ping': True})
        self.assertEqual(read(f.stack / 'state_flux.json')['adopt_warning'], warning)
        self.assertIsNone(f.proc.poll())
        return matches[0]

    def test_adopt_invalid_json_preserves_original_and_starts_declared_procs(self):
        self.check_unreadable_adopt('invalid_json', '{bad')

    def test_adopt_non_object_preserves_original_and_starts_declared_procs(self):
        self.check_unreadable_adopt('non_object', '[]')

    def check_unreadable_adopt(self, name, contents):
        f = self.stopped_adopt_fixture('adopt_' + name)
        target = f.body('script', 'stop', seconds=30)
        write(f.config, {'interval_ms': 20, 'procs': {'declared': {'exec': str(target)}}})
        state = f.stack / 'procs_state.json'
        state.write_text(contents)
        f.start()
        until(lambda: f.rows().get('declared', {}).get('phase') == 'running')
        self.assertNotIn('job', f.rows())
        copies = list(f.stack.glob('procs_state.json.bad-*'))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_text(), contents)
        line = self.assert_adopt_warning(f, 'procs_state.json is unreadable (',
            '; kept it as ' + copies[0].name + ' and started with an empty table')
        self.assertIn('); kept it as ', line)

    def test_adopt_skips_non_object_row_and_keeps_valid_row(self):
        f = self.stopped_adopt_fixture('adopt_bad_row')
        f.start()
        target = f.body('script', 'fail', seconds=.2)
        f.ctl('add', '--name', 'broken', str(target))
        until(lambda: f.rows().get('broken', {}).get('phase') == 'stopped')
        f.close()
        state = f.stack / 'procs_state.json'
        original = read(state)
        good = original['procs']['job'].copy()
        original['procs']['broken'] = 42
        write(state, original)
        contents = state.read_bytes()
        f.start()
        self.assertEqual(f.phase('stopped'), good)
        self.assertNotIn('broken', f.rows())
        copies = list(f.stack.glob('procs_state.json.bad-*'))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_bytes(), contents)
        line = self.assert_adopt_warning(f,
            'procs_state.json row broken is not an object; skipped it (copy kept as ',
            copies[0].name + ')')
        self.assertEqual(line, 'aos-daemon: warning: procs_state.json row broken '
            'is not an object; skipped it (copy kept as ' + copies[0].name + ')')

    def test_adopt_normal_or_missing_state_has_no_warning(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                f = self.stopped_adopt_fixture('adopt_clean_' + str(missing))
                good = f.row().copy()
                state = f.stack / 'procs_state.json'
                if missing:
                    state.rename(f.root / 'saved_procs_state.json')
                f.start()
                self.assertIsNone(read(f.stack / 'state_flux.json')['adopt_warning'])
                self.assertFalse(list(f.stack.glob('procs_state.json.bad-*')))
                self.assertNotIn('aos-daemon: warning:', (f.root / 'daemon.err').read_text())
                if missing:
                    self.assertEqual(f.rows(), {})
                else:
                    self.assertEqual(f.phase('stopped'), good)
                self.assertIsNone(f.proc.poll())
                f.close()

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

    def slow_term_fixture(self, name):
        f = self.fixture(name).start()
        f.script.write_text('''#!/usr/bin/env python3
# Keep SIGTERM pending long enough to observe daemon shutdown and recovery.
import os, pathlib, signal, sys, time
s = pathlib.Path(os.environ['AOS_STACK'])
def term(signum, frame):
    (s / 'termed').write_text('termed')
    time.sleep(1.5)
    (s / 'exited').write_text('exited')
    sys.exit(0)
signal.signal(signal.SIGTERM, term)
(s / 'ready').write_text('ready')
time.sleep(12)
''')
        f.add(f.body('script', 'stop'))
        return f

    def start_after_finish(self, f):
        f.start()
        until(lambda: read(f.stack / 'procs_state.json', {}).get('pid') == f.proc.pid)

    def assert_finish_result(self, f, mode):
        if mode == 'rm':
            self.assertIsNone(f.row(), f.row())
        else:
            self.assertEqual(f.row()['phase'], 'stopped' if mode == 'stop' else 'sleeping')

    def wait_child_gone(self, pid):
        stat = Path('/proc', str(pid), 'stat')
        def gone():
            try:
                return stat.read_text().rsplit(')', 1)[1].split()[0] == 'Z'
            except FileNotFoundError:
                return True
        until(gone)

    def test_finish_preserves_pending_remove_stop_and_sleep(self):
        for mode in ('rm', 'stop', 'sleep'):
            with self.subTest(mode=mode):
                f = self.slow_term_fixture('finish_pending_' + mode)
                f.ctl(mode, 'job')
                f.phase('stopping')
                f.close()
                self.assert_finish_result(f, mode)
                self.start_after_finish(f)
                if mode == 'sleep':
                    f.phase('running')
                else:
                    self.assert_finish_result(f, mode)
                f.close()

    def test_adopt_finish_preserves_stop_mode_alive_and_dead(self):
        for child_alive in (True, False):
            for mode in ('stop', 'rm', 'sleep'):
                with self.subTest(mode=mode, child_alive=child_alive):
                    f = self.slow_term_fixture('crash_finish_' + mode + '_' + str(child_alive))
                    pid = f.row()['pid']
                    f.ctl(mode, 'job')
                    f.phase('stopping')
                    f.proc.send_signal(signal.SIGTERM)
                    until(lambda: read(f.stack / 'state.json', {}).get('phase') == 'stopping')
                    write(f.root / 'crash_procs_state.json', read(f.stack / 'procs_state.json'))
                    self.assertEqual(read(f.root / 'crash_procs_state.json')['procs']['job']['stop_mode'],
                                     'remove' if mode == 'rm' else mode)
                    f.proc.kill()
                    f.proc.wait()
                    f.close()
                    if not child_alive:
                        until(lambda: (f.cell / 'exited').exists())
                        self.wait_child_gone(pid)
                    else:
                        self.assertFalse((f.cell / 'exited').exists())
                    self.start_after_finish(f)
                    if mode == 'rm':
                        until(lambda: not f.rows())
                        self.assertIsNone(f.row())
                    elif mode == 'stop':
                        f.phase('stopped')
                    else:
                        until(lambda: f.row() and f.row()['phase'] == 'running' and f.row()['pid'] != pid)
                    until(lambda: (f.cell / 'exited').exists())
                    self.wait_child_gone(pid)
                    f.close()


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
            'exec': str(target), 'stuck_after_cycles': 1, 'restart_on_stuck': True}}})
        f.start()
        f.phase('running')
        until(lambda: (f.cell / 'ready').exists())
        first = f.row()['pid']
        write(f.cell / 'state_flux.json', {'responded_at': None})
        time.sleep(.03)
        write(f.cell / 'ctl.json', {'cmd': 'pause', 'seq': 1})
        until(lambda: f.row() and f.row()['phase'] == 'running' and f.row()['pid'] != first)
        self.assertIn('control window response timed out; restarting', (f.root / 'daemon.log').read_text())

    def test_stuck_uses_custom_flux_and_skips_disabled_or_bad_windows(self):
        f = self.fixture('stuck_custom')
        target = f.body('script', 'stop', seconds=30)
        write(f.config, {'interval_ms': 20, 'procs': {'job': {
            'exec': str(target), 'stuck_after_cycles': 1}}})
        f.start()
        f.phase('running')
        until(lambda: (f.cell / 'ready').exists())
        # Stable state has no response fields; only the selected flux counts.
        write(f.cell / 'state.json', {'phase': 'running'})
        write(f.cell / 'state_flux.json', {'responded_at': None})
        for name in (None, 12, 'reply.json'):
            write(f.cell / 'loop.json', {'state_flux': name})
            write(f.cell / 'reply.json', [])
            time.sleep(.03)
            write(f.cell / 'ctl.json', {'cmd': 'pause', 'seq': str(name)})
            time.sleep(1.15)
            self.assertEqual(f.row()['phase'], 'running')
        write(f.cell / 'reply.json', {'responded_at': None})
        f.phase('stuck')
        from datetime import datetime, timezone
        at = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        write(f.cell / 'reply.json', {'responded_at': at})
        f.phase('running')

    def test_frozen_clock_stuck_deadlines_use_selected_unit(self):
        for unit, threshold in (('ms', 300), ('cycles', 1)):
            with self.subTest(unit=unit):
                f = self.fixture('frozen_clock_' + unit)
                clock = f.stack / 'clock'
                clock.write_text('5\n')
                target = f.body('script', 'stop', seconds=30)
                write(f.config, {'interval_ms': 20, 'procs': {'job': {
                    'exec': str(target), 'stuck_after_' + unit: threshold}}})
                with patch.dict(ENV, AOS_CLOCK=str(clock)):
                    f.start()
                f.phase('running')
                until(lambda: (f.cell / 'ready').exists())
                write(f.cell / 'state_flux.json', {'responded_at': None})
                time.sleep(.03)
                write(f.cell / 'ctl.json', {'cmd': 'pause', 'seq': 1})
                if unit == 'ms':
                    row = f.phase('stuck')
                    self.assertIn('300 ms', row['reason'])
                    self.assertNotIn('cycles', row['reason'])
                else:
                    time.sleep(1.5)
                    self.assertEqual(f.row()['phase'], 'running')
                self.assertEqual(clock.read_text(), '5\n')
                f.close()

    def test_stuck_deadline_rejects_conflicting_and_invalid_ms(self):
        bad = ({'stuck_after_cycles': 1, 'stuck_after_ms': 300},
               {'stuck_after_ms': 0}, {'stuck_after_ms': -1},
               {'stuck_after_ms': '300'}, {'stuck_after_ms': True},
               {'stuck_after_ms': 1.5}, {'stuck_after_ms': None},
               {'stuck_after_ms': 2**63}, {'stuck_after_ms': 2**64})
        for i, fields in enumerate(bad):
            with self.subTest(fields=fields):
                f = self.fixture('bad_stuck_ms_' + str(i))
                target = f.body('script', 'stop', seconds=30)
                write(f.config, {'interval_ms': 20, 'procs': {'job': {
                    'exec': str(target), **fields}}})
                result = subprocess.run(['aos-daemon', str(f.config)], cwd=f.root,
                    env=dict(ENV, AOS_STACK=str(f.stack)), capture_output=True,
                    text=True, timeout=5)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('CfgBad', result.stderr)

    def test_clock_key_is_ignored_without_exporting_clock(self):
        f = self.fixture('ignored_clock_key')
        f.script.write_text(f.script.read_text().replace(
            "(s / 'ready').write_text('ready')",
            "(s / 'clock_env.json').write_text(__import__('json').dumps("
            "{'AOS_CLOCK': os.environ.get('AOS_CLOCK')}))\n"
            "(s / 'ready').write_text('ready')"))
        target = f.body('script', 'stop', seconds=30)
        write(f.config, {'clock': True, 'interval_ms': 20,
                         'procs': {'job': {'exec': str(target)}}})
        with patch.dict(ENV):
            ENV.pop('AOS_CLOCK', None)
            f.start()
        f.phase('running')
        until(lambda: (f.cell / 'ready').exists())
        self.assertNotIn('_clock', f.rows())
        self.assertIsNone(read(f.cell / 'clock_env.json')['AOS_CLOCK'])
        self.assertFalse((f.stack / 'clock').exists())
        self.assertIsNone(f.proc.poll())

    def test_explicit_clock_proc_writes_exported_clock_path(self):
        f = self.fixture('explicit_clock')
        clock = f.stack / 'clock'
        write(f.config, {'interval_ms': 20, 'procs': {'_clock': {
            'exec': {'argv': ['aos-clock', {'$env': 'AOS_DAEMON', '$path': 'clock'}]},
            'interval_ms': 100, 'auto_restart': True, 'stuck_after_ms': 10000}}})
        with patch.dict(ENV, AOS_CLOCK=str(clock)):
            f.start()
        row = until(lambda: (r if (r := f.rows().get('_clock')) and
                             r['phase'] == 'running' else None))
        first = until(lambda: read(clock))
        until(lambda: (value := read(clock)) is not None and value > first)
        # The persistent loop owns the environment used to resolve its inline argv.
        raw = Path('/proc', str(row['pid']), 'environ').read_bytes()
        child_env = dict(entry.split(b'=', 1) for entry in raw.split(b'\0') if b'=' in entry)
        written = Path(os.fsdecode(child_env[b'AOS_DAEMON'])) / 'clock'
        exported = Path(os.fsdecode(child_env[b'AOS_CLOCK']))
        self.assertEqual(written.resolve(), exported.resolve())
        self.assertEqual(exported.resolve(), clock.resolve())
        self.assertFalse((f.stack / 'procs' / '_clock' / 'clock').exists())
        self.assertEqual(f.rows()['_clock']['phase'], 'running')

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
