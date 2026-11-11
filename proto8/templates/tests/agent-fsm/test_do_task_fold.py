# do_task save／load（11-11 fork-and-do-task/02）：真 daemon＋真 llm kernel＋假腦劇本——start→叫工具→end 後 history 只剩紀錄點＋總結、原文留檔；巢狀；任務中等信（預設信一起摺、keep_others 信留著）；停掉再起來紀錄點還在。
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

CELLS = Path(__file__).resolve().parents[2] / 'agent-fsm'
PROTO = CELLS.parents[1]
DO, PEEK = str(PROTO / 'lib/agent/do_task'), str(PROTO / 'lib/base/peek_now_time')


def calls(*items):
    return {'tool_calls': [{'name': n, 'arguments': a} for n, a in items]}


def start(task):
    return calls(('do_task', {'op': 'start', 'task': task}))


def end(summary, **more):
    return calls(('do_task', dict({'op': 'end', 'summary': summary}, **more)))


PEEKS = calls(('peek_now_time', {}))
# 劇本：按順序的那幾項＝任務裡做的事；摺完 assistant 則數會倒退，摺完之後的接法用 when（最後一則含那個字）
SCRIPTS = {
    'fold': [start('Find the time'), PEEKS, PEEKS, end('It is today.'),
             {'when': 'Task ended', 'content': 'Done.'}],
    'nested': [start('outer'), PEEKS, start('inner'), PEEKS, end('inner done'),
               {'when': 'Task ended (depth 2)', **end('outer done')}, {'when': 'Task ended (depth 1)', 'content': 'Done.'}],
    'mail': [start('Wait for bob'), {'content': 'Waiting for bob.'},
             {'when': 'Task ended', 'content': 'Done.'}, {'when': 'the answer is 42', **end('Bob said 42.')}],
    'mail_keep': [start('Wait for bob'), {'content': 'Waiting for bob.'},
                  {'when': 'Task ended', 'content': 'Done.'},
                  {'when': 'the answer is 42', **end('Bob said 42.', keep_others=True)}],
    'restart': [start('Long job'), {'content': 'Paused.'},
                {'when': 'Task ended', 'content': 'Done.'}, {'when': 'In 1 task', **end('Long job finished.')},
                {'when': 'Go on', **calls(('do_task', {'op': 'status'}))}],
}


