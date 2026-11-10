# Verify task context, tool limits, and best-effort observations with local fake commands.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

CELLS = Path(__file__).resolve().parents[2] / 'agent-fsm'   # 範本本身（測試 11-10 起搬到 templates/tests/<範本名>/）
CALL = {'id': 'one', 'type': 'function',
        'function': {'name': 'echo', 'arguments': '{"text":"雪"}'}}


class Cells(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = self.root / 'stack'
        self.stack.mkdir()
        self.definition = self.root / 'def'
        self.definition.mkdir()
        (self.definition / 'interfaces.json').write_text(json.dumps(
            {'aos-agent': {'tools': 'tools.json', 'llm': 'llm.json'}}))
        (self.definition / 'tools.json').write_text('{}')
        (self.definition / 'llm.json').write_text('{"model":"local"}')
        self.env = dict(os.environ, AOS_STACK=str(self.stack), AOS_CD=str(self.definition),
                        PATH=str(self.root) + os.pathsep + os.environ['PATH'])
        self.command('aos-tools', '''import json, sys
if 'ls' in sys.argv:
    print(json.dumps([{'name':'echo','path':'/fake/echo','tooldef':{'parameters':{'type':'object'}}}]))
else:
    sys.stdout.buffer.write(sys.stdin.buffer.read())
''')
        self.command('aos-llm', '''import json, sys
if sys.argv[1] == 'send':
    print('local-request')
else:
    assert '--full' in sys.argv
    print(json.dumps({'message':{'role':'assistant','content':'unchanged','extra':4},
                      'model':'fake','usage':{'prompt_tokens':9},'endpoint':'local'}))
''')
        self.command('aos-post', 'pass\n')

    def command(self, name, body):
        path = self.root / name
        path.write_text('#!' + sys.executable + '\n' + body)
        path.chmod(0o755)

    def history(self, messages):
        (self.stack / 'history.jsonl').write_text(''.join(json.dumps(m) + '\n' for m in messages))

    def run_cell(self, name, *args, code=0):
        result = subprocess.run([sys.executable, str(CELLS / (name + '.py')), *args],
                                env=self.env, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, code, result.stderr)
        return result

    def request(self):
        return json.loads((self.stack / 'think/request.json').read_text())['request']

    def test_model_and_tuning_keys(self):
        """11-10 晚使用者「把fsm認的endpoint這個key，也改名爲model吧」「agent能調的，就是一些與快取無關的」。"""
        self.history([{'role': 'user', 'content': 'hi'}])
        (self.stack / 'llm.json').write_text(json.dumps({'temperature': '0.2', 'max_tokens': '64', 'stop': 'END', 'top_k': '3'}))
        self.run_cell('brain')
        body = json.loads((self.stack / 'think/request.json').read_text())
        self.assertEqual(body['endpoint'], 'local')
        self.assertEqual((body['request']['temperature'], body['request']['max_tokens'], body['request']['stop']), (0.2, 64, ['END']))
        self.assertNotIn('top_k', body['request'])
        (self.stack / 'llm.json').write_text(json.dumps({'temperature': 'hot'}))
        self.assertIn('CfgBad temperature in llm.json must be a number', self.run_cell('brain', code=1).stderr)
        (self.stack / 'llm.json').write_text(json.dumps({'temperature': '0.5'}))
        self.run_cell("wait", code=11)   # 調整鍵改了＝brain 重組再寄（wait.py REBUILD）
        (self.stack / 'llm.json').write_text(json.dumps({'temperature': '0.2', 'max_tokens': '64', 'stop': 'END'}))
        r = subprocess.run([sys.executable, str(CELLS / 'wait.py')], env=self.env, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(r.returncode, 11, r.stderr)                   # 跟寄出的一樣＝照寄

    def test_context_and_tool_limits(self):
        old = [{'role':'user','content':'old'}, {'role':'assistant','tool_calls':[CALL]},
               {'role':'tool','tool_call_id':'one','content':'old result'}]
        task = [{'role':'user','content':'new'}, {'role':'assistant','tool_calls':[CALL, CALL]},
                {'role':'tool','tool_call_id':'one','content':'new result'}]
        self.history(old + task)
        self.run_cell('brain')
        self.assertEqual(self.request()['messages'], old + task)
        self.assertIn('tools', self.request())
        self.run_cell('brain', '--history=task', '--max-tool-calls=3')
        self.assertEqual(self.request()['messages'], task)
        self.assertIn('tools', self.request())
        self.run_cell('brain', '--max-tool-calls', '2')
        self.assertNotIn('tools', self.request())
        self.run_cell('brain', '--max-tool-calls', '0')
        self.assertNotIn('tools', self.request())
        self.history([{'role':'tool','content':'without user'}])
        self.run_cell('brain', '--history', 'task')
        self.assertEqual(len(self.request()['messages']), 1)
        for args in [('--history','bad'), ('--max-tool-calls','-1'), ('--max-tool-calls','1.5')]:
            self.run_cell('brain', *args, code=1)

    def test_wait_observation_preserves_message(self):
        self.history([{'role':'user','content':'hello'}])
        self.run_cell('brain')
        self.run_cell('wait', code=10)
        letter = (self.stack / 'think/pending.txt').read_text().strip()
        self.run_cell('wait')
        message = json.loads((self.stack / 'history.jsonl').read_text().splitlines()[-1])
        self.assertEqual(message, {'role':'assistant','content':'unchanged','extra':4})
        record = json.loads((self.stack / 'observed.jsonl').read_text().splitlines()[-1])
        self.assertEqual((record['kind'], record['endpoint'], record['model']), ('think','local','fake'))
        self.assertEqual(record['letter'], letter)
        self.assertEqual(record['letter'], 'local-request')
        self.assertEqual(record['usage'], {'prompt_tokens':9})
        self.assertGreaterEqual(record['elapsed_ms'], 0)

    def test_missing_or_bad_timing_only_warns(self):
        for timing in (None, 'broken', '[]', '{}', '{"started_ns":"bad"}'):
            with self.subTest(timing=timing):
                self.history([{'role':'user','content':'hello'}])
                self.run_cell('brain')
                self.run_cell('wait', code=10)
                path = self.stack / 'think/sent.json'
                if timing is None:
                    path.unlink()
                else:
                    path.write_text(timing)
                result = self.run_cell('wait')
                self.assertIn('warning: cannot read think timing:', result.stderr)
                record = json.loads((self.stack / 'observed.jsonl').read_text().splitlines()[-1])
                self.assertIsNone(record['elapsed_ms'])
                self.assertEqual(record['letter'], 'local-request')

    def test_pending_without_request_keeps_endpoint(self):
        self.command('aos-llm', "import json,sys\nprint('request' if sys.argv[1]=='send' else json.dumps({'message':{'role':'assistant','content':'ok'}}))\n")
        self.history([{'role':'user','content':'hello'}])
        self.run_cell('brain')
        self.run_cell('wait', code=10)
        (self.stack / 'think/request.json').unlink()
        self.run_cell('wait')
        record = json.loads((self.stack / 'observed.jsonl').read_text().splitlines()[-1])
        self.assertEqual(record['endpoint'], 'local')
        self.assertEqual(record['letter'], 'request')

    def test_tool_bytes_and_no_replay(self):
        self.history([{'role':'assistant','tool_calls':[CALL]}])
        self.run_cell('act')
        record = json.loads((self.stack / 'observed.jsonl').read_text().splitlines()[-1])
        size = len(CALL['function']['arguments'].encode('utf-8'))
        self.assertEqual((record['kind'], record['name'], record['code']), ('tool','echo',0))
        self.assertEqual((record['in_bytes'], record['out_bytes']), (size,size))
        self.run_cell('act')
        self.assertEqual(len((self.stack / 'observed.jsonl').read_text().splitlines()), 2)

    def test_timeout_uses_shared_metainfo(self):
        self.command('aos-tools', "import json,sys,time\nif 'ls' in sys.argv: print(json.dumps([{'name':'echo','path':'/fake/echo','tooldef':{},'metainfo':{'cost':{'time_ms':1},'timeout_ms':{'val':1000}}}]))\nelse: print('started',flush=True); time.sleep(5)\n")
        self.history([{'role':'assistant','tool_calls':[CALL]}])
        started = time.monotonic()
        result = self.run_cell('act')
        self.assertLess(time.monotonic() - started, 2.5)
        message = json.loads((self.stack / 'history.jsonl').read_text().splitlines()[-1])
        self.assertIn('[aos] tool: echo timed out after 1 s', message['content'])
        self.assertIn('started', message['content'])
        self.assertIn('timed out', result.stderr)

    def test_timeout_kills_grandchild_after_leader_exits(self):
        self.command('aos-tools', """import json,os,signal,sys,time
if 'ls' in sys.argv:
    print(json.dumps([{'name':'echo','path':'/fake/echo','tooldef':{},'metainfo':{'timeout_ms':100}}]))
else:
    if os.fork() == 0:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        print('grandchild ready', flush=True)
        time.sleep(30)
    else:
        time.sleep(30)
""")
        self.history([{'role':'assistant','tool_calls':[CALL]}])
        started = time.monotonic()
        self.run_cell('act')
        self.assertGreater(time.monotonic() - started, 2)
        message = json.loads((self.stack / 'history.jsonl').read_text().splitlines()[-1])
        self.assertIn('grandchild ready', message['content'])
        self.assertIn('timed out', message['content'])

    def test_failed_calls_are_observed(self):
        self.command('aos-tools', "import json,sys\nif 'ls' in sys.argv: print(json.dumps([{'name':'echo','path':'/fake/echo','tooldef':{}}]))\nelse: print('failed output'); sys.exit(7)\n")
        self.history([{'role':'assistant','tool_calls':[CALL]}])
        self.run_cell('act')
        record = json.loads((self.stack / 'observed.jsonl').read_text().splitlines()[-1])
        self.assertEqual(record['code'], 7)
        self.command('aos-llm', "import sys\nif sys.argv[1]=='send': print('request')\nelse: print('{\"error\":{\"code\":\"X\",\"msg\":\"y\"}}'); sys.exit(1)\n")
        self.history([{'role':'user','content':'hello'}])
        self.run_cell('brain')
        self.run_cell('wait', code=10)
        self.run_cell('wait', code=1)
        record = json.loads((self.stack / 'observed.jsonl').read_text().splitlines()[-1])
        self.assertEqual(record['kind'], 'think')
        self.assertEqual(record['letter'], 'request')
        self.assertEqual(record['endpoint'], 'local')
        self.assertIsNone(record['usage'])

    def test_observation_write_failure_only_warns(self):
        (self.stack / 'observed.jsonl').mkdir()
        self.history([{'role':'assistant','tool_calls':[CALL]}])
        result = self.run_cell('act')
        self.assertIn('agent-fsm: warning: cannot append to observed.jsonl:', result.stderr)
        self.history([{'role':'user','content':'hello'}])
        self.run_cell('brain')
        self.run_cell('wait', code=10)
        result = self.run_cell('wait')
        self.assertIn('agent-fsm: warning: cannot append to observed.jsonl:', result.stderr)


if __name__ == '__main__':
    unittest.main()
