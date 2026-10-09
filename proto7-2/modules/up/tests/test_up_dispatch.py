"""分派、信件觀看及前景訊號邊界。"""
import contextlib
import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from base import DaemonCase
import _proc
import test_up as cases

sys.path.insert(0, str(cases.UP.parent))
import aos7_up as up
import aos7_up_status as view
import aos7_up_cli as cli


class UpDispatch(unittest.TestCase):
    """〔up〕凍結的 exec 分派與只讀事件顯示。"""
    def test_brain_forwarding(self):
        import aos7_up_brain
        for sub in ('ask', 'brain'):
            with patch.object(aos7_up_brain, 'main', return_value=5) as forward:
                self.assertEqual(up.main([sub, '/tmp/bob', '一句話', '--wait', '7']), 5)
            forward.assert_called_once_with([sub, '/tmp/bob', '一句話', '--wait', '7'])

    def test_failed_start_reaps_daemon(self):
        child = subprocess.Popen(['python3', '-B', '-c', 'import time; time.sleep(60)'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'bob'
            (Path(tmp) / '.aosd').mkdir()
            try:
                with patch.object(up, 'prepare', return_value={'model': None}), \
                     patch.object(up, 'alive', return_value=False), \
                     patch.object(up.subprocess, 'Popen', return_value=child), \
                     patch.object(up.time, 'monotonic', side_effect=[0, 11]):
                    with self.assertRaises(view.UpError) as error:
                        up.up(node, None, True)
                self.assertEqual(error.exception.code, 1)
                self.assertIsNotNone(child.poll())
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait()

    def test_watch_events(self):
        def letter(path, status, extra=''):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'---\nstatus: {status}\n{extra}---\n# x\n')
        for outcome, expected in [('DONE', '→ 問 AI → 已回信'),
                                  ('FAILED', '→ AI 沒回成，已回信說卡住了'),
                                  ('BLOCKED', '→ AI 沒回成，已回信說卡住了'),
                                  (None, '→ 已回信')]:
            with tempfile.TemporaryDirectory() as tmp:
                node = Path(tmp) / 'bob'
                (node / 'inbox').mkdir(parents=True)
                tick = [0]
                def advance(_):
                    tick[0] += 1
                    if tick[0] == 1:   # 收到信
                        letter(node / 'inbox/r.md', 'REQUEST', 'id: r1\n')
                    elif tick[0] == 2:  # 辦完：信進 done，回信（ask 已歸檔到 you/inbox/done）
                        (node / 'inbox/done').mkdir()
                        (node / 'inbox/r.md').rename(node / 'inbox/done/r.md')
                        if outcome:
                            letter(Path(tmp) / 'you/inbox/done/reply.md', outcome, 're: r1\n')
                    elif tick[0] == 3:
                        raise KeyboardInterrupt
                output = io.StringIO()
                with patch.object(view, 'number', side_effect=[1, 2, 3, 4]), \
                     patch.object(view.time, 'sleep', side_effect=advance), contextlib.redirect_stdout(output):
                    with self.assertRaises(KeyboardInterrupt):
                        view.watch(node, None)
                self.assertIn('收到 1 封信', output.getvalue())
                self.assertIn(expected, output.getvalue())

    def test_preparation_interrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(cli, 'up', side_effect=KeyboardInterrupt), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(cli.main([str(Path(tmp) / 'bob')]), 3)
            self.assertIn('裝到一半被中斷', err.getvalue())

    def test_wakeup_timeout_reaps(self):
        child = subprocess.Popen(['python3', '-B', '-c', 'import time; time.sleep(60)'])
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'bob'
            (Path(tmp) / '.aosd').mkdir()
            try:
                with patch.object(up, 'prepare', return_value={'model': None}), \
                     patch.object(up, 'alive', side_effect=[False, True]), \
                     patch.object(up.subprocess, 'Popen', return_value=child), \
                     patch.object(up.time, 'monotonic', side_effect=[0, 0, 16]):
                    with self.assertRaises(view.UpError) as err:
                        up.up(node, None, True)
                self.assertEqual(err.exception.code, 3)
                self.assertIsNotNone(child.poll())
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait()

    def test_foreground_cleanup_timeout(self):
        from unittest.mock import Mock
        daemon = Mock()
        daemon.poll.return_value = None
        daemon.wait.side_effect = [subprocess.TimeoutExpired('daemon', 30), 0]
        with tempfile.TemporaryDirectory() as tmp:
            node = Path(tmp) / 'bob'
            (Path(tmp) / '.aosd').mkdir()
            with patch.object(up, 'prepare', return_value={'model': None}), \
                 patch.object(up, 'alive', side_effect=[False, True]), \
                 patch.object(up, 'node_round', side_effect=[0, 1, 1]), \
                 patch.object(up.subprocess, 'Popen', return_value=daemon), \
                 patch.object(up, 'watch', side_effect=KeyboardInterrupt), \
                 contextlib.redirect_stdout(io.StringIO()) as out:
                with self.assertRaises(view.UpError) as err:
                    up.up(node, None, False)
            self.assertEqual(err.exception.code, 3)
            daemon.kill.assert_called_once()
            self.assertNotIn('心跳停了', out.getvalue())

    def test_call_interrupt_kills_grandchild(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / 'spawn.py'
            pidfile = Path(tmp) / 'pid'
            script.write_text("import subprocess,time\np=subprocess.Popen(['sleep','60'])\nopen(" + repr(str(pidfile)) + ", 'w').write(str(p.pid))\ntime.sleep(60)\n")
            def interrupt(child):
                import time
                end = time.monotonic() + 5
                while not pidfile.exists() and time.monotonic() < end:
                    time.sleep(.01)
                raise KeyboardInterrupt
            with patch.object(subprocess.Popen, 'communicate', interrupt):
                with self.assertRaises(KeyboardInterrupt):
                    view.call(script)
            pid = int(pidfile.read_text())
            stat = Path(f'/proc/{pid}/stat')
            self.assertTrue(not stat.exists() or stat.read_text().split()[2] == 'Z')
