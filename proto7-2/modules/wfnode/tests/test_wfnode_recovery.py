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
import wfnode_judge


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


class JudgeTests(unittest.TestCase):
    def judge(self, filename, text, guide=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'workflows' / filename
            path.parent.mkdir()
            path.write_text(text)
            extra = root / 'GUIDE.md'
            if guide is not None:
                extra.write_text(guide)
            handled = wfnode_judge.resolve(root)
            return path.read_text(), handled, extra.read_text() if guide is not None else None

    def test_known_rules_only_change_target_section(self):
        for filename, rules in wfnode_judge.RULES.items():
            for heading, block, action, body in rules:
                with self.subTest(filename=filename, heading=heading):
                    section = heading + '\n\n' + block + '\n\n舊表\n\n'
                    before, after = '# title\n前段原樣\n', '## 交接\n後段原樣\n'
                    result, handled, _ = self.judge(filename, before + section + after)
                    expected = (heading + '\n\n\n舊表\n\n' if action == 'block' else
                                '' if action == 'delete' else heading + '\n\n' + body + '\n')
                    self.assertEqual(result, before + expected + after)
                    self.assertEqual(len(handled), 1)

    def test_changed_decision_preserves_section(self):
        text = ('## 跨機 / 離線差異\n\n自填表\n\n'
                '> 〔導入判斷〕並非只有單一開發環境，請保留此表\n')
        result, handled, _ = self.judge('dev-env.md', text)
        self.assertEqual(result, text)
        self.assertEqual(handled, [])

    def test_mixed_quote_preserves_section(self):
        for filename, rules in wfnode_judge.RULES.items():
            for heading, block, _, _ in rules:
                with self.subTest(filename=filename, heading=heading):
                    text = heading + '\n\n' + block + '\n> 〔導入判斷〕別的事\n\n自填表\n'
                    result, handled, _ = self.judge(filename, text)
                    self.assertEqual(result, text)
                    self.assertEqual(handled, [])

    def test_separate_unknown_preserves_entire_section(self):
        for filename, rules in wfnode_judge.RULES.items():
            for heading, block, action, _ in rules:
                with self.subTest(filename=filename, action=action, heading=heading):
                    text = heading + '\n\n' + block + '\n\n自填表\n\n> 〔導入判斷〕別的事\n'
                    result, handled, _ = self.judge(filename, text)
                    self.assertEqual(result, text)
                    self.assertEqual(handled, [])

    def test_anchor_only_replaces_matching_destination(self):
        heading, block, _, _ = wfnode_judge.RULES['routines.md'][0]
        text = heading + '\n\n' + block + '\n'
        guide = ('前文 [a](routines.md#時機分區（live-清單隨時增--改--刪）) '
                 '中間 [b](x.md) 後文\n[c](other.md#時機分區)\n'
                 '[d](#時機分區live) [e](workflows/routines.md#時機分區live)\n')
        _, _, result = self.judge('routines.md', text, guide)
        self.assertEqual(result, '前文 [a](routines.json) 中間 [b](x.md) 後文\n'
                         '[c](other.md#時機分區)\n[d](routines.json) [e](routines.json)\n')

    def test_custom_flow_line_preserved(self):
        heading, block, _, _ = wfnode_judge.RULES['routines.md'][0]
        for line in ('- **登記**：自訂時機分區內容', '2. 固定時機自訂時機分區內容',
                     '2. **對照清單**：自訂時機分區內容'):
            with self.subTest(line=line):
                text = '## 流程\n\n' + line + '\n\n' + heading + '\n\n' + block + '\n'
                result, _, _ = self.judge('routines.md', text)
                self.assertEqual(result, '## 流程\n\n' + line + '\n\n')


if __name__ == '__main__':
    unittest.main()
