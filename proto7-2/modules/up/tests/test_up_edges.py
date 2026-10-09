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


@unittest.skipUnless((cases.HOME / 'tools/wf-init.sh').is_file(), '找不到 workflows 模板')
class UpEdges(DaemonCase):
    """〔up〕共享心跳、群組訊號、鎖與模板錯誤。"""
    def setUp(self):
        super().setUp()
        self.node = Path(self.mknode("bob", interval_ms=200))

    def tearDown(self):
        self.invoke("stop", self.node)
        self._reap_all()

    invoke = cases.UpTests.invoke
    data = cases.UpTests.data
    names_once = cases.UpTests.names_once

    def foreground(self):
        p = subprocess.Popen([sys.executable, str(cases.UP), str(self.node)],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, start_new_session=True)
        _proc.track(self, p, grace=30, group=True)
        first = p.stdout.readline()
        self.assertTrue(first.startswith('bob 起好了'), first)
        return p, first

    def test_attached_interrupt_keeps_daemon(self):
        self.invoke(self.node, '-d')
        self.wait_round(2, 'bob')
        p, first = self.foreground()
        p.send_signal(signal.SIGINT)
        rest, _ = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, first + rest)
        self.assertIn('只停了觀看', rest)
        self.assertTrue(view.alive(Path(self.root)))

    def test_group_interrupt(self):
        p, first = self.foreground()
        os.killpg(p.pid, signal.SIGINT)
        rest, _ = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, first + rest)
        self.assertIn('心跳停了', rest)
        self.assertNotIn('Traceback', rest)
        self.assertFalse(view.alive(Path(self.root)))

    def test_foreground_sigterm(self):
        p, first = self.foreground()
        p.send_signal(signal.SIGTERM)
        rest, _ = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 0, first + rest)
        self.assertIn('心跳停了', rest)
        self.assertNotIn('Traceback', rest)
        self.assertFalse(view.alive(Path(self.root)))

    def test_parallel_up(self):
        procs = []
        for _ in range(2):
            p = subprocess.Popen([sys.executable, str(cases.UP), str(self.node), '-d'],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            _proc.track(self, p)
            procs.append(p)
        for p in procs:
            out, err = p.communicate(timeout=40)
            self.assertEqual(p.returncode, 0, out + err)
        self.names_once()
        self.assertTrue(view.alive(Path(self.root)))

    def test_missing_template(self):
        result = subprocess.run([sys.executable, str(cases.UP), str(self.node), '-d'],
                                capture_output=True, text=True,
                                env=dict(os.environ, AOS7_WF_HOME=self.root + '/missing'))
        self.assertEqual(result.returncode, 1)
        self.assertIn('缺工作流模板', result.stderr)
        self.assertFalse((self.node / '.aos/up.json').exists())

    def test_status_readonly_state_usage(self):
        self.invoke(self.node, '-d')
        self.invoke('stop', self.node)
        cases_run = [sys.executable, str(cases.P / 'modules/wfnode/aos7-wfnode'),
                     'state', str(self.node), '下一步測試']
        self.assertEqual(subprocess.run(cases_run, capture_output=True).returncode, 0)
        raw = self.node / 'llmcall/llm/c1/raw.json'
        raw.parent.mkdir(parents=True)
        raw.write_text('{}')
        def snapshot():
            return {str(p): p.read_bytes() for p in Path(self.root).rglob('*')
                    if p.is_file() and not p.is_symlink()}
        before = snapshot()
        output = self.invoke('status', self.node)
        self.assertEqual(before, snapshot())
        self.assertIn('下一步測試', output)
        self.assertIn('問過 1 次，用量約 0 字（讀加寫）', output)

    def test_reup_preserves_letter(self):
        self.invoke(self.node, '-d')
        self.invoke('stop', self.node)
        cases.UpTests.send(self)
        letter = next((self.node / 'inbox').glob('*.md'))
        letter.write_text(letter.read_text() + '\n{{user}}\n')
        before = letter.read_bytes()
        # Attach to a simulated heartbeat so a future brain cannot consume the fixture.
        for _ in range(3):
            with patch.object(up, 'alive', return_value=True), \
                 patch.object(up, 'node_round', side_effect=[0, 1, 1]), \
                 contextlib.redirect_stdout(io.StringIO()):
                up.up(self.node, None, True)
            self.assertEqual(before, letter.read_bytes())

    def test_bad_config(self):
        path = self.node / '.aos/up.json'
        for value in ([], None, {'model': 5}):
            path.write_text(__import__('json').dumps(value))
            before = path.read_bytes()
            for args in ((self.node, '-d'), ('status', self.node)):
                result = subprocess.run(['python3', '-B', str(cases.UP), *map(str, args)],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(len(result.stderr.splitlines()), 1)
                self.assertIn('aos7-up:', result.stderr)
                self.assertNotIn('Traceback', result.stderr)
            self.assertEqual(path.read_bytes(), before)


