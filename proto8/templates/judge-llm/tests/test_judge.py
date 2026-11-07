# Verify judge reply normalization, truncation, kernel failures, and measured check costs.
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parents[1]
PROTO = HERE.parents[1]
loader = importlib.machinery.SourceFileLoader('judge_entry', str(HERE / '_entry'))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


def write(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


class Judge(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(module.parse_content('prefix {"score": 4, "diff": [1]} suffix'),
                         {'score': 1, 'diff': [], 'why': ''})
        self.assertEqual(module.parse_content('{"score": -1}')['score'], 0)
        self.assertEqual(module.parse_content('before {"score": 0.7, "diff": ["a"], "why": "ok"} after'),
                         {'score': .7, 'diff': ['a'], 'why': 'ok'})
        self.assertEqual(module.parse_content('{"score": 0.5, "why": 3}')['why'], '')
        for diff in (None, 'file', {}, [False]):
            self.assertEqual(module.parse_content(json.dumps({'score': .5, 'diff': diff}))['diff'], [])
        for text in ('not json', '{"why":"missing"}', '{"score":true}', '{"score":NaN}'):
            with self.assertRaises(ValueError):
                module.parse_content(text)

    def test_sections(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'z').write_text('z')
            (root / 'a').write_text('a')
            self.assertEqual(module.folder_text(root, 100), '== a ==\na\n== z ==\nz\n')
            self.assertTrue(module.folder_text(root, 5).endswith('[truncated]'))
            self.assertEqual(module.truncate('中中'.encode(), 4), '中\n[truncated]')
            self.assertEqual(module.input_text(root, 100), '')
            (root / 'say.txt').write_text('Question')
            self.assertIn('Question', module.input_text(root, 100))

    def test_ask_failure_forwards_stderr(self):
        with tempfile.TemporaryDirectory(prefix='judge-failed-', dir='/tmp') as temp:
            root = Path(temp)
            (root / 'expect').mkdir()
            (root / 'got').mkdir()
            shim = root / 'aos-llm'
            shim.write_text('#!/usr/bin/env python3\n'
                '# Return a controlled downstream failure.\n'
                'import json, sys\n'
                'sys.stdin.read()\n'
                'print(json.dumps({"error":{"code":"EndpointMissing","msg":"no endpoint"}}))\n'
                'sys.stderr.write("aos-llm: warning: detail before failure\\n")\n'
                'sys.stderr.write("aos-llm: error: EndpointMissing no endpoint\\n")\n'
                'sys.exit(1)\n')
            shim.chmod(0o755)
            env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                       AOS_LLM_KERNEL=str(root / 'kernel'), AOS_STACK=str(root / 'stack'))
            result = subprocess.run([str(HERE / '_entry')],
                input=json.dumps({'expect': str(root / 'expect'), 'got': str(root / 'got'),
                                  'input': str(root)}), env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            final = 'judge-llm: error: EndpointMissing no endpoint\n'
            self.assertEqual(result.stdout, final)
            self.assertEqual(result.stderr, 'aos-llm: warning: detail before failure\n'
                'aos-llm: error: EndpointMissing no endpoint\n' + final)

    def test_kernel_and_measure(self):
        with tempfile.TemporaryDirectory(prefix='judge-test-', dir='/tmp') as temp:
            root = Path(temp)
            kernel = root / 'kernel'
            kernel.mkdir()
            bins = [str(p) for group in ('impls', 'cmd') for p in (PROTO / group).glob('*/bin')]
            env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
            env.update(PATH=os.pathsep.join(bins + [env['PATH']]),
                       PYTHONPATH=os.pathsep.join([str(PROTO / 'lib'), str(PROTO / 'py')]),
                       AOS_STACK=str(root / 'stack'), AOS_WS=str(root), AOS_CD=str(HERE))
            args = {'expect': str(root), 'got': str(root), 'input': str(root)}

            def run(target, payload, stack='stack', extra=None):
                return subprocess.run(['aos-exec', str(target)], input=json.dumps(payload),
                    env=dict(env, AOS_STACK=str(root / stack), **(extra or {})),
                    cwd=root, capture_output=True, text=True, timeout=40)

            missing = run(HERE, args)
            self.assertEqual(missing.returncode, 1)
            self.assertIn('LlmKernelMissing', missing.stderr)
            self.assertEqual(missing.stdout, missing.stderr)
            judge = root / 'judge'
            shutil.copytree(HERE, judge, ignore=shutil.ignore_patterns('tests', '__pycache__'))
            config = root / 'kernel.json'
            write(config, {'exec': str(HERE / 'tests/endpoint.py'), 'endpoint': 'judge',
                'endpoints': {'judge': {}, 'bad': {'exec': str(PROTO / 'lib/base/llm_fake'),
                    'script': [{'content': 'not JSON'}]}}})
            daemon_config = root / 'daemon.json'
            write(daemon_config, {'interval_ms': 10, 'exec': {'argv': [
                str(PROTO / 'impls/aos-llm-kernel/bin/aos-llm-kernel'), str(config)]}})
            env['AOS_LLM_KERNEL'] = str(kernel)
            with (root / 'daemon.log').open('w+') as log:
                process = subprocess.Popen(['aos-daemon', str(daemon_config)], cwd=root,
                    env=dict(env, AOS_STACK=str(kernel)), stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 5
                    while not (kernel / 'requests').is_dir():
                        self.assertIsNone(process.poll())
                        self.assertLess(time.monotonic(), deadline)
                        time.sleep(.02)
                    case = root / 'cases'
                    for name, expected in [('correct', '3\n'), ('wrong', '999\n')]:
                        item = case / name
                        (item / 'expect').mkdir(parents=True)
                        write(item / 'run.json', {'exec': 'lib/base/math', 'stdin': 'stdin.json'})
                        write(item / 'stdin.json', {'expr': '1+2'})
                        (item / 'expect/stdout.json').write_text(expected)
                        write(item / 'check.json', {'compare': str(judge), 'min_score': .9})
                    result = run(PROTO / 'lib/aos/measure', {'case': str(case), 'defs': str(PROTO)}, 'measure')
                    self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                    output = json.loads(result.stdout)
                    checks = [c['samples'][0]['check'] for c in output['cases']]
                    self.assertEqual([c['pass'] for c in checks], [True, False])
                    self.assertEqual([c['why'] for c in checks], ['same', 'wrong'])
                    self.assertEqual(output['check']['cost']['counter_calls'], 2)
                    self.assertEqual(output['check']['cost']['token']['in'], 14)
                    self.assertEqual(output['cost']['counter_calls'], 0)
                    self.assertEqual(output['cost']['token']['in'], 0)
                    write(judge / 'judge.json', {'endpoint': 'bad', 'max_bytes': 60000})
                    bad = run(judge, {'expect': str(case / 'correct/expect'),
                        'got': str(case / 'wrong/expect'), 'input': str(case / 'correct')}, 'bad')
                    self.assertEqual(bad.returncode, 1, bad.stdout)
                    self.assertIn('ReplyBad', bad.stderr)
                    self.assertEqual(bad.stdout, bad.stderr)
                    rows = [json.loads(s) for s in (root / 'bad/observed.jsonl').read_text().splitlines()]
                    self.assertEqual(rows[-1]['kind'], 'think')
                    deadline = time.monotonic() + 5
                    while True:
                        ledger = [json.loads(s) for s in (kernel / 'ledger.jsonl').read_text().splitlines()]
                        if rows[-1]['letter'] in [row['id'] for row in ledger] or time.monotonic() >= deadline:
                            break
                        time.sleep(.01)
                    self.assertIn(rows[-1]['letter'], [row['id'] for row in ledger])
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
