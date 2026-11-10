"""Test the hooks of agent-fsm (lib/agent/hooks.py and the four cells): six events, changes, blocking, on_fail, timeout, match, layering, tool_added."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

CELLS = Path(__file__).resolve().parents[1]
PROTO = CELLS.parents[1]
sys.path.insert(0, str(PROTO / "lib"))
from agent import hooks  # noqa: E402

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
        env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
        local = Path.home() / ".local" / "bin"
        self.env = dict(env, AOS_STACK=str(self.stack), AOS_CD=str(self.defn), HOOKDIR=str(self.defn),
                        PATH=os.pathsep.join([str(self.bin), str(local)] + [str(p) for p in PROTO.glob("impls/*/bin")]
                                             + [env["PATH"]]))
        self.tools(["echo"])
        self.command("aos-llm", """import json, os, sys
if sys.argv[1] == 'send':
    sys.stdin.read(); print('letter-1'); sys.exit(0)
code = int(os.environ.get('FAKE_RECV', '0'))
if code == 0:
    print(os.environ.get('FAKE_REPLY', json.dumps({'message': {'role': 'assistant', 'content': 'ok'}})))
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
        box = self.stack / "queue"
        subprocess.run(["aos-post", "init", str(box)], env=self.env, check=True, capture_output=True)
        subprocess.run(["aos-post", "send", "--ordered", str(box)], env=self.env, check=True, capture_output=True,
                       input=json.dumps({"role": "user", "content": content}), text=True)

    def history(self, messages=None):
        path = self.stack / "history.jsonl"
        if messages is not None:
            path.write_text("".join(json.dumps(m) + "\n" for m in messages))
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []

    def act_history(self):
        self.history([{"role": "user", "content": "hi"}, {"role": "assistant", "tool_calls": [CALL]}])

    # ---- queue
    def test_queue_before_changes_content_and_queue_after_sees_it(self):
        self.declare({"a_up": {"on": "queue_before",          # change 預設開（11-10 深夜）

                               "exec": self.hook("up", 'print(json.dumps({"content": ev["content"].upper()}))')},
                      "b_after": {"on": "queue_after", "exec": self.hook("after")}})
        self.letter("hello")
        self.run_cell("idle")
        self.assertEqual(self.history(), [{"role": "user", "content": "HELLO"}])
        before, after = self.events()
        self.assertEqual((before["event"], before["hook"], before["content"]), ("queue_before", "a_up", "hello"))
        self.assertEqual(before["stack"], str(self.stack))
        self.assertEqual((after["event"], after["content"], after["letter"]), ("queue_after", "HELLO", before["letter"]))
        self.assertTrue((self.stack / "hooks" / "a_up" / "event.json").is_file())

    def test_queue_before_drops_letter(self):
        self.declare({"drop": {"on": "queue_before", "change": True, "exec": self.hook("drop", "sys.exit(10)")},
                      "z": {"on": "queue_after", "exec": self.hook("z")}})
        self.letter("spam")
        self.run_cell("idle", code=10)
        self.assertEqual(self.history(), [])
        self.assertEqual(os.listdir(self.stack / "queue" / "cur"), [])
        self.assertIn("dropped by hook drop", (self.stack / "mailbox_warning.txt").read_text())
        self.assertEqual([e["event"] for e in self.events()], ["queue_before"])

    def test_without_change_stdout_and_10_do_nothing(self):
        self.declare({"n": {"on": "queue_before", "change": False, "exec": self.hook("n", 'print(json.dumps({"content": "X"})); sys.exit(10)')}})
        self.letter("keep")
        self.run_cell("idle")
        self.assertEqual(self.history(), [{"role": "user", "content": "keep"}])

    # ---- on_fail、逾時、wait false
    def test_on_fail_stop_keeps_letter_in_cur(self):
        self.declare({"bad": {"on": "queue_before", "exec": self.hook("bad", "sys.exit(3)")}})
        self.letter("again")
        r = self.run_cell("idle", code=1)
        self.assertIn("agent-fsm: error: HookFailed hook bad (event queue_before) failed: exited 3", r.stderr)
        self.assertEqual(self.history(), [])
        self.assertEqual(len(os.listdir(self.stack / "queue" / "cur")), 1)   # P-12：下次重跑再接
        self.declare({})
        self.run_cell("idle")
        self.assertEqual(self.history(), [{"role": "user", "content": "again"}])

    def test_on_fail_continue_warns_and_goes_on(self):
        self.declare({"bad": {"on": "queue_before", "on_fail": "continue", "change": True,
                              "exec": self.hook("bad", 'print("not json")')}})
        self.letter("go")
        r = self.run_cell("idle")
        self.assertIn("agent-fsm: warning: hook bad (event queue_before) failed: stdout is not JSON", r.stderr)
        self.assertEqual(self.history(), [{"role": "user", "content": "go"}])

    def test_timeout_kills_and_fails(self):
        self.declare({"slow": {"on": "queue_after", "timeout_ms": 300, "exec": self.hook("slow", "time.sleep(30)")}})
        self.letter("t")
        started = time.monotonic()
        r = self.run_cell("idle", code=1)
        self.assertLess(time.monotonic() - started, 10)
        self.assertIn("HookFailed hook slow (event queue_after) failed: did not finish in 300 ms", r.stderr)

    def test_no_wait_does_not_block(self):
        self.declare({"bg": {"on": "queue_after", "wait": False,
                             "exec": self.hook("bg", 'time.sleep(1.5); open(%r, "w").write("x")' % str(self.root / "late"))}})
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
        self.declare({"args": {"on": "tool_before", "change": True, "match": "echo",
                               "exec": self.hook("args", 'print(json.dumps({"arguments": {"text": "rain"}}))')},
                      "after": {"on": "tool_after", "exec": self.hook("after")}})
        self.act_history()
        self.run_cell("act")
        h = self.history()
        self.assertEqual(json.loads(h[-1]["content"]), {"text": "rain"})
        self.assertEqual(h[1]["tool_calls"], [CALL])                         # 紀錄不動
        before, after = self.events()
        self.assertEqual((before["name"], before["id"], before["arguments"]), ("echo", "c1", {"text": "snow"}))
        self.assertEqual((after["event"], after["arguments"], after["code"], after["timed_out"]),
                         ("tool_after", {"text": "rain"}, 0, False))

    def test_tool_before_blocks(self):
        self.declare({"no": {"on": "tool_before", "change": True, "exec": self.hook("no", 'print("not allowed"); sys.exit(10)')},
                      "after": {"on": "tool_after", "exec": self.hook("after")}})
        self.act_history()
        self.run_cell("act")
        self.assertEqual(self.history()[-1]["content"], "not allowed\n")
        self.assertEqual([e["event"] for e in self.events()], ["tool_before"])   # 攔下的不觸發 tool_after
        self.assertFalse((self.stack / "observed.jsonl").exists())
        self.declare({"no": {"on": "tool_before", "change": True, "exec": self.hook("no", "sys.exit(10)")}})
        self.act_history()
        self.run_cell("act")
        self.assertEqual(self.history()[-1]["content"], "(tool echo blocked by hook no)")

    def test_tool_after_changes_content_and_match_filters(self):
        self.declare({"a": {"on": "tool_after", "change": True, "match": ["echo"],
                            "exec": self.hook("a", 'print(json.dumps({"content": "[" + ev["content"] + "]"}))')},
                      "b": {"on": "tool_after", "match": "other", "exec": self.hook("b")}})
        self.act_history()
        self.run_cell("act")
        self.assertEqual(self.history()[-1]["content"], '[{"text":"snow"}]')
        self.assertEqual([e["hook"] for e in self.events()], ["a"])

    def test_bad_content_type_is_a_failure(self):
        self.declare({"a": {"on": "tool_after", "change": True, "exec": self.hook("a", 'print(json.dumps({"content": 5}))')}})
        self.act_history()
        r = self.run_cell("act", code=1)
        self.assertIn("HookFailed hook a (event tool_after) failed: content in stdout must be a string", r.stderr)
        self.assertEqual(len(self.history()), 2)                             # 沒接進 history，重跑再跑一次

    # ---- brain_failed、tool_added
    def test_brain_failed_on_kernel_error_and_bad_reply(self):
        self.declare({"bf": {"on": "brain_failed", "match": ["BrainFailed", "ReplyBad"], "exec": self.hook("bf")}})
        (self.stack / "think").mkdir()
        (self.stack / "think" / "pending.txt").write_text("letter-1\n")
        r = self.run_cell("wait", code=1, FAKE_RECV="1")
        self.assertIn("agent-fsm: error: BrainFailed", r.stderr)
        (self.stack / "think" / "pending.txt").write_text("letter-1\n")
        self.run_cell("wait", code=1, FAKE_REPLY="nope")
        self.assertEqual([(e["name"], e["reason"][:15]) for e in self.events()],
                         [("BrainFailed", "aos-llm recv ex"), ("ReplyBad", "aos-llm recv di")])

    def test_tool_added_first_run_only_records(self):
        self.declare({"new": {"on": "tool_added", "exec": self.hook("new")}})
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
        self.declare({"a": {"on": "queue_after", "exec": self.hook("defa")},
                      "b": {"on": "queue_after", "exec": self.hook("defb")}})
        self.declare({"a": {"on": "queue_after", "exec": self.hook("mine", folder=self.stack)}, "b": None}, self.stack)
        loaded = hooks.load(str(self.defn), str(self.stack))
        self.assertEqual(sorted(loaded), ["a"])
        self.assertEqual((loaded["a"]["from"], loaded["a"]["base"], loaded["a"]["wait"], loaded["a"]["timeout_ms"]),
                         (str(self.stack / "hooks.json"), str(self.stack), True, 60000))
        self.assertEqual(hooks.nulled(str(self.defn), str(self.stack)), ["b"])
        self.letter("x")
        self.run_cell("idle")
        self.assertEqual([e["hook"] for e in self.events()], ["a"])
        self.assertTrue((self.stack / "hooks" / "a" / "event.json").is_file())

    def test_directive_exec(self):
        self.hook("viaenv")
        self.declare({"d": {"on": "queue_after", "exec": {"$env": "HOOKDIR", "$path": "/viaenv.py"}}})
        self.letter("x")
        self.run_cell("idle")
        self.assertEqual([e["hook"] for e in self.events()], ["d"])

    def test_bad_list_is_hooks_bad(self):
        (self.defn / "hooks.json").write_text('{"hooks": {"a": {"on": "queue_after"}}}')
        self.letter("x")
        r = self.run_cell("idle", code=1)
        self.assertIn("agent-fsm: error: HooksBad hook a in", r.stderr)
        for entry in ({"on": "queue_before", "exec": "x", "match": "m"},
                      {"on": "tool_before", "exec": "x", "on_fail": "maybe"},
                      {"on": "tool_before", "exec": "x", "timeout_ms": 0},
                      {"on": "nope", "exec": "x"}):
            with self.assertRaises(hooks.HooksBad):
                hooks.validate_entry(entry)
        hooks.validate_entry({"on": "tool_before", "exec": "x", "change": True, "match": ["a"], "whatever": 1})
        # change 預設開之後：不能改的事件、不等的 hook 寫 change: true＝自然不看回話，不報錯（11-10 深夜）
        hooks.validate_entry({"on": "queue_after", "exec": "x", "change": True})
        hooks.validate_entry({"on": "tool_before", "exec": "x", "change": True, "wait": False})

    def test_change_on_unchangeable_event_ignores_stdout(self):
        self.declare({"talk": {"on": "queue_after", "exec": self.hook("talk", 'print("not json at all")')}})
        self.letter("hi")
        self.run_cell("idle")
        self.assertEqual(self.history(), [{"role": "user", "content": "hi"}])

    def test_nothing_declared_starts_nothing(self):
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {}}))
        with mock.patch("subprocess.Popen", side_effect=AssertionError("started a process")), \
                mock.patch("subprocess.run", side_effect=AssertionError("started a process")):
            r = hooks.fire("queue_before", {"content": "c"}, str(self.defn), str(self.stack))
            self.assertEqual((r["data"], r["blocked"]), ({"content": "c"}, False))
            self.declare({"a": {"on": "queue_after", "exec": "x"}})
            (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"hooks": "hooks.json"}}))
            hooks.fire("queue_before", {"content": "c"}, str(self.defn), str(self.stack))


if __name__ == "__main__":
    unittest.main()
