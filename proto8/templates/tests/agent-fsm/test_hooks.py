"""Test the hooks of agent-fsm (py/aos/agentlib/hooks.py and the four cells): six events, changes, blocking, on_fail, timeout, match, layering, tool_added."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
os.environ.setdefault("AOS_HOME", str(Path(__file__).resolve().parents[3]))   # 路徑規則一（11-17）：範本的格只經 AOS_HOME 找 lib，測試給它這份 proto8
from unittest import mock

CELLS = Path(__file__).resolve().parents[2] / 'agent-fsm'   # 範本本身（測試 11-10 起搬到 templates/tests/<範本名>/）
PROTO = CELLS.parents[1]
sys.path.insert(0, str(PROTO / "py"))
from aos.agentlib import hooks  # noqa: E402

CALL = {"id": "c1", "type": "function", "function": {"name": "echo", "arguments": '{"text":"snow"}'}}
PRELUDE = """import json, os, sys, time
ev = json.load(sys.stdin)
with open(%r, "a") as f:
    f.write(json.dumps(ev) + "\\n")
"""


class Hooks(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="aos-hooks-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.defn, self.stack, self.bin = self.root / "def", self.root / "st", self.root / "bin"
        for d in (self.defn, self.stack, self.bin):
            d.mkdir()
        (self.defn / "interfaces.json").write_text(json.dumps(
            {"aos-agent": {"tools": "tools.json", "llm": "llm.json", "hooks": "hooks.json"}}))
        (self.defn / "tools.json").write_text("{}")
        (self.defn / "llm.json").write_text('{"model":"local"}')
        self.log = self.root / "log.jsonl"
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") or k == "AOS_HOME"}
        self.env = dict(env, AOS_STACK=str(self.stack), AOS_CD=str(self.defn), HOOKDIR=str(self.defn),
                        PATH=os.pathsep.join([str(self.bin), str(PROTO / "bin")]
                                             + [env["PATH"]]))
        self.tools(["echo"])
        self.command("aos-llm", """import json, os, sys
if sys.argv[1] == 'send':
    sys.stdin.read(); print('letter-1'); sys.exit(0)
code = int(os.environ.get('FAKE_RECV', '0'))
if code == 0:
    print(os.environ.get('FAKE_REPLY', json.dumps({'message': {'role': 'assistant', 'content': 'ok'}})))
elif code == 1:
    print(os.environ.get('FAKE_REPLY', ''))
