# Check the three hook moments on the llm kernel and that add letters go to AOS_KERNEL when it is set.
import json
import subprocess
import unittest

import test_ledger

HANDLER = '''#!/usr/bin/env python3
# Test hook: log the event, then act on the marker in the first message.
import json, os, sys
event = json.load(sys.stdin)
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen.jsonl"), "a") as log:
    log.write(json.dumps({key: event.get(key) for key in ("event", "letter", "verdict", "error", "sender", "reply_to")}) + "\\n")
body = event["body"]
%s
'''
BEFORE_VERDICT = '''if body["request"]["messages"] and body["request"]["messages"][0]["content"] == "block me":
    print("not on my watch")
    sys.exit(10)
body["endpoint"] = "other"
body["request"]["hooked"] = True
print(json.dumps({"body": body}))'''
AFTER_VERDICT = '''marker = body["request"]["messages"][0]["content"] if body["request"]["messages"] else ""
if marker == "refuse me":
    print(json.dumps({"verdict": "refuse", "error": {"code": "Quota", "msg": "said the hook"}}))
if marker == "let me in":
    print(json.dumps({"verdict": "pass"}))'''
BEFORE_REPLY = '''mode = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mode")).read().strip()
if mode == "fail":
    sys.exit(3)
if mode == "block":
    print("kept inside")
    sys.exit(10)
body["message"]["content"] = "redacted"
body.pop("usage", None)
print(json.dumps({"body": body}))'''


