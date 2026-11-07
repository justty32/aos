# Verify priority stdin, child accounting, and error replies through a real daemon and kernel.
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


PROTO = Path(__file__).resolve().parents[3]
KERNEL = PROTO / 'impls/aos-llm-kernel/bin/aos-llm-kernel'
CHILD = {'kernel': '/downstream', 'letter': 'child-letter', 'extra': {'kept': [1, True]}}
SUCCESS = {'message': {'role': 'assistant', 'content': 'ok'},
           'usage': {'total_tokens': 7}, 'model': 'fake-nest', 'extra': {'kept': True}}
ERROR = {'error': {'code': 'X', 'msg': 'y', 'details': {'kept': True}}}


class LiveNesting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='aos-nest-live-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = self.root / 'kernel'
        self.stack.mkdir()
        self.box = self.root / 'replies'
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        bins = [str(p) for p in (PROTO / 'impls').glob('*/bin')]
        self.env['PATH'] = os.pathsep.join(bins + [self.env['PATH']])
        self.env.update(AOS_STACK=str(self.stack), AOS_WS=str(self.root),
                        AOS_CD=str(self.root), AOS_LLM_KERNEL=str(self.stack))

    def start(self, timeout_ms=None):
        endpoint = self.root / 'endpoint'
        endpoint.mkdir()
        entry = endpoint / '_entry'
        entry.write_text('''#!/usr/bin/env python3
# Return deterministic replies after the test inspects the actual endpoint stdin.
import json
import os
from pathlib import Path
import sys
import time
request = json.load(sys.stdin)
stack = Path(os.environ['AOS_STACK'])
(stack / 'captured.json').write_text(json.dumps(request))
until = time.monotonic() + 10
while not (stack / 'release').exists():
    if time.monotonic() >= until:
        sys.exit('test endpoint release timed out')
    time.sleep(0.01)
mode = request['endpoint']['mode']
if mode == 'text':
    print('plain failure')
    print('ignored second line')
    sys.exit(1)
if mode == 'error':
    print(json.dumps(ERROR))
    sys.exit(2)
reply = dict(SUCCESS)
if mode == 'child':
    reply['child'] = CHILD
print(json.dumps(reply))
'''.replace('ERROR', repr(ERROR)).replace('SUCCESS', repr(SUCCESS)).replace('CHILD', repr(CHILD)))
        entry.chmod(0o755)
        cfg = {'exec': str(endpoint), 'endpoint': 'ok',
               'endpoints': {mode: {'mode': mode} for mode in ('ok', 'child', 'error', 'text')}}
        if timeout_ms is not None:
            cfg['timeout_ms'] = timeout_ms
        config = self.root / 'kernel.json'
        config.write_text(json.dumps(cfg))
        daemon_config = self.root / 'daemon.json'
        daemon_config.write_text(json.dumps({'interval_ms': 10, 'exec': {
            'argv': [str(KERNEL), str(config)]}}))
        log = open(self.root / 'daemon.log', 'w+')
        self.addCleanup(log.close)
        self.daemon = subprocess.Popen(['aos-daemon', str(daemon_config)], cwd=self.root,
                                       env=self.env, stdout=log, stderr=log)
        self.addCleanup(self.stop)
        self.wait_for(lambda: (self.stack / 'endpoints.json').exists(), 'kernel did not start')

    def stop(self):
        (self.stack / 'ctl.json').write_text('{"cmd":"stop","seq":1}')
        try:
            self.daemon.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.daemon.terminate()
            self.daemon.wait(timeout=5)

    def wait_for(self, check, message):
        until = time.monotonic() + 10
        while time.monotonic() < until:
            value = check()
            if value:
                return value
            if self.daemon.poll() is not None:
                self.fail(message + ': ' + (self.root / 'daemon.log').read_text())
            time.sleep(0.01)
        self.fail(message + ': ' + (self.root / 'daemon.log').read_text())

    def read_json(self, path):
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, ValueError):
            return None

    def send(self, **fields):
        body = dict(request={'messages': [{'role': 'user', 'content': 'nest test'}]}, **fields)
        result = subprocess.run(['aos-llm', 'send', '--reply-to', str(self.box)],
                                input=json.dumps(body), capture_output=True, text=True,
                                env=self.env, timeout=5)
        self.assertEqual((result.returncode, result.stderr), (0, ''), result.stderr)
        name = result.stdout.strip()
        folder = self.stack / 'requests/cur' / name
        request = self.wait_for(lambda: self.read_json(folder / 'captured.json'), 'endpoint did not read stdin')
        proc = self.wait_for(lambda: self.read_json(folder / 'proc.json'), 'missing proc.json')
        self.assertEqual(request, self.read_json(folder / 'request.json'))
        self.assertIsInstance(proc['seen_at'], float)
        self.assertLessEqual(proc['seen_at'], proc['mounted_at'])
        return name, folder, request, proc

    def receive(self, name, folder):
        (folder / 'release').touch()
        until = time.monotonic() + 10
        while True:
            result = subprocess.run(['aos-llm', 'recv', '--full', str(self.box), name],
                                    capture_output=True, text=True, env=self.env, timeout=5)
            if result.returncode != 10 or time.monotonic() >= until:
                break
            time.sleep(0.01)
        self.assertNotEqual(result.returncode, 10, 'kernel did not reply')
        self.assertEqual(len(result.stdout.splitlines()), 1, result.stderr)
        path = self.stack / 'ledger.jsonl'
        self.wait_for(lambda: path.exists() and any(json.loads(line)['id'] == name
                      for line in path.read_text().splitlines()), 'missing ledger entry')
        row = next(json.loads(line) for line in path.read_text().splitlines() if json.loads(line)['id'] == name)
        return result, json.loads(result.stdout), row

    def test_letter_deadline_wins_and_level_is_raw(self):
        self.start(timeout_ms=60000)
        deadline = round(time.time() + 30, 3)
        iso = datetime.fromtimestamp(deadline, timezone.utc).isoformat()
        name, folder, request, proc = self.send(priority={'level': -7.25, 'deadline': iso})
        self.assertEqual(request['priority'], {'level': -7.25, 'deadline': deadline})
        self.assertLess(deadline, proc['mounted_at'] + 60)
        self.receive(name, folder)

    def test_kernel_timeout_wins(self):
        self.start(timeout_ms=60000)
        for priority in ({'level': 'high', 'deadline': time.time() + 3600}, 'low'):
            with self.subTest(priority=priority):
                name, folder, request, proc = self.send(priority=priority)
                level = priority['level'] if isinstance(priority, dict) else priority
                self.assertEqual(request['priority'], {'level': level, 'deadline': proc['mounted_at'] + 60})
                self.assertIsInstance(request['priority']['deadline'], float)
                self.receive(name, folder)

    def test_deadline_without_timeout_defaults_level(self):
        self.start()
        deadline = time.time() + 60
        name, folder, request, _ = self.send(priority={'deadline': deadline})
        self.assertEqual(request['priority'], {'level': 'normal', 'deadline': deadline})
        self.receive(name, folder)

    def test_no_deadline_and_default_level(self):
        self.start()
        for fields, level in (({}, 'normal'), ({'priority': {}}, 'normal'),
                              ({'priority': 'high'}, 'high'), ({'priority': -12.5}, -12.5)):
            with self.subTest(fields=fields):
                name, folder, request, proc = self.send(**fields)
                self.assertEqual(request['priority'], {'level': level})
                result, body, row = self.receive(name, folder)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(body, dict(SUCCESS, letter=name))
                self.assertEqual(row['seen_at'], proc['seen_at'])
                self.assertIsNone(row['child'])
                self.assertIsNone(row['code'])
                self.assertIs(row['switched'], False)

    def test_child_only_in_ledger(self):
        self.start()
        name, folder, _, proc = self.send(endpoint='child')
        result, body, row = self.receive(name, folder)
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        self.assertEqual(body, dict(SUCCESS, letter=name))
        self.assertEqual(row['child'], CHILD)
        self.assertEqual(row['seen_at'], proc['seen_at'])
        self.assertIsNone(row['code'])
        self.assertIs(row['switched'], False)
        self.assertEqual(row['usage'], SUCCESS['usage'])
        self.assertEqual(list(row), ['id', 'endpoint', 'sender', 'model', 'seen_at', 'mounted_at',
                                     'finished_at', 'elapsed_ms', 'usage', 'code', 'child', 'switched'])

    def test_nonzero_structured_and_plain_errors(self):
        self.start()
        for mode, expected in (('error', ERROR), ('text', {'error': {'code': 'EndpointFailed',
                    'msg': 'endpoint function exited with code 1: plain failure'}})):
            with self.subTest(mode=mode):
                name, folder, _, proc = self.send(endpoint=mode)
                result, body, row = self.receive(name, folder)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(body, expected)
                self.assertEqual(result.stderr, 'aos-llm: error: %s %s\n' % (
                    expected['error']['code'], expected['error']['msg']))
                self.assertEqual(row['code'], expected['error']['code'])
                self.assertEqual(row['seen_at'], proc['seen_at'])
                self.assertIsNone(row['child'])
                self.assertIs(row['switched'], False)


if __name__ == '__main__':
    unittest.main()
