"""工作流導入與續行點的端到端驗證。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE))
sys.dont_write_bytecode = True
import aos7_wfnode as wfnode

HOME = Path(os.environ.get('AOS7_WF_HOME', '~/repo/workflows')).expanduser()
SCRIPT = MODULE / 'aos7-wfnode'


def run(*args, **env):
    settings = os.environ.copy()
    settings.update(env)
    return subprocess.run([str(SCRIPT), *map(str, args)], env=settings,
                          capture_output=True, text=True)


@unittest.skipUnless(os.path.exists(HOME / 'tools/wf-init.sh'), '找不到 workflows 模板')
class NodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_tmp = tempfile.TemporaryDirectory()
        cls.seed = Path(cls.seed_tmp.name) / 'demo'
        result = run('init', cls.seed)
        if result.returncode:
            cls.seed_tmp.cleanup()
            raise AssertionError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.seed_tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.node = Path(self.tmp.name) / 'demo'
        shutil.copytree(self.seed, self.node)

    def ok(self, result, code=0):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result.stdout

    def clean(self):
        for path in wfnode.markdowns(self.node):
            text = path.read_text()
            self.assertNotIn('{{', text, str(path))
            self.assertNotIn('〔模板說明〕', text, str(path))
        result = subprocess.run(['bash', str(self.node / 'wf/tools/wf-lint.sh'), str(self.node)],
                                text=True, capture_output=True)
        self.ok(result)
        self.assertIn('TOTAL broken=0', result.stdout)

    def test_init_plain(self):
        self.clean()
        for rel in ('handoffs/NEXT-SESSION.md', 'ROSTER.md', 'line-claims.json'):
            self.assertTrue((self.node / 'wf' / rel).is_file())
        table = json.loads((self.node / 'wf/line-claims.json').read_text())
        self.assertEqual(table['contract'], 'wf-table/1')
        self.assertEqual(table['rows'], [])
        self.assertIn(self.node.name, (self.node / 'AGENTS.md').read_text())
        self.assertIn('不 commit main', (self.node / 'wf/workflows/common/user.md').read_text())
        index = (self.node / 'wf/INDEX.md').read_text()
        self.assertIn('[NEXT-SESSION](handoffs/NEXT-SESSION.md)', index)
        self.assertIn('[ROSTER](ROSTER.md)', index)

    def test_init_flavors(self):
        self.node = Path(self.tmp.name) / 'flavored'
        self.ok(run('init', self.node, '--flavor', 'heartbeat,multi-agent,dev'))
        self.clean()

    def test_rerun_preserves_bytes_and_mtime(self):
        for rel, extra in [('AGENTS.md', '\n使用者自己的註記\n'),
                           ('wf/SESSION-LOG.md', '\n- [dev] 寫 X → 跑測試\n')]:
            with (self.node / rel).open('a') as stream:
                stream.write(extra)
        (self.node / 'wf/ROSTER.md').unlink()
        before = {str(p.relative_to(self.node)): (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.node.rglob('*') if p.is_file()}
        output = self.ok(run('init', self.node))
        self.assertIn('已導入過，只補缺檔', output)
        after = {str(p.relative_to(self.node)): (p.read_bytes(), p.stat().st_mtime_ns)
                 for p in self.node.rglob('*') if p.is_file() and p != self.node / 'wf/ROSTER.md'}
        self.assertEqual(before, after)
        self.assertTrue((self.node / 'wf/ROSTER.md').exists())

    def test_rerun_finishes_interrupted_fill(self):
        agents = self.node / 'AGENTS.md'
        agents.write_text(agents.read_text().replace(self.node.name, '{{專案名}}', 1))
        user = self.node / 'wf/workflows/common/user.md'
        before = user.read_bytes(), user.stat().st_mtime_ns
        self.ok(run('init', self.node))
        self.assertNotIn('{{', agents.read_text())
        self.assertEqual((user.read_bytes(), user.stat().st_mtime_ns), before)

    def test_check_open_and_finished(self):
        self.ok(run('check', self.node))
        log = self.node / 'wf/SESSION-LOG.md'
        with log.open('a') as stream:
            stream.write('\n- [dev] 寫 X → 跑測試\n')
        self.assertIn('AI 手上 1 件', self.ok(run('check', self.node)))
        with log.open('a') as stream:
            stream.write('- [dev] 寫 Y ✅ 已完成\n')
        number = len(log.read_text().splitlines())
        output = self.ok(run('check', self.node), 1)
        self.assertIn(f'SESSION-LOG.md:{number}: - [dev] 寫 Y ✅ 已完成', output)
        shutil.copyfile(self.seed / 'wf/SESSION-LOG.md', log)
        wait = self.node / 'wf/WAIT_USER.md'
        with wait.open('a') as stream:
            stream.write('\n- [x] 請使用者裝 Z\n')
        number = len(wait.read_text().splitlines())
        output = self.ok(run('check', self.node), 1)
        self.assertIn(f'WAIT_USER.md:{number}: - [x] 請使用者裝 Z', output)
        self.assertIn('做完就刪掉這行', output)

    def test_check_broken_and_placeholder(self):
        index = self.node / 'wf/INDEX.md'
        with index.open('a') as stream:
            stream.write('\n[a](nope.md)\n')
        self.assertIn('BROKEN', self.ok(run('check', self.node), 1))
        shutil.copyfile(self.seed / 'wf/INDEX.md', index)
        (self.node / 'extra.md').write_text('{{還沒填}}\n')
        self.assertIn('extra.md:1:', self.ok(run('check', self.node), 1))

    def test_state_append_and_day_change(self):
        for line in ('寫完第一版', '下一步跑測試'):
            self.ok(run('state', self.node, line, AOS7_WFNODE_NOW='2026-10-09T15:30'))
        text = (self.node / 'wf/handoffs/2026-10-09/STATE.md').read_text()
        self.assertTrue(text.endswith('- 15:30 寫完第一版\n- 15:30 下一步跑測試\n'))
        next_file = self.node / 'wf/handoffs/NEXT-SESSION.md'
        link = '> 最新：[2026-10-09/STATE.md](2026-10-09/STATE.md)'
        self.assertEqual(next_file.read_text().splitlines().count(link), 1)
        self.ok(run('state', self.node, '繼續做', AOS7_WFNODE_NOW='2026-10-10T09:00'))
        text = next_file.read_text()
        self.assertEqual(text.count('> 最新：'), 1)
        self.assertIn('> 最新：[2026-10-10/STATE.md](2026-10-10/STATE.md)', text)
        self.assertNotIn(link, text)
        self.ok(run('check', self.node))
        self.ok(run('state', self.node, ''), 2)
        self.ok(run('state', self.node, '兩\n行'), 2)

    def test_state_without_line_shows_latest(self):
        self.assertIn('還沒記過', self.ok(run('state', self.node)))
        self.ok(run('state', self.node, '寫完第一版', AOS7_WFNODE_NOW='2026-10-09T15:30'))
        output = self.ok(run('state', self.node))
        self.assertIn('2026-10-09/STATE.md', output)
        self.assertIn('- 15:30 寫完第一版', output)

    def test_state_preserves_next_content(self):
        path = self.node / 'wf/handoffs/NEXT-SESSION.md'
        for text in ('# 自訂標題\n保留其他內容\n', '# 自訂標題\n\n（尚無）\n保留其他內容\n'):
            path.write_text(text)
            self.ok(run('state', self.node, '記進度', AOS7_WFNODE_NOW='2026-10-09T15:30'))
            self.assertIn('保留其他內容\n', path.read_text())
            self.assertEqual(path.read_text().count('> 最新：'), 1)

    def test_missing_init_and_template(self):
        empty = Path(self.tmp.name) / 'empty'
        empty.mkdir()
        self.assertIn('還沒 init', self.ok(run('check', empty), 2))
        self.ok(run('state', empty, '未導入'), 2)
        result = run('init', empty, AOS7_WF_HOME=str(empty / 'missing'))
        self.ok(result, 2)
        self.assertIn('AOS7_WF_HOME', result.stderr)

    def test_usage_errors(self):
        self.ok(run(), 2)
        self.ok(run('unknown'), 2)
        self.ok(run('check', self.node, '--json'), 2)
        self.ok(run('-h'))


if __name__ == '__main__':
    unittest.main()
