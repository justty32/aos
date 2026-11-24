# Verify aos-mcp runs tools/call at the same time (11-24 home-listen-1124: a long subagent listen held every other call):
# a slow call does not hold a fast one, a "parallel": false tool runs one call at a time, notifications/cancelled stops a call (no reply).
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

PROTO = Path(__file__).resolve().parents[4]
MCP = PROTO / 'bin' / 'aos-mcp'
FAKE = '''import json, os, sys, time
argv = sys.argv[1:]                               # --file REG ls --json | --file REG call NAME
if argv[2] == "ls":
    print(json.dumps([{"name": "slow", "tooldef": {}, "metainfo": {"timeout_ms": 0}},
                      {"name": "fast", "tooldef": {}, "metainfo": {}},
                      {"name": "solo", "tooldef": {}, "metainfo": {"parallel": False, "timeout_ms": 0}}]))
    sys.exit(0)
name, args = argv[3], json.load(sys.stdin)
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write("start %s %s\\n" % (name, args.get("n")))
time.sleep(args.get("sleep", 0))
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write("end %s %s\\n" % (name, args.get("n")))
print("done %s %s" % (name, args.get("n")))
'''


def call(mid, name, **args):
    return {'jsonrpc': '2.0', 'id': mid, 'method': 'tools/call', 'params': {'name': name, 'arguments': args}}


class Concurrent(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='aos-mcp-concurrent-'))
        fake = self.root / 'bin' / 'aos-tools'
        fake.parent.mkdir()
        fake.write_text('#!' + sys.executable + '\n' + FAKE)
        fake.chmod(0o755)
        self.reg = self.root / 'tools.json'
        self.reg.write_text('{}')
        self.log = self.root / 'calls.log'
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}
        self.env.update(PATH=os.pathsep.join([str(fake.parent), self.env['PATH']]), FAKE_LOG=str(self.log),
                        PYTHONDONTWRITEBYTECODE='1')
        self.p = subprocess.Popen([str(MCP), '--ws', str(self.root), '--stack', str(self.root / 'st'), str(self.reg)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)

    def tearDown(self):
        if self.p.poll() is None:
            self.p.kill()
            self.p.wait()
        for f in (self.p.stdin, self.p.stdout, self.p.stderr):
            f.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def send(self, *msgs):
        for m in msgs:
            self.p.stdin.write(json.dumps(m) + '\n')
        self.p.stdin.flush()

    def read(self):
        return json.loads(self.p.stdout.readline())

    def finish(self):
        self.p.stdin.close()
        rest = self.p.stdout.read()
        self.assertEqual(self.p.wait(timeout=30), 0, self.p.stderr.read())
        return [json.loads(line) for line in rest.splitlines() if line.strip()]

    def lines(self):
        return self.log.read_text().splitlines()

    def test_slow_call_does_not_hold_a_fast_one(self):
        t0 = time.monotonic()
        self.send(call(2, 'slow', sleep=4, n=1), call(3, 'fast', n=1))
        first = self.read()
        self.assertEqual(first['id'], 3)
        self.assertLess(time.monotonic() - t0, 3)
        self.assertEqual(first['result']['content'][0]['text'], 'done fast 1\n')
        self.assertEqual([m['id'] for m in self.finish()], [2])

    def test_parallel_false_tool_runs_one_call_at_a_time(self):
        self.send(call(2, 'solo', sleep=1, n=1), call(3, 'solo', sleep=1, n=2))
        got = sorted(m['id'] for m in self.finish())
        self.assertEqual(got, [2, 3])
        log = self.lines()
        self.assertEqual(len(log), 4)
        self.assertTrue(log[0].startswith('start') and log[1].startswith('end') and log[0][6:] == log[1][4:], log)

    def test_cancelled_call_is_stopped_and_not_answered(self):
        self.send(call(2, 'slow', sleep=30, n=1))
        for _ in range(100):                     # 等它真的起來
            if self.log.exists():
                break
            time.sleep(0.05)
        t0 = time.monotonic()
        self.send({'jsonrpc': '2.0', 'method': 'notifications/cancelled', 'params': {'requestId': 2}},
                  {'jsonrpc': '2.0', 'id': 3, 'method': 'ping'})
        self.assertEqual(self.read()['id'], 3)
        self.assertEqual(self.finish(), [])
        self.assertLess(time.monotonic() - t0, 10)
        self.assertEqual(self.lines(), ['start slow 1'])


if __name__ == '__main__':
    unittest.main()
