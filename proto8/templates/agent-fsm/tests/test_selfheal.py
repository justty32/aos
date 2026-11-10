# Verify the wait/think cells heal leftovers (reply box, lost letter, stale request, missing kernel) with fake aos-llm/aos-post/aos-tools.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

CELLS = Path(__file__).resolve().parents[1]
PROTO = CELLS.parents[1]
sys.path.insert(0, str(PROTO / 'lib'))
from agent import cooldown  # noqa: E402

USER = {'role': 'user', 'content': 'hi'}

# 假 aos-llm：每次呼叫把 argv 記一行；send 印 FAKE_LETTER、退 FAKE_SEND（非 0 時先印一行 error，像真的 LlmKernelMissing）；
# recv 退 FAKE_RECV（0＝印好的回信；10 且沒帶 --quiet＝印一行 hint，像真的 aos-llm），FAKE_RECV2 給第二次 recv 用。
FAKE_LLM = '''import json, os, sys
calls = os.environ['FAKE_CALLS']
with open(calls, 'a') as f:
    f.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1] == 'send':
    sys.stdin.read()
    code = int(os.environ.get('FAKE_SEND', '0'))
    if code:
        print('aos-llm: error: LlmKernelMissing fake', file=sys.stderr)
        sys.exit(code)
    print(os.environ.get('FAKE_LETTER', 'letter-1'))
    sys.exit(0)
box = sys.argv[-2]
for sub in ('tmp', 'new', 'cur'):
    if not os.path.isdir(os.path.join(box, sub)):
        print('aos-llm: error: MailboxMissing mailbox not found: ' + box, file=sys.stderr)
        sys.exit(1)
n = sum(1 for line in open(calls) if json.loads(line)[0] == 'recv')
code = int(os.environ.get('FAKE_RECV2' if n >= 2 and 'FAKE_RECV2' in os.environ else 'FAKE_RECV', '0'))
if code == 0:
    print(json.dumps({'message': {'role': 'assistant', 'content': 'ok'}, 'endpoint': 'local'}))
elif code == 10 and '--quiet' not in sys.argv:
    print('aos-llm: warning: fake reason why no reply yet', file=sys.stderr)
elif code == 1:
    print('aos-llm: error: EndpointFailed fake', file=sys.stderr)
sys.exit(code)
'''
FAKE_POST = '''import os, sys
assert sys.argv[1] == 'init'
for sub in ('tmp', 'new', 'cur'):
    os.makedirs(os.path.join(sys.argv[2], sub), exist_ok=True)
'''


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = self.root / 'stack'
        (self.stack / 'think').mkdir(parents=True)
        self.definition = self.root / 'def'
        self.definition.mkdir()
        (self.definition / 'interfaces.json').write_text(json.dumps({'aos-agent': {'llm': 'llm.json'}}))
        (self.definition / 'llm.json').write_text('{"endpoint":"local"}')
        self.calls = self.root / 'calls.jsonl'
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = dict({k: v for k, v in os.environ.items() if not k.startswith('AOS_')},
                        AOS_STACK=str(self.stack), AOS_CD=str(self.definition), FAKE_CALLS=str(self.calls),
                        PATH=str(self.bin) + os.pathsep + os.environ['PATH'])
        self.command('aos-llm', FAKE_LLM)
        self.command('aos-post', FAKE_POST)
        self.history([USER])
        self.request([USER])

    def command(self, name, body):
        path = self.bin / name
        path.write_text('#!' + sys.executable + '\n' + body)
        path.chmod(0o755)

    def history(self, messages):
        (self.stack / 'history.jsonl').write_text(''.join(json.dumps(m) + '\n' for m in messages))

    def request(self, messages):
        (self.stack / 'think/request.json').write_text(json.dumps(
            {'endpoint': 'local', 'request': {'messages': messages}}))

    def run_cell(self, cell, code, timeout=10, **env):
        result = subprocess.run([sys.executable, str(CELLS / cell)], env=dict(self.env, **env),
                                capture_output=True, text=True, timeout=timeout)
        self.assertEqual(result.returncode, code, result.stderr)
        return result

    def wait(self, code, **env):
        return self.run_cell('wait.py', code, **env)

    def call_log(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def sends(self):
        return sum(1 for argv in self.call_log() if argv[0] == 'send')

    def pending(self):
        p = self.stack / 'think/pending.txt'
        return p.read_text().strip() if p.exists() else None


class ReplyBox(Base):
    def test_pending_without_reply_box_inits_then_receives(self):
        """1：clone 後有 pending、think/reply 不在 git＝先 aos-post init 再 recv。"""
        (self.stack / 'think/pending.txt').write_text('letter-1\n')
        self.assertFalse((self.stack / 'think/reply').exists())
        self.wait(0)
        for sub in ('tmp', 'new', 'cur'):
            self.assertTrue((self.stack / 'think/reply' / sub).is_dir())
        last = json.loads((self.stack / 'history.jsonl').read_text().splitlines()[-1])
        self.assertEqual(last, {'role': 'assistant', 'content': 'ok'})


class LostLetter(Base):
    def setUp(self):
        super().setUp()
        self.kernel = self.root / 'llms/stacks/kernel'
        for q in ('new', 'cur'):
            (self.kernel / 'requests' / q).mkdir(parents=True)
        self.env['AOS_LLM_KERNEL'] = str(self.kernel)
        self.wait(10)                                    # 寄出 letter-1
        self.assertEqual(self.pending(), 'letter-1')

    def test_queued_letter_keeps_waiting(self):
        for q in ('new', 'cur'):
            with self.subTest(queue=q):
                letter = self.kernel / 'requests' / q / 'letter-1'
                letter.mkdir()
                result = self.wait(10, FAKE_RECV='10')
                self.assertEqual(self.pending(), 'letter-1')
                self.assertEqual(result.stderr, '')
                letter.rmdir()

    def test_lost_letter_is_sent_again(self):
        result = self.wait(10, FAKE_RECV='10')
        self.assertIsNone(self.pending())
        self.assertIn('agent-fsm: warning: the letter letter-1 is no longer queued at the llm kernel %s; '
                      'sending the request again' % self.kernel, result.stderr)
        self.assertEqual(sum(1 for a in self.call_log() if a[0] == 'recv'), 2)   # 確認前再收一次
        self.assertEqual(os.listdir(self.kernel / 'requests/new'), [])          # kernel 那邊只讀
        self.wait(10, FAKE_LETTER='letter-2')                                    # 下一拍重寄
        self.assertEqual((self.sends(), self.pending()), (2, 'letter-2'))

    def test_reply_lands_between_checks(self):
        """kernel 剛答完、刪了 cur：第二次 recv 收到＝照常接進 history，不重寄。"""
        self.wait(0, FAKE_RECV='10', FAKE_RECV2='0')
        self.assertIsNone(self.pending())
        self.assertEqual(self.sends(), 1)
        self.assertEqual(json.loads((self.stack / 'history.jsonl').read_text().splitlines()[-1])['content'], 'ok')

    def test_relative_kernel_from_daemon(self):
        result = self.wait(10, FAKE_RECV='10', AOS_LLM_KERNEL='../llms/stacks/kernel',
                           AOS_DAEMON=str(self.root / 'something'))
        self.assertEqual(self.pending(), 'letter-1')     # ../llms 從 something 算＝root/llms（不存在）→ 不判斷
        self.assertEqual(result.stderr, '')
        (self.root / 'something').mkdir()
        self.wait(10, FAKE_RECV='10', AOS_LLM_KERNEL='../llms/stacks/kernel',
                  AOS_DAEMON=str(self.root / 'something'))
        self.assertIsNone(self.pending())

    def test_no_kernel_setting_keeps_waiting(self):
        for value in ('', str(self.root / 'nowhere')):
            with self.subTest(kernel=value):
                result = self.wait(10, FAKE_RECV='10', AOS_LLM_KERNEL=value)
                self.assertEqual(self.pending(), 'letter-1')
                self.assertEqual(result.stderr, '')


class QuietRecv(Base):
    def setUp(self):
        super().setUp()
        self.wait(10)

    def recvs(self):
        return [a for a in self.call_log() if a[0] == 'recv']

    def test_quiet_on_normal_ticks(self):
        result = self.wait(10, FAKE_RECV='10')
        self.assertIn('--quiet', self.recvs()[-1])
        self.assertEqual(result.stderr, '')

    def test_ten_minute_tick_lets_recv_print_its_reason(self):
        old = time.time() - 11 * 60
        os.utime(self.stack / 'think/pending.txt', (old, old))
        result = self.wait(10, FAKE_RECV='10')
        self.assertNotIn('--quiet', self.recvs()[-1])
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 2, result.stderr)
        self.assertIn('aos-llm: warning: fake reason', lines[0])
        self.assertIn('agent-fsm: warning: no reply from the brain for 11 minutes', lines[1])
        self.assertIn('AOS_LLM_KERNEL is not set', lines[1])
        result = self.wait(10, FAKE_RECV='10')           # 同一個 10 分鐘不再印
        self.assertIn('--quiet', self.recvs()[-1])
        self.assertEqual(result.stderr, '')

    def test_ten_minute_warning_says_where_the_letter_is(self):
        # B10：提醒說出信在 kernel 的哪一格（排隊沒開始、正在跑）
        kernel = self.root / 'llms/stacks/kernel'
        old = time.time() - 11 * 60
        for part, words in (('new', 'still queued at the llm kernel %s and not started yet'),
                            ('cur', 'the llm kernel %s is running it; the brain call itself is slow')):
            with self.subTest(part=part):
                (kernel / 'requests' / part / 'letter-1').mkdir(parents=True)
                os.utime(self.stack / 'think/pending.txt', (old, old))
                (self.stack / 'think/wait_warned.txt').unlink(missing_ok=True)
                result = self.wait(10, FAKE_RECV='10', AOS_LLM_KERNEL=str(kernel))
                self.assertIn(words % kernel, result.stderr.splitlines()[-1])
                (kernel / 'requests' / part / 'letter-1').rmdir()


