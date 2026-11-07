# Verify definition swaps, byte recovery, and busy guards through real aos tools.
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

PROTO = Path(__file__).resolve().parents[4]


def snapshot(root):
    return {str(p.relative_to(root)): ('link', os.readlink(p)) if p.is_symlink()
            else ('dir',) if p.is_dir() else ('file', p.read_bytes())
            for p in root.rglob('*')}


class SwapAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-swap-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.defs, self.copy = self.root / 'defs', self.root / 'copy'
        for base, content in ((self.defs, b'old\x00\xff\n'), (self.copy, b'new\x00\xfe\n')):
            (base / 'd' / 'nested').mkdir(parents=True)
            (base / 'd' / 'empty').mkdir()
            (base / 'd' / 'link').symlink_to('data.bin')
            (base / 'd' / 'data.bin').write_bytes(content)
            (base / 'd' / 'nested' / 'second').write_bytes(content[::-1])
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        bins = [str(p) for group in ('impls', 'cmd') for p in (PROTO / group).glob('*/bin')]
        self.env['PATH'] = os.pathsep.join(bins + [self.env['PATH']])
        self.env['PYTHONPATH'] = os.pathsep.join([str(PROTO / 'lib'), str(PROTO / 'py')])
        (self.root / 'tools').mkdir()
        self.env.update(AOS_WS=str(self.root), AOS_STACK=str(self.root / 'tools'))

    def tool(self, name, **extra):
        data = {'defs': str(self.defs), 'target': 'd'}
        if name == 'promote':
            data['from'] = str(self.copy)
        data.update(extra)
        return subprocess.run(['aos-exec', str(PROTO / 'lib/aos' / name)],
                              input=json.dumps(data), env=self.env, cwd=self.root,
                              capture_output=True, text=True, timeout=15)

    def success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def error(self, result, code):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(code, result.stderr)
        self.assertEqual(result.stdout.strip(), result.stderr.strip().splitlines()[-1])

    def test_promote_and_rollback_preserve_all_bytes(self):
        old, new = snapshot(self.defs / 'd'), snapshot(self.copy / 'd')
        result = self.success(self.tool('promote'))
        self.assertEqual(result['target'], 'd')
        prev = Path(result['prev'])
        self.assertEqual(prev.parent, self.defs / '.prev/d')
        self.assertEqual(prev.name, result['promoted_at'].replace(':', '-'))
        self.assertNotIn(':', prev.name)
        self.assertEqual(snapshot(prev), old)
        self.assertEqual(snapshot(self.defs / 'd'), new)
        self.assertEqual(snapshot(self.copy / 'd'), new)
        restored = self.success(self.tool('rollback'))
        self.assertEqual(restored['restored'], prev.name)
        self.assertEqual(snapshot(self.defs / 'd'), old)
        self.assertFalse((self.defs / '.prev/d').exists())

    def test_invalid_targets_never_change_either_tree(self):
        before = snapshot(self.root)
        for target in ('../x', '/abs', '.prev/d', 'd/../x', 'd/.hidden'):
            for name in ('promote', 'rollback'):
                with self.subTest(target=target, tool=name):
                    self.error(self.tool(name, target=target), 'PathBad')
                    self.assertEqual(snapshot(self.root), before)

    def test_missing_definitions_do_not_create_backups(self):
        before = snapshot(self.root)
        self.error(self.tool('promote', target='absent'), 'DefMissing')
        self.error(self.tool('promote', **{'from': str(self.root / 'absent')}), 'DefMissing')
        self.assertEqual(snapshot(self.root), before)

    def test_failed_daemon_query_leaves_both_trees_unchanged(self):
        before, source = snapshot(self.defs), snapshot(self.copy)
        for name in ('promote', 'rollback'):
            self.error(self.tool(name, daemons=[str(self.root / 'missing_daemon')]), 'DaemonFailed')
            self.assertEqual(snapshot(self.defs), before)
            self.assertEqual(snapshot(self.copy), source)

    def test_multiple_previous_versions_restore_newest_first(self):
        old = snapshot(self.defs / 'd')
        first = self.success(self.tool('promote'))
        middle = snapshot(self.defs / 'd')
        (self.copy / 'd/data.bin').write_bytes(b'third')
        second = self.success(self.tool('promote'))
        self.assertNotEqual(first['prev'], second['prev'])
        self.assertEqual(self.success(self.tool('rollback'))['restored'], second['promoted_at'].replace(':', '-'))
        self.assertEqual(snapshot(self.defs / 'd'), middle)
        self.assertEqual(self.success(self.tool('rollback'))['restored'], first['promoted_at'].replace(':', '-'))
        self.assertEqual(snapshot(self.defs / 'd'), old)
        self.error(self.tool('rollback'), 'PrevMissing')

    def test_nested_target_history_is_not_a_parent_version(self):
        original_child = snapshot(self.defs / 'd/nested')
        child = self.success(self.tool('promote', target='d/nested'))
        parent_before = snapshot(self.defs / 'd')
        parent = self.success(self.tool('promote'))
        restored = self.success(self.tool('rollback'))
        self.assertEqual(restored['restored'], parent['promoted_at'].replace(':', '-'))
        self.assertEqual(snapshot(self.defs / 'd'), parent_before)
        self.assertTrue(Path(child['prev']).is_dir())
        restored_child = self.success(self.tool('rollback', target='d/nested'))
        self.assertEqual(restored_child['restored'], child['promoted_at'].replace(':', '-'))
        self.assertEqual(snapshot(self.defs / 'd/nested'), original_child)
        self.assertFalse((self.defs / '.prev/d/nested').exists())

    def test_ambiguous_timestamp_child_history_is_rejected_without_changes(self):
        child = '2099-01-01T00-00-00.000Z'
        for root, content in ((self.defs, b'old child'), (self.copy, b'new child')):
            (root / 'd' / child).mkdir()
            (root / 'd' / child / 'data').write_bytes(content)
        self.success(self.tool('promote', target='d/' + child))
        self.success(self.tool('promote'))
        before, source = snapshot(self.defs), snapshot(self.copy)
        self.error(self.tool('rollback'), 'SwapFailed')
        self.assertEqual(snapshot(self.defs), before)
        self.assertEqual(snapshot(self.copy), source)

    def ctl(self, *args):
        result = subprocess.run(['aos-daemon-ctl', *args], env=self.env, cwd=self.root,
                                capture_output=True, text=True, timeout=12)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result

    def wait_rows(self, predicate):
        deadline = time.monotonic() + 6
        while True:
            table = json.loads(self.ctl('ls', '--json').stdout)['procs']
            rows = [dict(row, name=name) for name, row in table.items()]
            if predicate(rows):
                return rows
            self.assertLess(time.monotonic(), deadline, rows)
            time.sleep(.02)

    def test_real_daemon_descendant_busy_then_stopped_is_allowed(self):
        # The fixture follows the proc's public control contract and needs no LLM.
        program = ('#!/usr/bin/env python3\n# Wait until the public ctl requests stop.\n'
                   'import json, os, pathlib, time\n'
                   'ctl = pathlib.Path(os.environ["AOS_STACK"]) / "ctl.json"\n'
                   'while True:\n'
                   ' try:\n'
                   '  if json.loads(ctl.read_text()).get("cmd") == "stop": break\n'
                   ' except (FileNotFoundError, ValueError): pass\n'
                   ' time.sleep(.01)\n')
        for base in (self.defs, self.copy):
            entry = base / 'd/nested/_entry'
            entry.write_text(program)
            entry.chmod(0o755)
        self.success(self.tool('promote'))
        daemon = self.root / 'daemon'
        daemon.mkdir()
        config = self.root / 'daemon.json'
        config.write_text(json.dumps({'interval_ms': 10, 'procs': {}}))
        self.env['AOS_DAEMON'] = str(daemon)
        with (self.root / 'daemon.log').open('w+') as log:
            process = subprocess.Popen(['aos-daemon', str(config)], env=dict(self.env, AOS_STACK=str(daemon)),
                                       cwd=self.root, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 6
                while not (daemon / 'procs_state.json').exists():
                    self.assertIsNone(process.poll())
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(.02)
                alias = self.root / 'alias'
                alias.symlink_to(self.defs / 'd', target_is_directory=True)
                self.ctl('add', '--name', 'busy', '--def', str(alias / 'nested'),
                         str(self.defs / 'd/nested'))
                self.wait_rows(lambda rows: any(r['name'] == 'busy' and r['phase'] != 'stopped' for r in rows))
                before, source = snapshot(self.defs), snapshot(self.copy)
                for name in ('promote', 'rollback'):
                    self.error(self.tool(name), 'DefBusy')
                    self.assertEqual(snapshot(self.defs), before)
                    self.assertEqual(snapshot(self.copy), source)
                self.ctl('stop', 'busy')
                self.wait_rows(lambda rows: any(r['name'] == 'busy' and r['phase'] == 'stopped' for r in rows))
                self.success(self.tool('promote'))
                self.assertEqual(snapshot(self.defs / 'd'), snapshot(self.copy / 'd'))
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
