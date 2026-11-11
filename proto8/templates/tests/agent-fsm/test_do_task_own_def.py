# do_task 沒給 from、登記格也沒設 AOS_DO_TASK_FROM＝用呼叫者自己的定義（11-11 使用者「不是就呼叫者自己的範本嗎？」）：真 daemon＋假腦，子、孫都從父的定義生，孫再叫＝DepthExceeded。
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


def write(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def records(stack):
    interface = json.loads((stack / 'interfaces.json').read_text())
    return [json.loads(line) for line in (stack / interface['aos-observed']['file']).read_text().splitlines()]


class DoTaskOwnDefinition(unittest.TestCase):
    def test_no_from_uses_the_callers_definition_and_depth_still_stops(self):
        with tempfile.TemporaryDirectory(prefix='aos-dotask-') as tmp:
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
            # 一份定義：範本原樣（hooks.json 照帶），只換工具成 do_task 一支、腦換假腦 same
            own = root / 'own_def'
            shutil.copytree(CELLS, own, ignore=shutil.ignore_patterns('tests', '__pycache__'))
            write(own / 'llm.json', {'model': 'same'})
            write(own / 'tools.json', {'tools': {'do_task': {'path': str(PROTO / 'lib/agent/do_task')}}})
            write(own / 'loop.json', {'exec': 'fsm.json', 'interval_ms': 10, 'ctl': 'ctl.json', 'state': 'state.json',
                                      'state_flux': 'state_flux.json'})
            # 每一隻（父、子、孫）都從同一份劇本：第一則叫 do_task（不給 from），第二則答 Done.
            kernel_config = root / 'kernel.json'
            write(kernel_config, {'exec': str(PROTO / 'lib/base/llm_fake'), 'endpoint': 'same', 'endpoints': {'same': {'script': [
                {'tool_calls': [{'name': 'do_task', 'arguments': {'goal': 'Say done.', 'timeout_s': 60}}]},
                {'content': 'Done.'}]}}})
            write(root / 'daemon.json', {'interval_ms': 10, 'procs': {}})
            write(root / 'kernel_daemon.json', {'interval_ms': 10, 'exec': {'argv': [
                str(PROTO / 'impls/aos-llm-kernel/bin/aos-llm-kernel'), str(kernel_config)]}})

            def agent(*args):
                r = subprocess.run(['aos-agent', '--daemon', str(daemon_stack), *args], cwd=root, env=env,
                                   capture_output=True, text=True, timeout=120)
                self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
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
                    agent('ctl', 'add', '--name', 'parent', '--ws', str(root), str(own))
                    agent('say', '--target', 'parent', 'Go.')
                    self.assertIn('Done.', agent('listen', '--target', 'parent', '--timeout-s', '100'))
                    stack = Path(agent('ctl', 'where', '--target', 'parent').strip())
                    calls = [r for r in records(stack) if r['kind'] == 'tool']
                    self.assertEqual([(c['name'], c['code']) for c in calls], [('do_task', 0)])
                    child = stack / calls[0]['child']
                    child_rows = records(child)
                    self.assertEqual(child_rows[0]['def'], str(own))          # 子＝父自己的定義
                    child_calls = [r for r in child_rows if r['kind'] == 'tool']
                    self.assertEqual([(c['name'], c['code']) for c in child_calls], [('do_task', 0)])
                    grand = child / child_calls[0]['child']
                    grand_rows = records(grand)
                    self.assertEqual(grand_rows[0]['def'], str(own))          # 孫也是
                    grand_calls = [r for r in grand_rows if r['kind'] == 'tool']
                    self.assertEqual([(c['name'], c['code']) for c in grand_calls], [('do_task', 1)])   # 深度 2 再叫＝DepthExceeded
                    history = (grand / '..').resolve()
                    self.assertEqual(sorted(p.name for p in (daemon_stack / 'procs').iterdir()), ['parent'])   # 子孫都收掉了
                    agent('ctl', 'rm', 'parent')
                finally:
                    for p in (daemon, kernel):
                        p.terminate()
                    for p in (daemon, kernel):
                        try:
                            p.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            p.kill()
                            p.wait(timeout=5)
