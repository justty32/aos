"""Test brain_notify with a fake aos-mailbox: refusal notices, deduplication, and nonfatal errors."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PROTO = Path(__file__).resolve().parents[3]
ENTRY = PROTO / "py" / "tools" / "agent" / "brain_notify" / "_entry"
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\n")
if os.environ.get("FAKE_FAIL"):
    sys.stderr.write("aos-mailbox: error: MailboxMissing no mailbox here\n")
    sys.exit(1)
print("letter-1")
'''


class BrainNotify(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="brain-notify-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.agent = self.root / "procs" / "worker"
        self.cell = self.agent / "hookeds" / "brain_notify"
        self.cell.mkdir(parents=True)
        self.history = self.agent / "history.jsonl"
        self.seen = self.cell / "notified.json"
        self.box = self.root / "parent" / "mailbox"
        for part in ("tmp", "new", "cur"):
            (self.box / part).mkdir(parents=True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "aos-mailbox"
        fake.write_text(FAKE)
        fake.chmod(0o755)
        self.log = self.root / "mailbox.log"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        self.env.update(PATH=os.pathsep.join((str(self.bin), os.environ["PATH"])),
                        AOS_STACK=str(self.cell), AOS_NOTIFY_BOX=str(self.box),
                        FAKE_LOG=str(self.log), PYTHONDONTWRITEBYTECODE="1")
        self.event = {"event": "brain_failed", "hook": "brain_notify", "stack": str(self.agent),
                      "name": "BudgetMissing", "reason": "max_calls 150 reached in this window (day); not run"}

    def run_hook(self, event=None, text=None, env=None, argv=()):
        r = subprocess.run([sys.executable, str(ENTRY), *argv],
                           input=json.dumps(self.event if event is None else event) if text is None else text,
                           capture_output=True, text=True, env=self.env if env is None else env, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def warning(self, result, code):
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        self.assertTrue(result.stderr.startswith("brain_notify: warning: " + code), result.stderr)
        self.assertNotIn("brain_notify: error:", result.stderr)

    def test_first_send_deduplicates_then_history_growth_sends_again(self):
        self.history.write_text('{"role":"user","content":"work"}\n')
        r = self.run_hook(env=dict(self.env, AOS_NOTIFY_BOX="  " + str(self.box) + " \n"))
        self.assertEqual((r.stdout, r.stderr), ("", ""))
        self.assertEqual(self.calls(), [["--stack", str(self.agent), "send", "--from", "worker", "--box", str(self.box),
                                        "--status", "BLOCKED", "--title", "worker: brain refused (BudgetMissing), waiting",
                                        "--", self.event["reason"] + ". It sends the same request again by itself after a "
                                        "cooldown (30 s doubling to 30 min). Raise the budget, or stop it."]])
        self.assertEqual(json.loads(self.seen.read_text()), {"code": "BudgetMissing", "history_lines": 1})
        r = self.run_hook()
        self.assertEqual((r.stdout, r.stderr), ("", ""))
        self.assertEqual(len(self.calls()), 1)
        with self.history.open("a") as f:
            f.write('{"role":"assistant","content":"done"}\n')
        self.run_hook()
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(json.loads(self.seen.read_text()), {"code": "BudgetMissing", "history_lines": 2})
        self.assertEqual(list(self.cell.glob("*.tmp")), [])

    def test_error_with_resets_at_says_waiting_until_local_time(self):
        import datetime
        at = datetime.datetime(2026, 11, 14, 13, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
        local = at.astimezone().strftime("%H:%M")
        self.run_hook(event=dict(self.event, error={"code": "BudgetMissing", "window": "hour",
                                                    "resets_at": "2026-11-14T13:00:00+08:00"}))
        call = self.calls()[0]
        self.assertEqual(call[call.index("--title") + 1], "worker: brain refused (BudgetMissing), waiting until " + local)
        self.assertIn("sends the same request again by itself then", call[-1])
        self.assertIn(self.event["reason"], call[-1])
        self.assertEqual(json.loads(self.seen.read_text()), {"code": "BudgetMissing", "history_lines": 0})
        self.run_hook(event=dict(self.event, error={"window": "hour", "resets_at": "2026-11-14T14:00:00+08:00"}))
        self.assertEqual(len(self.calls()), 1)               # dedup unchanged

    def test_error_window_all_says_stopped(self):
        self.run_hook(event=dict(self.event, error={"code": "BudgetMissing", "window": "all", "resets_at": None}))
        call = self.calls()[0]
        self.assertEqual(call[call.index("--title") + 1], "worker: brain refused (BudgetMissing), stopped")
        self.assertEqual(call[-1], self.event["reason"] + ". The budget never resets; raise it, then start the agent again.")

    def test_error_without_usable_fields_keeps_old_text(self):
        for i, error in enumerate(({"code": "BudgetMissing", "msg": "x"}, "text", {"resets_at": "soon"},
                                   {"resets_at": "2026-11-14T13:00:00"}, {"resets_at": None, "window": "day"})):
            (self.seen).unlink(missing_ok=True)
            self.run_hook(event=dict(self.event, error=error))
            call = self.calls()[i]
            self.assertEqual(call[call.index("--title") + 1], "worker: brain refused (BudgetMissing), waiting")
            self.assertTrue(call[-1].endswith("after a cooldown (30 s doubling to 30 min). Raise the budget, or stop it."))

    def test_missing_history_counts_zero_and_different_code_sends(self):
        self.run_hook()
        self.assertEqual(json.loads(self.seen.read_text()), {"code": "BudgetMissing", "history_lines": 0})
        self.run_hook()
        self.assertEqual(len(self.calls()), 1)
        self.run_hook(event=dict(self.event, name="BrainFailed", reason="endpoint unavailable"))
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(json.loads(self.seen.read_text()), {"kind": "stopped", "code": "BrainFailed", "history_lines": 0, "attempt": 0})
        self.assertEqual(self.calls()[-1][-3], "worker: brain failed (BrainFailed), stopped")

    def failed(self, **fields):
        event = dict(self.event, name='BrainFailed', code='ReplyBad', retry=True, attempt=1,
                     status=200, error={'msg': 'no choices'}, reason='aos-llm recv exited 1')
        event.update(fields)
        return event

    def test_retrying_first_two_silent_third_notifies_once_then_rearms(self):
        for attempt in (1, 2):
            r = self.run_hook(self.failed(attempt=attempt))
            self.assertEqual((r.stdout, r.stderr), ('', ''))
            self.assertEqual(self.calls(), [])
            self.assertEqual(json.loads(self.seen.read_text()), {'kind': 'retrying', 'armed': True})
        self.run_hook(self.failed(attempt=3))
        call = self.calls()[0]
        self.assertEqual(call[call.index('--status') + 1], 'BLOCKED')
        self.assertEqual(call[call.index('--title') + 1], 'worker: brain failed (ReplyBad), retrying by itself')
        for text in ('no choices', 'status 200', 'tried 3 times', 'keeps retrying by itself', 'use stop'):
            self.assertIn(text, call[-1])
        self.assertEqual(json.loads(self.seen.read_text()), {'kind': 'retrying', 'armed': False})
        for attempt in (3, 4, 10):
            self.run_hook(self.failed(attempt=attempt))
            self.assertEqual(len(self.calls()), 1)
        for attempt in (1, 2, 3):
            self.run_hook(self.failed(attempt=attempt))
        self.assertEqual(len(self.calls()), 2)

    def test_attempt_over_three_without_record_still_notifies(self):
        self.run_hook(self.failed(attempt=4))
        self.assertEqual(len(self.calls()), 1)
        self.run_hook(self.failed(attempt=5))
        self.assertEqual(len(self.calls()), 1)

    def test_same_history_retrying_then_stopped_still_sends_and_deduplicates_attempt(self):
        for attempt in (1, 3):
            self.run_hook(self.failed(attempt=attempt))
        stopped = self.failed(retry=False, attempt=4, status=401, code='EndpointFailed', error={'msg': 'unauthorized'})
        self.run_hook(stopped)
        self.assertEqual(len(self.calls()), 2)
        call = self.calls()[-1]
        self.assertEqual(call[call.index('--title') + 1], 'worker: brain failed (EndpointFailed), stopped')
        self.assertIn('unauthorized', call[-1])
        self.assertIn('status 401', call[-1])
        self.assertIn('start the agent again', call[-1])
        self.assertNotIn('until', call[-1])
        self.assertEqual(json.loads(self.seen.read_text()),
                         {'kind': 'stopped', 'code': 'EndpointFailed', 'history_lines': 0, 'attempt': 4})
        self.run_hook(stopped)
        self.assertEqual(len(self.calls()), 2)
        self.run_hook(dict(stopped, attempt=5))
        self.assertEqual(len(self.calls()), 3)

    def test_stopped_without_code_uses_name_and_reason(self):
        event = self.failed(retry=False)
        for field in ('code', 'error', 'status', 'attempt'):
            event.pop(field)
        self.run_hook(event)
        call = self.calls()[0]
        self.assertEqual(call[call.index('--title') + 1], 'worker: brain failed (BrainFailed), stopped')
        self.assertIn(event['reason'], call[-1])
        self.assertNotIn('status', call[-1])

    def test_retry_not_boolean_true_sends_stopped(self):
        for attempt, retry in enumerate(('true', 1, None), 1):
            self.run_hook(self.failed(retry=retry, attempt=attempt))
            self.assertTrue(self.calls()[-1][-3].endswith(', stopped'))
        self.assertEqual(len(self.calls()), 3)

    def test_stopped_says_start_waits_out_the_cooldown(self):
        (self.agent / 'cooldown.json').write_text(json.dumps({'until': '2026-11-16T09:45:00Z'}))
        self.run_hook(self.failed(retry=False))
        text = self.calls()[-1][-1]
        self.assertIn('after start it first waits out its cooldown', text)
        self.assertNotIn('09:45', text)

    def test_retrying_failed_send_does_not_disarm_and_can_retry(self):
        self.run_hook(self.failed(attempt=1))
        self.warning(self.run_hook(self.failed(attempt=3), env=dict(self.env, FAKE_FAIL='1')), 'CommandFailed')
        self.assertEqual(json.loads(self.seen.read_text()), {'kind': 'retrying', 'armed': True})
        self.run_hook(self.failed(attempt=4))
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual(json.loads(self.seen.read_text()), {'kind': 'retrying', 'armed': False})

    def test_corrupt_record_sends_once_and_rewrites(self):
        self.seen.write_text('{"code":')
        r = self.run_hook()
        self.assertEqual((r.stdout, r.stderr), ("", ""))
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(json.loads(self.seen.read_text()), {"code": "BudgetMissing", "history_lines": 0})
        r = self.run_hook()
        self.assertEqual((r.stdout, r.stderr), ("", ""))
        self.assertEqual(len(self.calls()), 1)

    def test_unset_or_blank_box_warns_without_sending(self):
        for box in (None, " \t\n"):
            with self.subTest(box=box):
                env = dict(self.env)
                env.pop("AOS_NOTIFY_BOX")
                if box is not None:
                    env["AOS_NOTIFY_BOX"] = box
                r = self.run_hook(env=env)
                self.assertEqual(r.stderr, "brain_notify: warning: AOS_NOTIFY_BOX is not set; nobody is told that "
                                          "worker got BudgetMissing\n")
                self.assertEqual(r.stdout, "")
                self.assertEqual(self.calls(), [])
                self.assertFalse(self.seen.exists())

    def test_send_failure_warns_without_recording_and_can_retry(self):
        r = self.run_hook(env=dict(self.env, FAKE_FAIL="1"))
        self.warning(r, "CommandFailed")
        self.assertEqual(len(self.calls()), 1)
        self.assertFalse(self.seen.exists())
        self.run_hook()
        self.assertEqual(len(self.calls()), 2)
        self.assertTrue(self.seen.exists())

    def test_missing_mailbox_command_warns_without_recording(self):
        r = self.run_hook(env=dict(self.env, PATH=str(self.root / "no-commands")))
        self.warning(r, "LaunchFailed")
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.seen.exists())

    def test_bad_stdin_warns_without_sending(self):
        for text in ("not json", "[]", "null", "{}", json.dumps(dict(self.event, stack="relative")),
                     json.dumps(dict(self.event, name=None)), json.dumps(dict(self.event, reason=None))):
            with self.subTest(text=text):
                self.warning(self.run_hook(text=text), "ArgumentsBad")
                self.assertEqual(self.calls(), [])
                self.assertFalse(self.seen.exists())

    def test_missing_hook_cell_warns_without_sending(self):
        env = dict(self.env)
        env.pop("AOS_STACK")
        self.warning(self.run_hook(env=env), "StackMissing")
        self.assertEqual(self.calls(), [])

    def test_write_failure_warns_after_send_without_recording(self):
        missing_cell = self.root / "missing-cell"
        self.warning(self.run_hook(env=dict(self.env, AOS_STACK=str(missing_cell))), "WriteFailed")
        self.assertEqual(len(self.calls()), 1)
        self.assertFalse((missing_cell / "notified.json").exists())

    def test_help_and_unknown_argument(self):
        r = self.run_hook(text="not json", argv=("--help",))
        self.assertIn("usage: brain_notify", r.stdout)
        self.assertEqual(r.stderr, "")
        self.warning(self.run_hook(argv=("--unknown",)), "ArgumentsBad")
        self.assertEqual(self.calls(), [])

    def test_template_mount(self):
        hooks = json.loads((PROTO / "templates" / "agent-fsm" / "hookeds.json").read_text())
        self.assertEqual(hooks["brain_notify"],
                         {"event": "brain_failed", "condition": ["BudgetMissing", "BrainFailed"],
                          "handler": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/brain_notify"},
                          "timeout_ms": 10000})
        self.assertIn("AOS_NOTIFY_BOX", hooks["description"])

    def test_eca_retry_series_arms_then_notifies_once_and_rearms(self):
        for name in ('CliFailed', 'ReplyMissing'):
            with self.subTest(name=name):
                before = len(self.calls())
                event = dict(self.event, name=name, code=name, retry=True, attempt=1,
                             reason='claude exited 1', status=529, cause='api_529', dropped=0,
                             error={'msg': 'must not replace the eca reason'})
                for attempt in (1, 2):
                    r = self.run_hook(dict(event, attempt=attempt))
                    self.assertEqual((r.stdout, r.stderr), ('', ''))
                    self.assertEqual(len(self.calls()), before)
                    self.assertEqual(json.loads(self.seen.read_text()), {'kind': 'retrying', 'armed': True})
                self.run_hook(dict(event, attempt=3))
                self.assertEqual(len(self.calls()), before + 1)
                call = self.calls()[-1]
                self.assertEqual(call[call.index('--status') + 1], 'BLOCKED')
                self.assertEqual(call[call.index('--title') + 1],
                                 'worker: brain failed (%s), retrying by itself' % name)
                self.assertEqual(call[-1], '%s: claude exited 1; status 529; cause api_529. '
                                 'It has tried 3 times and keeps retrying by itself after each cooldown; '
                                 'the unanswered turn is continued in the same conversation. '
                                 'No action is needed. To stop it, use stop.' % name)
                self.assertEqual(json.loads(self.seen.read_text()), {'kind': 'retrying', 'armed': False})
                for attempt in (3, 4, 10):
                    self.run_hook(dict(event, attempt=attempt))
                    self.assertEqual(len(self.calls()), before + 1)
                for attempt in (1, 3):
                    self.run_hook(dict(event, attempt=attempt))
                self.assertEqual(len(self.calls()), before + 2)

    def test_eca_stopped_uses_reason_status_cause_and_dropped_count(self):
        for name in ('CliFailed', 'ReplyMissing'):
            with self.subTest(name=name):
                event = dict(self.event, name=name, code=name, retry=False, attempt=4,
                             reason='claude exited 1', status=401, cause='api_401', dropped=2,
                             error={'msg': 'must not replace the eca reason'})
                before = len(self.calls())
                r = self.run_hook(event)
                self.assertEqual((r.stdout, r.stderr), ('', ''))
                self.assertEqual(len(self.calls()), before + 1)
                call = self.calls()[-1]
                self.assertEqual(call[call.index('--title') + 1], 'worker: brain failed (%s), stopped' % name)
                self.assertEqual(call[-1], '%s: claude exited 1; status 401; cause api_401. '
                                 'Fix the cause, then start the agent again; after start it first waits out its '
                                 'cooldown (30 s doubling to 30 min). 2 letter(s) handed over in that turn '
                                 'got no answer and are not retried.' % name)
                self.assertEqual(json.loads(self.seen.read_text()),
                                 {'kind': 'stopped', 'code': name, 'history_lines': 0, 'attempt': 4})
                self.run_hook(event)
                self.assertEqual(len(self.calls()), before + 1)
                self.run_hook(dict(event, attempt=5))
                self.assertEqual(len(self.calls()), before + 2)

    def test_eca_stopped_without_dropped_letters_omits_last_sentence(self):
        for name in ('CliFailed', 'ReplyMissing'):
            with self.subTest(name=name):
                self.run_hook(dict(self.event, name=name, retry=False, attempt=1,
                                   reason='the screen closed', dropped=0))
                self.assertEqual(self.calls()[-1][-1], '%s: the screen closed. Fix the cause, then start the '
                                 'agent again; after start it first waits out its cooldown '
                                 '(30 s doubling to 30 min).' % name)
                self.assertNotIn('llm.json', self.calls()[-1][-1])
                self.assertNotIn('letter(s)', self.calls()[-1][-1])

    def test_eca_without_boolean_retry_is_silent_without_recording(self):
        no_box_or_cell = dict(self.env)
        no_box_or_cell.pop('AOS_NOTIFY_BOX')
        no_box_or_cell.pop('AOS_STACK')
        for name in ('CliFailed', 'ReplyMissing'):
            for retry in ('missing', None, 0, 1, 'true', 'false'):
                for env in (self.env, no_box_or_cell):
                    with self.subTest(name=name, retry=retry, box='AOS_NOTIFY_BOX' in env):
                        event = dict(self.event, name=name)
                        if retry != 'missing':
                            event['retry'] = retry
                        r = self.run_hook(event, env=env)
                        self.assertEqual((r.stdout, r.stderr), ('', ''))
                        self.assertEqual(self.calls(), [])
                        self.assertFalse(self.seen.exists())

    def test_eca_ignored_codex_event_preserves_existing_record(self):
        original = '{"kind": "retrying", "armed": true}\n'
        self.seen.write_text(original)
        for name in ('CliFailed', 'ReplyMissing'):
            r = self.run_hook(dict(self.event, name=name))
            self.assertEqual((r.stdout, r.stderr), ('', ''))
            self.assertEqual(self.calls(), [])
            self.assertEqual(self.seen.read_text(), original)

    def test_eca_dropped_must_be_integer_not_boolean(self):
        for attempt, dropped in enumerate((None, '2', True, 0.0), 1):
            with self.subTest(dropped=dropped):
                self.run_hook(dict(self.event, name='CliFailed', retry=False, attempt=attempt,
                                   reason='claude exited 1', dropped=dropped))
                self.assertEqual(self.calls()[-1][-1], 'CliFailed: claude exited 1. Fix the cause, then start '
                                 'the agent again; after start it first waits out its cooldown '
                                 '(30 s doubling to 30 min; changing llm.json clears it).')

    def test_brain_failed_without_dropped_keeps_exact_text(self):
        self.run_hook(self.failed(attempt=3))
        call = self.calls()[-1]
        self.assertEqual(call[call.index('--title') + 1], 'worker: brain failed (ReplyBad), retrying by itself')
        self.assertEqual(call[-1], 'ReplyBad: no choices; status 200. It has tried 3 times and keeps retrying '
                         'by itself; no action is needed. To stop it, use stop.')
        self.run_hook(self.failed(retry=False, attempt=4))
        call = self.calls()[-1]
        self.assertEqual(call[call.index('--title') + 1], 'worker: brain failed (ReplyBad), stopped')
        self.assertEqual(call[-1], 'ReplyBad: no choices; status 200. Fix the cause, then start the agent again; '
                         'after start it first waits out its cooldown '
                         '(30 s doubling to 30 min; changing llm.json clears it).')

    def test_unreachable_endpoint_asks_for_someone_and_says_when(self):
        # 11-24 ops 意見 ②：端點沒在聽（EndpointFailed、沒有 status、連不上／逾時）＝要有人處理、下一次本地時刻、ctl retry；不說 no action is needed。
        event = self.failed(attempt=3, code='EndpointFailed', wait_s=120,
                            error={'msg': 'cannot connect to http://127.0.0.1:4000/v1: [Errno 111] Connection refused'})
        del event['status']
        self.run_hook(event)
        call = self.calls()[-1]
        self.assertEqual(call[call.index('--title') + 1], 'worker: brain endpoint not answering (EndpointFailed), retrying by itself')
        text = call[-1]
        self.assertTrue(text.startswith('EndpointFailed: cannot connect to http://127.0.0.1:4000/v1'), text)
        self.assertIn('The endpoint is not answering, so someone needs to look at it', text)
        self.assertRegex(text, r'keeps retrying by itself \(next try at \d\d:\d\d:\d\d\); once the endpoint is back, '
                               r'aos-agent ctl retry worker makes it try at once')
        self.assertNotIn('no action is needed', text)

    def test_other_retrying_error_with_wait_s_adds_next_try_and_retry(self):
        self.run_hook(self.failed(attempt=3, wait_s=60))
        text = self.calls()[-1][-1]
        self.assertRegex(text, r'^ReplyBad: no choices; status 200\. It has tried 3 times and keeps retrying by itself; '
                               r'no action is needed\. Next try at \d\d:\d\d:\d\d; aos-agent ctl retry worker makes it try now\. '
                               r'To stop it, use stop\.$')

    def test_eca_template_mount(self):
        hooks = json.loads((PROTO / 'templates' / 'eca-claude' / 'hookeds.json').read_text())
        self.assertEqual(hooks['brain_notify'],
                         {'event': 'brain_failed', 'condition': ['CliFailed', 'ReplyMissing'],
                          'handler': {'$env': 'AOS_HOME', '$path': '/lib/tools/agent/brain_notify'},
                          'timeout_ms': 10000})
        self.assertIn('AOS_NOTIFY_BOX', hooks['description'])
        self.assertIn('codex events are ignored', hooks['description'])


if __name__ == "__main__":
    unittest.main()