class HookTests(unittest.TestCase):
    setUp = test_ledger.LedgerTests.setUp
    prepare = test_ledger.LedgerTests.prepare
    ledger = test_ledger.LedgerTests.ledger

    def configure(self, event, code, **more):
        handler = self.stack / 'hook_handler'
        handler.write_text(HANDLER % code)
        handler.chmod(0o755)
        cfg = {'exec': str(test_ledger.FAKE.parent), 'endpoints': {'fake': {}, 'other': {}}, 'endpoint': 'fake',
               'hooks': {'probe': {'event': event, 'handler': str(handler)}}}
        cfg.update(more)
        self.config.write_text(json.dumps(cfg))
        self.box = self.stack / 'replies'
        for part in ('new', 'tmp', 'cur'):
            (self.box / part).mkdir(parents=True, exist_ok=True)

    def run_kernel(self, code=0):
        result = subprocess.run([str(test_ledger.KERNEL), str(self.config)], env=self.env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, code, result.stderr)
        return result

    def send(self, name, content, **body):
        folder = self.stack / 'requests/new' / name
        folder.mkdir()
        body['request'] = {'messages': [{'role': 'user', 'content': content}]}
        (folder / 'letter.json').write_text(json.dumps({'sender': '/sender', 'reply_to': str(self.box), 'body': body}))

    def replies(self):
        found = {}
        for path in (self.box / 'new').glob('*/letter.json'):
            letter = json.loads(path.read_text())
            found[letter['in_reply_to']] = letter['body']
        return found

    def seen(self):
        return [json.loads(line) for line in (self.stack / 'seen.jsonl').read_text().splitlines()]

    def test_before_verdict_changes_the_body_or_blocks(self):
        self.configure('before_verdict', BEFORE_VERDICT)
        self.send('changed', 'hello')
        self.send('blocked', 'block me')
        self.run_kernel()
        folder = self.stack / 'requests/cur/changed'
        self.assertEqual(json.loads((folder / 'proc.json').read_text())['endpoint'], 'other')
        self.assertIs(json.loads((folder / 'request.json').read_text())['request']['hooked'], True)
        self.assertEqual(self.replies(), {'blocked': {'error': {'code': 'HookRejected', 'msg': 'not on my watch'}}})
        self.assertFalse((self.stack / 'requests/new/blocked').exists())
        self.assertFalse((self.stack / 'ledger.jsonl').exists())          # 沒掛過的不進帳

    def test_after_verdict_once_per_verdict_and_can_overrule(self):
        self.configure('after_verdict', AFTER_VERDICT, slots=1)
        self.send('a-first', 'hello')
        self.send('b-refused', 'refuse me', priority='high')
        self.send('c-waits', 'hello', priority='low')
        self.run_kernel()
        self.assertEqual(self.replies(), {'b-refused': {'error': {'code': 'Quota', 'msg': 'said the hook'}}})
        self.assertTrue((self.stack / 'requests/cur/a-first/proc.json').exists())
        self.assertTrue((self.stack / 'requests/new/c-waits').exists())
        first = [(row['letter'], row['verdict']) for row in self.seen()]
        self.assertEqual(first, [('b-refused', 'pass'), ('a-first', 'pass'), ('c-waits', 'queue')])
        self.run_kernel()                                                  # 繼續排的不再跑
        self.assertEqual(len(self.seen()), 3)
        folder = self.stack / 'requests/cur/a-first'
        (folder / 'state.json').write_text('{"phase":"done","code":0}')
        (folder / 'reply.json').write_text(json.dumps(self.reply))
        self.run_kernel()                                                  # 放出一格：離開隊時再一次
        self.assertEqual([(row['letter'], row['verdict']) for row in self.seen()][3:], [('c-waits', 'pass')])
        self.assertTrue((self.stack / 'requests/cur/c-waits/proc.json').exists())
        self.send('d-full', 'let me in')                                   # 沒格是排，hook 改判放行就照掛
        self.run_kernel()
        self.assertTrue((self.stack / 'requests/cur/d-full/proc.json').exists())
        self.assertEqual(self.seen()[-1]['verdict'], 'queue')

    def test_before_reply_changes_the_reply_after_the_books_are_written(self):
        self.configure('before_reply', BEFORE_REPLY)
        mode = self.stack / 'mode'
        folder = self.prepare('answer', self.reply)
        (folder / 'letter.json').write_text(json.dumps({'sender': '/sender', 'reply_to': str(self.box)}))
        mode.write_text('fail')
        result = self.run_kernel(code=1)                                   # hook 自己失敗：這輪退 1、信留著
        self.assertIn('kernel_llm: error: HookFailed ', result.stderr)
        self.assertEqual(self.replies(), {})
        self.assertEqual(len(self.ledger()), 1)
        mode.write_text('change')
        self.run_kernel()                                                  # 下一輪重來，帳不記第二次
        expected = {key: value for key, value in self.reply.items() if key != 'usage'}
        expected['message'] = dict(self.reply['message'], content='redacted')
        self.assertEqual(self.replies(), {'answer': expected})
        self.assertEqual([row['usage'] for row in self.ledger()], [self.reply['usage']])
        self.assertEqual(json.loads((self.stack / 'used.json').read_text())['counter_calls'], 1)
        self.assertEqual(self.seen()[-1], {'event': 'before_reply', 'letter': 'answer', 'verdict': None, 'error': None,
                                           'sender': '/sender', 'reply_to': str(self.box)})
        self.assertFalse(folder.exists())

    def test_before_reply_block_answers_hook_rejected(self):
        self.configure('before_reply', BEFORE_REPLY)
        (self.stack / 'mode').write_text('block')
        folder = self.prepare('kept', self.reply)
        (folder / 'letter.json').write_text(json.dumps({'sender': '/sender', 'reply_to': str(self.box)}))
        self.run_kernel()
        self.assertEqual(self.replies(), {'kept': {'error': {
            'code': 'HookRejected', 'msg': 'reply blocked by hook probe: kept inside'}}})
        self.assertIsNone(self.ledger()[0]['code'])                        # 帳記的是端點函數原本的回話

    def test_add_letter_goes_to_aos_kernel_when_set(self):
        self.configure('before_verdict', 'pass')
        gate = self.stack / 'gate'
        for part in ('new', 'tmp', 'cur'):
            (gate / part).mkdir(parents=True)
        self.env['AOS_KERNEL'] = str(gate)
        self.send('via-gate', 'hello')
        self.run_kernel()
        (letter,) = [json.loads(path.read_text()) for path in (gate / 'new').glob('*/letter.json')]
        self.assertEqual(list(letter['body']['procs_added']), ['llm_via-gate'])
        self.assertEqual(list((self.stack / 'procs_requests/new').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
