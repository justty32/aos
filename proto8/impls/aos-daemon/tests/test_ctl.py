# Exercise public controls, prune inspection and age selection, command errors and help.
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

from support import ENV, PROTO, dc, read, write
sys.path.insert(0, str(PROTO / 'cmd' / 'aos-agent'))
from aos_agent import hints
from aos_agent.ctl import shared


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
            valid_phases = {valid, 'stopping'} if cmd == 'sleep' else {valid}
            for phase in valid_phases:
                dc.need_phase(cmd, 'job', {'phase': phase})
            already = {'stop': 'stopped', 'sleep': 'sleeping', 'start': 'running', 'wake': 'running'}[cmd]
            for invalid in {'running', 'stopping', 'stopped', 'sleeping'} - valid_phases:
                if invalid == already:           # 11-10 cli-sweep Q4＝A：已經是那個狀態＝成功（Already），不是 PhaseBad
                    with self.assertRaises(dc.Already):
                        dc.need_phase(cmd, 'job', {'phase': invalid})
                    continue
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
            with patch.object(shared, 'daemon_path', return_value=str(self.root)), \
                 patch.object(dc, 'row_of', return_value={'phase': phase}):
                self.assertEqual(shared.phase_body(cmd, 'job'), {'procs_' + key: ['job']})

    def test_agent_sleep_waits_for_stopped_when_escalating(self):
        from aos_agent.ctl import phase
        agent = SimpleNamespace(name='job', phase='stopping', stack=str(self.root))
        def wait(cmd, body, reached, *args, **kwargs):
            self.assertEqual(cmd, 'sleep')
            self.assertEqual(body, {'procs_slept': ['job']})
            self.assertTrue(reached(None))
        with patch.object(phase, 'need_table'), patch.object(phase, 'target', return_value=agent), \
             patch.object(phase, 'phase_body', return_value={'procs_slept': ['job']}), \
             patch.object(phase, 'row_named', side_effect=[{'phase': 'stopping', 'stop_mode': 'stop'}, {'phase': 'stopped'}]), \
             patch.object(phase.aos_ws, 'history', return_value=[]), \
             patch.object(phase, 'ctl_wait', side_effect=wait), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            phase.cmd_sleep([])
        self.assertIn('stopped, stack kept', out.getvalue())
        self.assertIn('ctl start', out.getvalue())

    def test_agent_sleep_keeps_sleep_and_remove_pending_modes(self):
        from aos_agent.ctl import phase
        for mode in ('sleep', 'remove', None):
            with self.subTest(mode=mode):
                agent = SimpleNamespace(name='job', phase='stopping' if mode else 'running', stack=str(self.root))
                first = {'phase': agent.phase, 'stop_mode': mode}
                last = None if mode == 'remove' else {'phase': 'sleeping'}
                def wait(cmd, body, reached, *args, **kwargs):
                    self.assertTrue(reached(None))
                with patch.object(phase, 'need_table'), patch.object(phase, 'target', return_value=agent), \
                     patch.object(phase, 'phase_body', return_value={'procs_slept': ['job']}), \
                     patch.object(phase, 'row_named', side_effect=[first, last]), \
                     patch.object(phase.aos_ws, 'history', return_value=[]), \
                     patch.object(phase, 'ctl_wait', side_effect=wait), \
                     contextlib.redirect_stdout(io.StringIO()) as out:
                    phase.cmd_sleep([])
                self.assertIn('asleep, stack kept', out.getvalue())

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