class SendFailed(Base):
    def setUp(self):
        super().setUp()
        self.kernel = self.root / 'llms/stacks/kernel'
        self.env['AOS_LLM_KERNEL'] = str(self.kernel)

    def test_missing_kernel_waits_without_stopping(self):
        result = self.wait(10, FAKE_SEND='1')
        self.assertNotIn('agent-fsm: error', result.stderr)
        self.assertIn('agent-fsm: warning: aos-llm send exited 1 (its reason is above)', result.stderr)
        rec = json.loads((self.stack / cooldown.NAME).read_text())
        self.assertEqual(rec['code'], 'SendFailed')
        self.assertIn('(llm kernel folder not found)', rec['reason'])
        for _ in range(3):                               # 冷卻中：不寄、不印
            result = self.wait(10, FAKE_SEND='1')
            self.assertEqual(result.stderr, '')
        self.assertEqual(self.sends(), 1)
        self.kernel.mkdir(parents=True)                  # kernel 剛出現：立刻重寄（不等 30 秒）
        self.wait(10)
        self.assertEqual((self.sends(), self.pending()), (2, 'letter-1'))
        self.wait(0)
        self.assertFalse((self.stack / cooldown.NAME).exists())

    def test_unset_kernel_waits(self):
        result = self.wait(10, FAKE_SEND='1', AOS_LLM_KERNEL='')
        self.assertIn('agent-fsm: warning:', result.stderr)
        self.assertNotIn('agent-fsm: error', result.stderr)

    def test_send_failure_with_kernel_present_keeps_cooldown(self):
        """kernel 資料夾在、send 還是失敗：照冷卻間隔，不每拍重寄。"""
        self.kernel.mkdir(parents=True)
        self.wait(10, FAKE_SEND='1')
        rec = json.loads((self.stack / cooldown.NAME).read_text())
        self.assertNotIn('kernel folder not found', rec['reason'])
        self.wait(10, FAKE_SEND='1')
        self.assertEqual(self.sends(), 1)

    def test_brain_failed_still_stops(self):
        self.kernel.mkdir(parents=True)
        self.wait(10)
        result = self.wait(1, FAKE_RECV='1')
        self.assertIn('agent-fsm: error: BrainFailed', result.stderr)


