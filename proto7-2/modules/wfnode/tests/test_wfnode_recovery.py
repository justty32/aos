"""首次導入復原、名稱與 CLI 引用的端到端測試。"""
import os
from pathlib import Path
import shlex
import shutil
import tempfile
import unittest
from unittest.mock import patch

from test_wfnode import HOME, run
import aos7_wfnode as wfnode


@unittest.skipUnless((HOME / 'tools/wf-init.sh').exists(), '找不到 workflows 模板')
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.node = Path(self.tmp.name) / 'demo'

    def init_ok(self):
        result = run('init', self.node)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.node / '.wfnode-tmp').exists())
        return result.stdout

    def test_init_merges_existing_directories(self):
        before = {}
        for rel in ('.aos/x.json', '.claude/mine.md'):
            path = self.node / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'original bytes\n')
            before[rel] = path.read_bytes(), path.stat().st_mtime_ns
        self.init_ok()
        for rel, expected in before.items():
            path = self.node / rel
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), expected)
        self.assertTrue((self.node / '.claude/commands').is_dir())

    def test_init_recovers_missing_marker_and_tools(self):
        self.init_ok()
        (self.node / 'AGENTS.md').unlink()
        shutil.rmtree(self.node / 'wf/tools')
        self.init_ok()
        self.assertTrue((self.node / 'AGENTS.md').is_file())
        self.assertTrue((self.node / 'wf/tools/wf-lint.sh').is_file())

    def test_init_discards_stale_staging(self):
        stale = self.node / '.wfnode-tmp/垃圾'
        stale.parent.mkdir(parents=True)
        stale.write_text('residue')
        self.init_ok()

    def test_init_marker_published_last(self):
        original = wfnode.merge_missing
        def interrupt(source, dest):
            original(source, dest)
            if dest == self.node / 'wf':
                raise OSError('interrupted before marker')
        with patch.object(wfnode, 'merge_missing', interrupt):
            with self.assertRaises(OSError):
                wfnode.init(self.node)
        self.assertFalse((self.node / 'AGENTS.md').exists())
        self.assertFalse((self.node / '.wfnode-tmp').exists())
        self.init_ok()

    def test_real_oversize_warning_init_and_check(self):
        self.init_ok()
        (self.node / 'wf/workflows/large.md').write_text('# Large\n' + 'ordinary prose\n' * 600)
        index = self.node / 'wf/INDEX.md'
        index.write_text(index.read_text() + '\n[large](workflows/large.md)\n')
        for command in ('init', 'check'):
            result = run(command, self.node)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('OVERSIZE', result.stdout)
            self.assertRegex(result.stdout, r'oversize=[1-9]')

    def test_init_rejects_markdown_node_names(self):
        for name in ('a{{b}}', 'x[y]'):
            result = run('init', Path(self.tmp.name) / name)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn('node 名只能用一般字元', result.stderr)

    def test_init_quotes_next_step(self):
        self.node = Path(self.tmp.name) / 'my node'
        output = self.init_ok()
        step = next(line.split('下一步：', 1)[1] for line in output.splitlines() if line.startswith('下一步：'))
        self.assertEqual(shlex.split(step), ['aos7-wfnode', 'check', str(self.node)])


if __name__ == '__main__':
    unittest.main()
