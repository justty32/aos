"""up 的真子程序整合測試，不依賴 brain 安裝。"""
import collections
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import unittest

from base import DaemonCase, TOP
import _proc

P = Path(TOP)
UP = P / 'modules/up/aos7-up'
HOME = Path(os.environ.get('AOS7_WF_HOME', '~/repo/workflows')).expanduser()


@unittest.skipUnless((HOME / 'tools/wf-init.sh').is_file(), '找不到 workflows 模板')
class UpTests(DaemonCase):
    """〔up〕起停、冪等、重接與唯讀狀態。"""
    def setUp(self):
        super().setUp()
        self.node = Path(self.mknode('bob', interval_ms=200))

    def tearDown(self):
        self.invoke('stop', self.node)
        super()._reap_all()

    def invoke(self, *args, rc=0, **env):
        result = subprocess.run([sys.executable, str(UP), *map(str, args)],
                                capture_output=True, text=True, timeout=40,
                                env=dict(os.environ, **env))
        self.assertEqual(result.returncode, rc, result.stdout + result.stderr)
        return result.stdout

    def data(self, rel):
        return json.loads((self.node / rel).read_text())

    def names_once(self):
        counts = collections.Counter(t['name'] for t in self.data('.aos/tasks.json')['tasks'])
        self.assertEqual(counts, dict.fromkeys(('budget-llm', 'brain', 'compact', 'routines'), 1))
        tasks = {t['name']: t['argv'] for t in self.data('.aos/tasks.json')['tasks']}
        self.assertEqual(tasks['brain'], ['python3', str(P / 'modules/up/aos7-up'), 'brain', str(self.node)])
        for box in (self.node / 'events', self.node.parent / 'you/inbox', self.node.parent / 'you/events'):
            self.assertTrue(box.is_dir(), box)

    def send(self):
        # PROGRESS 不會被 brain 辦掉（它只辦 REQUEST），信才留在原地好比對
        p = subprocess.run([sys.executable, str(P / 'modules/mail/aos7-mail'), '--root', self.root,
                            'send', 'you', 'bob', 'PROGRESS', '測試信'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)['id']

    def test_idempotent(self):
        self.invoke(self.node, '-d')
        grant = (self.node / 'budget/llm/grant.json').read_bytes()
        self.wait_round(2, 'bob')
        self.invoke('stop', self.node)
        self.invoke(self.node, '-d')
        self.invoke(self.node, '-d')
        self.names_once()
        self.assertEqual(grant, (self.node / 'budget/llm/grant.json').read_bytes())
        self.assertFalse((self.node / '.aos/up/wfcheck.sh').exists())
        books = list((P / 'modules/skills/library').iterdir())
        self.assertEqual(len(books), 3)
        for book in books:
            self.assertTrue((self.node / 'skills' / book.name).is_symlink())
        config = self.data('.aos/up.json')
        expected = dict(v=1, model=None, gateway='llm.fake', budget='budget/llm', holder='brain',
                        node=str(self.node), house=self.root, mail_root=self.root, name='bob', you='you',
                        litellm_url='http://localhost:4000/v1')
        self.assertEqual(config, expected)
        self.assertTrue((Path(self.root) / 'you/inbox').is_dir())

    def test_sigkill_reconnect(self):
        self.invoke(self.node, '-d')
        self.wait_round(3, 'bob')
        self.wait_pid(str(self.node), 'budget-llm')
        spent = subprocess.run(['python3', '-B', str(P / 'packs/llmcall/bin/aos7-llmcall'),
            'call', 'budget/llm', '--holder', 'brain', '--call', 't1', '--request',
            str(P / 'packs/llmcall/examples/fake/req-ok.json'), '--reserve', '1000'],
            cwd=self.node, capture_output=True, text=True, timeout=20)
        self.assertEqual(spent.returncode, 0, spent.stdout + spent.stderr)
        def budget():
            result = subprocess.run(['python3', '-B', str(P / 'packs/budget/bin/aos7-budget'),
                'status', 'budget/llm'], cwd=self.node, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        before = budget()
        self.assertGreater(before['used'], 0)
        ident = self.send()
        def locate():
            return next(p for p in (self.node / 'inbox').rglob('*.md')
                        if f'id: {ident}\n' in p.read_text())
        original = locate().read_bytes()
        title = next(s for s in original.decode().splitlines() if s.startswith('# '))
        n = self.node_round('bob')
        old = json.loads((Path(self.root) / '.aosd/gen.json').read_text())['pid']
        self.wait_pid(str(self.node), 'budget-llm')
        os.kill(old, signal.SIGKILL)
        from aos7_up_status import alive
        self.wait_for(lambda: not alive(Path(self.root)))
        self.invoke(self.node, '-d')
        self.wait_round(n + 3, 'bob')
        letter = locate()
        self.assertEqual(title, next(s for s in letter.read_text().splitlines() if s.startswith('# ')))
        if letter.parent == self.node / 'inbox':
            self.assertEqual(original, letter.read_bytes())
        after = budget()
        self.assertEqual((before['used'], before['available']), (after['used'], after['available']))
        self.names_once()
        new_pid = self.wait_pid(str(self.node), 'budget-llm')['pid']
        # /proc 身份掃描：舊代帳任務必須消失，只有一個 ledger 存活。
        live = []
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():
                continue
            try:
                argv = (entry / 'cmdline').read_bytes().split(b'\0')
                env = (entry / 'environ').read_bytes().split(b'\0')
                if b'AOS7_NODE=' + str(self.node).encode() in env and b'ledger' in argv:
                    live.append(int(entry.name))
            except OSError:
                pass
        self.assertEqual(live, [new_pid])

    def test_foreground_interrupt(self):
        p = subprocess.Popen([sys.executable, str(UP), str(self.node)], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, start_new_session=True)
        _proc.track(self, p, grace=30, group=True)
        lines = [p.stdout.readline() for _ in range(5)]
        p.send_signal(signal.SIGINT)
        rest, _ = p.communicate(timeout=30)
        output = ''.join(lines) + rest
        self.assertEqual(p.returncode, 0, output)
        self.assertTrue(lines[0].startswith('bob 起好了'))
        self.assertIn('起好了', lines[0])
        self.assertIn('心跳停了', output)
        self.assertNotIn('回合', output)
        self.assertNotIn('Traceback', output)
        from aos7_up_status import alive
        self.assertFalse(alive(Path(self.root)))

    def test_status_and_stop(self):
        self.invoke(self.node, '-d')
        self.wait_round(2, 'bob')
        self.send()
        lines = self.invoke('status', self.node).splitlines()
        self.assertEqual(len(lines), 6)
        self.assertEqual([s.split('：')[0] for s in lines], ['心跳', '信', '工作簿', '技能', 'AI', '要收掉'])
        for word in ('回合', '帳', '預留', 'ack', '退出碼', 'daemon', 'tick', 'call', '體檢', 'you-2'):
            self.assertNotIn(word, '\n'.join(lines))
        self.assertIn('bob 還沒收到信', lines[1])
        # 心跳行只說活著／停了，不印像秒數的次數；練習用的 AI 不印字數
        self.assertEqual(lines[0], '心跳：活著')
        self.assertEqual(lines[4], 'AI：練習用的 AI（不連網、不花錢，照抄你的信回你）；bob 一共問過 AI 0 次')
        self.invoke('stop', self.node)
        self.assertEqual(self.invoke('status', self.node).splitlines()[0],
                         f'心跳：停了；要再起：aos7-up {self.node}')
        self.assertIn('心跳已經停了', self.invoke('stop', self.node))

    def test_invalid_and_missing(self):
        for name in ('you', '.bob', 'bad name'):
            self.invoke(Path(self.root) / name, '-d', rc=2)
        self.invoke('status', self.node, rc=2)
        self.assertIn('心跳已經停了', self.invoke('stop', self.node))


sys.path.insert(0, str(UP.parent))