class StaleRequest(Base):
    def test_request_older_than_history_rebuilds(self):
        self.history([USER, {'role': 'assistant', 'content': 'a'}, {'role': 'user', 'content': 'newer'}])
        self.wait(11)
        self.assertEqual(self.sends(), 0)

    def test_history_edited_after_request_rebuilds(self):
        """11-10 晚 self-family：中間幾行被 aos-agent history 改了、最後一則一樣＝history 比 request.json 新＝重組。"""
        self.history([{'role': 'user', 'content': 'summary'}, USER])
        self.request([{'role': 'user', 'content': 'old'}, {'role': 'assistant', 'content': 'a'}, USER])
        req = self.stack / 'think/request.json'
        os.utime(self.stack / 'history.jsonl', ns=(req.stat().st_mtime_ns + 10**9,) * 2)
        self.wait(11)
        self.assertEqual(self.sends(), 0)
        os.utime(self.stack / 'history.jsonl', ns=(req.stat().st_mtime_ns,) * 2)   # 同一刻（brain 剛組好）＝照寄
        self.wait(10)
        self.assertEqual(self.sends(), 1)

    def test_same_message_with_other_key_order_sends(self):
        msg = {'role': 'user', 'content': 'hi', 'name': 'bob'}
        (self.stack / 'history.jsonl').write_text('{"name": "bob", "content": "hi", "role": "user"}\n\n')
        self.request([{'role': 'system', 'content': 's'}, msg])
        self.wait(10)
        self.assertEqual(self.sends(), 1)

    def test_empty_history_or_no_messages_sends_as_before(self):
        for setup in ('empty-history', 'no-messages'):
            with self.subTest(setup=setup):
                (self.stack / 'think/pending.txt').unlink(missing_ok=True)
                if setup == 'empty-history':
                    (self.stack / 'history.jsonl').write_text('')
                else:
                    self.history([USER])
                    (self.stack / 'think/request.json').write_text(json.dumps({'endpoint': 'local', 'request': {}}))
                self.wait(10)


