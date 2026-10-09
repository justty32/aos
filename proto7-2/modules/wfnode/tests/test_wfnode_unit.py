"""填寫、原子發佈、NEXT 插入與確定性並發驗證。"""
import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE))
import aos7_wfnode as wfnode
import wfnode_fill
import wfnode_state
SCRIPT = MODULE / 'aos7-wfnode'


class FillTests(unittest.TestCase):
    def test_known_unknown_and_blocks(self):
        text = ('前文 {{專案名}}\n\n> 先說\n> 〔模板說明〕第一段\n> 後說\n\n'
                '中間 {{奇怪的東西}}\n\n> 〔模板說明〕第二段\n\n'
                '> 〔導入判斷〕保留\n\n後文\n')
        result = wfnode.fill_text(text, 'demo')
        self.assertNotIn('{{', result)
        self.assertNotIn('〔模板說明〕', result)
        self.assertIn('（未定：奇怪的東西）', result)
        self.assertEqual(result, '前文 demo\n\n中間 （未定：奇怪的東西）\n\n'
                                '> 〔導入判斷〕保留\n\n後文\n')


class UnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.node = Path(self.tmp.name) / 'demo'
        tool = self.node / 'wf/tools/wf-lint.sh'
        tool.parent.mkdir(parents=True)
        tool.touch()
        self.env = patch.dict(os.environ, AOS7_WFNODE_NOW='2026-10-09T15:30')
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_state_concurrent_keeps_every_line(self):
        env = dict(os.environ, AOS7_WFNODE_NOW='2026-10-09T15:30')
        procs = [subprocess.Popen([str(SCRIPT), 'state', str(self.node), f'第 {i} 行'], env=env,
                                  stdout=subprocess.DEVNULL) for i in range(8)]
        self.assertEqual([p.wait() for p in procs], [0] * 8)
        text = (self.node / 'wf/handoffs/2026-10-09/STATE.md').read_text()
        self.assertEqual(sorted(l for l in text.splitlines() if l.startswith('- ')),
                         sorted(f'- 15:30 第 {i} 行' for i in range(8)))

    def test_state_first_open_serialized(self):
        opened, release, second_started, second_done = (threading.Event() for _ in range(4))
        errors = []
        def hook():
            if threading.current_thread().name == 'first':
                opened.set()
                if not release.wait(5):
                    raise AssertionError('first caller never released')
        def call(line):
            try:
                if line == 'second':
                    second_started.set()
                self.assertEqual(wfnode.state(self.node, line), 0)
            except BaseException as error:
                errors.append(error)
            finally:
                if line == 'second':
                    second_done.set()
        with patch.object(wfnode_state, '_after_open', hook):
            first = threading.Thread(target=call, args=('first',), name='first')
            second = threading.Thread(target=call, args=('second',), name='second')
            first.start()
            try:
                self.assertTrue(opened.wait(5))
                second.start()
                self.assertTrue(second_started.wait(5))
                blocked = not second_done.wait(.2)
            finally:
                release.set()
                first.join(5)
                if second.ident is not None:
                    second.join(5)
        self.assertTrue(blocked, 'second caller bypassed the state lock')
        self.assertEqual(errors, [])
        text = (self.node / 'wf/handoffs/2026-10-09/STATE.md').read_text()
        self.assertEqual(text.count('# 續行點'), 1)
        self.assertIn('- 15:30 first\n', text)
        self.assertIn('- 15:30 second\n', text)

    def test_supplement_interrupted_publish(self):
        real = wfnode.tempfile.NamedTemporaryFile
        for rel in ('handoffs/NEXT-SESSION.md', 'ROSTER.md', 'line-claims.json'):
            with self.subTest(rel=rel):
                wfnode.supplement(self.node)
                dest = self.node / 'wf' / rel
                expected = dest.read_text()
                dest.unlink()
                def broken(**kwargs):
                    stream = real(**kwargs)
                    def write(content):
                        if content == expected:
                            stream.file.write(content[:4])
                            raise OSError('interrupted write')
                        return stream.file.write(content)
                    stream.write = write
                    return stream
                real_open = Path.open
                def broken_open(path, mode='r', *args, **kwargs):
                    stream = real_open(path, mode, *args, **kwargs)
                    if mode == 'x':
                        def write(content):
                            stream.write_original(content[:4])
                            raise OSError('interrupted write')
                        stream.write_original = stream.write
                        stream.write = write
                    return stream
                with patch.object(wfnode.tempfile, 'NamedTemporaryFile', broken), \
                        patch.object(Path, 'open', broken_open):
                    with self.assertRaises(OSError):
                        wfnode.supplement(self.node)
                self.assertFalse(dest.exists())
                self.assertEqual(list((self.node / 'wf').rglob('.wfnode-*')), [])
                wfnode.supplement(self.node)
                content = dest.read_text()
                if rel.endswith('.json'):
                    self.assertEqual(json.loads(content)['rows'], [])
                else:
                    self.assertEqual(content, wfnode.NEXT if 'NEXT' in rel else wfnode.ROSTER)

    def test_next_missing_newline_and_prefix(self):
        path = self.node / 'wf/handoffs/NEXT-SESSION.md'
        path.parent.mkdir(parents=True)
        for text in ('# 自訂標題', '前面其他內容\n# 自訂標題', ''):
            with self.subTest(text=text):
                path.write_text(text)
                for _ in range(2):
                    self.assertEqual(wfnode.state(self.node, '記進度'), 0)
                result = path.read_text()
                self.assertEqual(result.count('> 最新：'), 1)
                self.assertEqual(sum(line.startswith('> 最新：') for line in result.splitlines()), 1)
                if text:
                    for line in text.splitlines():
                        self.assertIn(line, result.splitlines())
                else:
                    self.assertIn('下一次開場先讀', result)

    def test_fill_quotes_verification_path(self):
        with patch.object(wfnode_fill, '__file__', '/tmp/my repo/modules/wfnode/wfnode_fill.py'):
            text = wfnode.fill_text('{{測試 / build / lint 指令}}', 'demo')
        self.assertEqual(shlex.split(text.strip('`')), ['python3', '/tmp/my repo/tests/run_all.py'])

    def test_lint_warnings_init_and_check(self):
        (self.node / 'AGENTS.md').write_text('# demo\n')
        for key in ('oversize', 'biglist', 'biglist_links', 'querycmd'):
            output = f'OVERSIZE detail\nSUMMARY wf: {key}=1\nTOTAL broken=0\n'
            fake = subprocess.CompletedProcess([], 0, output, '')
            for command in (wfnode.init, wfnode.check):
                with self.subTest(key=key, command=command.__name__):
                    capture = io.StringIO()
                    with patch.object(wfnode.subprocess, 'run', return_value=fake), contextlib.redirect_stdout(capture):
                        self.assertEqual(command(self.node), 0)
                    self.assertIn(output, capture.getvalue())


if __name__ == '__main__':
    unittest.main()
