"""Test the hooks of aos-eca-turn (eca's reduced set: before_queue, after_queue, brain_failed, tool_added) with a fake claude CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROTO = HERE.parents[2]
TURN = PROTO / "cmd" / "aos-eca" / "bin" / "aos-eca-turn"
LOCAL_BIN = os.path.expanduser("~/.local/bin")
PRELUDE = """import json, os, sys
ev = json.load(sys.stdin)
with open(%r, "a") as f:
    f.write(json.dumps(ev) + "\\n")
"""


class EcaHooks(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="eca-hooks-")
        self.addCleanup(tmp.cleanup)
        self.t = Path(tmp.name)
        self.bin, self.defn, self.ws, self.stack, self.home = (self.t / n for n in ("bin", "def", "ws", "stack", "home"))
        for d in (self.bin, self.defn, self.ws, self.stack, self.home):
            d.mkdir()
        (self.bin / "claude").symlink_to(HERE / "fake_claude")
        (self.defn / "cli.json").write_text(json.dumps({"kind": "claude", "timeout_ms": 30000}))
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"tools": "tools.json", "hooks": "hooks.json"}}))
        self.log, self.cli_log, self.tools_log = self.t / "hooks.jsonl", self.t / "cli.jsonl", self.t / "tools.jsonl"
        subprocess.run(["aos-post", "init", str(self.stack / "queue")], env=self.env(), check=True, capture_output=True)

    def env(self, **more):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("AOS_", "FAKE_CLI_")) and k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME")}
        env.update(PATH="%s:%s:%s" % (self.bin, LOCAL_BIN, env.get("PATH", "")), HOME=str(self.home),
                   AOS_STACK=str(self.stack), AOS_WS=str(self.ws), FAKE_CLI_LOG=str(self.cli_log), PYTHONDONTWRITEBYTECODE="1")
        env.update(more)
        return env

    # ---- 小工具
    def hook(self, name, body=""):
        path = self.defn / (name + ".py")
        path.write_text("#!" + sys.executable + "\n" + PRELUDE % str(self.log) + body)
        path.chmod(0o755)
        return path.name

    def declare(self, table):
        (self.defn / "hooks.json").write_text(json.dumps({"hooks": table}))

    def tools(self, names):
        """登記檔＋假的 aos-tools：ls --json 列 names，每次叫都記一行。"""
        (self.defn / "tools.json").write_text("{}")
        listed = [{"name": n, "path": "/fake/" + n, "tooldef": {}} for n in names]
        path = self.bin / "aos-tools"
        path.write_text("#!%s\nimport json, sys\nopen(%r, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\nprint(json.dumps(%r))\n"
                        % (sys.executable, str(self.tools_log), listed))
        path.chmod(0o755)

    def say(self, *texts):
        for text in texts:
            subprocess.run(["aos-post", "send", "--ordered", str(self.stack / "queue")], check=True, capture_output=True,
                           input=json.dumps({"role": "user", "content": text}), env=self.env(), text=True)

    def turn(self, **env):
        return subprocess.run([str(TURN), "--on-empty", "idle", str(self.defn)], env=self.env(**env),
                              capture_output=True, text=True, timeout=60)

    def read_lines(self, path):
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []

    def history(self):
        return self.read_lines(self.stack / "history.jsonl")

    def queue(self, stage="cur"):
        return sorted(n for n in os.listdir(self.stack / "queue" / stage) if not n.startswith("."))

    # ---- 測試
    def test_queue_before_changes_content_and_queue_after_sees_it(self):
        self.declare({"up": {"event": "before_queue", "handler": self.hook("up", 'print(json.dumps({"content": ev["content"].upper()}))\n'),
                             "intercept": True},
                      "seen": {"event": "after_queue", "handler": self.hook("seen")}})
        self.say("hello")
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read_lines(self.cli_log)[-1]["stdin"], "HELLO")
        self.assertEqual(self.history(), [{"role": "user", "content": "HELLO"}, {"role": "assistant", "content": "FAKE: HELLO"}])
        ev = self.read_lines(self.log)
        self.assertEqual([(e["event"], e["content"]) for e in ev], [("before_queue", "hello"), ("after_queue", "HELLO")])
        self.assertEqual(ev[0]["stack"], str(self.stack))
        self.assertTrue(ev[0]["letter"])

    def test_queue_before_drops_one_letter(self):
        self.declare({"drop": {"event": "before_queue", "intercept": True,
                               "handler": self.hook("drop", 'sys.exit(10 if ev["content"] == "spam" else 0)\n')}})
        self.say("spam", "keep")
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read_lines(self.cli_log)[-1]["stdin"], "keep")
        self.assertEqual([m["content"] for m in self.history()], ["keep", "FAKE: keep"])
        self.assertRegex((self.stack / "mailbox_warning.txt").read_text(), r"^letter \S+ dropped by hook drop\n$")
        self.assertEqual(self.queue(), [])

    def test_queue_before_drops_all_no_cli(self):
        self.declare({"drop": {"event": "before_queue", "intercept": True, "handler": self.hook("drop", "sys.exit(10)\n")}})
        self.say("a", "b")
        r = self.turn()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.cli_log.exists())
        self.assertEqual(self.history(), [])
        self.assertEqual(self.queue(), [])

    def test_hook_stops_before_handing_keeps_letter(self):
        self.declare({"bad": {"event": "before_queue", "handler": self.hook("bad", "sys.exit(3)\n")}})
        self.say("hello")
        r = self.turn()
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-eca-turn: error: HookFailed hook bad (event before_queue) failed: exited 3", r.stderr)
        self.assertFalse(self.cli_log.exists())
        self.assertEqual(self.history(), [])
        self.assertEqual(len(self.queue()), 1)
        self.declare({})                                  # 修好重跑：同一封照問
        self.assertEqual(self.turn().returncode, 0)
        self.assertEqual([m["content"] for m in self.history()], ["hello", "FAKE: hello"])

    def test_hooks_bad(self):
        (self.defn / "hooks.json").write_text("not json")
        self.say("hello")
        r = self.turn()
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-eca-turn: error: HooksBad", r.stderr)
        self.assertEqual(len(self.queue()), 1)

    def test_queue_after_failing_keeps_answer(self):
        self.declare({"bad": {"event": "after_queue", "handler": self.hook("bad", "sys.exit(3)\n")}})
        self.say("hello")
        r = self.turn()
        self.assertEqual(r.returncode, 1)
        self.assertIn("HookFailed hook bad (event after_queue)", r.stderr)
        self.assertEqual([m["content"] for m in self.history()], ["hello", "FAKE: hello"])
        self.assertEqual(self.queue(), [])

    def test_brain_failed(self):
        self.declare({"bf": {"event": "brain_failed", "condition": "CliFailed", "handler": self.hook("bf")}})
        self.say("hello")
        r = self.turn(FAKE_CLI_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("aos-eca-turn: error: CliFailed", r.stderr)
        (ev,) = self.read_lines(self.log)
        self.assertEqual((ev["event"], ev["name"]), ("brain_failed", "CliFailed"))
        self.assertIn(ev["reason"], r.stderr)
        self.assertTrue((self.stack / "cooldown.json").exists())

    def test_brain_failed_hook_stops(self):
        self.declare({"bf": {"event": "brain_failed", "handler": self.hook("bf", "sys.exit(3)\n")}})
        self.say("hello")
        r = self.turn(FAKE_CLI_FAIL="1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("HookFailed hook bf (event brain_failed)", r.stderr)
        self.assertFalse((self.stack / "cooldown.json").exists())

    def test_tool_added(self):
        self.tools(["a"])
        self.declare({"ta": {"event": "tool_added", "handler": self.hook("ta")}})
        self.say("one")
        self.assertEqual(self.turn().returncode, 0)
        self.assertEqual(self.read_lines(self.log), [])                       # 第一次只記
        self.assertEqual(json.loads((self.stack / "hook_tools_seen.json").read_text()), ["a"])
        self.assertIn(["--file", str(self.defn / "tools.json"), "ls", "--json"], self.read_lines(self.tools_log))
        mcp = json.loads((self.stack / "claude" / "mcp.json").read_text())["mcpServers"]["aos"]["args"]
        self.assertEqual(mcp[mcp.index("--hooks") + 1], str(self.defn))      # aos-mcp 拿到定義資料夾
        self.tools(["a", "b"])
        self.say("two")
        self.assertEqual(self.turn().returncode, 0)
        ev = self.read_lines(self.log)
        self.assertEqual([(e["event"], e["name"], e["path"]) for e in ev], [("tool_added", "b", "/fake/b")])

    def test_tool_added_uses_stack_registry(self):
        self.tools(["a"])
        (self.stack / "tools.json").write_text("{}")                            # 這隻自己那份在＝用它
        self.declare({"ta": {"event": "tool_added", "handler": self.hook("ta")}})
        self.say("one")
        self.assertEqual(self.turn().returncode, 0)
        self.assertIn(["--file", str(self.stack / "tools.json"), "ls", "--json"], self.read_lines(self.tools_log))

    def test_no_tool_added_hook_no_listing(self):
        self.tools(["a"])
        (self.stack / "hook_tools_seen.json").write_text('["a"]')
        self.declare({})
        self.say("one")
        self.assertEqual(self.turn().returncode, 0)
        self.assertFalse(self.tools_log.exists())                               # 沒這種 hook：不多起 aos-tools
        self.assertFalse((self.stack / "hook_tools_seen.json").exists())


if __name__ == "__main__":
    unittest.main()
