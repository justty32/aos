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
                        AOS_LLM_KERNEL=str(self.root / 'missing-kernel'),
                        FAKE_CALLS=str(self.calls), FAKE_REQUESTS=str(self.root / 'requests.jsonl'),
                        FAKE_SEND='0', FAKE_RECV='0',
                        PATH=str(self.root) + os.pathsep + os.environ['PATH'])
        self.command('aos-llm', '''import json, os, sys
with open(os.environ['FAKE_CALLS'], 'a') as f:
    f.write(sys.argv[1] + '\\n')
if sys.argv[1] == 'send':
    with open(os.environ['FAKE_REQUESTS'], 'a') as f:
        f.write(json.dumps(sys.stdin.read()) + '\\n')
    print('letter-1')
    sys.exit(int(os.environ['FAKE_SEND']))
code = int(os.environ['FAKE_RECV'])
if code == 0:
    print(json.dumps({'message': {'role': 'assistant', 'content': 'ok'}, 'endpoint': 'local'}))
elif code == 1:
    print(os.environ.get('FAKE_REPLY', ''))
    print(os.environ.get('FAKE_ERROR', 'aos-llm: error: EndpointFailed fake'), file=sys.stderr)
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

    def test_budget_missing_cools_then_retries_same_request_and_clears(self):
        msg = 'budget for this window (day) is used up; not run'
        request = (self.stack / 'think/request.json').read_text()
        history = (self.stack / 'history.jsonl').read_text()
        observed = self.stack / 'observed.jsonl'
        observed.write_text(json.dumps({'kind': 'think', 'letter': 'previous'}) + '\n')
        before = observed.read_text()
        self.wait(10)
        result = self.wait(10, FAKE_RECV='1',
                           FAKE_REPLY=json.dumps({'error': {'code': 'BudgetMissing', 'msg': msg}}),
                           FAKE_ERROR='aos-llm: error: BudgetMissing ' + msg)
        self.assertIn('agent-fsm: warning: BudgetMissing ' + msg, result.stderr)
        self.assertNotIn('agent-fsm: error:', result.stderr)
        rec = self.record()
        self.assertEqual((rec['code'], rec['failures'], rec['dropped']), ('BudgetMissing', 1, 0))
        self.assertEqual(rec['reason'], msg)
        self.assertEqual(self.gap(rec), 30)
        self.assertEqual(observed.read_text(), before)
        self.assertEqual((self.stack / 'history.jsonl').read_text(), history)
        self.assertEqual((self.stack / 'think/request.json').read_text(), request)
        self.assertFalse((self.stack / 'think/pending.txt').exists())
        self.wait(10)
        self.assertEqual(self.sends(), 1)
        self.assertFalse((self.stack / 'think/pending.txt').exists())
        self.past()
        self.wait(10)
        self.assertEqual(self.sends(), 2)
        sent = [json.loads(line) for line in (self.root / 'requests.jsonl').read_text().splitlines()]
        self.assertEqual(sent, [request, request])
        self.wait(0)
        self.assertFalse((self.stack / cooldown.NAME).exists())
        last = json.loads((self.stack / 'history.jsonl').read_text().splitlines()[-1])
        self.assertEqual(last, {'role': 'assistant', 'content': 'ok'})
        self.assertEqual(len(observed.read_text().splitlines()), 2)

    def test_non_budget_error_stdout_stays_brain_failed(self):
        replies = [json.dumps({'error': {'code': 'EndpointFailed', 'msg': 'fake'}}),
                   'not json', '{}', '[]', '{"error":null}', '{"error":"BudgetMissing"}']
        for reply in replies:
            with self.subTest(reply=reply):
                (self.stack / 'think/pending.txt').write_text('letter-1\n')
                result = self.wait(1, FAKE_RECV='1', FAKE_REPLY=reply)
                self.assertIn('agent-fsm: error: BrainFailed', result.stderr)
                self.assertEqual(self.record()['code'], 'BrainFailed')

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
        before = (self.stack / cooldown.NAME).read_text()
        self.wait(11)
        self.assertEqual((self.stack / cooldown.NAME).read_text(), before)
        self.assertEqual(self.sends(), 0)

    def test_endpoint_mismatch_clears_budget_missing_cooldown(self):
        cooldown.fail(str(self.stack), 'BudgetMissing', 'budget used up')
        (self.definition / 'llm.json').write_text('{"model":"other"}')
        self.wait(11)
        self.assertFalse((self.stack / cooldown.NAME).exists())
        self.assertEqual(self.sends(), 0)

    def test_tuning_mismatch_clears_due_budget_missing_cooldown(self):
        cooldown.fail(str(self.stack), 'BudgetMissing', 'budget used up')
        self.past()
        (self.definition / 'llm.json').write_text('{"model":"local","temperature":0.5}')
        self.wait(11)
        self.assertFalse((self.stack / cooldown.NAME).exists())
        self.assertEqual(self.sends(), 0)

    def test_stale_history_rebuild_keeps_budget_missing_cooldown(self):
        cooldown.fail(str(self.stack), 'BudgetMissing', 'budget used up')
        before = (self.stack / cooldown.NAME).read_text()
        (self.stack / 'history.jsonl').write_text('{"role":"user","content":"changed"}\n')
        self.wait(11)
        self.assertEqual((self.stack / cooldown.NAME).read_text(), before)
        self.assertEqual(self.sends(), 0)

    # ---- structured BudgetMissing (resets_at / window)
    MSG = 'budget for this window (hour) is used up; not run'

    def refuse(self, **fields):
        """Send, then let recv answer BudgetMissing with the given extra error fields; returns (result, wall time before the call)."""
        self.wait(10)
        before = time.time()
        error = dict({'code': 'BudgetMissing', 'msg': self.MSG}, **fields)
        result = self.wait(10 if fields.get('window') != 'all' else 1, FAKE_RECV='1', FAKE_REPLY=json.dumps({'error': error}),
                           FAKE_ERROR='aos-llm: error: BudgetMissing ' + self.MSG)
        return result, before

    def iso_at(self, t):
        import datetime
        return datetime.datetime.fromtimestamp(t, datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%dT%H:%M:%S+08:00')

    def test_fail_until_writes_same_record_with_given_until(self):
        stack = str(self.stack)
        cooldown.fail(stack, 'CliFailed', 'x', dropped=2, now=1000)
        rec = cooldown.fail_until(stack, 'BudgetMissing', '  a\n b ', 5000, dropped=1, now=1010)
        self.assertEqual(rec, self.record())
        self.assertEqual((rec['failures'], rec['dropped'], rec['code'], rec['reason']), (2, 3, 'BudgetMissing', 'a b'))
        self.assertEqual((rec['until'], rec['at']), (cooldown.iso(5000), cooldown.iso(1010)))
        self.assertEqual(cooldown.state(stack, now=4999)[0], 'cooling')
        self.assertEqual(cooldown.state(stack, now=5000)[0], 'due')
        self.assertEqual([p.name for p in self.stack.iterdir() if p.name.endswith('.tmp')], [])
        with self.assertRaises(OSError):
            cooldown.fail_until(str(self.root / 'nope'), 'C', 'r', 1)

    def test_budget_missing_resets_at_in_future_cools_until_reset_plus_5(self):
        reset = int(time.time()) + 3600
        result, _ = self.refuse(window='hour', resets_at=self.iso_at(reset))
        rec = self.record()
        self.assertEqual((rec['code'], rec['failures'], rec['dropped']), ('BudgetMissing', 1, 0))
        self.assertEqual(cooldown.parse(rec['until']), reset + 5)
        self.assertIn('agent-fsm: warning: BudgetMissing ' + self.MSG, result.stderr)
        self.assertNotIn('agent-fsm: error:', result.stderr)
        self.wait(10)                                    # still cooling: no resend
        self.assertEqual(self.sends(), 1)

    def test_budget_missing_resets_at_very_near_waits_at_least_30_s(self):
        before = time.time()
        self.refuse(window='hour', resets_at=self.iso_at(int(before) + 3))
        rec = self.record()
        self.assertGreaterEqual(cooldown.parse(rec['until']), before + 29)
        self.assertEqual(self.gap(rec), 30)

    def test_budget_missing_resets_at_just_passed_waits_30_s(self):
        self.refuse(window='day', resets_at=self.iso_at(int(time.time()) - 20))
        rec = self.record()
        self.assertEqual((rec['failures'], self.gap(rec)), (1, 30))

    def test_budget_missing_resets_at_old_garbage_or_missing_uses_steps(self):
        for fields in ({'window': 'day', 'resets_at': self.iso_at(int(time.time()) - 3600)},
                       {'window': 'day', 'resets_at': 'tomorrow noon'},
                       {'window': 'day', 'resets_at': '2099-01-01T00:00:00'},      # no offset
                       {'window': 'day', 'resets_at': 12345},
                       {'window': 'day', 'resets_at': None},
                       {}):
            with self.subTest(fields=fields):
                (self.stack / cooldown.NAME).unlink(missing_ok=True)
                (self.stack / 'think/pending.txt').unlink(missing_ok=True)
                self.refuse(**fields)
                rec = self.record()
                self.assertEqual((rec['failures'], self.gap(rec)), (1, 30))

    def test_budget_missing_failures_keep_counting_with_resets_at(self):
        cooldown.fail(str(self.stack), 'BudgetMissing', 'earlier')
        self.past()
        self.refuse(window='hour', resets_at=self.iso_at(int(time.time()) + 600))
        self.assertEqual(self.record()['failures'], 2)

    def test_budget_missing_window_all_stops_without_cooldown(self):
        request = (self.stack / 'think/request.json').read_text()
        observed = self.stack / 'observed.jsonl'
        result, _ = self.refuse(window='all', resets_at=None, limit='max_calls', max=10, scope='total')
        self.assertEqual(result.stderr.strip().splitlines()[-1],
                         'agent-fsm: error: BudgetMissing ' + self.MSG +
                         ' (window all: it never resets; raise the budget, then start me again)')
        self.assertFalse((self.stack / cooldown.NAME).exists())
        self.assertEqual((self.stack / 'think/request.json').read_text(), request)
        self.assertFalse((self.stack / 'think/pending.txt').exists())
        self.assertFalse(observed.exists())
        self.wait(10)                                    # starting again resends the same request
        self.assertEqual(self.sends(), 2)
        sent = [json.loads(line) for line in (self.root / 'requests.jsonl').read_text().splitlines()]
        self.assertEqual(sent, [request, request])


if __name__ == '__main__':
    unittest.main()
