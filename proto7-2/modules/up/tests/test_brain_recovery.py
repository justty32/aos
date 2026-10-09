"""mail／state 之間與 state／刪 pending 之間的 SIGKILL。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

TOP = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(TOP / 'tests'), str(TOP / 'modules/up/examples')]
from base import DaemonCase, read_json, write_json
from brain_node import setup
HOME = Path(os.environ.get('AOS7_WF_HOME', '~/repo/workflows')).expanduser()


@unittest.skipUnless((HOME / 'tools/wf-init.sh').exists(), '找不到 workflows 模板')
class BrainRecoveryTests(DaemonCase):
    def exercise(self, point):
        node = setup(Path(self.mknode('bob')), interval_ms=200)
        self.set_tasks(str(node), [t for t in self.tasks(str(node)) if t['name'] != 'brain'])
        self.start_daemon(register=['bob'])
        self.wait_round(2, 'bob')
        p = subprocess.run([sys.executable, str(TOP / 'modules/mail/aos7-mail'), 'send',
                            'you', 'bob', 'REQUEST', '崩潰窗口', '--root', self.root],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0, p.stderr)
        ident = json.loads(p.stdout)['id']
        slot = node / 'test-brain'
        slot.mkdir()
        env = dict(os.environ, AOS7_ROOT=self.root, AOS7_NODE=str(node), AOS7_NODE_ID='bob',
                   AOS7_TASK=str(slot), AOS7_TID='brain', AOS7_RUN='1')
        def launch(rnd, crash):
            write_json(str(slot / 'tock.json'), dict(round=rnd, run=1))
            p = subprocess.Popen([sys.executable, str(TOP / 'modules/up/aos7_up_brain.py'),
                                  'brain', str(node)], env=dict(env, AOS7_TEST_CRASH=crash),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.procs.append(p)
            return p
        self.assertEqual(launch(1, point).wait(30), -9)
        pending = node / 'brain/pending.json'
        self.assertTrue(pending.exists())
        launch(2, '')
        self.wait_for(lambda: not pending.exists())
        state = '\n'.join(p.read_text() for p in (node / 'wf/handoffs').glob('*/STATE.md'))
        self.assertEqual(state.count('回了 ' + ident), 1)
        self.assertEqual(len(list((Path(self.root) / 'you/inbox').glob('*.md'))), 1)
        self.assertEqual(list(read_json(str(node / 'llmcall/fake-remote.json'))['sends'].values()), [1])

    def test_killed_after_mail(self):
        self.exercise('up-brain-after-mail')

    def test_killed_after_state(self):
        self.exercise('up-brain-after-state')
