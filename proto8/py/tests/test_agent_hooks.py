"""Test aos.agentlib.agent_hooks, the agent's hook remote: fire like hooks.fire (the agent family's rules), the two layers, take_letter's three steps, guard_tool's default text, announce_tools, clock_tick, the empty remote and fail(). A fake aos-post on PATH; real aos-exec."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
PY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PY))
from aos.agentlib import agent_hooks, hooks


class Stop(Exception):
    def __init__(self, code, sentence):
        super().__init__(sentence)
        self.code = code


def die(code, sentence):
    raise Stop(code, sentence)


class AgentHandle(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="agent-hooks-")
        self.addCleanup(tmp.cleanup)
        self.d = Path(os.path.realpath(tmp.name))
        self.defn, self.stack, fake = self.d / "def", self.d / "stack", self.d / "bin"
        for p in (self.defn, self.stack, fake):
            p.mkdir()
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {}, "hookeds": "hookeds.json"}))
        self.hooks = {}
        self.posted = self.d / "posted.txt"
        post = fake / "aos-post"
        post.write_text("#!/bin/sh\necho \"$@\" >> '%s'\nexit ${FAKE_POST_CODE:-0}\n" % self.posted)
        post.chmod(0o755)
        old = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(old)))
        os.environ["PATH"] = "%s:%s" % (fake, os.environ.get("PATH", ""))
        self.warned = []

    def handler(self, name, body, event, **entry):
        p = self.defn / ("h_" + name)
        p.write_text("#!/bin/sh\n" + body + "\n")
        p.chmod(0o755)
        self.hooks[name] = dict({"event": event, "handler": p.name}, **entry)
        (self.defn / "hookeds.json").write_text(json.dumps(self.hooks))

    def open(self, fail=die):
        return agent_hooks.open(str(self.defn), str(self.stack), fail, warn=self.warned.append)

    def stopped(self, code, fn, *args):
        with self.assertRaises(Stop) as c:
            fn(*args)
        self.assertEqual(c.exception.code, code)
        return str(c.exception)

    def test_fire_matches_hooks_fire_and_the_stack_layer(self):
        self.handler("a", "echo '{\"content\": \"changed\"}'", "after_tool", condition="ls")
        h = self.open()
        data = {"name": "ls", "id": "1", "content": "x", "code": 0, "timed_out": False}
        self.assertEqual(h.fire("after_tool", data), hooks.fire("after_tool", data, hooks.load(str(self.defn), str(self.stack)), str(self.stack)))
        self.assertEqual(h.fire("after_tool", data)["data"]["content"], "changed")
        (self.stack / "hookeds.json").write_text(json.dumps({"a": None}))   # the stack copy turns it off
        self.assertFalse(h.has("after_tool"))
        self.assertEqual(h.fire("after_tool", data)["changed"], [])

    def test_content_check_and_errors_go_to_fail(self):
        self.handler("a", "echo '{\"content\": 5}'", "after_tool")
        self.assertEqual(self.open().fire("after_tool", {"content": "x"})["data"]["content"], "x")   # after_tool cannot be blocked: a warning
        self.assertIn("content in stdout must be a string", self.warned[-1])
        self.handler("b", "echo '{\"content\": \"\"}'", "before_queue")
        self.assertIn("content in stdout must be a non-empty string", self.stopped("HookFailed", self.open().fire, "before_queue", {"content": "x"}))
        self.assertEqual(self.open().fire("before_save", {})["changed"], [])   # an event no rule knows: hooks run, nothing changes
        (self.defn / "hookeds.json").write_text(json.dumps({"a": {"event": "on_clock", "handler": "x"}}))
        self.assertIn("needs exactly one of every_cycles, every_ms", self.stopped("HooksBad", self.open().fire, "on_clock", {}))
        self.assertIn("needs exactly one", self.stopped("HooksBad", self.open().clock_tick))
        got = []
        with self.assertRaises(agent_hooks.FailReturned):
            self.open(fail=lambda code, sentence: got.append(code)).fire("on_clock", {})
        self.assertEqual(got, ["HooksBad"])

    def test_take_letter(self):
        h = self.open()
        self.assertEqual(h.take_letter("BOX", "L1", "hi"), "hi")          # nobody listens
        self.handler("a_up", "echo '{\"content\": \"HI\"}'", "before_queue")
        self.assertEqual(h.take_letter("BOX", "L1", "hi"), "HI")
        self.handler("b_drop", "exit 10", "before_queue")
        self.assertIsNone(h.take_letter("BOX", "L2", "hi"))
        self.assertEqual(self.posted.read_text(), "done BOX L2\n")
        self.assertEqual((self.stack / "mailbox_warning.txt").read_text(), "letter L2 dropped by hook b_drop\n")
        dropped = json.loads((self.stack / "letters.json").read_text())["dropped"]
        self.assertEqual([(x["letter"], x["reason"]) for x in dropped], [("L2", "blocked")])
        os.environ["FAKE_POST_CODE"] = "3"
        self.assertIn("aos-post done exited 3", self.stopped("PostFailed", h.take_letter, "BOX", "L3", "hi"))

    def test_guard_tool(self):
        h = self.open()
        args = {"path": "a"}
        self.assertIs(h.guard_tool("ls", "c1", args)[1], args)              # unchanged = the same object
        self.handler("a", "echo '{\"arguments\": {\"path\": \"b\"}}'", "before_tool")
        self.assertEqual(h.guard_tool("ls", "c1", args), ("run", {"path": "b"}))
        self.handler("a", "exit 10", "before_tool", condition="rm")
        self.assertEqual(h.guard_tool("rm", "c2", args), ("blocked", "[aos] hook: tool rm blocked by hook a."))
        self.handler("a", "echo not now; exit 10", "before_tool")
        self.assertEqual(h.guard_tool("ls", "c3", args), ("blocked", "not now\n"))

    def test_announce_tools(self):
        h = self.open()
        asked = []
        h.announce_tools(lambda: asked.append(1) or [])
        self.assertEqual(asked, [])                                         # nobody listens: not asked
        self.handler("a", "cat >> \"%s\"" % (self.d / "added.jsonl"), "tool_added")
        h.announce_tools([("ls", "/t/ls")])                                 # the first time only records
        self.assertFalse((self.d / "added.jsonl").exists())
        h.announce_tools(lambda: [("ls", "/t/ls"), ("cat", "/t/cat")])
        got = [json.loads(line) for line in (self.d / "added.jsonl").read_text().splitlines()]
        self.assertEqual([(g["name"], g["path"]) for g in got], [("cat", "/t/cat")])

    def test_clock_tick_and_the_empty_handle(self):
        self.handler("tick", "cat > \"$AOS_STACK/got.json\"", "on_clock", every_cycles=1, clock="./clockfile")
        (self.stack / "clockfile").write_text("7\n")
        self.assertEqual(self.open().clock_tick(), ["tick"])
        self.assertEqual(json.loads((self.stack / "hookeds" / "tick" / "got.json").read_text())["cycle"], 7)
        empty = agent_hooks.open(None, str(self.stack), die)
        self.assertEqual(empty.fire("before_tool", {"arguments": {}}),
                         {"data": {"arguments": {}}, "changed": [], "blocked": False, "hook": None, "text": ""})
        self.assertEqual(empty.clock_tick(), [])
        self.assertFalse(empty.has("before_tool"))

    def test_no_declaration_needed(self):
        """A declaration is only for reading: hooks run without one; no hookeds = nobody listens."""
        self.handler("a", "exit 3", "after_tool")
        self.open().fire("after_tool", {"name": "ls"})
        self.assertIn("exited 3", self.warned[-1])
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {}}))
        self.assertFalse(self.open().has("after_tool"))
        (self.defn / "interfaces.json").write_text(json.dumps({"hookeds": 5}))
        self.assertIn("must be a file name", self.stopped("HooksBad", self.open().fire, "after_tool", {}))


if __name__ == "__main__":
    unittest.main()
