# test_retry.py - Test claude temporary-error continuation, failure accounting and unchanged codex turns with fake CLIs.
import hashlib
import json
import sys
import unittest

from test_switch import Base, HERE, cooldown

MAX_FAILURES = 10          # = aos/apps/eca/retry.py MAX_FAILURES


class RetryBase(Base):
    def setUp(self):
        super().setUp()
        (self.bin / "claude").unlink()
        (self.bin / "claude").symlink_to(HERE / "fake_claude_api")
        self.events_path = self.t / "events.jsonl"
        self.capture = self.defn / "capture.py"
        self.capture.write_text(
            "#!" + sys.executable + "\nimport json, sys\n"
            "event = json.load(sys.stdin)\n"
            "with open(%r, 'a') as f:\n    f.write(json.dumps(event) + '\\n')\n"
            % str(self.events_path))
        self.capture.chmod(0o755)
        (self.defn / "interfaces.json").write_text(json.dumps({"hookeds": "hookeds.json"}))
        self.declare({"failed": {"event": "brain_failed", "handler": self.capture.name}})

    def declare(self, hooks):
        (self.defn / "hookeds.json").write_text(json.dumps(hooks))

    def events(self):
        return [json.loads(line) for line in self.events_path.read_text().splitlines()] if self.events_path.exists() else []

    def letters(self):
        return json.loads((self.stack / "letters.json").read_text())

    def retry(self):
        return json.loads((self.stack / "retry.json").read_text())

    def assert_sum_noted(self):
        digest = hashlib.sha256((self.stack / "history.jsonl").read_bytes()).hexdigest()
        self.assertEqual((self.cell / ".history_sum").read_text().strip(), digest)

    def assert_failed_letters(self, sigs):
        rec = self.letters()
        self.assertEqual(rec["pending"], [])
        self.assertEqual([(row["letter"], row["reason"]) for row in rec["dropped"]],
                         [(sig, "failed") for sig in sigs])

    def assert_one_cli_error(self, result, prog="aos-eca-turn"):
        self.assertEqual(result.returncode, 1, result.stderr)
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 1, result.stderr)
        self.assertTrue(lines[0].startswith(prog + ": error: CliFailed"), result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class ClaudeRetry(RetryBase):
    def test_529_cooling_then_resume_answers_only_owed_letters(self):
        self.say("ORIGINAL LETTER A", "ORIGINAL LETTER B")
        sigs = self.queue()
        result = self.turn(FAKE_CLI_API_ERROR="529")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.queue(), [])
        self.assertEqual(self.letters(), {"pending": sigs, "dropped": []})
        rec = self.retry()
        self.assertEqual((rec["letters"], rec["attempt"], rec["tools"]), (sigs, 1, 0))
        cool = cooldown.read(str(self.stack))
        self.assertEqual((cool["failures"], cool["dropped"], cool["code"]), (1, 0, "CliFailed"))
        self.assertIs(cool["retry"], True)                # cooldown-1118：暫時錯＝自己接著試
        self.assertNotIn("error", cool)
        self.assert_sum_noted()
        event = self.events()[-1]
        self.assertEqual({key: event[key] for key in ("name", "code", "retry", "attempt", "dropped", "wait_s", "status", "cause")},
                         {"name": "CliFailed", "code": "CliFailed", "retry": True, "attempt": 1,
                          "dropped": 0, "wait_s": 30, "status": 529, "cause": "api_529"})
        old_sid = self.sid()
        self.assertTrue(old_sid)
        self.assertEqual([row["role"] for row in self.history()], ["user", "user"])
        self.say("NEW LETTER MUST WAIT")
        waiting = self.queue()
        before = self.history()
        self.ok_turn()
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.history(), before)
        self.assertEqual(self.queue(), waiting)
        self.make_due()
        self.ok_turn()
        last = self.calls()[-1]
        expected = ("[aos] retry: the last turn failed before you answered (%s: %s). "
                    "Its messages (2 letters) are already in this conversation, or in the record above. "
                    "Go on from where it stopped and answer them now." % (rec["code"], rec["reason"]))
        self.assertEqual(last["stdin"], expected)
        self.assertNotIn("ORIGINAL LETTER", last["stdin"])
        self.assertEqual(last["argv"][last["argv"].index("--resume") + 1], old_sid)
        self.assertEqual(self.sid(), old_sid)
        self.assertEqual(self.queue(), waiting)
        self.assertEqual(sorted(p.name for p in (self.stack / "queue" / "new").iterdir()), waiting)
        self.assertEqual(list((self.stack / "queue" / "cur").iterdir()), [])
        answers = [row for row in self.history() if row["role"] == "assistant"]
        self.assertEqual(answers, [{"role": "assistant", "content": "FAKE: " + expected,
                                    "aos": {"answer_to": sigs}}])
        self.assertEqual(self.letters(), {"pending": [], "dropped": []})
        self.assertFalse((self.stack / "retry.json").exists())
        self.assertIsNone(cooldown.read(str(self.stack)))
        self.assert_sum_noted()

    def test_three_temporary_errors_do_not_repeat_letters(self):
        self.say("ORIGINAL UNIQUE CONTENT")
        sigs = self.queue()
        for attempt in range(1, 4):
            if attempt > 1:
                self.make_due()
            self.ok_turn(FAKE_CLI_API_ERROR="529", FAKE_CLI_TOOL="Read")
            rec = self.retry()
            self.assertEqual((rec["attempt"], rec["letters"], rec["tools"]), (attempt, sigs, attempt))
            self.assertEqual(cooldown.read(str(self.stack))["failures"], attempt)
            self.assertEqual(cooldown.read(str(self.stack))["dropped"], 0)
            self.assertEqual(self.events()[-1]["attempt"], attempt)
            self.assertTrue(self.events()[-1]["retry"])
            self.assertEqual(self.events()[-1]["wait_s"], cooldown.step_s(attempt))
            self.assertEqual(self.letters()["pending"], sigs)
            self.assert_sum_noted()
        self.assertEqual(sum(row["content"] == "ORIGINAL UNIQUE CONTENT" for row in self.history()), 1)
        self.assertFalse(any(row["role"] == "assistant" for row in self.history()))
        self.assertEqual(self.queue(), [])
        self.make_due()
        self.ok_turn()
        self.assertIn("already called tools in that turn (3 calls)", self.calls()[-1]["stdin"])
        self.assertEqual(self.history()[-1]["aos"]["answer_to"], sigs)
        self.assertFalse((self.stack / "retry.json").exists())

    def test_tenth_temporary_failure_in_a_row_is_permanent(self):
        self.say("stuck letter")
        sigs = self.queue()
        for attempt in range(1, MAX_FAILURES):
            if attempt > 1:
                self.make_due()
            self.ok_turn(FAKE_CLI_API_ERROR="529")
            self.assertTrue(self.events()[-1]["retry"])
        self.assertEqual(self.retry()["attempt"], MAX_FAILURES - 1)
        self.make_due()
        result = self.turn(FAKE_CLI_API_ERROR="529")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("gave up after %d temporary failures in a row" % MAX_FAILURES, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.stack / "retry.json").exists())
        self.assert_failed_letters(sigs)
        event = self.events()[-1]
        self.assertEqual((event["retry"], event["attempt"], event["dropped"]), (False, MAX_FAILURES, 1))
        self.assertNotIn("wait_s", event)
        self.assertIn("gave up after", event["reason"])

    def test_temporary_then_401_drops_owed_and_stops(self):
        self.say("first", "second")
        sigs = self.queue()
        self.ok_turn(FAKE_CLI_API_ERROR="529")
        self.make_due()
        result = self.turn(FAKE_CLI_API_ERROR="401")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("CliFailed", result.stderr)
        self.assert_failed_letters(sigs)
        self.assertFalse((self.stack / "retry.json").exists())
        cool = cooldown.read(str(self.stack))
        self.assertEqual((cool["failures"], cool["dropped"]), (2, 2))
        event = self.events()[-1]
        self.assertEqual((event["retry"], event["attempt"], event["dropped"], event["status"]), (False, 2, 2, 401))
        self.assertNotIn("wait_s", event)
        self.assertFalse(any(row["role"] == "assistant" for row in self.history()))

    def test_unsaved_first_turn_reseeds_original_and_retry(self):
        self.say("ORIGINAL UNSAVED LETTER")
        sigs = self.queue()
        self.ok_turn(FAKE_CLI_API_ERROR="529", FAKE_CLI_NO_SAVE="1")
        first = self.calls()[-1]["argv"]
        first_id = first[first.index("--session-id") + 1]
        self.assertFalse(self.sid())
        self.assertFalse((self.cell / ".session_home").exists())
        self.assert_sum_noted()
        self.make_due()
        self.ok_turn()
        last = self.calls()[-1]
        self.assertNotIn("--resume", last["argv"])
        self.assertNotEqual(last["argv"][last["argv"].index("--session-id") + 1], first_id)
        self.assertTrue(last["stdin"].startswith("[aos] session: "), last["stdin"])
        self.assertIn("[user] ORIGINAL UNSAVED LETTER\n", last["stdin"])
        self.assertIn("--- end of record ---\n\n[aos] retry: ", last["stdin"])
        self.assertEqual(self.history()[-1]["aos"]["answer_to"], sigs)
        self.assertFalse((self.stack / "retry.json").exists())

    def test_tool_warning_is_in_continuation_prompt(self):
        self.say("task")
        self.ok_turn(FAKE_CLI_API_ERROR="529", FAKE_CLI_TOOL="Bash")
        self.assertEqual(self.retry()["tools"], 1)
        self.make_due()
        self.ok_turn()
        self.assertIn("You had already called tools in that turn (1 calls): "
                      "check what is already done before doing anything again.", self.calls()[-1]["stdin"])

    def test_retry_record_without_cooldown_still_takes_priority(self):
        self.say("owed")
        sigs = self.queue()
        self.ok_turn(FAKE_CLI_API_ERROR="529")
        (self.stack / "cooldown.json").unlink()
        self.say("new mail")
        waiting = self.queue()
        self.ok_turn()
        self.assertTrue(self.calls()[-1]["stdin"].startswith("[aos] retry: "))
        self.assertEqual(self.queue(), waiting)
        self.assertEqual(self.history()[-1]["aos"]["answer_to"], sigs)

    def test_goal_turn_without_letters_retries_once_and_clears(self):
        self.say("first")
        self.ok_turn()
        (self.stack / "goal.json").write_text(json.dumps({
            "text": "Write the report.", "status": "active", "reason": "", "reminded": 0, "limit": 10,
            "set_by": "outside", "updated_by": "outside", "updated_at": "2026-11-16T00:00:00Z"}))
        self.ok_turn(FAKE_CLI_API_ERROR="529")
        self.assertEqual(self.retry()["letters"], [])
        self.make_due()
        self.ok_turn()
        self.assertTrue(self.calls()[-1]["stdin"].startswith("[aos] retry: "))
        self.assertTrue(self.calls()[-1]["stdin"].endswith("Its prompt is already in this conversation, or in the record above. "
                                                           "Go on from where it stopped and answer it now."))
        self.assertFalse((self.stack / "retry.json").exists())
        self.assertIsNone(cooldown.read(str(self.stack)))
        self.ok_turn()
        self.assertFalse(self.calls()[-1]["stdin"].startswith("[aos] retry:"))

    def check_permanent(self, **env):
        self.say("permanent task")
        sigs = self.queue()
        result = self.turn(**env)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("CliFailed", result.stderr)
        self.assertFalse((self.stack / "retry.json").exists())
        self.assert_failed_letters(sigs)
        self.assertEqual(cooldown.read(str(self.stack))["dropped"], 1)
        self.assertIs(cooldown.read(str(self.stack))["retry"], False)   # cooldown-1118：永久錯＝退 1 停下
        event = self.events()[-1]
        self.assertEqual((event["retry"], event["attempt"], event["dropped"]), (False, 1, 1))
        self.assertNotIn("wait_s", event)
        return event

    def test_401_is_permanent(self):
        self.assertEqual(self.check_permanent(FAKE_CLI_API_ERROR="401")["status"], 401)

    def test_404_is_permanent(self):
        self.assertEqual(self.check_permanent(FAKE_CLI_API_ERROR="404")["status"], 404)

    def test_usage_limit_without_api_fields_is_permanent(self):
        self.assertEqual(self.check_permanent(FAKE_CLI_FAIL="1")["cause"], "unknown")

    def test_missing_result_is_permanent(self):
        missing = self.t / "missing_result.py"
        missing.write_text("#!" + sys.executable + "\nimport json, sys\nsys.stdin.read()\n"
                           "print(json.dumps({'type': 'system', 'session_id': 'missing'}))\nsys.exit(1)\n")
        missing.chmod(0o755)
        (self.bin / "claude").unlink()
        (self.bin / "claude").symlink_to(missing)
        self.assertEqual(self.check_permanent()["cause"], "no_result")

    def test_compact_temporary_failure_drops_slash_without_retry(self):
        self.say("establish conversation")
        self.ok_turn()
        self.say("/compact")
        sigs = self.queue()
        self.ok_turn(FAKE_CLI_API_ERROR="529")
        self.assert_failed_letters(sigs)
        self.assertFalse((self.stack / "retry.json").exists())
        self.assertEqual((cooldown.read(str(self.stack))["failures"], cooldown.read(str(self.stack))["dropped"]), (1, 1))
        event = self.events()[-1]
        self.assertEqual((event["retry"], event["attempt"], event["dropped"]), (True, 1, 1))
        self.assert_sum_noted()

    def check_nontext(self, value):
        self.say("nontext")
        sigs = self.queue()
        result = self.turn(FAKE_CLI_RESULT_JSON=json.dumps(value))
        self.assert_one_cli_error(result)
        self.assertIn("claude's result is not text", result.stderr)
        self.assert_failed_letters(sigs)
        self.assertFalse(self.events()[-1]["retry"])
        self.assertEqual(self.events()[-1]["name"], "CliFailed")
        self.assertEqual(cooldown.read(str(self.stack))["dropped"], 1)
        self.assertFalse((self.stack / "retry.json").exists())

    def test_nontext_true(self):
        self.check_nontext(True)

    def test_nontext_object(self):
        self.check_nontext({"a": 1})

    def test_nontext_list(self):
        self.check_nontext([])

    def test_one_nontext_results_have_one_error_without_traceback(self):
        for value in (True, {"a": 1}, []):
            with self.subTest(value=value):
                result = self.turn("--one", stdin='{"prompt": "nontext tool form"}',
                                   FAKE_CLI_RESULT_JSON=json.dumps(value))
                self.assert_one_cli_error(result, "def")
                self.assertIn("claude's result is not text", result.stderr)

    def test_brain_failed_hook_failure_warns_and_retry_goes_on(self):
        # 11-21: brain_failed cannot block; a failing hook is one warning line and the temporary error is retried as without it
        self.capture.write_text(self.capture.read_text() + "sys.exit(3)\n")
        self.say("owed")
        sigs = self.queue()
        result = self.turn(FAKE_CLI_API_ERROR="529")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("aos-eca-turn: warning: hook failed (event brain_failed) failed: exited 3", result.stderr)
        self.assertNotIn("HookFailed", result.stderr)
        self.assertEqual(self.retry()["letters"], sigs)
        self.assertEqual(self.letters()["pending"], sigs)
        self.assert_sum_noted()
        self.assertIs(cooldown.read(str(self.stack))["retry"], True)
        self.assertTrue(self.events()[-1]["retry"])

    def test_after_queue_hook_failure_warns_and_api_error_stays_temporary(self):
        # 11-21: after_queue cannot block; a failing hook is one warning line, the 529 stays a temporary error (retried)
        after = self.defn / "after.py"
        after.write_text("#!" + sys.executable + "\nimport sys\nsys.exit(3)\n")
        after.chmod(0o755)
        self.declare({"after": {"event": "after_queue", "handler": after.name},
                      "failed": {"event": "brain_failed", "handler": self.capture.name}})
        self.say("task")
        sigs = self.queue()
        result = self.turn(FAKE_CLI_API_ERROR="529")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("aos-eca-turn: warning: hook after (event after_queue) failed: exited 3", result.stderr)
        self.assertEqual(self.letters(), {"pending": sigs, "dropped": []})
        self.assertTrue(self.events()[-1]["retry"])
        self.assertEqual(self.retry()["letters"], sigs)


