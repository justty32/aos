# 驗證 listen 等交出去的信時讀問腦失敗紀錄（cooldown.json＋stderr.txt）：身體停在錯上就馬上帶原因結束，會自己重送的只提醒（small-1118）。
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

PROTO = Path(__file__).resolve().parents[4]
BIN = PROTO / 'bin/aos-agent'
SIG = '000000000001.q'
# 照 11-18 實跑的 stderr.txt 寫：fsm 的錯誤行後面還有 brain_notify 的 warning、aos-loop 的 RunFailed（別支的行）。
FSM_STOP = ('aos-llm: error: EndpointFailed HTTP 400: model not supported\n'
            'brain_notify: warning: AOS_NOTIFY_BOX is not set; nobody is told that kid got EndpointFailed\n'
            'agent-fsm: error: BrainFailed aos-llm recv exited 1 (its reason is above)\n'
            'aos-loop: error: RunFailed run 9: fsm.json failed with exit code 1\n')
FSM_RETRY = ('aos-llm: error: EndpointFailed HTTP 503: unavailable\n'
             'brain_notify: warning: AOS_NOTIFY_BOX is not set; nobody is told that kid got EndpointFailed\n'
             'agent-fsm: warning: EndpointFailed HTTP 503: unavailable; attempt 1, the same request is sent again in 30 s\n')


