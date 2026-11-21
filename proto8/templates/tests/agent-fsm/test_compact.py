# Verify compact requests, history folding, reply matching, and continued work with fake commands.
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile
import time
import unittest
os.environ.setdefault("AOS_HOME", str(Path(__file__).resolve().parents[3]))   # 路徑規則一（11-17）：範本的格只經 AOS_HOME 找 lib，測試給它這份 proto8
from unittest import mock

import test_reply_match as reply_tests

CELLS = reply_tests.CELLS
PROTO = reply_tests.PROTO
sys.dont_write_bytecode = True
sys.path[:0] = [str(CELLS), str(PROTO / "py")]
import compact
from aos import ws as aos_ws

CALL = reply_tests.CALL
OLD = [{"role": "user", "content": "old question"},
       {"role": "assistant", "content": "old answer"},
       {"role": "user", "content": "another question"},
       {"role": "assistant", "tool_calls": [CALL]},
       {"role": "tool", "tool_call_id": "c1", "content": "result"},
       {"role": "assistant", "content": "finished"}]


def die(code, reason):
    raise RuntimeError(code + " " + reason)


class Compact(unittest.TestCase):
    setUp = reply_tests.ReplyMatch.setUp
    command = reply_tests.ReplyMatch.command
    send = reply_tests.ReplyMatch.send
    letter = reply_tests.ReplyMatch.letter
    history = reply_tests.ReplyMatch.history
    letters = reply_tests.ReplyMatch.letters

    def run_cell(self, name, code=0, *args, **env):
        r = subprocess.run([sys.executable, str(CELLS / (name + ".py")), *args],
                           env=dict(self.env, **env), capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, code, r.stderr)
        return r

    def setUp(self):
        reply_tests.ReplyMatch.setUp(self)
        self.command("aos-tools", "import json,sys\nif 'ls' in sys.argv: print(json.dumps([{'name':'echo','path':'/fake/echo','tooldef':{'parameters':{'type':'object'}}}]))\nelse: print('tool result')\n")
        self.warnings = []

    def request(self):
        return json.loads((self.stack / "think/request.json").read_text())["request"]

    def fold(self, content="The work summary.", **more):
        return compact.fold(str(self.stack), str(self.stack / "history.jsonl"),
                            dict({"role": "assistant", "content": content}, **more),
                            aos_ws, self.warnings.append, die)

    def removed(self):
        path = self.stack / "history_removed.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def start_idle(self, text="/compact"):
        self.history(OLD)
        name = self.letter(text)
        self.run_cell("idle")
        return name

    def start_mid(self, pending=True):
        self.history(OLD)
        name = self.letter("Keep working on the actual task") if pending else None
        if pending:
            self.run_cell("idle")
        else:
            self.history(OLD + [{"role": "user", "content": "[aos] goal: continue the work"}])
        self.history(self.history() + [{"role": "assistant", "tool_calls": [CALL]},
                                       {"role": "tool", "tool_call_id": "c1", "content": "result"}])
        requested = self.letter("/compact")
        self.run_cell("brain")
        return name, requested

    def test_between_turns_full_round_trip(self):
        name = self.start_idle()
        self.run_cell("brain")
        request = self.request()
        self.assertNotIn("tools", request)
        self.assertTrue(request["messages"][-1]["content"].startswith(compact.ASK_PREFIX))
        self.run_cell("wait", 10)
        self.run_cell("wait", 11, FAKE_MESSAGE=json.dumps({"role": "assistant", "content": "The work summary."}))
        h = self.history()
        self.assertEqual(len(h), 2)
        self.assertTrue(h[0]["content"].startswith("[aos] summary: lines 1-7, 7 messages. The work summary."))
        self.assertEqual(h[1]["aos"], {"answer_to": [name], "compact": True})
        self.assertEqual([r["op"] for r in self.removed()], ["compact"] * 7)
        self.assertIn("The work summary.", (self.stack / "handoff.md").read_text())
        self.assertEqual(self.letters()["pending"], [])
        self.assertEqual(aos_ws.answer_for(str(self.stack), name)[0], "answered")
        observed = json.loads((self.stack / "observed.jsonl").read_text().splitlines()[-1])
        self.assertEqual(observed["kind"], "compact")
        self.run_cell("brain", 10)
        self.run_cell("idle", 10)

    def test_mid_turn_keeps_pending_and_continues_tools(self):
        task, requested = self.start_mid()
        self.assertNotIn("tools", self.request())
        self.assertTrue(compact.state(str(self.stack))["mid_turn"])
        self.assertTrue(self.fold())
        h = self.history()
        self.assertEqual(h[2], {"role": "user", "content": "Keep working on the actual task", "aos": {"letter": task}})
        self.assertEqual(h[-1]["content"], compact.CONTINUE)
        self.assertEqual(self.letters()["pending"], [task])
        self.assertFalse((self.stack / "queue/new" / requested).exists())
        self.run_cell("brain")
        self.assertIn("tools", self.request())
        self.run_cell("wait", 10)
        self.run_cell("wait", FAKE_MESSAGE=json.dumps({"role": "assistant", "tool_calls": [CALL]}))
        self.run_cell("act")
        self.assertEqual(self.history()[-1]["role"], "tool")
        self.run_cell("brain")
        self.run_cell("wait", 10)
        self.run_cell("wait")
        self.assertEqual(self.history()[-1]["aos"]["answer_to"], [task])
        self.assertEqual(aos_ws.answer_for(str(self.stack), requested)[0], "answered")

    def test_entire_batch_is_taken_before_one_ask(self):
        self.history(OLD)
        a = self.letter("letter A")
        c = self.letter("/compact")
        b = self.letter("letter B")
        c2 = self.letter("/compact focus on files")
        self.run_cell("idle")
        h = self.history()
        self.assertEqual([m["content"] for m in h[6:8]], ["letter A", "letter B"])
        self.assertEqual(sum(compact.is_ask(m) for m in h), 1)
        self.assertEqual(compact.state(str(self.stack))["letters"], [c, c2])
        self.assertTrue(self.fold())
        self.assertEqual([m["aos"]["letter"] for m in self.history()[2:]], [a, b])
        self.assertEqual(self.letters()["pending"], [a, b])
        self.assertEqual(list((self.stack / "queue/cur").iterdir()), [])

    def test_short_history_answers_without_folding(self):
        self.history(OLD[:2])
        c = self.letter("/compact")
        self.run_cell("idle", 10)
        self.assertEqual(self.history()[:2], OLD[:2])
        self.assertEqual(self.history()[2]["aos"], {"answer_to": [c], "compact": True, "skipped": True})
        self.assertEqual(aos_ws.answer_for(str(self.stack), c),
                         ("answered", compact.SKIP % (2, compact.MIN_ROWS)))
        self.assertFalse((self.stack / "mailbox_warning.txt").exists())
        self.assertFalse((self.stack / "think/request.json").exists())

    def test_short_same_batch_does_not_strand_letter_a(self):
        a = self.letter("letter A")
        c = self.letter("/compact")
        self.run_cell("idle")
        self.assertEqual([m["role"] for m in self.history()], ["assistant", "user"])   # the short answer goes before letter A
        self.assertEqual(self.history()[1]["aos"]["letter"], a)
        self.assertEqual(aos_ws.answer_for(str(self.stack), c)[0], "answered")
        self.run_cell("brain")
        self.run_cell("wait", 10)
        self.run_cell("wait")
        self.assertEqual(aos_ws.answer_for(str(self.stack), a)[0], "answered")

    def test_empty_summary_restores_history_and_drops_letter(self):
        c = self.start_idle()
        self.assertFalse(self.fold("  "))
        self.assertEqual(self.history(), OLD)
        self.assertEqual(compact.state(str(self.stack))["phase"], "failed")
        self.assertEqual(aos_ws.answer_for(str(self.stack), c), ("dropped", "failed"))
        self.assertEqual([r["op"] for r in self.removed()], ["compact_failed"])
        self.run_cell("brain", 10)

    def test_extra_instructions_and_command_boundary(self):
        self.start_idle(" /compact focus on the open files \n")
        self.assertTrue(self.history()[-1]["content"].endswith("Extra instructions from the sender: focus on the open files"))
        self.assertEqual(compact.is_compact("/compactly"), (False, ""))
        self.assertEqual(compact.is_compact("/clear"), (False, ""))

    def test_external_summarize_before_reply_preserves_ask(self):
        self.start_idle()
        ask = self.history()[-1]
        self.run_cell("brain")
        self.run_cell("wait", 10)
        daemon = self.root / "daemon"
        daemon.mkdir()
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"history": "history.jsonl"}}))
        (daemon / "procs_state.json").write_text(json.dumps({"procs": {"fake": {
            "phase": "paused", "stack": str(self.stack), "ws": str(self.root), "def": str(self.defn)}}}))
        result = subprocess.run([str(PROTO / "bin/aos-agent"), "--daemon", str(daemon),
                                 "history", "--target", "fake", "summarize", "1-2", "Earlier summary"],
                                env=self.env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.history()[-1], ask)
        self.run_cell("wait", 11)
        self.assertEqual(compact.state(str(self.stack))["phase"], "done")
        self.assertEqual(len(self.history()), 2)

    def test_do_task_end_reports_missing_marker(self):
        self.start_idle()
        self.assertTrue(self.fold())
        task_cell = self.stack / "tools/do_task"
        task_cell.mkdir(parents=True)
        (task_cell / "tasks.json").write_text(json.dumps({"tasks": [{"call": "gone", "task": "old task", "started_at": "now"}]}))
        end_call = {"id": "end", "type": "function", "function": {"name": "do_task", "arguments": "{}"}}
        self.history(self.history() + [{"role": "assistant", "tool_calls": [end_call]}])
        self.command("aos-agent", "import json,os,sys\nfrom pathlib import Path\nif 'who' in sys.argv: print('fake')\nelse: print(json.dumps([{'message':json.loads(l)} for l in Path(os.environ['HISTORY']).read_text().splitlines()]))\n")
        r = subprocess.run([sys.executable, str(PROTO / "py/tools/agent/do_task/_entry")],
                           input=json.dumps({"op": "end", "summary": "Finished"}),
                           env=dict(self.env, AOS_STACK=str(task_cell), AOS_WS=str(self.root), HISTORY=str(self.stack / "history.jsonl")),
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("MarkerMissing", r.stdout)
        self.assertEqual(json.loads((task_cell / "tasks.json").read_text())["tasks"], [])

    def test_goal_reminder_after_between_turn_compact(self):
        self.start_idle()
        self.assertTrue(self.fold())
        (self.stack / "goal.json").write_text(json.dumps({"text": "Keep going", "status": "active", "limit": 10, "reminded": 0}))
        self.run_cell("idle")
        self.assertTrue(self.history()[-1]["content"].startswith("[aos] goal:"))

    def test_mid_turn_without_pending_never_returns_idle(self):
        self.start_mid(pending=False)
        self.assertTrue(self.fold())
        self.assertTrue(self.history()[1]["aos"]["compact"])
        self.assertEqual(self.letters()["pending"], [])
        self.run_cell("brain")
        self.assertIn("tools", self.request())
        self.run_cell("wait", 10)
        self.run_cell("wait", FAKE_MESSAGE=json.dumps({"role": "assistant", "tool_calls": [CALL]}))
        self.run_cell("act")
        self.assertEqual(self.history()[-1]["role"], "tool")

    def test_task_mode_request_keeps_summary(self):
        self.start_mid()
        original = self.history()
        self.run_cell("brain", 0, "--history", "task")
        self.assertEqual(len(self.request()["messages"]), len(original))
        self.fold()
        self.run_cell("brain", 0, "--history", "task")
        self.assertTrue(self.request()["messages"][0]["content"].startswith("[aos] summary:"))
        self.assertEqual(self.request()["messages"][-1]["content"], compact.CONTINUE)
        self.assertTrue(all("aos" not in m for m in self.request()["messages"]))

    def test_idle_does_not_take_mail_while_asking(self):
        self.start_idle()
        before = self.history()
        new = self.letter("new work")
        self.run_cell("idle")
        self.assertEqual(self.history(), before)
        self.assertTrue((self.stack / "queue/new" / new).exists())
        self.assertNotIn(new, self.letters()["pending"])

    def test_compact_bypasses_both_queue_hooks(self):
        hook = self.defn / "fail.py"
        hook.write_text("#!" + sys.executable + "\nimport sys\nsys.exit(1)\n")
        hook.chmod(0o755)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {}, "hookeds": "hookeds.json"}))
        (self.defn / "hookeds.json").write_text(json.dumps({name: {"event": name, "handler": "fail.py"} for name in ("before_queue", "after_queue")}))
        self.start_idle()
        self.assertTrue(compact.asking(str(self.stack), self.history()))

    def test_brain_only_claims_mail_at_safe_foldable_boundary(self):
        self.history(OLD[:2] + [{"role": "user", "content": "new"}])
        c = self.letter("/compact")
        other = self.letter("ordinary letter")
        self.run_cell("brain")
        self.assertTrue((self.stack / "queue/new" / c).exists())
        self.assertTrue((self.stack / "queue/new" / other).exists())
        self.history(OLD + [{"role": "assistant", "tool_calls": [CALL]}])
        self.run_cell("brain", 10)
        self.assertTrue((self.stack / "queue/new" / c).exists())
        self.history(self.history() + [{"role": "tool", "tool_call_id": "c1", "content": "result"}])
        self.run_cell("brain")
        self.assertFalse((self.stack / "queue/new" / c).exists())
        self.assertTrue((self.stack / "queue/cur" / other).exists())
        self.assertEqual(compact.state(str(self.stack))["letters"], [c])

    def test_foldable_count_excludes_pending_and_trailing_users(self):
        rows = [{"role": "user", "content": "pending", "aos": {"letter": "p"}}, *OLD[:2],
                {"role": "user", "content": "reminder"}]
        aos_ws.letters_take(str(self.stack), ["p"])
        self.assertEqual(compact.foldable(str(self.stack), rows, aos_ws), 2)

    def test_fingerprint_retry_does_not_duplicate_removed(self):
        self.start_idle()
        fingerprint = compact.fingerprint
        calls = []

        def changing(path):
            actual = fingerprint(path)
            calls.append(actual)
            return (actual[0] + 1, actual[1]) if len(calls) == 2 else actual

        with mock.patch.object(compact, "fingerprint", side_effect=changing):
            self.assertTrue(self.fold())
        self.assertEqual(len(self.removed()), 7)

    def test_give_up_write_race_keeps_asked_state(self):
        self.start_idle()
        with mock.patch.object(compact, "replace", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "WriteFailed"):
                self.fold("")
        self.assertEqual(compact.state(str(self.stack))["phase"], "asked")
        self.assertTrue(compact.is_ask(self.history()[-1]))
        self.assertEqual(len(self.letters()["pending"]), 1)