class MemoryMissing(Base):
    """7：--memory 讀不到知識庫＝warning、system 裡說一句、照樣寫請求。"""

    def setUp(self):
        super().setUp()
        (self.definition / 'interfaces.json').write_text(json.dumps(
            {'aos-agent': {'llm': 'llm.json', 'tools': 'tools.json'}}))
        (self.definition / 'system.txt').write_text('You are a test.\n')
        tool = self.root / 'memory_tool'
        tool.mkdir()
        lib_memory = PROTO / 'lib/agent/memory'
        (tool / '_entry').write_text(json.dumps([str(lib_memory / '_entry')]))
        for name in ('_metainfo.json', '_tooldef.json'):
            (tool / name).symlink_to(lib_memory / name)
        (tool / '_memory.json').write_text(json.dumps({'base': str(self.root / 'no-such-knowledge')}))
        self.tool = tool
        (self.definition / 'tools.json').write_text(json.dumps({'tools': {'memory': {'path': str(tool)}}}))

    def brain(self, timeout=10):
        result = subprocess.run(
            [sys.executable, str(CELLS / 'brain.py'), '--system', 'system.txt', '--memory', 'memory'],
            env=self.env, capture_output=True, text=True, timeout=timeout)
        self.assertEqual(result.returncode, 0, result.stderr)
        system = json.loads((self.stack / 'think/request.json').read_text())['request']['messages'][0]
        return result, system

    def test_missing_knowledge_base_warns_and_answers(self):
        result, system = self.brain()
        warnings = [l for l in result.stderr.splitlines() if l.startswith('agent-fsm:')]
        self.assertEqual(len(warnings), 1, result.stderr)
        self.assertIn('agent-fsm: warning: tool memory (op read of the root) exited', warnings[0])
        self.assertTrue(system['content'].startswith('You are a test.'))
        self.assertIn('Knowledge base is not available right now: tool memory', system['content'])

    def test_slow_knowledge_base_warns_and_answers(self):
        (self.tool / '_entry').write_text(json.dumps([str(self.root / 'slow')]))
        slow = self.root / 'slow'
        slow.write_text('#!/bin/sh\nsleep 120\n')
        slow.chmod(0o755)
        started = time.monotonic()
        result, system = self.brain(timeout=60)
        self.assertLess(time.monotonic() - started, 45)
        self.assertIn('agent-fsm: warning: tool memory (op read of the root) did not finish in 30 s', result.stderr)
        self.assertIn('Knowledge base is not available right now:', system['content'])


if __name__ == '__main__':
    unittest.main()