sys.exit(code)
""")

    # ---- 小工具
    def command(self, name, body):
        path = self.bin / name
        path.write_text("#!" + sys.executable + "\n" + body)
        path.chmod(0o755)

    def tools(self, names):
        """假的 aos-tools：ls 列 names；call 把 stdin 原樣印回（echo）。"""
        listed = [{"name": n, "path": "/fake/" + n, "tooldef": {}} for n in names]
        self.command("aos-tools", "import json, sys\nif 'ls' in sys.argv: print(json.dumps(%r))\n"
                                  "else: sys.stdout.buffer.write(sys.stdin.buffer.read())\n" % listed)

    def hook(self, name, body="", folder=None):
        """hook 腳本：把事件 JSON 記一行到 log，然後跑 body（ev＝事件）。"""
        path = (folder or self.defn) / (name + ".py")
        path.write_text("#!" + sys.executable + "\n" + PRELUDE % str(self.log) + body)
        path.chmod(0o755)
        return path.name

    def declare(self, table, where=None):
        (where or self.defn).joinpath("hooks.json").write_text(json.dumps({"hooks": table}))

    def events(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def run_cell(self, name, code=0, **env):
        r = subprocess.run([sys.executable, str(CELLS / (name + ".py"))], env=dict(self.env, **env),
                           capture_output=True, text=True, timeout=20)
        self.assertEqual(r.returncode, code, r.stderr)
        return r

    def letter(self, content):
        """寄一封進 queue；回信名（aos-post send 印的；回答配對 aos.letter 記的就是它）。"""
        box = self.stack / "queue"
        subprocess.run(["aos-post", "init", str(box)], env=self.env, check=True, capture_output=True)
        return subprocess.run(["aos-post", "send", "--ordered", str(box)], env=self.env, check=True, capture_output=True,
                              input=json.dumps({"role": "user", "content": content}), text=True).stdout.strip()

    def letters(self):
        path = self.stack / "letters.json"
        return json.loads(path.read_text()) if path.exists() else None

    def history(self, messages=None):
        path = self.stack / "history.jsonl"
        if messages is not None:
            path.write_text("".join(json.dumps(m) + "\n" for m in messages))
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []

    def act_history(self):
        self.history([{"role": "user", "content": "hi"}, {"role": "assistant", "tool_calls": [CALL]}])

    # ---- queue
    def test_queue_before_changes_content_and_queue_after_sees_it(self):
        self.declare({"a_up": {"event": "before_queue",          # change 預設開（11-10 深夜）

                               "handler": self.hook("up", 'print(json.dumps({"content": ev["content"].upper()}))')},
                      "b_after": {"event": "after_queue", "handler": self.hook("after")}})
        name = self.letter("hello")
        self.run_cell("idle")
        self.assertEqual(self.history(), [{"role": "user", "content": "HELLO", "aos": {"letter": name}}])
        self.assertEqual(self.letters()["pending"], [name])
        before, after = self.events()
        self.assertEqual((before["event"], before["hook"], before["content"]), ("before_queue", "a_up", "hello"))
        self.assertEqual(before["stack"], str(self.stack))
        self.assertEqual((after["event"], after["content"], after["letter"]), ("after_queue", "HELLO", before["letter"]))
        self.assertTrue((self.stack / "hooks" / "a_up" / "event.json").is_file())

    def test_queue_before_drops_letter(self):
        self.declare({"drop": {"event": "before_queue", "intercept": True, "handler": self.hook("drop", "sys.exit(10)")},
                      "z": {"event": "after_queue", "handler": self.hook("z")}})
        name = self.letter("spam")
        self.run_cell("idle", code=10)
        self.assertEqual(self.history(), [])
        self.assertEqual(self.letters()["pending"], [])
        self.assertEqual([(x["letter"], x["reason"]) for x in self.letters()["dropped"]], [(name, "blocked")])
        self.assertEqual(os.listdir(self.stack / "queue" / "cur"), [])
        self.assertIn("dropped by hook drop", (self.stack / "mailbox_warning.txt").read_text())
        self.assertEqual([e["event"] for e in self.events()], ["before_queue"])

    def test_without_change_stdout_and_10_do_nothing(self):
        self.declare({"n": {"event": "before_queue", "intercept": False, "handler": self.hook("n", 'print(json.dumps({"content": "X"})); sys.exit(10)')}})
        name = self.letter("keep")
        self.run_cell("idle")
        self.assertEqual(self.history(), [{"role": "user", "content": "keep", "aos": {"letter": name}}])

    # ---- on_fail、逾時、wait false
    def test_on_fail_stop_keeps_letter_in_cur(self):
        self.declare({"bad": {"event": "before_queue", "handler": self.hook("bad", "sys.exit(3)")}})
        name = self.letter("again")
        r = self.run_cell("idle", code=1)
        self.assertIn("agent-fsm: error: HookFailed hook bad (event before_queue) failed: exited 3", r.stderr)
        self.assertEqual(self.history(), [])
        self.assertIsNone(self.letters())                                     # hook 停下：還沒交出、pending 不記
        self.assertEqual(len(os.listdir(self.stack / "queue" / "cur")), 1)   # P-12：下次重跑再接
        self.declare({})
        self.run_cell("idle")
        self.assertEqual(self.history(), [{"role": "user", "content": "again", "aos": {"letter": name}}])
        self.assertEqual(self.letters(), {"pending": [name], "dropped": []})

    def test_on_fail_continue_warns_and_goes_on(self):
        self.declare({"bad": {"event": "before_queue", "on_error": "continue", "intercept": True,
                              "handler": self.hook("bad", 'print("not json")')}})
        name = self.letter("go")
        r = self.run_cell("idle")
        self.assertIn("agent-fsm: warning: hook bad (event before_queue) failed: stdout is not JSON", r.stderr)
        self.assertEqual(self.history(), [{"role": "user", "content": "go", "aos": {"letter": name}}])

    def test_timeout_kills_and_fails(self):
        self.declare({"slow": {"event": "after_queue", "timeout_ms": 300, "handler": self.hook("slow", "time.sleep(30)")}})
        self.letter("t")
        started = time.monotonic()
        r = self.run_cell("idle", code=1)
        self.assertLess(time.monotonic() - started, 10)
        self.assertIn("HookFailed hook slow (event after_queue) failed: did not finish in 300 ms", r.stderr)

    def test_no_wait_does_not_block(self):
        self.declare({"bg": {"event": "after_queue", "async": True,
                             "handler": self.hook("bg", 'time.sleep(1.5); open(%r, "w").write("x")' % str(self.root / "late"))}})
        self.letter("w")
        started = time.monotonic()
        with open(self.root / "err.txt", "w") as err:              # stderr 是透出的：管子會被 hook 拿著，改接檔
            p = subprocess.run([sys.executable, str(CELLS / "idle.py")], env=self.env, stdout=subprocess.DEVNULL,
                               stderr=err, timeout=20)
        self.assertEqual(p.returncode, 0)
        self.assertLess(time.monotonic() - started, 1.4)
        self.assertFalse((self.root / "late").exists())
        deadline = time.monotonic() + 10
        while not (self.root / "late").exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertTrue((self.root / "late").exists())

    # ---- tool
    def test_tool_before_changes_arguments(self):
        self.declare({"args": {"event": "before_tool", "intercept": True, "condition": "echo",
                               "handler": self.hook("args", 'print(json.dumps({"arguments": {"text": "rain"}}))')},
                      "after": {"event": "after_tool", "handler": self.hook("after")}})
        self.act_history()
        self.run_cell("act")
        h = self.history()
        self.assertEqual(json.loads(h[-1]["content"]), {"text": "rain"})
        self.assertEqual(h[1]["tool_calls"], [CALL])                         # 紀錄不動
        before, after = self.events()
        self.assertEqual((before["name"], before["id"], before["arguments"]), ("echo", "c1", {"text": "snow"}))
        self.assertEqual((after["event"], after["arguments"], after["code"], after["timed_out"]),
                         ("after_tool", {"text": "rain"}, 0, False))

    def test_tool_before_blocks(self):
        self.declare({"no": {"event": "before_tool", "intercept": True, "handler": self.hook("no", 'print("not allowed"); sys.exit(10)')},
                      "after": {"event": "after_tool", "handler": self.hook("after")}})
        self.act_history()
        self.run_cell("act")
        self.assertEqual(self.history()[-1]["content"], "not allowed\n")
        self.assertEqual([e["event"] for e in self.events()], ["before_tool"])   # 攔下的不觸發 after_tool
        self.assertFalse((self.stack / "observed.jsonl").exists())
        self.declare({"no": {"event": "before_tool", "intercept": True, "handler": self.hook("no", "sys.exit(10)")}})
        self.act_history()
        self.run_cell("act")
        self.assertEqual(self.history()[-1]["content"], "[aos] hook: tool echo blocked by hook no.")

    def test_tool_after_changes_content_and_match_filters(self):
        self.declare({"a": {"event": "after_tool", "intercept": True, "condition": ["echo"],
                            "handler": self.hook("a", 'print(json.dumps({"content": "[" + ev["content"] + "]"}))')},
                      "b": {"event": "after_tool", "condition": "other", "handler": self.hook("b")}})
        self.act_history()
        self.run_cell("act")
        self.assertEqual(self.history()[-1]["content"], '[{"text":"snow"}]')
        self.assertEqual([e["hook"] for e in self.events()], ["a"])

    def test_bad_content_type_is_a_failure(self):
        self.declare({"a": {"event": "after_tool", "intercept": True, "handler": self.hook("a", 'print(json.dumps({"content": 5}))')}})
        self.act_history()
        r = self.run_cell("act", code=1)
        self.assertIn("HookFailed hook a (event after_tool) failed: content in stdout must be a string", r.stderr)
        self.assertEqual(len(self.history()), 2)                             # 沒接進 history，重跑再跑一次

    # ---- brain_failed、tool_added
    def test_brain_failed_on_kernel_error_and_bad_reply(self):
        self.declare({"bf": {"event": "brain_failed", "condition": ["BrainFailed", "ReplyBad"], "handler": self.hook("bf")}})
        (self.stack / "think").mkdir()
        (self.stack / "think" / "pending.txt").write_text("letter-1\n")
        r = self.run_cell("wait", code=1, FAKE_RECV="1")
        self.assertIn("agent-fsm: error: BrainFailed", r.stderr)
        (self.stack / "think" / "pending.txt").write_text("letter-1\n")
        self.run_cell("wait", code=1, FAKE_REPLY="nope")
        self.assertEqual([(e["name"], e["reason"][:15]) for e in self.events()],
                         [("BrainFailed", "aos-llm recv ex"), ("ReplyBad", "aos-llm recv di")])

    def test_budget_missing_hook_gets_kernel_reason_not_brain_failed(self):
        msg = 'budget.senders key "worker" (sender worker): max_calls 150 reached in this window (day); not run'
        self.declare({"budget": {"event": "brain_failed", "condition": ["BudgetMissing"],
                                 "handler": self.hook("budget")},
                      "broken": {"event": "brain_failed", "condition": ["BrainFailed"],
                                 "handler": self.hook("broken")}})
        (self.stack / "think").mkdir()
        (self.stack / "think" / "pending.txt").write_text("letter-1\n")
        self.run_cell("wait", code=10, FAKE_RECV="1",
                      FAKE_REPLY=json.dumps({"error": {"code": "BudgetMissing", "msg": msg}}))
        self.assertEqual([(e["event"], e["hook"], e["name"], e["reason"]) for e in self.events()],
                         [("brain_failed", "budget", "BudgetMissing", msg)])

    def test_brain_failed_event_carries_the_error_object(self):
        msg = "budget for this window (hour) is used up; not run"
        error = {"code": "BudgetMissing", "msg": msg, "window": "hour", "resets_at": None, "max": 5}
        self.declare({"all": {"event": "brain_failed", "handler": self.hook("all")}})
        (self.stack / "think").mkdir()
        (self.stack / "think" / "pending.txt").write_text("letter-1\n")
        self.run_cell("wait", code=10, FAKE_RECV="1", FAKE_REPLY=json.dumps({"error": error}))
        (self.stack / "think" / "pending.txt").write_text("letter-1\n")
        plain = {"code": "EndpointFailed", "msg": "boom"}
        self.run_cell("wait", code=1, FAKE_RECV="1", FAKE_REPLY=json.dumps({"error": plain}))
        (self.stack / "think" / "pending.txt").write_text("letter-1\n")
        self.run_cell("wait", code=1, FAKE_RECV="1", FAKE_REPLY="nope")          # no error object parsed: no field
        events = self.events()
        self.assertEqual([e["name"] for e in events], ["BudgetMissing", "BrainFailed", "BrainFailed"])
        self.assertEqual(events[0]["error"], error)
        self.assertEqual(events[1]["error"], plain)
        self.assertNotIn("error", events[2])

    def test_brain_failed_window_all_fires_hook_then_stops(self):
        msg = "budget for this window (all) is used up; not run"
        self.declare({"budget": {"event": "brain_failed", "condition": ["BudgetMissing"], "handler": self.hook("budget")}})
        (self.stack / "think").mkdir()
        (self.stack / "think" / "pending.txt").write_text("letter-1\n")
        error = {"code": "BudgetMissing", "msg": msg, "window": "all", "resets_at": None}
        r = self.run_cell("wait", code=1, FAKE_RECV="1", FAKE_REPLY=json.dumps({"error": error}))
        self.assertIn("agent-fsm: error: BudgetMissing " + msg + " (window all: it never resets", r.stderr)
        self.assertEqual([(e["name"], e["error"]["window"]) for e in self.events()], [("BudgetMissing", "all")])
        self.assertFalse((self.stack / "cooldown.json").exists())

    def test_tool_added_first_run_only_records(self):
        self.declare({"new": {"event": "tool_added", "handler": self.hook("new")}})
        self.history([{"role": "user", "content": "hi"}])
        self.run_cell("brain")
        self.assertEqual(self.events(), [])
        self.assertEqual(json.loads((self.stack / hooks.SEEN).read_text()), ["echo"])
        self.tools(["echo", "clock", "web"])
        self.run_cell("brain")
        self.assertEqual([(e["name"], e["path"]) for e in self.events()], [("clock", "/fake/clock"), ("web", "/fake/web")])
        self.run_cell("brain")
        self.assertEqual(len(self.events()), 2)
        self.declare({})
        self.run_cell("brain")
        self.assertFalse((self.stack / hooks.SEEN).exists())

    # ---- 清單：疊兩份、null、路徑、壞的
    def test_stack_overrides_definition_and_null_turns_off(self):
        self.declare({"a": {"event": "after_queue", "handler": self.hook("defa")},
                      "b": {"event": "after_queue", "handler": self.hook("defb")}})
        self.declare({"a": {"event": "after_queue", "handler": self.hook("mine", folder=self.stack)}, "b": None}, self.stack)
        loaded = hooks.load(str(self.defn), str(self.stack))
        self.assertEqual(sorted(loaded), ["a"])
        self.assertEqual((loaded["a"]["from"], loaded["a"]["base"], loaded["a"]["async"], loaded["a"]["timeout_ms"]),
                         (str(self.stack / "hooks.json"), str(self.stack), False, 60000))
        self.assertEqual(hooks.nulled(str(self.defn), str(self.stack)), ["b"])
        self.letter("x")
        self.run_cell("idle")
        self.assertEqual([e["hook"] for e in self.events()], ["a"])
        self.assertTrue((self.stack / "hooks" / "a" / "event.json").is_file())

    def test_directive_exec(self):
        self.hook("viaenv")
        self.declare({"d": {"event": "after_queue", "handler": {"$env": "HOOKDIR", "$path": "/viaenv.py"}}})
        self.letter("x")
        self.run_cell("idle")
        self.assertEqual([e["hook"] for e in self.events()], ["d"])

    def test_bad_list_is_hooks_bad(self):
        (self.defn / "hooks.json").write_text('{"hooks": {"a": {"event": "after_queue"}}}')
        self.letter("x")
        r = self.run_cell("idle", code=1)
        self.assertIn("agent-fsm: error: HooksBad hook a in", r.stderr)
        for entry in ({"event": "before_queue", "handler": "x", "condition": "m"},
                      {"event": "before_tool", "handler": "x", "on_error": "maybe"},
                      {"event": "before_tool", "handler": "x", "timeout_ms": -1},
                      {"event": "nope", "handler": "x"}):
            with self.assertRaises(hooks.HooksBad):
                hooks.validate_entry(entry)
        hooks.validate_entry({"event": "before_tool", "handler": "x", "intercept": True, "condition": ["a"], "whatever": 1})
        hooks.validate_entry({"event": "before_tool", "handler": "x", "timeout_ms": 0})   # 0＝不限時（252669c47，頂層 11-14）
        # change 預設開之後：不能改的事件、不等的 hook 寫 change: true＝自然不看回話，不報錯（11-10 深夜）
        hooks.validate_entry({"event": "after_queue", "handler": "x", "intercept": True})
        hooks.validate_entry({"event": "before_tool", "handler": "x", "intercept": True, "async": True})

    def test_change_on_unchangeable_event_ignores_stdout(self):
        self.declare({"talk": {"event": "after_queue", "handler": self.hook("talk", 'print("not json at all")')}})
        name = self.letter("hi")
        self.run_cell("idle")
        self.assertEqual(self.history(), [{"role": "user", "content": "hi", "aos": {"letter": name}}])

    def test_nothing_declared_starts_nothing(self):
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {}}))
        with mock.patch("subprocess.Popen", side_effect=AssertionError("started a process")), \
                mock.patch("subprocess.run", side_effect=AssertionError("started a process")):
            r = hooks.fire("before_queue", {"content": "c"}, str(self.defn), str(self.stack))
            self.assertEqual((r["data"], r["blocked"]), ({"content": "c"}, False))
            self.declare({"a": {"event": "after_queue", "handler": "x"}})
            (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"hooks": "hooks.json"}}))
            hooks.fire("before_queue", {"content": "c"}, str(self.defn), str(self.stack))


if __name__ == "__main__":
    unittest.main()
