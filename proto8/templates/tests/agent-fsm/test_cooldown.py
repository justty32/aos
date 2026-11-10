# Verify the wait cell's cooldown after outside failures (two-machines 06) with a fake aos-llm on PATH.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

CELLS = Path(__file__).resolve().parents[2] / 'agent-fsm'   # 範本本身（測試 11-10 起搬到 templates/tests/<範本名>/）
sys.path.insert(0, str(CELLS.parents[1] / 'lib'))
from agent import cooldown  # noqa: E402


class Cooldown(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = self.root / 'stack'
        (self.stack / 'think').mkdir(parents=True)
        self.definition = self.root / 'def'
        self.definition.mkdir()
        (self.definition / 'interfaces.json').write_text(json.dumps({'aos-agent': {'llm': 'llm.json'}}))
        (self.definition / 'llm.json').write_text('{"model":"local"}')
        self.calls = self.root / 'calls.txt'
        self.env = dict({k: v for k, v in os.environ.items() if not k.startswith('AOS_')}, AOS_STACK=str(self.stack), AOS_CD=str(self.definition),
                        FAKE_CALLS=str(self.calls), FAKE_SEND='0', FAKE_RECV='0',
                        PATH=str(self.root) + os.pathsep + os.environ['PATH'])
        self.command('aos-llm', '''import json, os, sys
with open(os.environ['FAKE_CALLS'], 'a') as f:
    f.write(sys.argv[1] + '\\n')
if sys.argv[1] == 'send':
    sys.stdin.read()
    print('letter-1')
    sys.exit(int(os.environ['FAKE_SEND']))
code = int(os.environ['FAKE_RECV'])
if code == 0:
    print(json.dumps({'message': {'role': 'assistant', 'content': 'ok'}, 'endpoint': 'local'}))
elif code == 1:
    print('aos-llm: error: EndpointFailed fake', file=sys.stderr)
sys.exit(code)
''')
        self.command('aos-post', 'pass\n')
        (self.stack / 'history.jsonl').write_text(json.dumps({'role': 'user', 'content': 'hi'}) + '\n')
        (self.stack / 'think/request.json').write_text(json.dumps(
            {'endpoint': 'local', 'request': {'messages': [{'role': 'user', 'content': 'hi'}]}}))

    def command(self, name, body):
        path = self.root / name
        path.write_text('#!' + sys.executable + '\n' + body)
        path.chmod(0o755)

    def wait(self, code, **env):
        result = subprocess.run([sys.executable, str(CELLS / 'wait.py')], env=dict(self.env, **env),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, code, result.stderr)
        return result

    def sends(self):
        return self.calls.read_text().split().count('send') if self.calls.exists() else 0

    def record(self):
        return json.loads((self.stack / cooldown.NAME).read_text())

    def gap(self, rec):
        return cooldown.parse(rec['until']) - cooldown.parse(rec['at'])

    def past(self):
        rec = self.record()
        rec['until'] = cooldown.iso(time.time() - 5)
        (self.stack / cooldown.NAME).write_text(json.dumps(rec))

    def test_brain_failed_cools_then_retries_and_clears(self):
        self.wait(10)                                    # 寄出
        result = self.wait(1, FAKE_RECV='1')             # kernel 回錯
        self.assertIn('agent-fsm: error: BrainFailed', result.stderr)
        rec = self.record()
        self.assertEqual((rec['failures'], rec['code'], rec['dropped']), (1, 'BrainFailed', 0))
        self.assertEqual(self.gap(rec), 30)
        self.assertFalse((self.stack / 'think/pending.txt').exists())
        self.wait(10)                                    # 冷卻中：不寄
        self.assertEqual(self.sends(), 1)
        self.assertFalse((self.stack / 'think/pending.txt').exists())
        self.past()
        self.wait(10)                                    # 到了：重寄同一份
        self.assertEqual(self.sends(), 2)
        self.wait(1, FAKE_RECV='1')
        rec = self.record()
        self.assertEqual(rec['failures'], 2)
        self.assertEqual(self.gap(rec), 60)
        self.past()
        self.wait(10)
        self.wait(10, FAKE_RECV='10')                    # 還沒回
        self.assertTrue((self.stack / cooldown.NAME).exists())
        self.wait(0)                                     # 好的回信
        self.assertFalse((self.stack / cooldown.NAME).exists())
        last = json.loads((self.stack / 'history.jsonl').read_text().splitlines()[-1])
        self.assertEqual(last, {'role': 'assistant', 'content': 'ok'})

    def test_send_failed_cools(self):
        result = self.wait(10, FAKE_SEND='3')             # 11-10 TS：send 失敗＝warning、留在 wait，不停
        self.assertIn('agent-fsm: warning: aos-llm send exited 3', result.stderr)
        self.assertNotIn('error:', result.stderr)
        rec = self.record()
        self.assertEqual((rec['failures'], rec['code']), (1, 'SendFailed'))
        self.assertEqual(self.gap(rec), 30)
        self.wait(10)
        self.assertEqual(self.sends(), 1)

    def test_reply_bad_does_not_cool(self):
        self.wait(10)
        self.command('aos-llm', "import sys\nprint('not json')\n")
        self.wait(1)
        self.assertFalse((self.stack / cooldown.NAME).exists())

    def test_cooldown_unwritable_only_warns(self):
        (self.stack / cooldown.NAME).mkdir()             # 擋住改名：寫不成
        result = self.wait(10, FAKE_SEND='2')
        self.assertIn('agent-fsm: warning: cannot write', result.stderr)
        self.assertIn('agent-fsm: warning: aos-llm send exited 2', result.stderr)

    def test_endpoint_mismatch_still_rebuilds_while_cooling(self):
        cooldown.fail(str(self.stack), 'BrainFailed', 'x')
        (self.definition / 'llm.json').write_text('{"model":"other"}')
        self.wait(11)


if __name__ == '__main__':
    unittest.main()