class CodexUnchanged(RetryBase):
    kind = "codex"

    def test_failure_event_drop_and_due_pick_one_stay_unchanged(self):
        self.say("failed one", "failed two")
        sigs = self.queue()
        result = self.turn(FAKE_CLI_FAIL="1")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("CliFailed", result.stderr)
        self.assertEqual(self.queue(), [])
        self.assert_failed_letters(sigs)
        self.assertFalse((self.stack / "retry.json").exists())
        cool = cooldown.read(str(self.stack))
        self.assertEqual((cool["failures"], cool["dropped"]), (1, 2))
        event = self.events()[-1]
        self.assertEqual(set(event), {"event", "hook", "stack", "name", "reason"})
        self.assertEqual(event["name"], "CliFailed")
        self.say("OLDEST WAITING", "SECOND WAITING")
        oldest, second = self.queue()
        self.make_due()
        self.ok_turn()
        self.assertEqual(self.queue(), [second])
        self.assertTrue(self.calls()[-1]["stdin"].endswith("OLDEST WAITING"))
        self.assertNotIn("SECOND WAITING", self.calls()[-1]["stdin"])
        self.assertFalse(self.calls()[-1]["stdin"].startswith("[aos] retry:"))
        self.assertEqual(self.history()[-1]["aos"]["answer_to"], [oldest])
        self.assertIsNone(cooldown.read(str(self.stack)))

    def test_stray_retry_record_is_ignored(self):
        rec = {"letters": ["stray-letter"], "attempt": 9, "tools": 2, "code": "CliFailed",
               "cause": "api_529", "reason": "old failure", "at": "2026-11-16T08:00:00Z"}
        (self.stack / "retry.json").write_text(json.dumps(rec))
        self.say("codex normal")
        sigs = self.queue()
        self.ok_turn()
        self.assertEqual(self.calls()[-1]["stdin"], "codex normal")
        self.assertEqual(self.history()[-1]["aos"]["answer_to"], sigs)
        self.assertEqual(self.retry(), rec)
        self.assertEqual(self.queue(), [])
        self.assertEqual(self.events(), [])


if __name__ == "__main__":
    unittest.main()
