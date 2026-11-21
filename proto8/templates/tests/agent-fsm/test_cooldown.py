# Verify the wait cell's cooldown after outside failures (two-machines 06) with a fake aos-llm on PATH.
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
os.environ.setdefault("AOS_HOME", str(Path(__file__).resolve().parents[3]))   # 路徑規則一（11-17）：範本的格只經 AOS_HOME 找 lib，測試給它這份 proto8

CELLS = Path(__file__).resolve().parents[2] / 'agent-fsm'   # 範本本身（測試 11-10 起搬到 templates/tests/<範本名>/）
sys.path.insert(0, str(CELLS.parents[1] / 'py'))
from aos.agentlib import cooldown  # noqa: E402


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
        self.env = dict({k: v for k, v in os.environ.items() if not k.startswith('AOS_') or k == 'AOS_HOME'}, AOS_STACK=str(self.stack), AOS_CD=str(self.definition),
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

    def lettered(self):
        """回答配對：history 那則 user 是信 L1 交進來的（帶 aos.letter、在 pending）；request.json 照舊是剝過 aos 的那則。"""
        (self.stack / 'history.jsonl').write_text(json.dumps({'role': 'user', 'content': 'hi', 'aos': {'letter': 'L1'}}) + '\n')
        (self.stack / 'letters.json').write_text(json.dumps({'pending': ['L1'], 'dropped': []}))
        request = self.stack / 'think/request.json'
        request.write_text(request.read_text())          # 請求在 history 之後寫（不然 mtime 就判過期）

    def letters(self):
        return json.loads((self.stack / 'letters.json').read_text())

    def past(self):
        rec = self.record()
        rec['until'] = cooldown.iso(time.time() - 5)
        (self.stack / cooldown.NAME).write_text(json.dumps(rec))

    def test_brain_failed_cools_then_retries_and_clears(self):
        self.lettered()
        self.wait(10)                                    # 寄出（history 最後一則剝掉 aos 才跟 request 比：不算過期）
        self.capture_failures()
        permanent = json.dumps({'error': {'code': 'EndpointFailed', 'msg': 'unauthorized', 'retry': False, 'status': 401}})
        result = self.wait(1, FAKE_RECV='1', FAKE_REPLY=permanent)  # kernel 永久錯誤
        self.assertIs(self.events()[-1]['retry'], False)
        self.assertEqual((self.events()[-1]['code'], self.events()[-1]['status'], self.events()[-1]['attempt']),
                         ('EndpointFailed', 401, 1))
        self.assertIn('agent-fsm: error: BrainFailed', result.stderr)
        self.assertEqual(self.letters()['pending'], ['L1'])   # 腦失敗：pending 留著（head-tools 裁 5a）
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
        self.wait(1, FAKE_RECV='1', FAKE_REPLY=permanent)
        self.assertEqual(self.events()[-1]['attempt'], 2)
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
        self.assertEqual(last, {'role': 'assistant', 'content': 'ok', 'aos': {'answer_to': ['L1']}})   # 失敗前交出的信算進這則
        self.assertEqual(self.letters()['pending'], [])

    def capture_failures(self):
        self.event_log = self.root / 'events.jsonl'
        self.command('capture', '''import json, os, sys
with open(os.environ['EVENT_LOG'], 'a') as f:
    f.write(json.dumps(json.load(sys.stdin)) + '\\n')
''')
        self.env['EVENT_LOG'] = str(self.event_log)
        path = self.definition / 'interfaces.json'
        files = json.loads(path.read_text())
        files['hookeds'] = 'hookeds.json'
        path.write_text(json.dumps(files))
        (self.definition / 'hookeds.json').write_text(json.dumps({
            'capture': {'event': 'brain_failed', 'handler': str(self.root / 'capture')}
        }))

    def events(self):
        return [json.loads(line) for line in self.event_log.read_text().splitlines()]

    def temporary(self, **fields):
        error = dict(code='ReplyBad', msg='no choices', retry=True, status=200)
        error.update(fields)
        return self.wait(10, FAKE_RECV='1', FAKE_REPLY=json.dumps({'error': error}))

    def test_temporary_retries_same_request_without_history_change_then_clears(self):
        self.capture_failures()
        request = (self.stack / 'think/request.json').read_bytes()
        history = (self.stack / 'history.jsonl').read_bytes()
        for attempt, gap in enumerate((30, 60, 120), 1):
            self.wait(10)
            result = self.temporary()
            self.assertNotIn('agent-fsm: error:', result.stderr)
            self.assertIn('attempt %d' % attempt, result.stderr)
            rec = self.record()
            self.assertEqual((rec['failures'], rec['code'], rec['dropped'], self.gap(rec)),
                             (attempt, 'BrainFailed', 0, gap))
            event = self.events()[-1]
            self.assertEqual((event['name'], event['code'], event['retry'], event['attempt'], event['wait_s'], event['status']),
                             ('BrainFailed', 'ReplyBad', True, attempt, gap, 200))
            self.assertEqual(event['error']['msg'], 'no choices')
            self.assertEqual((self.stack / 'history.jsonl').read_bytes(), history)
            self.assertEqual((self.stack / 'think/request.json').read_bytes(), request)
            self.wait(10)
            self.assertEqual(self.sends(), attempt)
            self.past()
        self.wait(10)
        sent = [json.loads(line).encode() for line in (self.root / 'requests.jsonl').read_text().splitlines()]
        self.assertEqual(sent, [request] * 4)
        self.wait(0)
        self.assertFalse((self.stack / cooldown.NAME).exists())
        rows = [json.loads(line) for line in (self.stack / 'observed.jsonl').read_text().splitlines()]
        self.assertEqual(sum(row['kind'] == 'think' for row in rows), 4)

    def test_temporary_has_no_attempt_limit(self):
        self.capture_failures()
        for _ in range(20):
            cooldown.fail(str(self.stack), 'BrainFailed', 'earlier failure')
        self.past()
        self.wait(10)
        self.temporary()
        self.assertEqual((self.record()['failures'], self.gap(self.record())), (21, 1800))
        self.assertEqual(self.events()[-1]['attempt'], 21)

    def test_retry_after_bounds_types_and_repeated_count(self):
        self.capture_failures()
        cases = [(100, 100), (5, 30), (99999, 1800), (100.5, 100.5),
                 (True, 30), (False, 30), (-5, 30), ('100', 30), (None, 30), ([], 30)]
        for value, gap in cases:
            with self.subTest(value=value):
                cooldown.clear(str(self.stack))
                self.wait(10)
                self.temporary(retry_after_s=value)
                self.assertAlmostEqual(self.gap(self.record()), gap, delta=1)
                self.assertEqual(self.events()[-1]['wait_s'], gap)
        cooldown.clear(str(self.stack))
        for attempt in (1, 2):
            self.wait(10)
            self.temporary(retry_after_s=100)
            self.assertEqual((self.record()['failures'], self.gap(self.record())), (attempt, 100))
            self.assertEqual(self.events()[-1]['attempt'], attempt)
            self.past()

    def test_other_cooldown_codes_reset_temporary_attempt(self):
        self.capture_failures()
        for code in ('BudgetMissing', 'SendFailed'):
            with self.subTest(code=code):
                cooldown.clear(str(self.stack))
                for _ in range(3):
                    cooldown.fail(str(self.stack), code, 'earlier failure')
                self.past()
                self.wait(10)
                self.temporary()
                self.assertEqual((self.record()['failures'], self.gap(self.record())), (1, 30))
                self.assertEqual(self.events()[-1]['attempt'], 1)

    def test_retry_requires_boolean_true_and_missing_retry_stops(self):
        self.capture_failures()
        for fields in ({'retry': 'true'}, {'retry': 1}, {'retry': None}, {}):
            with self.subTest(fields=fields):
                cooldown.clear(str(self.stack))
                self.wait(10)
                error = dict(code='RequestBad', msg='invalid request', **fields)
                self.wait(1, FAKE_RECV='1', FAKE_REPLY=json.dumps({'error': error}))
                event = self.events()[-1]
                self.assertIs(event['retry'], False)
                self.assertEqual(event['attempt'], 1)
                self.assertNotIn('wait_s', event)
                self.assertNotIn('status', event)

    def test_endpoint_and_tuning_changes_clear_brain_failed_cooldown(self):
        self.capture_failures()
        for cfg in ({'model': 'other'}, {'model': 'local', 'temperature': 0.5}):
            with self.subTest(cfg=cfg):
                (self.definition / 'llm.json').write_text('{"model":"local"}')
                self.wait(10)
                self.temporary()
                (self.definition / 'llm.json').write_text(json.dumps(cfg))
                self.wait(11)
                self.assertFalse((self.stack / cooldown.NAME).exists())
                body = json.loads((self.stack / 'think/request.json').read_text())
                body['endpoint'] = cfg['model']
                if 'temperature' in cfg:
                    body['request']['temperature'] = cfg['temperature']
                (self.stack / 'think/request.json').write_text(json.dumps(body))
                sends = self.sends()
                self.wait(10)
                self.assertEqual(self.sends(), sends + 1)
                self.wait(0)
                (self.stack / 'history.jsonl').write_text('{"role":"user","content":"hi"}\n')
                (self.stack / 'think/request.json').write_text(json.dumps(
                    {'endpoint': 'local', 'request': {'messages': [{'role': 'user', 'content': 'hi'}]}}))

    def test_budget_missing_cools_then_retries_same_request_and_clears(self):
        msg = 'budget for this window (day) is used up; not run'
        request = (self.stack / 'think/request.json').read_text()
        history = (self.stack / 'history.jsonl').read_text()
        observed = self.stack / 'observed.jsonl'
        observed.write_text(json.dumps({'kind': 'think', 'letter': 'previous'}) + '\n')
        before = observed.read_text()
        self.lettered()
        history = (self.stack / 'history.jsonl').read_text()
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
        self.assertEqual(last, {'role': 'assistant', 'content': 'ok', 'aos': {'answer_to': ['L1']}})
        self.assertEqual(self.letters()['pending'], [])
        self.assertEqual(len(observed.read_text().splitlines()), 2)

    def priority_request(self, priority):
        path = self.stack / 'think/request.json'
        body = json.loads(path.read_text())
        body['priority'] = priority
        path.write_text(json.dumps(body))
        return path.read_bytes()

    def assert_deadline_rebuild(self, raw):
        request = self.stack / 'think/request.json'
        before_request = request.read_bytes()
        cooling = self.stack / cooldown.NAME
        before_cooldown = cooling.read_bytes() if cooling.exists() else None
        sends = self.sends()
        result = self.wait(11)
        self.assertEqual(result.stderr.strip(),
                         "agent-fsm: warning: the request's deadline %s has passed (or passes within 5 s); "
                         "not sending it, going back to think to rebuild the request" % raw)
        self.assertEqual(self.sends(), sends)
        self.assertFalse((self.stack / 'think/pending.txt').exists())
        self.assertEqual(request.read_bytes(), before_request)
        self.assertEqual(cooling.read_bytes() if cooling.exists() else None, before_cooldown)
        return result

    def test_past_epoch_deadline_rebuilds_without_sending(self):
        raw = time.time() - 60
        self.priority_request({'level': 'normal', 'deadline': raw})
        cooldown.fail(str(self.stack), 'BudgetMissing', 'budget used up')
        self.past()
        self.assert_deadline_rebuild(raw)
        self.assertFalse(self.calls.exists())
        self.assertFalse((self.root / 'requests.jsonl').exists())
        self.assertFalse((self.stack / 'think/reply').exists())
        self.assertFalse((self.stack / 'think/sent.json').exists())
        self.assertFalse((self.stack / 'observed.jsonl').exists())

    def test_past_iso_deadline_with_offset_rebuilds(self):
        raw = self.iso_at(time.time() - 60)
        self.priority_request({'level': 'normal', 'deadline': raw})
        self.assert_deadline_rebuild(raw)
        self.assertFalse(self.calls.exists())
        self.assertFalse((self.root / 'requests.jsonl').exists())

    def test_past_utc_z_deadline_rebuilds(self):
        raw = datetime.datetime.fromtimestamp(time.time() - 60, datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        self.priority_request({'level': 'normal', 'deadline': '  ' + raw + '  '})
        self.assert_deadline_rebuild('  ' + raw + '  ')
        self.assertFalse(self.calls.exists())
        self.assertFalse((self.root / 'requests.jsonl').exists())

    def test_pending_request_with_passed_deadline_still_receives(self):
        self.wait(10)
        self.priority_request({'level': 'normal', 'deadline': time.time() - 60})
        result = self.wait(0)
        self.assertNotIn("the request's deadline", result.stderr)
        self.assertEqual(self.sends(), 1)
        self.assertFalse((self.stack / 'think/pending.txt').exists())
        last = json.loads((self.stack / 'history.jsonl').read_text().splitlines()[-1])
        self.assertEqual(last, {'role': 'assistant', 'content': 'ok'})

    def test_deadline_within_three_seconds_rebuilds(self):
        raw = time.time() + 3
        self.priority_request({'level': 'normal', 'deadline': raw})
        self.assert_deadline_rebuild(raw)
        self.assertFalse(self.calls.exists())

    def test_future_epoch_and_iso_deadlines_send(self):
        future = time.time() + 3600
        utc = datetime.datetime.fromtimestamp(future, datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
        for raw in (future, int(future), self.iso_at(future), utc, '  ' + self.iso_at(future) + '  '):
            with self.subTest(deadline=raw):
                pending = self.stack / 'think/pending.txt'
                pending.write_text('')
                request = self.priority_request({'level': 'normal', 'deadline': raw})
                sends = self.sends()
                self.wait(10)
                self.assertEqual(self.sends(), sends + 1)
                self.assertEqual(pending.read_text(), 'letter-1\n')
                sent = (self.root / 'requests.jsonl').read_text().splitlines()
                self.assertEqual(json.loads(sent[-1]), request.decode())

    def test_missing_or_unparseable_deadline_is_left_to_kernel(self):
        cases = [{}, {'priority': 'high'}, {'priority': {'level': 'normal'}},
                 {'priority': {'deadline': 'garbage'}}, {'priority': {'deadline': '2000-01-01T00:00:00'}},
                 {'priority': {'deadline': True}}, {'priority': {'deadline': False}},
                 {'priority': {'deadline': None}}, {'priority': {'deadline': []}},
                 {'priority': {'deadline': {}}}, {'priority': {'deadline': float('nan')}},
                 {'priority': {'deadline': float('inf')}}, {'priority': {'deadline': float('-inf')}}]
        for fields in cases:
            with self.subTest(fields=fields):
                pending = self.stack / 'think/pending.txt'
                pending.write_text('')
                body = {'endpoint': 'local', 'request': {'messages': [{'role': 'user', 'content': 'hi'}]}}
                body.update(fields)
                request = self.stack / 'think/request.json'
                request.write_text(json.dumps(body))
                before = request.read_bytes()
                sends = self.sends()
                result = self.wait(10)
                self.assertEqual(self.sends(), sends + 1)
                self.assertEqual(pending.read_text(), 'letter-1\n')
                self.assertNotIn("the request's deadline", result.stderr)
                self.assertEqual(request.read_bytes(), before)
                self.assertFalse((self.stack / cooldown.NAME).exists())

    def test_passed_deadline_while_cooling_waits_without_warning(self):
        self.priority_request({'level': 'normal', 'deadline': time.time() - 60})
        cooldown.fail_until(str(self.stack), 'BudgetMissing', 'budget used up', time.time() + 3600)
        before_request = (self.stack / 'think/request.json').read_bytes()
        before_cooldown = (self.stack / cooldown.NAME).read_bytes()
        result = self.wait(10)
        self.assertEqual(result.stderr, '')
        self.assertEqual(self.sends(), 0)
        self.assertFalse((self.stack / 'think/pending.txt').exists())
        self.assertFalse((self.root / 'requests.jsonl').exists())
        self.assertEqual((self.stack / 'think/request.json').read_bytes(), before_request)
        self.assertEqual((self.stack / cooldown.NAME).read_bytes(), before_cooldown)

    def test_due_budget_missing_cooldown_with_passed_deadline_rebuilds(self):
        self.refuse(window='hour', resets_at=self.iso_at(time.time() + 3600))
        raw = time.time() - 60
        self.priority_request({'level': 'normal', 'deadline': raw})
        self.past()
        sent = (self.root / 'requests.jsonl').read_bytes()
        self.assert_deadline_rebuild(raw)
        self.assertEqual(self.sends(), 1)
        self.assertEqual((self.root / 'requests.jsonl').read_bytes(), sent)

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
        cooldown.fail(str(self.stack), 'SendFailed', 'x')
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

    # ---- cooldown-1118: retry and error fields (使用者 11-18 裁「寫進狀態檔」)
    def fields(self):
        rec = self.record()
        return rec.get('retry'), rec.get('error')

    def test_fields_permanent_brain_failed_records_kernel_error_and_retry_false(self):
        self.wait(10)
        reply = json.dumps({'error': {'code': 'EndpointFailed', 'msg': 'HTTP 400:\n model not supported', 'retry': False,
                                      'status': 400}})
        self.wait(1, FAKE_RECV='1', FAKE_REPLY=reply)
        rec = self.record()
        self.assertEqual((rec['code'], rec['reason']), ('BrainFailed', 'aos-llm recv exited 1'))   # old fields unchanged
        self.assertEqual(self.fields(), (False, {'code': 'EndpointFailed', 'msg': 'HTTP 400: model not supported'}))

    def test_fields_temporary_brain_failed_is_retry_true(self):
        self.wait(10)
        self.temporary(code='EndpointFailed', msg='HTTP 503: unavailable')
        self.assertEqual(self.fields(), (True, {'code': 'EndpointFailed', 'msg': 'HTTP 503: unavailable'}))

    def test_fields_unreadable_reply_is_retry_false_without_error(self):
        self.wait(10)
        self.wait(1, FAKE_RECV='1', FAKE_REPLY='not json')
        self.assertEqual(self.fields(), (False, None))

    def test_fields_send_failed_and_budget_missing_are_retry_true(self):
        self.wait(10, FAKE_SEND='3')
        self.assertEqual(self.fields(), (True, None))
        cooldown.clear(str(self.stack))
        self.refuse()
        self.assertEqual(self.fields(), (True, {'code': 'BudgetMissing', 'msg': self.MSG}))

    def test_fields_are_optional_when_read(self):
        stack = str(self.stack)
        rec = cooldown.fail(stack, 'X', 'r', now=1000)
        self.assertNotIn('retry', rec)
        self.assertNotIn('error', rec)
        self.assertEqual(cooldown.read(stack), rec)              # a file without them reads as before
        rec = cooldown.fail(stack, 'X', 'r', now=1001, retry=True, error={'code': 'E', 'msg': 'm', 'status': 1})
        self.assertEqual((rec['retry'], rec['error']), (True, {'code': 'E', 'msg': 'm'}))
        rec = cooldown.fail(stack, 'X', 'r', now=1002)            # each failure rewrites the whole record
        self.assertNotIn('retry', rec)
        for bad in ({'retry': 'yes'}, {'error': 'E'}, {'error': {'msg': 'no code'}}, {'error': {'code': 'E', 'msg': 3}}):
            with self.subTest(bad=bad):
                (self.stack / cooldown.NAME).write_text(json.dumps(dict(rec, **bad)))
                got = cooldown.read(stack)
                self.assertEqual(got, rec)                       # only the bad optional field is dropped
        self.assertIsNone(cooldown.error_of({'code': ''}))
        self.assertEqual(cooldown.error_of({'code': 'E'}), {'code': 'E', 'msg': ''})


if __name__ == '__main__':
    unittest.main()