def write(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


class DoTaskFold(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='aos-dotask-')
        root = cls.root = Path(os.path.realpath(cls.tmp))
        cls.daemon_stack, kernel_stack = root / 'daemon', root / 'kernel'
        cls.daemon_stack.mkdir()
        kernel_stack.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        bins = [str(p) for p in (PROTO / 'impls').glob('*/bin')] + [str(p) for p in (PROTO / 'cmd').glob('*/bin')]
        env['PATH'] = os.pathsep.join(bins + [env['PATH']])
        env['PYTHONPATH'] = os.pathsep.join([str(PROTO / 'lib'), str(PROTO / 'py')])
        env.update(AOS_STACK=str(cls.daemon_stack), AOS_CD=str(root), AOS_WS=str(root), AOS_HOME=str(PROTO),
                   AOS_DAEMON=str(cls.daemon_stack), AOS_LLM_KERNEL=str(kernel_stack))
        cls.env = env
        for name in SCRIPTS:                         # 每個情境一份定義：範本原樣，工具換成 do_task＋peek_now_time，腦＝那個情境的劇本
            d = root / ('def_' + name)
            shutil.copytree(CELLS, d, ignore=shutil.ignore_patterns('tests', '__pycache__'))
            write(d / 'llm.json', {'model': name})
            write(d / 'tools.json', {'tools': {'do_task': {'path': DO}, 'peek_now_time': {'path': PEEK}}})
            write(d / 'loop.json', {'exec': 'fsm.json', 'interval_ms': 10, 'ctl': 'ctl.json', 'state': 'state.json',
                                    'state_flux': 'state_flux.json'})
        kernel_config = root / 'kernel.json'
        write(kernel_config, {'exec': str(PROTO / 'lib/base/llm_fake'), 'endpoint': 'fold',
                              'endpoints': {n: {'script': s} for n, s in SCRIPTS.items()}})
        write(root / 'daemon.json', {'interval_ms': 10, 'procs': {}})
        write(root / 'kernel_daemon.json', {'interval_ms': 10, 'exec': {'argv': [
            str(PROTO / 'impls/aos-llm-kernel/bin/aos-llm-kernel'), str(kernel_config)]}})
        cls.log = (root / 'daemon.log').open('w+')
        cls.daemons = [subprocess.Popen(['aos-daemon', str(root / 'daemon.json')], cwd=root, env=env, stdout=cls.log, stderr=cls.log),
                       subprocess.Popen(['aos-daemon', str(root / 'kernel_daemon.json')], cwd=root,
                                        env=dict(env, AOS_STACK=str(kernel_stack)), stdout=cls.log, stderr=cls.log)]
        deadline = time.monotonic() + 5
        while not (cls.daemon_stack / 'procs_state.json').exists():
            assert cls.daemons[0].poll() is None, 'daemon exited during startup'
            assert time.monotonic() < deadline, 'daemon did not become ready'
            time.sleep(.02)

    @classmethod
    def tearDownClass(cls):
        for p in cls.daemons:
            p.terminate()
        for p in cls.daemons:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)
        cls.log.close()
        if os.environ.get('KEEP_TMP'):
            print('kept', cls.tmp)
        else:
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def agent(self, *args):
        r = subprocess.run(['aos-agent', '--daemon', str(self.daemon_stack), *args], cwd=self.root, env=self.env,
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return r.stdout

    def begin(self, name):
        self.agent('ctl', 'add', '--name', name, '--ws', str(self.root), str(self.root / ('def_' + name)))
        self.addCleanup(lambda: subprocess.run(['aos-agent', '--daemon', str(self.daemon_stack), 'ctl', 'rm', name],
                                               cwd=self.root, env=self.env, capture_output=True, timeout=60))
        return Path(self.agent('ctl', 'where', '--target', name).strip())

    def ask(self, name, text):
        self.agent('say', '--target', name, text)
        return self.agent('listen', '--target', name, '--timeout-s', '100')

    def history(self, stack):
        return [json.loads(l) for l in (stack / 'history.jsonl').read_text().splitlines() if l.strip()]

    def removed(self, stack):
        return [json.loads(l) for l in (stack / 'history_removed.jsonl').read_text().splitlines()]

    def tasks(self, stack):
        return json.loads((stack / 'tools/do_task/tasks.json').read_text())['tasks']

    def roles(self, h):
        return [m['role'] for m in h]

    def test_fold(self):
        stack = self.begin('fold')
        self.assertIn('Done.', self.ask('fold', 'Go.'))
        h = self.history(stack)
        self.assertEqual(self.roles(h), ['user', 'assistant', 'tool', 'user', 'assistant', 'tool', 'assistant'])
        self.assertEqual(json.loads(h[1]['tool_calls'][0]['function']['arguments'])['op'], 'start')   # 紀錄點
        self.assertTrue(h[2]['content'].startswith('Task started (depth 1) "Find the time".'))
        self.assertEqual(h[3]['content'], '[aos] summary: lines 4-7, 4 messages. Task "Find the time" ended: It is today.')
        self.assertIn('4 messages (lines 4-7) are now one summary at line 4', h[5]['content'])
        folded = [r['message'] for r in self.removed(stack)]
        self.assertEqual([m['role'] for m in folded], ['assistant', 'tool', 'assistant', 'tool'])     # 原文留檔
        self.assertEqual(folded[0]['tool_calls'][0]['function']['name'], 'peek_now_time')
        self.assertEqual(self.tasks(stack), [])

    def test_nested(self):
        stack = self.begin('nested')
        self.assertIn('Done.', self.ask('nested', 'Go.'))
        h = self.history(stack)
        self.assertEqual(self.roles(h), ['user', 'assistant', 'tool', 'user', 'assistant', 'tool', 'assistant'])
        self.assertTrue(h[2]['content'].startswith('Task started (depth 1) "outer".'))
        self.assertEqual(h[3]['content'], '[aos] summary: lines 4-10, 7 messages. Task "outer" ended: outer done')
        inner = [r['message'] for r in self.removed(stack) if 'inner done' in str(r['message'].get('content'))]
        self.assertEqual(len(inner), 1)                                   # 裡面那段的總結也摺進外面那段、原文留著
        self.assertTrue(inner[0]['content'].startswith('[aos] summary: lines 8-9, 2 messages. Task "inner" ended'))

    def test_letter_during_the_task_is_folded_by_default(self):
        stack = self.begin('mail')                                        # 使用者 11-11「可選。預設清掉。」
        self.assertIn('Waiting for bob.', self.ask('mail', 'Go.'))      # 任務中自己答了一句、停下來等
        self.assertEqual(len(self.tasks(stack)), 1)
        self.assertIn('Done.', self.ask('mail', 'From bob: the answer is 42.'))
        h = self.history(stack)
        self.assertEqual(self.roles(h), ['user', 'assistant', 'tool', 'user', 'assistant', 'tool', 'assistant'])
        self.assertEqual(h[3]['content'], '[aos] summary: lines 4-5, 2 messages. Task "Wait for bob" ended: Bob said 42.')
        self.assertIn('2 messages (lines 4-5) are now one summary at line 4', h[5]['content'])
        self.assertIn('1 of them came from others during the task (letters, reminders) and was folded too', h[5]['content'])
        folded = [r['message'] for r in self.removed(stack)]
        self.assertEqual(folded[1], {'role': 'user', 'content': 'From bob: the answer is 42.'})   # 信的原文留檔

    def test_letter_during_the_task_stays_with_keep_others(self):
        stack = self.begin('mail_keep')
        self.assertIn('Waiting for bob.', self.ask('mail_keep', 'Go.'))
        self.assertIn('Done.', self.ask('mail_keep', 'From bob: the answer is 42.'))
        h = self.history(stack)
        self.assertEqual(self.roles(h), ['user', 'assistant', 'tool', 'user', 'user', 'assistant', 'tool', 'assistant'])
        self.assertEqual(h[3]['content'], '[aos] summary: line 4, 1 message. Task "Wait for bob" ended: Bob said 42.')
        self.assertIn('1 message (lines 4-5) is now one summary at line 4', h[6]['content'])
        self.assertEqual(h[4], {'role': 'user', 'content': 'From bob: the answer is 42.'})   # 信沒被摺
        self.assertIn('1 message from others during the task is kept after the summary', h[6]['content'])

    def test_stop_and_start_keeps_the_mark(self):
        stack = self.begin('restart')
        self.assertIn('Paused.', self.ask('restart', 'Go.'))
        self.agent('ctl', 'stop', '--target', 'restart')
        self.assertEqual([t.get('task') for t in self.tasks(stack)], ['Long job'])
        self.agent('ctl', 'start', '--target', 'restart')
        self.assertIn('Done.', self.ask('restart', 'Go on.'))
        h = self.history(stack)
        status = [m['content'] for m in h if m['role'] == 'tool' and m['content'].startswith('In 1 task')]
        self.assertEqual(len(status), 0)                                  # status 那次也在任務裡，一起摺掉了
        statuses = [r['message']['content'] for r in self.removed(stack) if r['message'].get('role') == 'tool']
        self.assertTrue(any(s.startswith('In 1 task (outermost first):\n1. "Long job" started ') for s in statuses), statuses)
        self.assertEqual(self.roles(h), ['user', 'assistant', 'tool', 'user', 'assistant', 'tool', 'assistant'])
        self.assertNotIn({'role': 'user', 'content': 'Go on.'}, h)       # 任務中別人說的話預設一起摺
        self.assertEqual(self.tasks(stack), [])


if __name__ == '__main__':
    unittest.main()
