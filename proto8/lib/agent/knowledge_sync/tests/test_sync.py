"""Exercise knowledge_sync against temporary local Git repositories and tool errors."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / '_entry'
RULES = '.*.tmp\n.tmp.*\n'


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='knowledge-sync-', dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / 'origin.git'
        self.a, self.b = self.root / 'a', self.root / 'b'
        self.git(self.root, 'init', '--bare', '--initial-branch=main', str(self.remote))
        self.git(self.root, 'clone', str(self.remote), str(self.a))
        self.config(self.a)
        (self.a / '.gitignore').write_text(RULES)
        (self.a / 'node.md').write_text('# Node\nbase\n')
        self.commit(self.a)
        self.git(self.a, 'push', '-u', 'origin', 'main')
        self.git(self.root, 'clone', str(self.remote), str(self.b))
        self.config(self.b)

    def git(self, root, *args):
        p = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def config(self, root):
        self.git(root, 'config', 'user.email', 'sync@example.invalid')
        self.git(root, 'config', 'user.name', 'Sync Test')

    def commit(self, root):
        self.git(root, 'add', '-A')
        self.git(root, 'commit', '-m', 'test setup')

    def call(self, root, op='sync', code=None, **args):
        env = dict(os.environ, AOS_KNOWLEDGE=str(root), AOS_CD=str(self.root / 'no-config'))
        p = subprocess.run([str(ENTRY)], input=json.dumps(dict(op=op, **args)),
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 1 if code else 0, p.stdout + p.stderr)
        if code:
            self.assertIn('knowledge_sync: error: ' + code + ' ', p.stdout)
            self.assertIn(p.stdout.splitlines()[-1], p.stderr)
        return p

    def test_different_nodes_both_survive(self):
        (self.a / 'alpha.md').write_text('# Alpha\n')
        (self.b / 'beta.md').write_text('# Beta\n')
        self.call(self.a)
        self.call(self.b)
        self.call(self.a)
        for root in (self.a, self.b):
            self.assertTrue((root / 'alpha.md').exists())
            self.assertTrue((root / 'beta.md').exists())
        message = self.git(self.a, 'log', '--all', '--format=%s')
        self.assertIn(socket.gethostname(), message)
        self.assertRegex(message, r'knowledge_sync .* \d{4}-\d\d-\d\dT.*\+00:00')

    def test_later_sync_wins_same_hunk(self):
        (self.a / 'node.md').write_text('# Node\nfirst\n')
        (self.b / 'node.md').write_text('# Node\nlater\n')
        self.call(self.a)
        self.call(self.b)
        self.call(self.a)
        self.assertEqual((self.a / 'node.md').read_text(), '# Node\nlater\n')

    def test_delete_modify_aborts_to_premerge_tree(self):
        (self.a / 'node.md').unlink()
        (self.b / 'node.md').write_text('# Node\nchanged locally\n')
        self.call(self.a)
        self.call(self.b, code='SyncConflict')
        self.assertEqual((self.b / 'node.md').read_text(), '# Node\nchanged locally\n')
        self.assertEqual(self.git(self.b, 'status', '--porcelain'), '')
        self.assertEqual(self.git(self.b, 'diff', 'HEAD', '--'), '')
        self.assertFalse((self.b / '.git/MERGE_HEAD').exists())

    def test_nonrepo(self):
        self.call(self.root, code='NotGitRepo')

    def test_remote_missing(self):
        self.git(self.a, 'remote', 'remove', 'origin')
        self.call(self.a, code='RemoteMissing')

    def test_ignore_missing_no_mutation(self):
        (self.a / '.gitignore').write_text('.tmp.*\n')
        before = self.git(self.a, 'status', '--porcelain')
        p = self.call(self.a, code='IgnoreMissing')
        self.assertEqual(p.stdout.splitlines()[:2], RULES.splitlines())
        self.assertEqual(self.git(self.a, 'status', '--porcelain'), before)

    def test_status_counts_and_no_network(self):
        (self.a / 'one.md').write_text('# One\n')
        self.assertEqual(json.loads(self.call(self.a, op='status').stdout),
                         {'changed_files': 1, 'ahead': 0, 'behind': 0})
        self.commit(self.a)
        self.assertEqual(json.loads(self.call(self.a, op='status').stdout)['ahead'], 1)

    def test_ignored_temporary_files(self):
        for name in ('.tmp.x', '.node.json.123.tmp'):
            (self.a / name).write_text('not knowledge')
        self.call(self.a)
        self.assertEqual(self.git(self.a, 'status', '--porcelain'), '')

    def test_ignore_overrides_are_rejected(self):
        for exception in ('!.tmp.*', '!knowledge_sync_probe/.*.tmp'):
            (self.a / '.gitignore').write_text(RULES + exception + '\n')
            self.call(self.a, code='IgnoreMissing')

    def test_status_whitespace_filenames(self):
        for name in (' leading.md', 'trailing.md ', 'line\nbreak.md'):
            (self.a / name).write_text('# Space\n')
        self.assertEqual(json.loads(self.call(self.a, op='status').stdout)['changed_files'], 3)
        self.git(self.a, 'mv', 'node.md', ' renamed\nnode.md ')
        self.assertEqual(json.loads(self.call(self.a, op='status').stdout)['changed_files'], 4)

    def test_status_counts_nested_untracked_files(self):
        nested = self.a / 'nested/deeper'
        nested.mkdir(parents=True)
        (nested / 'one.md').write_text('# One\n')
        (nested / 'two.md').write_text('# Two\n')
        (self.a / 'nested/three.md').write_text('# Three\n')
        self.assertEqual(json.loads(self.call(self.a, op='status').stdout)['changed_files'], 3)

    def test_status_rename_counts_once(self):
        self.git(self.a, 'mv', 'node.md', 'renamed.md')
        result = json.loads(self.call(self.a, op='status').stdout)
        self.assertEqual(result['changed_files'], 1)

    def test_configuration_uses_shared_knowledge_root(self):
        folder = self.root / 'no-config'
        folder.mkdir()
        (folder / '_knowledge.json').write_text(json.dumps({'base': '../a'}))
        self.call(self.root, op='status')

    def test_existing_merge_is_not_changed(self):
        marker = self.a / '.git/MERGE_HEAD'
        marker.write_text(self.git(self.a, 'rev-parse', 'HEAD') + '\n')
        self.call(self.a, code='CommandFailed')
        self.assertTrue(marker.exists())

    def test_invalid_arguments_and_help(self):
        self.call(self.a, op='bad', code='OpUnknown')
        self.call(self.a, timeout_s=-1, code='ArgumentsBad')
        p = subprocess.run([str(ENTRY), '--help'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertIn('--timeout-s', p.stdout)


if __name__ == '__main__':
    unittest.main()
