"""驗 py/aos/agentlib/hooks.py：agent 一家自己的 hook 規矩（11-21 第四層：引擎只叫 handler，攔、改、condition、失敗怎麼算在這裡）——能攔的點退 10、能改的鍵與型別、condition、能攔的點失敗＝停、其餘失敗＝warning、照名字串改、only；跑 handler 沒有第二份；只把 py/ 放上路徑也找得到引擎；格的檢查。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))
from aos import hook_lists, hook_run  # noqa: E402
from aos.agentlib import hooks  # noqa: E402


class Engine(unittest.TestCase):
    def test_same_names(self):
        self.assertIs(hooks.HooksBad, hook_lists.HooksBad)
        self.assertEqual((hooks.BLOCK, hooks.CELLS), (hook_run.BLOCK, hook_run.CELLS))

    def test_no_second_copy_of_the_runner(self):
        """跑 handler、收行程群只在引擎；hooks.py 不起行程。"""
        source = (LIB / "aos" / "agentlib" / "hooks.py").read_text(encoding="utf-8")
        for word in ("killpg", "Popen", "subprocess"):
            with self.subTest(word=word):
                self.assertNotIn(word, source)

    def test_import_with_only_py_on_the_path(self):
        code = ("import sys; sys.dont_write_bytecode = True; sys.path[:0] = [%r]; before = list(sys.path); "
                "from aos.agentlib import hooks; from aos import hook_run; "
                "assert sys.path == before, sys.path; print(hook_run.__file__)" % str(LIB))
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        r = subprocess.run([sys.executable, "-S", "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd="/")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout.strip(), str(LIB / "aos" / "hook_run.py"))

    def test_entry_checks(self):
        """引擎的鍵先驗，再驗 agent 自己的（condition、on_clock 的鍵）；intercept／async／on_error 不再是鍵（不驗、不讀）。"""
        hooks.check_entry({"event": "after_tool", "handler": "h", "on_error": "x", "async": 3, "intercept": "no"})
        hooks.check_entry({"event": "after_queue", "handler": "h", "condition": "any"})     # a point without a field: kept, never compared
        cases = (
            ({"event": "on_clock", "handler": "h", "every_ms": 0, "timeout_ms": -1}, "timeout_ms must be a whole number of milliseconds >= 0 (0 = no limit)"),
            ({"event": "on_clock", "handler": "h", "every_ms": 0}, "every_ms must be a positive integer"),
            ({"event": "on_clock", "handler": "h"}, "event on_clock needs exactly one of every_cycles, every_ms"),
            ({"event": "on_clock", "handler": "h", "every_cycles": 1, "clock": ""},
             "clock must be a non-empty string (a proc name, or the path of a clock file or of a folder with one)"),
            ({"event": "after_tool", "handler": "h", "every_cycles": 1}, "every_cycles is only for event on_clock"),
            ({"event": "after_tool", "handler": "h", "condition": ["a", 1]}, "condition must be a non-empty string or an array of them"),
        )
        for entry, message in cases:
            with self.subTest(entry=entry):
                with self.assertRaises(hooks.HooksBad) as caught:
                    hooks.check_entry(entry)
                self.assertEqual(str(caught.exception), message)


class Rules(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(os.path.realpath(tmp.name))
        self.stack = self.root / "stack"
        self.stack.mkdir()
        self.entries, self.warned = {}, []

    def hook(self, name, event, body, **keys):
        p = self.root / ("h_" + name)
        p.write_text("#!/bin/sh\ncat > '%s.in'\n%s\n" % (p, body))
        p.chmod(0o755)
        self.entries[name] = dict({"event": event, "handler": p.name, "from": str(self.root / "hookeds.json"), "base": str(self.root)}, **keys)

    def fire(self, event, data, **kw):
        return hooks.fire(event, data, self.entries, str(self.stack), warn=self.warned.append, **kw)

    def seen(self, name):
        return json.loads((self.root / ("h_%s.in" % name)).read_text())

    def test_block_only_where_the_rule_says(self):
        self.hook("a", "before_tool", "echo nope; exit 10")
        self.hook("b", "before_tool", "exit 0")
        got = self.fire("before_tool", {"name": "ls", "arguments": {}})
        self.assertEqual((got["blocked"], got["hook"], got["text"]), (True, "a", "nope\n"))
        self.assertFalse((self.root / "h_b.in").exists())          # stops at the blocking one
        self.hook("c", "after_tool", "echo '{\"content\": \"y\"}'; exit 10")
        got = self.fire("after_tool", {"name": "ls", "content": "x"})   # 10 on a point that cannot be blocked = went on
        self.assertEqual((got["blocked"], got["data"]["content"]), (False, "y"))

    def test_changes_chain_in_name_order_and_only_allowed_keys(self):
        self.hook("a", "before_queue", "echo '{\"content\": \"A\", \"letter\": \"hacked\"}'")
        self.hook("b", "before_queue", "echo '{\"content\": \"B\"}'")
        got = self.fire("before_queue", {"letter": "L", "content": "x"})
        self.assertEqual(got["data"], {"letter": "L", "content": "B"})
        self.assertEqual(got["changed"], ["content"])
        self.assertEqual(self.seen("b")["content"], "A")            # the next one sees what the earlier changed

    def test_condition(self):
        self.hook("a", "before_tool", "exit 10", condition=["rm", "mv"])
        self.assertFalse(self.fire("before_tool", {"name": "ls"})["blocked"])
        self.assertTrue(self.fire("before_tool", {"name": "rm"})["blocked"])
        self.assertTrue(self.fire("before_tool", {"name": "ls"}, only=["a"])["blocked"])   # only = no condition compared

    def test_failure_stops_a_blockable_point_and_warns_elsewhere(self):
        self.hook("a", "before_tool", "exit 3")
        with self.assertRaises(hooks.HookFailed) as cm:
            self.fire("before_tool", {"name": "ls"})
        self.assertEqual(str(cm.exception), "hook a (event before_tool) failed: exited 3")
        self.hook("b", "brain_failed", "echo '{'; exit 0")
        self.hook("c", "brain_failed", "exit 0")
        self.assertFalse(self.fire("brain_failed", {"name": "X"})["blocked"])
        self.assertTrue((self.root / "h_c.in").exists())              # the next one still ran
        self.assertEqual(self.warned, [])                             # brain_failed takes no reply: stdout not read
        self.hook("d", "after_queue", "exit 7")
        self.fire("after_queue", {})
        self.assertEqual(self.warned, ["hook d (event after_queue) failed: exited 7; going on without it"])

    def test_content_reply_is_checked(self):
        self.hook("q", "before_queue", "echo '{\"content\": \"\"}'")
        with self.assertRaises(hooks.HookFailed) as caught:
            self.fire("before_queue", {"content": "x"})
        self.assertEqual(str(caught.exception), "hook q (event before_queue) failed: content in stdout must be a non-empty string")
        self.hook("t", "after_tool", "echo '{\"content\": \"\"}'")
        got = self.fire("after_tool", {"name": "n", "content": "x"})
        self.assertEqual((got["data"]["content"], got["changed"]), ("", ["content"]))


if __name__ == "__main__":
    unittest.main()
