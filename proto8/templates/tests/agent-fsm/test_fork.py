# fork（11-11 fork-and-do-task/01）：真 daemon＋真 llm kernel＋假腦劇本——父先聽到暗號、叫 fork，分身帶著整段對話答出暗號、再叫 fork＝DepthExceeded；結論回到父那則 tool、父 history 沒有分身的過程；分身收掉（keep 時留著、停著）。
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
SECRET = 'plum-42'


def write(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def lines(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def records(stack):
    interface = json.loads((stack / 'interfaces.json').read_text())
    return lines(stack / interface['aos-observed']['file'])


def script(keep):
    """父：0 答 OK、1 叫 fork；分身（最後一則是開場、含 Your task:）叫 fork＝DepthExceeded；之後按 assistant 則數：父 2 收尾、分身 3 答暗號。"""
    fork = {'goal': 'Tell me the password the user gave earlier.', 'timeout_s': 60}
    if keep:
        fork['keep'] = True
    return [{'content': 'OK, I will remember it.'},
            {'tool_calls': [{'name': 'fork', 'arguments': fork}]},
            {'when': 'Your task:', 'tool_calls': [{'name': 'fork', 'arguments': {'goal': 'Again.', 'timeout_s': 30}}]},
            {'content': 'The copy has answered.'},
            {'content': 'The password is %s.' % SECRET}]


class Fork(unittest.TestCase):
    def test_fork_copies_the_conversation_and_returns_only_the_conclusion(self):
        with tempfile.TemporaryDirectory(prefix='aos-fork-') as tmp:
            root = Path(os.path.realpath(tmp))
            daemon_stack, kernel_stack = root / 'daemon', root / 'kernel'
            daemon_stack.mkdir()
            kernel_stack.mkdir()
            env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
            bins = [str(p) for p in (PROTO / 'impls').glob('*/bin')] + [str(p) for p in (PROTO / 'cmd').glob('*/bin')]
            env['PATH'] = os.pathsep.join(bins + [env['PATH']])
            env['PYTHONPATH'] = os.pathsep.join([str(PROTO / 'lib'), str(PROTO / 'py')])
            env.update(AOS_STACK=str(daemon_stack), AOS_CD=str(root), AOS_WS=str(root), AOS_HOME=str(PROTO),
                       AOS_DAEMON=str(daemon_stack), AOS_LLM_KERNEL=str(kernel_stack))
            defs = {}
            for model in ('plain', 'kept'):             # 兩份定義：範本原樣（hooks.json 照帶），工具只有 fork，腦各一份劇本
                own = root / ('def_' + model)
                shutil.copytree(CELLS, own, ignore=shutil.ignore_patterns('tests', '__pycache__'))
                write(own / 'llm.json', {'model': model})
                write(own / 'tools.json', {'tools': {'fork': {'path': str(PROTO / 'lib/agent/fork')}}})
                write(own / 'loop.json', {'exec': 'fsm.json', 'interval_ms': 10, 'ctl': 'ctl.json', 'state': 'state.json',
                                          'state_flux': 'state_flux.json'})
                defs[model] = own
            kernel_config = root / 'kernel.json'
            write(kernel_config, {'exec': str(PROTO / 'lib/base/llm_fake'), 'endpoint': 'plain', 'endpoints': {
                'plain': {'script': script(False)}, 'kept': {'script': script(True)}}})
            write(root / 'daemon.json', {'interval_ms': 10, 'procs': {}})
            write(root / 'kernel_daemon.json', {'interval_ms': 10, 'exec': {'argv': [
                str(PROTO / 'impls/aos-llm-kernel/bin/aos-llm-kernel'), str(kernel_config)]}})

            def logs():                                 # 失敗時附上各隻的 stderr.txt（daemon 寫在 proc 的 stack）
                return ''.join('\n== %s\n%s' % (p, p.read_text()[-3000:])
                               for p in sorted((daemon_stack / 'procs').glob('*/stderr.txt')))

            def agent(*args, stdin=None):
                r = subprocess.run(['aos-agent', '--daemon', str(daemon_stack), *args], cwd=root, env=env, input=stdin,
                                   capture_output=True, text=True, timeout=120)
                self.assertEqual(r.returncode, 0, r.stderr + r.stdout + logs())
                return r.stdout

            with (root / 'daemon.log').open('w+') as log:
                daemon = subprocess.Popen(['aos-daemon', str(root / 'daemon.json')], cwd=root, env=env, stdout=log, stderr=log)
                kernel = subprocess.Popen(['aos-daemon', str(root / 'kernel_daemon.json')], cwd=root,
                                          env=dict(env, AOS_STACK=str(kernel_stack)), stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 5
                    while not (daemon_stack / 'procs_state.json').exists():
                        self.assertIsNone(daemon.poll(), 'daemon exited during startup')
                        self.assertLess(time.monotonic(), deadline, 'daemon did not become ready')
                        time.sleep(.02)
                    for name, model in (('pat', 'plain'), ('kim', 'kept')):
                        agent('ctl', 'add', '--name', name, '--ws', str(root), str(defs[model]))
                        agent('system', '--target', name, 'set', '-', stdin='You are %s.\n' % name)   # 自己改過的設定（stack 那份）
                        agent('say', '--target', name, 'The password is %s. Remember it.' % SECRET)
                        self.assertIn('OK', agent('listen', '--target', name, '--timeout-s', '60'))
                        agent('say', '--target', name, 'Fork and ask the copy for the password.')
                        self.assertIn('The copy has answered.', agent('listen', '--target', name, '--timeout-s', '100'))

                    procs = daemon_stack / 'procs'
                    for name in ('pat', 'kim'):
                        stack = Path(agent('ctl', 'where', '--target', name).strip())
                        history = lines(stack / 'history.jsonl')
                        self.assertEqual([m['role'] for m in history], ['user', 'assistant', 'user', 'assistant', 'tool', 'assistant'])
                        result = history[4]['content']
                        self.assertTrue(result.startswith('The password is %s.' % SECRET), result)   # 結論回到父的那則 tool
                        text = json.dumps(history)
                        self.assertNotIn('Your task:', text)                  # 分身的開場、它叫的 fork、DepthExceeded 都不在父這邊
                        self.assertNotIn('DepthExceeded', text)
                        calls = [r for r in records(stack) if r['kind'] == 'tool']
                        self.assertEqual([(c['name'], c['code']) for c in calls], [('fork', 0)])
                        copy = stack / calls[0]['child']                      # 分身的帳抄回父的工具小格
                        copy_calls = [r for r in records(copy) if r['kind'] == 'tool']
                        self.assertEqual([(c['name'], c['code']) for c in copy_calls], [('fork', 1)])   # 分身再叫＝DepthExceeded

                    kept = [p for p in procs.iterdir() if p.name.startswith('f-kim-')]
                    self.assertEqual(sorted(p.name for p in procs.iterdir() if not p.name.startswith('f-kim-')), ['kim', 'pat'])
                    self.assertEqual(len(kept), 1)                            # pat 的分身收掉了、kim 的（keep）留著
                    kid = kept[0]
                    table = json.loads(agent('ctl', 'ls', '--json'))
                    self.assertEqual({r['name']: r['phase'] for r in table}[kid.name], 'stopped')
                    self.assertIn('details: procs/%s/' % kid.name, lines(Path(agent('ctl', 'where', '--target', 'kim').strip())
                                                                         / 'history.jsonl')[4]['content'])
                    copied = lines(kid / 'history.jsonl')
                    self.assertEqual(copied[0]['content'], 'The password is %s. Remember it.' % SECRET)   # 整段對話抄過去
                    self.assertTrue(copied[4]['content'].startswith('[aos] fork: you are the copy made by this call'))
                    self.assertTrue(copied[5]['content'].startswith('[aos] fork: you are a fork'))
                    self.assertIn('Your task: Tell me the password the user gave earlier.', copied[5]['content'])
                    self.assertIn('You cannot fork again', copied[5]['content'])
                    self.assertIn('DepthExceeded', copied[7]['content'])
                    self.assertEqual(copied[-1]['content'], 'The password is %s.' % SECRET)
                    request = json.loads((kid / 'think' / 'request.json').read_text())
                    self.assertIn(SECRET, json.dumps(request))                # 分身的腦看得到父那時的對話
                    self.assertEqual((kid / 'system.txt').read_text(), 'You are kim.\n')   # 自己改過的 system 跟著過去
                    self.assertFalse((kid / 'goal.json').exists())
                    agent('ctl', 'rm', '--purge', kid.name)
                    agent('ctl', 'rm', 'pat')
                    agent('ctl', 'rm', 'kim')
                finally:
                    for p in (daemon, kernel):
                        p.terminate()
                    for p in (daemon, kernel):
                        try:
                            p.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            p.kill()
                            p.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
