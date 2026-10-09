"""統一錯誤的一行訊息與退出碼。"""
import contextlib
import io
import json
import sys
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import test_up as cases
import aos7_up as up
import aos7_up_cli as cli
import aos7_up_status as view


class UpErrors(unittest.TestCase):
    def setUp(self):
        # cli.main 會換掉 SIGINT／SIGTERM 處理；測完還原，別留在測試程序裡
        for sig in (signal.SIGINT, signal.SIGTERM):
            self.addCleanup(signal.signal, sig, signal.getsignal(sig))

    def test_child_failure_summary(self):
        for rc, expected in ((1, 1), (2, 1), (3, 3), (4, 1)):
            result = subprocess.CompletedProcess([], rc, '', '長說明\n最後原因\n')
            with patch.object(up, 'call', return_value=result):
                with self.assertRaises(view.UpError) as err:
                    up.run('bin/aos7-ctl', 'add')
            self.assertEqual(err.exception.code, expected)
            self.assertIn('最後原因', str(err.exception))
            self.assertNotIn('長說明', str(err.exception))
            if rc == 3:
                self.assertTrue(str(err.exception).startswith('不確定：'))

    def test_oserror_one_line(self):
        with patch.object(cli, 'up', side_effect=OSError('讀檔\n故障')), \
             contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.main(['/tmp/aos/bob']), 3)
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertTrue(err.getvalue().startswith('aos7-up: 不確定：'))
        self.assertIn('留著', err.getvalue())
        self.assertIn('再跑', err.getvalue())

    def test_stop_timeout(self):
        with patch.object(up, 'alive', return_value=True), \
             patch.object(up, 'run'), \
             patch.object(up.time, 'monotonic', side_effect=[0, 31]), \
             contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.main(['stop', '/tmp/aos/bob']), 3)
        self.assertIn('30 秒還沒停', err.getvalue())
        self.assertEqual(len(err.getvalue().splitlines()), 1)

    def test_bad_name_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('.bob', 'you', 'bad name'):
                node = Path(tmp) / name
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    self.assertEqual(cli.main([str(node), '-d']), 2)
                self.assertFalse(node.exists())
                self.assertEqual(len(err.getvalue().splitlines()), 1)