class Prune(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-prune-ctl-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cli = PROTO / 'cmd' / 'aos-daemon-ctl' / 'bin' / 'aos-daemon-ctl'
        self.procs = {}

    def row(self, name, phase='stopped', **fields):
        stack = self.root / name
        stack.mkdir(exist_ok=True)
        self.procs[name] = dict(phase=phase, stack=name, **fields)
        write(self.root / 'procs_state.json', {'procs': self.procs})
        return stack

    def ctl(self, *args):
        return subprocess.run([str(self.cli), '--daemon', str(self.root), *args],
                              env=ENV, capture_output=True, text=True, timeout=5)

    def test_duration_units_and_invalid_values(self):
        for value, seconds in [('30s', 30), ('15m', 900), ('12h', 43200), ('7d', 604800)]:
            self.assertEqual(dc.duration(value), seconds)
        for value in ('0s', '-1d', '+1h', '1.5h', '3x', '1D', '1', ' 1d', '', '1d\n'):
            with self.subTest(value=value), self.assertRaises(dc.Fail) as got:
                dc.duration(value)
            self.assertEqual(got.exception.code, 'ArgumentsBad')

    def test_check_reports_each_suspicious_row_once_and_exits_zero(self):
        missing = self.row('missing', code=0)
        missing.rmdir()
        bad = self.row('bad', reason='failed\nwith\ttabs')
        write(bad / 'ctl.json', [])
        custom = self.row('custom')
        write(custom / 'loop.json', {'ctl': 'control.json'})
        (custom / 'control.json').write_text('{broken')
        self.row('gone', 'running', pid=2147483647, started_at_ticks=1)
        self.row('reused', 'stopping', pid=os.getpid(), started_at_ticks=-1)
        self.row('live', 'running')
        self.row('healthy')
        result = self.ctl('prune')
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 3, result.stdout)
        self.assertIn('missing: stopped: stack missing', lines)
        self.assertIn('bad: stopped: ctl is not a JSON object:', result.stdout)
        self.assertIn('failed with tabs', result.stdout)
        self.assertIn('control.json', result.stdout)
        self.assertNotIn('gone:', result.stdout)
        self.assertNotIn('reused:', result.stdout)
        self.assertNotIn('live:', result.stdout)
        self.assertNotIn('healthy:', result.stdout)

    def test_pending_rows_without_stacks_are_healthy(self):
        for phase in ('stopped', 'sleeping'):
            self.row(phase, phase, pid=None, code=None).rmdir()
        result = self.ctl('prune')
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
        for name, fields in (('exited', {'code': 0}), ('recorded', {'pid': 123}),
                             ('running', {'phase': 'running'})):
            row = dict(phase='stopped', stack=str(self.root / name), pid=None, code=None)
            row.update(fields)
            with self.subTest(name=name):
                self.assertIn('stack missing', dc.inspect_row(str(self.root), name, row))

    def test_ctl_json_shapes_and_parent_filename_fallback(self):
        stack = self.row('job')
        row = dc.row_of(str(self.root), 'job')
        for value in ({}, [], None, True, 'text', 4):
            write(stack / 'ctl.json', value)
            self.assertEqual(bool(dc.inspect_row(str(self.root), 'job', row)),
                             not isinstance(value, dict))
        for ctl in (None, '', 12):
            write(stack / 'loop.json', {'ctl': ctl})
            self.assertIn('ctl is not a JSON object', dc.inspect_row(str(self.root), 'job', row))
        write(self.root / 'procs_state.json', {'procs_loop': 'parent.json', 'procs': self.procs})
        write(stack / 'parent.json', {'ctl': 'public.json'})
        write(stack / 'public.json', {})
        self.assertEqual(dc.inspect_row(str(self.root), 'job', row), '')
        (stack / 'public.json').unlink()
        self.assertEqual(dc.inspect_row(str(self.root), 'job', row), '')

    def test_mtime_uses_stack_and_direct_files_without_recursing(self):
        stack = self.row('job')
        nested = stack / 'nested'
        nested.mkdir()
        (nested / 'new').write_text('not JSON')
        direct = stack / 'direct'
        direct.write_text('not JSON either')
        os.utime(direct, (200, 200))
        os.utime(stack, (100, 100))
        self.assertEqual(dc.last_change(str(stack)), 200)
        os.utime(stack, (300, 300))
        self.assertEqual(dc.last_change(str(stack)), 300)
        self.assertIsNone(dc.last_change(str(stack / 'missing')))
        with patch('os.scandir', side_effect=PermissionError('denied')), self.assertRaises(dc.Fail) as got:
            dc.last_change(str(stack))
        self.assertEqual(got.exception.code, 'StateBad')

    def test_candidates_are_strictly_old_stopped_or_sleeping_only(self):
        for phase in ('stopped', 'sleeping', 'running', 'stopping', 'stuck'):
            stack = self.row(phase, phase)
            os.utime(stack, (100, 100))
        self.row('missing').rmdir()
        rows = dc.rows(str(self.root))
        selected = dict(dc.prune_candidates(str(self.root), rows, 50, 151))
        self.assertEqual(set(selected), {'stopped', 'sleeping'})
        self.assertEqual(selected['stopped'], '1970-01-01T00:01:40+00:00')
        self.assertEqual(dict(dc.prune_candidates(str(self.root), rows, 50, 150)), {})
        self.assertEqual(dict(dc.prune_candidates(str(self.root), rows, 10 ** 400, 151)), {})

    def test_apply_uses_rm_send_wait_and_error_paths_and_keeps_files(self):
        stack = self.row('job')
        marker = stack / 'keep'
        marker.write_text('keep')
        os.utime(marker, (100, 100))
        os.utime(stack, (100, 100))
        cli = runpy.run_path(str(self.cli))
        opts = {'daemon': str(self.root)}
        with patch.object(dc, 'send', return_value='letter') as send, \
             patch.object(dc, 'mailbox_of', return_value='box'), \
             patch.object(dc, 'reply_box', return_value='rbox'), \
             patch.object(dc, 'take_reply', return_value={'applied': True}), \
             patch.object(dc, 'wait_taken', return_value=True) as wait:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                cli['cmd_rm'](opts, ['--timeout-s', '2', 'job'])
            rm_call, rm_wait = send.call_args, wait.call_args
            self.assertEqual(out.getvalue(), 'letter\n')
            with contextlib.redirect_stdout(io.StringIO()) as out:
                cli['cmd_prune'](opts, ['--older-than', '1d', '--apply', '--timeout-s', '2'])
            self.assertEqual(out.getvalue(), 'job: removed\n')
            self.assertEqual(send.call_args, rm_call)
            self.assertEqual(wait.call_args, rm_wait)
            self.assertTrue(send.call_args.kwargs['direct'])
            self.assertEqual(send.call_args.args[1], {'procs_removed': ['job']})
            with contextlib.redirect_stdout(io.StringIO()):
                cli['cmd_prune'](opts, ['--older-than', '1d', '--apply', '--reply-to', 'replies'])
            self.assertEqual(send.call_args.args[2], os.path.abspath('replies'))
            self.assertEqual(wait.call_count, 2)  # reply-to follows rm's send-only path.
        with patch.object(dc, 'send', side_effect=dc.Fail('SendFailed', 'send failed')), \
             patch.object(dc, 'reply_box', return_value='rbox'):
            for cmd, args in [('cmd_rm', ['job']),
                              ('cmd_prune', ['--older-than', '1d', '--apply'])]:
                with contextlib.redirect_stdout(io.StringIO()) as out, self.assertRaises(dc.Fail) as got:
                    cli[cmd](opts, args)
                self.assertEqual(got.exception.code, 'SendFailed')
                self.assertNotIn('removed', out.getvalue())
        self.assertEqual(marker.read_text(), 'keep')
        self.assertEqual(read(self.root / 'procs_state.json')['procs'], self.procs)

    def test_apply_rechecks_rows_that_started_or_changed_while_waiting(self):
        stack = self.row('job')
        os.utime(stack, (100, 100))
        initial = dc.rows(str(self.root))
        cli = runpy.run_path(str(self.cli))
        for changed in (dict(initial['job'], phase='running'), initial['job']):
            with self.subTest(changed=changed):
                os.utime(stack, (100, 100))
                calls = 0
                def snapshot(_):
                    nonlocal calls
                    calls += 1
                    if calls == 2 and changed['phase'] == 'stopped':
                        os.utime(stack, None)
                    return initial if calls == 1 else {'job': changed}
                with patch.object(dc, 'rows', side_effect=snapshot):
                    with patch.object(dc, 'send') as send, contextlib.redirect_stdout(io.StringIO()) as out:
                        cli['cmd_prune']({'daemon': str(self.root)}, ['--older-than', '1d', '--apply'])
                    send.assert_not_called()
                    self.assertNotIn('removed', out.getvalue())
                    self.assertEqual(calls, 2)

    def test_dry_run_never_sends_and_bad_flags_have_usage(self):
        self.row('missing').rmdir()
        cli = runpy.run_path(str(self.cli))
        for flags in ([], ['--apply']):
            with patch.object(dc, 'send') as send, contextlib.redirect_stdout(io.StringIO()) as out:
                cli['cmd_prune']({'daemon': str(self.root)}, ['--older-than', '1d', *flags])
            send.assert_not_called()
            self.assertEqual(out.getvalue(), '')
        for args in (['--apply'], ['--older-than', '3x'], ['--older-than', '0s'],
                     ['--older-than'], ['--apply=yes'], ['unexpected'], ['--reply-to', ''],
                     ['--timeout-s', 'nan'], ['--timeout-s', '1', '--reply-to', 'box']):
            with self.subTest(args=args):
                result = self.ctl('prune', *args)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, '')
                self.assertIn('aos-daemon-ctl: error: ArgumentsBad', result.stderr)
                self.assertIn('(usage: aos-daemon-ctl [--daemon D] prune', result.stderr)
        result = self.ctl('prune', '--unknown')
        self.assertEqual(result.returncode, 1)
        self.assertIn('FlagUnknown', result.stderr)

    def test_help_lists_prune_and_explains_all_flags_in_english(self):
        for args in (['--help'], ['prune', '--help'], ['prune', '-h']):
            result = self.ctl(*args)
            self.assertEqual((result.returncode, result.stderr), (0, ''))
            self.assertIn('prune', result.stdout)
            self.assertTrue(result.stdout.isascii())
            for flag in ('--older-than', '--apply'):
                self.assertIn(flag, result.stdout)
        self.assertIn('stack / workspace file', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
