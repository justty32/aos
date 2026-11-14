"""驗 lib/agent/hooks.py 用的是共用引擎 lib/hook_run.py（11-13 kernel-framework 批 1b）：類別同一個、跑與解回話沒有第二份、兩種 import 法都找得到引擎、agent 自己的檢查（on_clock 的鍵、content 的回話）還在。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
LIB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LIB))
import hook_run  # noqa: E402
from agent import hooks  # noqa: E402


class Engine(unittest.TestCase):
    def test_same_classes_and_constants(self):
        self.assertIs(hooks.HooksBad, hook_run.HooksBad)
        self.assertIs(hooks.HookFailed, hook_run.HookFailed)
        self.assertEqual((hooks.DEFAULTS, hooks.BLOCK, hooks.CELLS), (hook_run.DEFAULTS, hook_run.BLOCK, hook_run.CELLS))

    def test_no_second_copy_of_the_runner(self):
        """跑 handler、收行程群、解回話只在引擎：hooks.py 自己不再起子行程。"""
        source = (LIB / "agent" / "hooks.py").read_text(encoding="utf-8")
        for word in ("subprocess", "killpg", "Popen", "json.loads"):
            with self.subTest(word=word):
                self.assertNotIn(word, source)

    def test_import_without_lib_on_the_path(self):
        """只把 lib/agent 放上 sys.path（hook_fire、範本格的寫法）也找得到父層的引擎，而且 sys.path 不留東西。"""
        code = ("import sys; sys.dont_write_bytecode = True; sys.path[:0] = [%r]; before = list(sys.path); import hooks, hook_run; "
                "assert sys.path == before, sys.path; assert hooks.HooksBad is hook_run.HooksBad; "
                "print(hook_run.__file__)" % str(LIB / "agent"))
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        r = subprocess.run([sys.executable, "-S", "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd="/")
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertEqual(r.stdout.strip(), str(LIB / "hook_run.py"))

    def test_common_keys_are_checked_before_the_clock_keys(self):
        """一格同時有共通鍵的錯與 on_clock 專用鍵的錯：先報共通鍵那句（使用者 11-13「4可以。」；改用引擎前先報 on_clock 那句）。"""
        cases = (
            ({"event": "on_clock", "handler": "h", "every_ms": 0, "timeout_ms": -1}, "timeout_ms must be a whole number of milliseconds >= 0 (0 = no limit)"),
            ({"event": "on_clock", "handler": "h", "on_error": "x"}, "on_error must be stop or continue"),
            ({"event": "after_tool", "handler": "h", "clock": "c", "on_error": "x"}, "on_error must be stop or continue"),
            ({"event": "on_clock", "handler": "h", "every_ms": 0}, "every_ms must be a positive integer"),
            ({"event": "on_clock", "handler": "h"}, "event on_clock needs exactly one of every_cycles, every_ms"),
            ({"event": "on_clock", "handler": "h", "every_cycles": 1, "clock": ""},
             "clock must be a non-empty string (a proc name, or the path of a clock file or of a folder with one)"),
            ({"event": "after_tool", "handler": "h", "every_cycles": 1}, "every_cycles is only for event on_clock"),
        )
        for entry, message in cases:
            with self.subTest(entry=entry):
                with self.assertRaises(hooks.HooksBad) as caught:
                    hooks.validate_entry(entry)
                self.assertEqual(str(caught.exception), message)

    def test_content_reply_is_still_checked(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(os.path.realpath(tmp.name))
        defn, stack = root / "def", root / "stack"
        defn.mkdir()
        stack.mkdir()
        (defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"hooks": "hooks.json"}}))
        (defn / "h").write_text("#!/bin/sh\ncat >/dev/null\necho '{\"content\": \"\"}'\n")
        (defn / "h").chmod(0o755)
        (defn / "hooks.json").write_text(json.dumps({"hooks": {"q": {"event": "before_queue", "handler": "h"},
                                                               "t": {"event": "after_tool", "handler": "h"}}}))
        with self.assertRaises(hooks.HookFailed) as caught:
            hooks.fire("before_queue", {"content": "x"}, str(defn), str(stack))
        self.assertEqual(str(caught.exception), "hook q (event before_queue) failed: content in stdout must be a non-empty string")
        got = hooks.fire("after_tool", {"name": "n", "content": "x"}, str(defn), str(stack))
        self.assertEqual((got["data"]["content"], got["changed"]), ("", ["content"]))


if __name__ == "__main__":
    unittest.main()