class InterfaceTests(unittest.TestCase):
    setUp = UpErrors.setUp

    def invoke(self, args):
        return subprocess.run([sys.executable, '-B', str(cases.UP), *args],
                              capture_output=True, text=True, timeout=10)

    def test_help_everywhere(self):
        expected = """用法：
  aos7-up <node>                起 node；開著別關，停＝按 Ctrl-C
  aos7-up ask <node> '一句話'    另開視窗寄信給它，等回信（最多 60 秒）
  aos7-up status <node>         看它現在怎樣
例：aos7-up /tmp/aos/bob
更多（真 AI、背景跑、停）見 proto7-2/modules/up/ADVANCED.md
"""
        for args in (['--help'], ['-h'], ['ask', '--help'], ['status', '--help'],
                     ['stop', '--help'], ['brain', '--help'],
                     ['ask', '/missing', 'test', '--bad', '-h']):
            with self.subTest(args=args):
                p = self.invoke(args)
                self.assertEqual((p.returncode, p.stdout, p.stderr), (0, expected, ''))
                self.assertLessEqual(len(p.stdout.splitlines()), 8)
                for word in ('stop', '-d', '--model', '退出', 'DONE', 'BLOCKED', 'token',
                             '帳', '回合', '預留', 'ack', 'daemon', 'tick'):
                    self.assertNotIn(word, p.stdout)

    def test_bad_arguments_all_commands(self):
        for args in ([], ['--bad'], ['ask'], ['ask', 'bob', 'test', '--wait', 'bad'],
                     ['brain'], ['brain', 'bob', '--bad'], ['status'], ['stop']):
            with self.subTest(args=args):
                p = self.invoke(args)
                self.assertEqual(p.returncode, 2)
                self.assertEqual(p.stdout, '')
                self.assertEqual(len(p.stderr.splitlines()), 1)
                self.assertTrue(p.stderr.startswith('aos7-up: '))
                self.assertIn('。例如 aos7-up', p.stderr)
                self.assertNotIn('usage:', p.stderr)
                self.assertNotIn('Traceback', p.stderr)

    def test_cleanup_shared_and_mixed_house(self):
        with tempfile.TemporaryDirectory() as tmp:
            house = Path(tmp)
            node = house / 'bob'
            (node / '.aos').mkdir(parents=True)
            (node / '.aos/up.json').write_text('{}')
            (house / 'you').mkdir()
            (house / '.aosd').mkdir()
            self.assertEqual(view.cleanup_hint(node), f'要收掉：刪掉整個資料夾：rm -r {house}')
            with patch.object(view, 'alive', return_value=True):
                self.assertEqual(view.cleanup_hint(node),
                                 f'要收掉：先在視窗 1 按 Ctrl-C 停心跳，再刪掉整個資料夾：rm -r {house}')
            (house / 'other.txt').write_text('保留')
            hint = view.cleanup_hint(node)
            self.assertEqual(hint.split('rm -r ')[1], f'{node} {house}/you {house}/.aosd')
            second = house / 'alice'
            (second / '.aos').mkdir(parents=True)
            (second / '.aos/up.json').write_text('{}')
            self.assertEqual(view.cleanup_hint(node), f'要收掉：刪掉這幾個資料夾：rm -r {node}')
            (house / 'other.txt').unlink()
            self.assertEqual(view.cleanup_hint(node), f'要收掉：刪掉整個資料夾：rm -r {house}')
            # 不是 up 起的 node（只有 .aos/、沒有 up.json）也在用 you 與 .aosd：不整屋、也不刪共用
            (second / '.aos/up.json').unlink()
            self.assertEqual(view.cleanup_hint(node).split('rm -r ')[1], str(node))

    def test_plain_state_line(self):
        ident = 'you-20261009T195030-18814f9c0220'
        titles = {ident: '幫我寫一首短詩', 'you-20261009T195030-aaaaaaaaaaaa': '一二三四五六七八九十一二三四五六七八九十一二三四五六七八九十'}
        for raw, wanted in ((f'- 16:51 回了 {ident}', '回了「幫我寫一首短詩」'),
                            (f'- 19:51 卡住：問 AI 那筆一直不確定（call {ident}）',
                             '卡住：問 AI 那筆一直不確定（「幫我寫一首短詩」）'),
                            # 現在 brain 寫的卡住行本身就白話，原樣顯示
                            ('- 19:51 卡住：「幫我寫一首短詩」問 AI 時被打斷', '卡住：「幫我寫一首短詩」問 AI 時被打斷'),
                            (f'- 第 2 回合 {ident}-s2：第 2 回合，下一步第 3 回合',
                             '第 2 步「幫我寫一首短詩」：第 2 步，下一步第 3 步'),
                            ('- 10:00 回了 bob-20261009T195030-bbbbbbbbbbbb', '回了一封信'),
                            ('- 回了 you-20261009T195030-aaaaaaaaaaaa', '回了「一二三四五六七八九十一二三四五六七八九十一二三四…」'),
                            ('下一步測試', '下一步測試'), ('- ', '還沒開始')):
            with self.subTest(raw=raw):
                self.assertEqual(view.plain(raw, titles), wanted)

    def test_watch_heartbeat_stopped_elsewhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'bob'
            node.mkdir()
            daemon = subprocess.Popen(['true'])
            daemon.wait()
            for n, wanted in ((3, f'心跳被別處停掉了（例如跑了 stop）；檔案都留著，再跑 aos7-up {node} 就接上'),
                              (0, f'心跳沒跑起來。請看 {tmp}/.aosd/up-daemon.log 後重跑')):
                with patch.object(view, 'number', return_value=n), \
                     contextlib.redirect_stdout(io.StringIO()), \
                     self.assertRaises(view.UpError) as caught:
                    view.watch(node, daemon)
                self.assertEqual(str(caught.exception), wanted)

    def test_status_checkup_only_when_broken(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'bob'
            (node / '.aos').mkdir(parents=True)
            cfg = dict(v=1, node=str(node), house=tmp, name='bob', you='you', mail_root=tmp,
                       model=None, litellm_url='', budget='budget/llm', holder='brain', gateway='llm.fake')
            (node / '.aos/up.json').write_text(json.dumps(cfg))
            for rc in (0, 1):
                with patch.object(view, 'call', return_value=subprocess.CompletedProcess([], rc, '{}')), \
                     contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(view.status(node), 0)
                lines = out.getvalue().splitlines()
                self.assertEqual(lines[2], '工作簿：最後記下：還沒開始' +
                                 (f'；工作簿有地方寫壞了（看哪裡：aos7-wfnode check {node}）' if rc else ''))
                self.assertEqual(lines[4], 'AI：假 AI（不連網、不花錢，照抄你的信回你）；bob 一共問過 AI 0 次')
                self.assertNotIn('體檢', out.getvalue())
            (node / 'wf').mkdir()
            (node / 'wf/SESSION-LOG.md').write_text('## open\n- 寫報告\n- 改錯字\n')
            with patch.object(view, 'call', return_value=subprocess.CompletedProcess([], 0, '{}')), \
                 contextlib.redirect_stdout(io.StringIO()) as out:
                view.status(node)
            self.assertEqual(out.getvalue().splitlines()[2], '工作簿：最後記下：還沒開始；還有 2 件事沒做完')

    def test_config_read_failure_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'bob'
            (node / '.aos').mkdir(parents=True)
            (node / '.aos/up.json').write_text('{}')
            before = sorted(node.rglob('*'))
            for args in (['status', str(node)], [str(node)]):
                with patch.object(Path, 'read_text', side_effect=PermissionError('private')), \
                     contextlib.redirect_stderr(io.StringIO()) as err, \
                     contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(cli.main(args), 3)
                self.assertEqual(out.getvalue(), '')
                self.assertEqual(err.getvalue(), f'aos7-up: 不確定：讀不到 {node}/.aos/up.json，什麼都沒改。確認讀得到後照原樣再跑一次\n')
                self.assertEqual(before, sorted(node.rglob('*')))

    def test_status_unknown_usage_and_readonly(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'bob'
            (node / '.aos').mkdir(parents=True)
            cfg = dict(v=1, node=str(node), house=tmp, name='bob', you='you', mail_root=tmp,
                       model='m1', litellm_url='', budget='budget/llm', holder='brain', gateway='llm.litellm')
            (node / '.aos/up.json').write_text(json.dumps(cfg))
            before = {p: p.read_bytes() for p in node.rglob('*') if p.is_file()}
            for rc, content, wanted in ((3, '', 'AI：m1；bob 一共問過 AI 0 次，用了多少字不明'),
                                         (0, '{}', 'AI：m1；bob 一共問過 AI 0 次，用了多少字不明'),
                                         (0, 'bad', '用了多少字不明'), (0, '[1]', '用了多少字不明'),
                                         (0, '{"used":1104}', 'AI：m1；bob 一共問過 AI 0 次，AI 讀加寫共約 1104 字（真 AI 照字數收錢）')):
                with patch.object(view, 'call', return_value=subprocess.CompletedProcess([], rc, content)), \
                     contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(view.status(node), 0)
                self.assertIn(wanted, out.getvalue())
                self.assertNotIn('token', out.getvalue())
                self.assertEqual(out.getvalue().splitlines()[-1], view.cleanup_hint(node))
            self.assertEqual(before, {p: p.read_bytes() for p in node.rglob('*') if p.is_file()})
            self.assertFalse((node.parent / '.aosd').exists())

    def test_stop_uses_same_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'bob'
            (node / '.aos').mkdir(parents=True)
            (node / '.aos/up.json').write_text('{}')
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(up.stop(node), 0)
            self.assertEqual(out.getvalue().splitlines()[-1], view.cleanup_hint(node))