class ListenBrainFailure(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='listen-brain-failure-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.daemon = self.root / 'daemon'
        self.stack = self.daemon / 'procs/kid'
        for name in ('queue/new', 'queue/cur', 'queue/tmp', 'think'):
            (self.stack / name).mkdir(parents=True)
        (self.stack / 'state.json').write_text('{"phase":"running"}')
        (self.stack / 'history.jsonl').write_text(json.dumps({'role': 'user', 'content': 'hi', 'aos': {'letter': SIG}}) + '\n')
        (self.stack / 'letters.json').write_text(json.dumps({'pending': [SIG], 'dropped': []}))
        self.row = {'phase': 'running', 'stack': 'procs/kid', 'def': str(self.root / 'definition')}
        self.write_table()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('AOS_')}

    def write_table(self):
        (self.daemon / 'procs_state.json').write_text(json.dumps({'procs': {'kid': self.row}}))

    def fail(self, stderr, code='BrainFailed', reason='aos-llm recv exited 1'):
        now = time.time()
        iso = lambda t: time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t))
        (self.stack / 'cooldown.json').write_text(json.dumps({
            'failures': 1, 'until': iso(now + 30), 'at': iso(now), 'code': code, 'reason': reason, 'dropped': 0}))
        (self.stack / 'stderr.txt').write_text(stderr)

    def listen(self, timeout='20'):
        start = time.monotonic()
        r = subprocess.run([sys.executable, str(BIN), '-d', str(self.daemon), 'listen', '-t', 'kid', '--letter', SIG,
                            '--timeout-s', timeout], env=self.env, capture_output=True, text=True, timeout=40)
        return r, time.monotonic() - start

    def error_line(self, r):
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(r.stdout, '')
        return next(l for l in r.stderr.splitlines() if 'error: AnswerMissing' in l)

    def test_stopped_on_error_ends_at_once_with_the_reason(self):
        self.fail(FSM_STOP)
        r, took = self.listen()
        line = self.error_line(r)
        self.assertLess(took, 10, r.stderr)
        self.assertIn('stopped on an error before answering', line)
        self.assertIn('aos-llm: error: EndpointFailed HTTP 400: model not supported / agent-fsm: error: BrainFailed', line)
        self.assertNotIn('RunFailed', line)
        self.assertNotIn('brain_notify', line)
        self.assertIn('failure 1 in a row', line)
        self.assertIn('ctl start --target kid', line)
        self.assertIn('listen --target kid --letter %s' % SIG, line)

    def test_stopped_with_auto_restart_says_the_daemon_restarts_it(self):
        self.row['auto_restart'] = True
        self.write_table()
        self.fail(FSM_STOP)
        line = self.error_line(self.listen()[0])
        self.assertIn('the daemon restarts kid', line)

    def test_stopped_row_on_the_table_also_ends_at_once(self):
        self.row.update(phase='stopped', reason='exited 1')
        self.write_table()
        self.fail(FSM_STOP)
        r, took = self.listen()
        self.assertLess(took, 10, r.stderr)
        self.assertIn('stopped on an error before answering', self.error_line(r))

    def test_retrying_failure_warns_once_and_waits(self):
        self.fail(FSM_RETRY, reason='aos-llm recv exited 1 (its reason is above)')
        r, took = self.listen('2.5')
        self.assertGreaterEqual(took, 2)
        warns = [l for l in r.stderr.splitlines() if 'warning:' in l and 'last brain call failed' in l]
        self.assertEqual(len(warns), 1, r.stderr)
        line = self.error_line(r)
        self.assertIn('waited 2.5 s;', line)
        self.assertNotIn('stopped on an error', line)
        self.assertIn("kid's last brain call failed: aos-llm: error: EndpointFailed HTTP 503", line)

    def test_same_body_warning_after_the_error_is_not_stopped(self):
        self.fail(FSM_STOP + FSM_RETRY, reason='aos-llm recv exited 1 (its reason is above)')
        r, took = self.listen('1.5')
        self.assertGreaterEqual(took, 1)
        line = self.error_line(r)
        self.assertNotIn('stopped on an error', line)
        self.assertIn('last brain call failed: aos-llm: error: EndpointFailed HTTP 503', line)

    def test_brain_call_in_flight_is_not_stopped(self):
        self.fail(FSM_STOP)
        (self.stack / 'think/pending.txt').write_text('brain-letter\n')
        r, took = self.listen('1.5')
        self.assertGreaterEqual(took, 1)
        self.assertNotIn('stopped on an error', self.error_line(r))

    def test_other_code_on_the_last_line_is_not_stopped(self):
        self.fail(FSM_STOP, code='SendFailed', reason='aos-llm send exited 1')
        r, took = self.listen('1.5')
        self.assertGreaterEqual(took, 1)
        line = self.error_line(r)
        self.assertNotIn('stopped on an error', line)
        self.assertIn('last brain call failed', line)

    def test_no_cooldown_keeps_the_old_line(self):
        (self.stack / 'stderr.txt').write_text(FSM_STOP)
        line = self.error_line(self.listen('1')[0])
        self.assertIn('waited 1 s; %s was handed over and is not answered yet (last state: handed)' % SIG, line)
        self.assertNotIn('brain call failed', line)

    # ---- cooldown-1118：冷卻檔有 retry／error 欄（fsm、eca 寫的）＝只讀欄位，不看 stderr 的格式
    def fail_fields(self, retry, error=None, stderr='', code='BrainFailed', reason='aos-llm recv exited 1'):
        self.fail(stderr, code, reason)
        rec = json.loads((self.stack / 'cooldown.json').read_text())
        rec['retry'] = retry
        if error:
            rec['error'] = error
        (self.stack / 'cooldown.json').write_text(json.dumps(rec))

    def test_fields_retry_false_ends_at_once_without_any_stderr(self):
        self.fail_fields(False, {'code': 'EndpointFailed', 'msg': 'HTTP 400: model not supported'})
        r, took = self.listen()
        line = self.error_line(r)
        self.assertLess(took, 10, r.stderr)
        self.assertIn('stopped on an error before answering: EndpointFailed HTTP 400: model not supported / '
                      'BrainFailed aos-llm recv exited 1 (failure 1 in a row', line)
        self.assertIn('ctl start --target kid', line)

    def test_fields_win_over_the_stderr_lines(self):
        self.fail_fields(True, {'code': 'EndpointFailed', 'msg': 'HTTP 503: unavailable'}, stderr=FSM_STOP)
        r, took = self.listen('1.5')
        self.assertGreaterEqual(took, 1)
        line = self.error_line(r)
        self.assertNotIn('stopped on an error', line)
        self.assertIn("kid's last brain call failed: EndpointFailed HTTP 503: unavailable (failure 1", line)
        warns = [l for l in r.stderr.splitlines() if 'warning:' in l and 'last brain call failed' in l]
        self.assertEqual(len(warns), 1, r.stderr)

    def test_fields_retry_false_while_asking_again_is_not_stopped(self):
        self.fail_fields(False, {'code': 'EndpointFailed', 'msg': 'HTTP 400: x'})
        (self.stack / 'think/pending.txt').write_text('brain-letter\n')
        r, took = self.listen('1.5')
        self.assertGreaterEqual(took, 1)
        self.assertNotIn('stopped on an error', self.error_line(r))

    def test_fields_without_error_use_code_and_reason(self):
        self.fail_fields(False, code='CliFailed', reason='claude exited 1: usage limit reached')
        line = self.error_line(self.listen()[0])
        self.assertIn('stopped on an error before answering: CliFailed claude exited 1: usage limit reached (failure 1', line)

    def test_answered_letter_still_prints_the_answer(self):
        self.fail(FSM_STOP)
        with open(self.stack / 'history.jsonl', 'a') as f:
            f.write(json.dumps({'role': 'assistant', 'content': 'hello', 'aos': {'answer_to': [SIG]}}) + '\n')
        r, _ = self.listen('5')
        self.assertEqual((r.returncode, r.stdout), (0, 'hello\n'), r.stderr)


if __name__ == '__main__':
    unittest.main()
