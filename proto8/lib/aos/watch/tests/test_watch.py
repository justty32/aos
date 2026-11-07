# Verify watch acceptance, persistent retry decisions, public rollback calls and atomic writes.
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PROTO = Path(__file__).resolve().parents[4]
TOOL = PROTO / 'lib/aos/watch'


class WatchAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-watch-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.watch = self.root / 'reviews/watch.json'
        self.defs = self.root / 'defs'
        self.copy = self.root / 'copy'
        for base, data in ((self.defs, b'old\x00\xff\n'), (self.copy, b'new\x00\xfe\n')):
            (base / 'd').mkdir(parents=True)
            (base / 'd/data.bin').write_bytes(data)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        bins = [str(p) for group in ('impls', 'cmd') for p in (PROTO / group).glob('*/bin')]
        self.env['PATH'] = os.pathsep.join(bins + [self.env['PATH']])
        self.env['PYTHONPATH'] = os.pathsep.join([str(PROTO / 'lib'), str(PROTO / 'py')])
        self.env.update(AOS_WS=str(self.root), AOS_STACK=str(self.root / 'stack'))
        self.promotion = self.success(self.tool('promote', {
            'defs': str(self.defs), 'target': 'd', 'from': str(self.copy)}))

    def tool(self, name, data, *flags):
        return subprocess.run(['aos-exec', str(PROTO / 'lib/aos' / name), *flags],
                              input=json.dumps(data), env=self.env, cwd=self.root,
                              capture_output=True, text=True, timeout=15)

    def success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, '')
        return json.loads(result.stdout)

    def opened(self, **extra):
        args = {'op': 'open', 'watch': str(self.watch), 'defs': str(self.defs), 'target': 'd',
                'round': '2026-11-07T00-00-00.000Z', 'promoted_at': self.promotion['promoted_at'],
                'metric': '/token/in', 'baseline': 1.0, 'window': 3, 'tolerance': .10}
        args.update(extra)
        return self.success(self.tool('watch', args))

    def feed(self, unit, passed=True, **extra):
        measure = {'cost': {'token': {'in': unit * 100}}, 'size_bytes': 100, 'check': {'pass': passed}}
        measure.update(extra)
        return self.tool('watch', {'op': 'feed', 'watch': str(self.watch), 'case': 'cases/test',
                                   'measure': measure})

    def document(self):
        return json.loads(self.watch.read_text())

    def state(self):
        return self.document()['watch'][0]

    def assert_version(self, old=False):
        expected = b'old\x00\xff\n' if old else b'new\x00\xfe\n'
        self.assertEqual((self.defs / 'd/data.bin').read_bytes(), expected)
        self.assertEqual(Path(self.promotion['prev']).exists(), not old)

    def test_acceptance_expensive_window_rolls_back_on_third_case(self):
        # Criterion 1: 1.05, 1.15, 1.15 average above baseline * 1.10.
        self.opened()
        for unit in (1.05, 1.15):
            change = self.success(self.feed(unit))['changes'][0]
            self.assertEqual(change['state'], 'watching')
            self.assert_version()
        result = self.success(self.feed(1.15))
        self.assertEqual(result['changes'][0]['state'], 'rolled_back')
        self.assertEqual(self.state()['state'], 'rolled_back')
        self.assertEqual(len(self.state()['samples']), 3)
        self.assert_version(old=True)
        records = [json.loads(line) for line in (self.root / 'stack/observed.jsonl').read_text().splitlines()]
        self.assertEqual([r['code'] for r in records if r.get('name') == 'rollback'], [0])

    def test_acceptance_tolerated_window_keeps_previous_version(self):
        self.opened()
        for unit in (1.05, 1.15, 1.05):
            result = self.success(self.feed(unit))
        self.assertEqual(result['changes'][0]['state'], 'kept')
        self.assertEqual(self.state()['state'], 'kept')
        self.assert_version()
        before = self.document()
        self.assertEqual(self.success(self.feed(50, passed=False)), {'changes': []})
        self.assertEqual(self.document(), before)

    def test_acceptance_quality_failure_rolls_back_immediately(self):
        self.opened()
        result = self.success(self.feed(.5, passed=False))
        self.assertEqual(result['changes'][0]['state'], 'rolled_back')
        self.assertEqual(len(self.state()['samples']), 1)
        self.assert_version(old=True)

    def test_exact_tolerance_boundary_is_kept(self):
        self.opened(window=1)
        self.assertEqual(self.success(self.feed(1.1))['changes'][0]['state'], 'kept')
        self.assert_version()

    def test_several_windows_use_their_own_metric_and_keep_inactive_records(self):
        self.opened()
        self.opened(target='second', metric='/cpu~1time/~0ticks/0', baseline=10, window=1)
        data = self.document()
        inactive = {'target': 'done', 'state': 'rolled_back', 'custom': 'preserved'}
        data['watch'].append(inactive)
        data['custom'] = {'preserved': True}
        self.watch.write_text(json.dumps(data))
        result = self.success(self.feed(1, cost={'token': {'in': 100}, 'cpu/time': {'~ticks': [900]}}))
        self.assertEqual([c['state'] for c in result['changes']], ['watching', 'kept'])
        windows = self.document()['watch']
        self.assertEqual(windows[1]['samples'][0]['unit_cost'], 9)
        self.assertEqual(windows[2], inactive)
        self.assertEqual(self.document()['custom'], {'preserved': True})

    def busy_daemon(self):
        binaries = self.root / 'bin'
        binaries.mkdir()
        ctl = binaries / 'aos-daemon-ctl'
        ctl.write_text('#!/usr/bin/env python3\n# Expose one busy proc through the public listing.\n'
                       'import json, os\n'
                       'print(json.dumps({"procs": {"busy": {"phase": "running", "def": '
                       + repr(str(self.defs / 'd')) + '}}} if os.environ.get("TEST_BUSY") else {"procs": {}}))\n')
        ctl.chmod(0o755)
        self.env.update(PATH=str(binaries) + os.pathsep + self.env['PATH'],
                        AOS_DAEMON=str(self.root / 'daemon'), TEST_BUSY='yes')

    def test_busy_rollback_is_exit_zero_and_quality_failure_retries(self):
        self.opened()
        self.busy_daemon()
        result = self.success(self.feed(.5, passed=False))
        change = result['changes'][0]
        self.assertEqual(change['state'], 'watching')
        self.assertIn('DefBusy ', change['error'])
        self.assertTrue(change['error'].endswith('[exit code 1]'))
        self.assertEqual(self.state()['state'], 'watching')
        self.assert_version()
        self.env.pop('TEST_BUSY')
        result = self.success(self.feed(.5))
        self.assertEqual(result['changes'][0]['state'], 'rolled_back')
        self.assertEqual(len(self.state()['samples']), 2)
        self.assert_version(old=True)

    def test_cost_rollback_failure_retries_original_window(self):
        self.opened(window=1)
        self.busy_daemon()
        self.assertIn('error', self.success(self.feed(2))['changes'][0])
        self.env.pop('TEST_BUSY')
        self.assertEqual(self.success(self.feed(0))['changes'][0]['state'], 'rolled_back')
        self.assert_version(old=True)

    def test_bad_measure_does_not_write_or_roll_back(self):
        self.opened(window=1)
        before = self.watch.read_bytes()
        for extra in ({'size_bytes': 0}, {'size_bytes': -1}, {'cost': {}},
                      {'cost': {'token': {'in': True}}}, {'check': {'pass': 'false'}},
                      {'cost': {'token': {'in': float('nan')}}}):
            with self.subTest(extra=extra):
                result = self.feed(5, **extra)
                self.assertEqual(result.returncode, 1)
                self.assertIn('MeasureBad ', result.stderr)
                self.assertEqual(result.stdout, result.stderr)
                self.assertEqual(self.watch.read_bytes(), before)
                self.assert_version()

    def test_missing_or_bad_watch_and_invalid_open_use_tool_errors(self):
        self.assertEqual(self.success(self.feed(1)), {'changes': []})
        self.assertFalse(self.watch.exists())
        cases = [({'op': 'unknown', 'watch': str(self.watch)}, 'ArgumentsBad'),
                 ({'op': 'open', 'watch': 'relative'}, 'PathBad'),
                 ({'op': 'open', 'watch': str(self.watch)}, 'ArgumentsBad')]
        for data, code in cases:
            with self.subTest(code=code):
                result = self.tool('watch', data)
                self.assertEqual(result.returncode, 1)
                self.assertIn(code, result.stderr)
                self.assertEqual(result.stdout, result.stderr)
        self.watch.parent.mkdir(parents=True)
        self.watch.write_text('{bad')
        result = self.feed(1)
        self.assertEqual(result.returncode, 1)
        self.assertIn('FileBad', result.stderr)

    def test_help_is_schema_generated(self):
        result = self.tool('watch', {}, '--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--op', result.stdout)
        self.assertIn('--measure', result.stdout)


class AtomicWrite(unittest.TestCase):
    def test_failed_replace_preserves_original_and_removes_temporary(self):
        sys.path.insert(0, str(PROTO / 'lib'))
        self.addCleanup(sys.path.remove, str(PROTO / 'lib'))
        spec = importlib.util.spec_from_file_location('watch_state_test', TOOL / 'watch_state.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix='aos-watch-atomic-', dir='/tmp') as temporary:
            path = Path(temporary) / 'watch.json'
            path.write_text('{"watch": []}\n')
            original = path.read_bytes()
            with patch.object(module.os, 'replace', side_effect=OSError('replace denied')):
                with self.assertRaises(module.Error) as raised:
                    module._save(path, {'watch': [{'target': 'new'}]})
            self.assertEqual(raised.exception.code, 'WriteFailed')
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(temporary).iterdir()), [path])


if __name__ == '__main__':
    unittest.main()
