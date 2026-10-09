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
        result = run('check', empty)
        self.ok(result, 2)
        self.assertIn('還沒 init', result.stderr)
        self.ok(run('state', empty, '未導入'), 2)
        result = run('init', empty, AOS7_WF_HOME=str(empty / 'missing'))
        self.ok(result, 2)
        self.assertIn('AOS7_WF_HOME', result.stderr)

    def error(self, result, code):
        self.ok(result, code)
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 1, result.stderr)  # 人看的只有一行
        last = lines[0]
        self.assertTrue(last.startswith('aos7-wfnode: '), result.stderr)
        self.assertIn('。', last)
        if code == 3:
            self.assertTrue(last.startswith('aos7-wfnode: 不確定：'), last)
        return last

    def test_error_missing_init(self):
        node = Path(self.tmp.name) / 'not initialized'
        for args in (('check', node), ('state', node, '進度')):
            with self.subTest(command=args[0]):
                last = self.error(run(*args), 2)
                self.assertIn('還沒 init', last)
                self.assertIn(f"init '{node}'", last)
                self.assertFalse(node.exists())

    def test_error_invalid_state_line(self):
        before = sorted(p.relative_to(self.node) for p in self.node.rglob('*'))
        for line in ('', '  ', '兩\n行', '兩\r行'):
            with self.subTest(line=line):
                self.assertIn('進度要一行非空文字', self.error(run('state', self.node, line), 2))
        self.assertEqual(before, sorted(p.relative_to(self.node) for p in self.node.rglob('*')))

    def test_error_invalid_now(self):
        for now in ('yesterday', '2026-13-40T99:99', '2026-02-30T15:30'):
            with self.subTest(now=now):
                last = self.error(run('state', self.node, '進度', AOS7_WFNODE_NOW=now), 2)
                self.assertIn('AOS7_WFNODE_NOW 格式不對', last)
        self.assertFalse((self.node / 'wf/handoffs/.state.lock').exists())

    def test_error_missing_template(self):
        node = Path(self.tmp.name) / 'new'
        last = self.error(run('init', node, AOS7_WF_HOME=str(node / 'missing')), 2)
        self.assertIn('AOS7_WF_HOME', last)
        self.assertFalse(node.exists())

    def test_error_invalid_node_name(self):
        node = Path(self.tmp.name) / 'bad[name]'
        self.assertIn('node 名只能用一般字元', self.error(run('init', node), 2))
        self.assertFalse(node.exists())

    def test_error_check_failed(self):
        (self.node / 'extra.md').write_text('{{沒填}}\n')
        result = run('check', self.node)
        self.assertIn('體檢沒過', self.error(result, 1))
        self.assertIn('extra.md:1:', result.stdout)
        self.assertNotIn('OK：', result.stdout)

    def test_success_stderr_empty(self):
        for args in (('init', self.node), ('state', self.node, '進度'), ('check', self.node)):
            with self.subTest(command=args[0]):
                result = run(*args)
                self.ok(result)
                self.assertEqual(result.stderr, '')

    def test_error_lint_unknown(self):
        (self.node / 'wf/tools/wf-lint.sh').write_text('echo boom; exit 2\n')
        result = run('check', self.node)
        self.error(result, 3)
        self.assertIn('boom', result.stdout)
        self.assertNotIn('OK：', result.stdout)

    def test_error_known_failure_over_unknown(self):
        (self.node / 'wf/tools/wf-lint.sh').write_text('echo boom; exit 2\n')
        with (self.node / 'wf/SESSION-LOG.md').open('a') as stream:
            stream.write('\n- [x] 做完没刪\n')
        result = run('check', self.node)
        self.assertIn('體檢沒過', self.error(result, 1))
        self.assertIn('做完就刪掉這行', result.stdout)

    @unittest.skipIf(os.geteuid() == 0, 'root 不受目錄寫入權限限制')
    def test_error_oserror(self):
        handoffs = self.node / 'wf/handoffs'
        mode = handoffs.stat().st_mode & 0o777
        handoffs.chmod(0o500)
        try:
            result = run('state', self.node, '進度')
            self.assertTrue(result.stderr.startswith('aos7-wfnode: 不確定：'), result.stderr)
            last = self.error(result, 3)
            self.assertIn('讀寫檔案出錯', last)
            self.assertIn('先跑 aos7-wfnode state', last)  # 可能已記上，先看再重記
        finally:
            handoffs.chmod(mode)

    def test_error_invalid_utf8(self):
        (self.node / 'extra.md').write_bytes(b'\xff')
        self.assertIn('讀寫檔案出錯', self.error(run('check', self.node), 3))

    def test_error_bad_flavor(self):
        node = Path(self.tmp.name) / 'parent/fresh'
        result = run('init', node, '--flavor', 'no-such-flavor')
        self.assertIn('--flavor', self.error(result, 2))
        self.assertFalse(node.exists())

    def test_error_line_break_in_path(self):
        node = Path(self.tmp.name) / 'a\nb'
        self.assertIn('還沒 init', self.error(run('check', node), 2))

    def test_error_bad_argument(self):
        self.assertIn('init／state／check', self.error(run('bogus'), 2))

    def test_error_init_script_failed(self):
        home = Path(self.tmp.name) / 'template'
        (home / 'tools').mkdir(parents=True)
        (home / 'tools/wf-init.sh').write_text('printf script-error >&2; exit 7\n')
        node = Path(self.tmp.name) / 'new'
        result = run('init', node, AOS7_WF_HOME=str(home))
        last = self.error(result, 1)
        self.assertIn('退出碼 7', last)
        self.assertIn('script-error', result.stdout)
        self.assertFalse(node.exists())

    def test_error_init_lint_verdicts(self):
        tool = self.node / 'wf/tools/wf-lint.sh'
        for script, code, message in (
                ('echo boom; exit 2', 3, '檔案裝好了，但連結檢查沒跑完'),
                ('echo BROKEN; echo "TOTAL broken=1"; exit 1', 1, '裝好了但有壞連結')):
            with self.subTest(code=code):
                tool.write_text(script + '\n')
                self.assertIn(message, self.error(run('init', self.node), code))

    def test_error_init_residue(self):
        (self.node / 'extra.md').write_text('{{未關閉\n')
        result = run('init', self.node)
        self.assertIn('還有 1 處 {{ 沒填好', self.error(result, 1))
        self.assertIn('還有 1 處 {{ 沒填好', result.stdout)

    def test_usage_errors(self):
        self.error(run(), 2)
        self.error(run('unknown'), 2)
        self.error(run('check', self.node, '--json'), 2)
        self.ok(run('-h'))


class SourceTests(unittest.TestCase):
    def test_no_legacy_error_phrase(self):
        phrase = ''.join(map(chr, (0x7121, 0x6cd5, 0x5b8c, 0x6210)))
        sources = [MODULE / 'aos7-wfnode', *MODULE.rglob('*.py')]
        for path in sources:
            with self.subTest(path=path.name):
                self.assertNotIn(phrase, path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
