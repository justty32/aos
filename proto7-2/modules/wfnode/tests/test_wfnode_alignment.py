"""W0 凍結項：預設骨架、strict 殘留、資料表與判斷處理。"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_wfnode import HOME, run, wfnode
import wfnode_judge


@unittest.skipUnless((HOME / 'tools/wf-init.sh').is_file(), '找不到 workflows 模板')
class AlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.seed = Path(cls.tmp.name) / 'demo'
        result = run('init', cls.seed)
        assert result.returncode == 0, result.stdout + result.stderr
        cls.kernel = Path(cls.tmp.name) / 'kernel'
        result = run('init', cls.kernel, '--flavor', '')
        assert result.returncode == 0, result.stdout + result.stderr

    def test_default_flavor_strict_and_tables(self):
        node = self.seed
        for rel in ('inbox/ROSTER.md', 'routines.md', 'dev-env.md'):
            self.assertTrue((node / 'wf/workflows' / rel).is_file(), rel)
        for path in wfnode.markdowns(node):
            for marker in ('{{', '〔模板說明〕', '〔導入判斷〕'):
                self.assertNotIn(marker, path.read_text(), str(path))
        result = subprocess.run(['bash', str(node / 'wf/tools/wf-lint.sh'), '--strict', str(node)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('[workflows/inbox/ROSTER.md](workflows/inbox/ROSTER.md)',
                      (node / 'wf/ROSTER.md').read_text())
        for name, columns in (('routines', ['name', 'every', 'inst', 'last_round', 'last_time', 'last_code']),
                              ('schedule', ['name', 'at', 'inst', 'claimed'])):
            text = (node / f'wf/{name}.json').read_text()
            self.assertEqual(json.loads(text), {'contract': 'wf-table/1',
                'source': f'workflows/{name}.md', 'extracted': dt.date.today().isoformat(),
                'columns': columns, 'rows': []})
            self.assertEqual(text, json.dumps(json.loads(text), indent=1, ensure_ascii=False) + '\n')
        routines = (node / 'wf/workflows/routines.md').read_text()
        self.assertNotIn('時機分區', routines)
        self.assertNotIn('（範例）', routines)
        self.assertNotIn('跨機 / 離線差異', (node / 'wf/workflows/dev-env.md').read_text())
        result = run('check', node)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_kernel_unknown_decision_fails_check(self):
        self.assertIn('## 現役成員\n\n（目前無）', (self.kernel / 'wf/ROSTER.md').read_text())
        self.assertFalse((self.kernel / 'wf/routines.json').exists())
        result = run('check', self.kernel)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('wf/WORKFLOWS.md:', result.stdout)
        self.assertIn('〔導入判斷〕', result.stdout)

    def test_default_rerun_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'demo'
            shutil.copytree(self.seed, node)
            def hashes():
                return {str(p.relative_to(node)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in node.rglob('*') if p.is_file()}
            before = hashes()
            result = run('init', node)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(before, hashes())

    def test_check_template_explanation_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'demo'
            shutil.copytree(self.seed, node)
            (node / 'extra.md').write_text('> 〔模板說明〕未清理\n')
            result = run('check', node)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn('extra.md:1:', result.stdout)

    def test_rerun_preserves_schedule_decision_and_user_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'demo'
            shutil.copytree(self.seed, node)
            path = node / 'wf/workflows/schedule.md'
            path.write_text('# schedule\n\n## 一次性時刻表（live）\n\n'
                            '| 2026-10-10 17:00 | 客戶備份 | agent | 自填 |\n\n'
                            + wfnode_judge.RULES['schedule.md'][0][1] + '\n')
            before = path.read_bytes()
            number = path.read_text().count('\n')
            result = run('init', node)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(path.read_bytes(), before)
            self.assertIn('要你決定：1 段', result.stdout)
            self.assertIn(f'wf/workflows/schedule.md:{number}', result.stdout)
            result = run('check', node)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn(f'wf/workflows/schedule.md:{number}:', result.stdout)