class CompactDaemon(unittest.TestCase):
    def test_automatic_compact_twice_with_real_daemon(self):
        scratch = Path.home() / ".aos/scratch/ok-fsmwrap"
        scratch.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="compact-e2e-", dir=scratch)).resolve()
        daemon, kernel, definition = root / "daemon", root / "kernel", root / "definition"
        daemon.mkdir()
        kernel.mkdir()
        shutil.copytree(CELLS, definition, ignore=shutil.ignore_patterns("__pycache__"))

        def write(path, value):
            path.write_text(json.dumps(value), encoding="utf-8")

        write(definition / "llm.json", {"model": "growing"})
        write(definition / "tools.json", {"tools": {"peek_now_time": {"path": str(PROTO / "py/tools/base/peek_now_time")}}})
        write(definition / "hookeds.json", {"context_wrap": {
            "event": "on_clock", "every_cycles": 1, "config": {"percent": 35, "wrap": False},
            "handler": str(PROTO / "py/tools/agent/context_wrap"), "timeout_ms": 20000}})
        write(definition / "loop.json", {"exec": "fsm.json", "interval_ms": 10,
                                        "ctl": "ctl.json", "state": "state.json", "state_flux": "state_flux.json"})
        endpoint = root / "endpoint.py"
        endpoint.write_text("#!" + sys.executable + "\n# Return increasing token usage and compact summaries for an integration test.\n" + '''import json,sys,time
from pathlib import Path
root = Path(__file__).resolve().parent
request = json.load(sys.stdin)['request']
state_path = root / 'endpoint_state.json'
state = json.loads(state_path.read_text()) if state_path.exists() else {'compacts':0,'calls':0}
last = request['messages'][-1]
summary = last.get('role') == 'user' and str(last.get('content','')).startswith('[aos] compact: your conversation')
if summary:
    assert 'tools' not in request
    state['compacts'] += 1
    state['calls'] = 0
    message = {'role':'assistant','content':'Integration summary %d: keep doing the small time checks.' % state['compacts']}
    used = 10
else:
    state['calls'] += 1
    used = min(900, 100 * state['calls'])
    if state['compacts'] >= 2 and state['calls'] >= 3:
        message = {'role':'assistant','content':'Finished the time checks.'}
        used = 100
    else:
        message = {'role':'assistant','content':None,'tool_calls':[{'id':'time_%d_%d' % (state['compacts'],state['calls']),
            'type':'function','function':{'name':'peek_now_time','arguments':'{}'}}]}
state_path.write_text(json.dumps(state))
with (root / 'requests.jsonl').open('a') as stream:
    stream.write(json.dumps({'compact':summary,'used':used,'request':request}) + '\\n')
time.sleep(.12)
print(json.dumps({'message':message,'usage':{'prompt_tokens':used,'completion_tokens':5},'model':'fake-growing'}))
''')
        endpoint.chmod(0o755)
        write(root / "kernel.json", {"exec": str(endpoint), "endpoint": "growing",
                                     "endpoints": {"growing": {"context": 1000}}})
        write(root / "daemon.json", {"interval_ms": 10, "procs": {"_clock": {
            "exec": {"argv": ["aos-clock", str(daemon / "clock")]}, "interval_ms": 10}}})
        write(root / "kernel_daemon.json", {"interval_ms": 10, "exec": {"argv": [
            str(PROTO / "py/tools/aos/kernel_llm/_entry"), str(root / "kernel.json")]}})
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") or k == "AOS_HOME"}
        bins = [str(PROTO / "bin")]
        env.update(PATH=os.pathsep.join(bins + [env["PATH"]]),
                   PYTHONPATH=os.pathsep.join([str(PROTO / "py")]),
                   PYTHONDONTWRITEBYTECODE="1", AOS_HOME=str(PROTO), AOS_STACK=str(daemon),
                   AOS_CD=str(root), AOS_WS=str(root), AOS_DAEMON=str(daemon), AOS_CLOCK=str(daemon / "clock"),
                   AOS_LLM_KERNEL=str(kernel))
        log = (root / "daemon.log").open("w+")
        processes = []
        self.addCleanup(log.close)

        def shutdown():
            for process, stack in reversed(processes):
                if process.poll() is None:
                    cwd = Path(os.readlink("/proc/%d/cwd" % process.pid)).resolve()
                    self.assertEqual(cwd, root)
                    self.assertTrue(stack.is_relative_to(scratch))
                    print("shutdown", stack)
                    subprocess.run(["aos-daemon-ctl", "-d", str(stack), "shutdown"],
                                   cwd=root, env=env, capture_output=True, timeout=30)
                    process.wait(timeout=30)
        self.addCleanup(shutdown)
        for config, stack in (("daemon.json", daemon), ("kernel_daemon.json", kernel)):
            process = subprocess.Popen(["aos-daemon", str(root / config)], cwd=root,
                                       env=dict(env, AOS_STACK=str(stack)), stdout=log, stderr=log)
            processes.append((process, stack))

        def until(predicate, timeout=60):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                self.assertTrue(all(p.poll() is None for p, _ in processes), (root / "daemon.log").read_text()[-4000:])
                try:
                    found = predicate()
                except (FileNotFoundError, ValueError, KeyError):
                    found = False
                if found:
                    return found
                time.sleep(.03)
            self.fail("timed out: %s\n%s" % (root, (root / "daemon.log").read_text()[-4000:]))

        def agent(*args):
            result = subprocess.run(["aos-agent", "--daemon", str(daemon), *args], cwd=root,
                                    env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            return result.stdout.strip()

        until(lambda: (daemon / "procs_state.json").exists())
        agent("ctl", "add", "--name", "compact", "--ws", str(root), str(definition))
        stack = Path(agent("ctl", "where", "--target", "compact"))
        task = agent("say", "--target", "compact", "Do the small time checks and retain the task through summaries.").splitlines()[-1]
        until(lambda: (root / "endpoint_state.json").exists() and
              json.loads((root / "endpoint_state.json").read_text())["compacts"] >= 2)
        until(lambda: aos_ws.answer_for(str(stack), task)[0] == "answered")
        until(lambda: json.loads((stack / "hookeds/context_wrap/state.json").read_text())["phase"] == "idle")
        agent("ctl", "pause", "compact")
        history = aos_ws.history(str(stack))
        self.assertTrue(history[0]["content"].startswith("[aos] summary:"))
        self.assertIn("Integration summary 2", history[0]["content"])
        removed = [json.loads(line) for line in (stack / "history_removed.jsonl").read_text().splitlines()]
        self.assertTrue(any(row["op"] == "compact" and row["message"].get("tool_calls") for row in removed))
        handoff = (stack / "handoff.md").read_text()
        self.assertIn("Integration summary 1", handoff)
        self.assertIn("Integration summary 2", handoff)
        requests = [json.loads(line) for line in (root / "requests.jsonl").read_text().splitlines()]
        self.assertEqual(sum(row["compact"] for row in requests), 2)
        self.assertTrue(any(row["used"] >= 350 and not row["compact"] for row in requests))
        self.assertTrue(all(not row["compact"] or "tools" not in row["request"] for row in requests))
        observed = [json.loads(line) for line in (stack / "observed.jsonl").read_text().splitlines()]
        self.assertEqual(sum(row["kind"] == "compact" for row in observed), 2)
        self.assertEqual(json.loads((kernel / "endpoints.json").read_text())["growing"]["context"], 1000)
        self.assertEqual(aos_ws.letters_pending(str(stack)), [])
        print("integration artifacts:", root)


if __name__ == "__main__":
    unittest.main()
