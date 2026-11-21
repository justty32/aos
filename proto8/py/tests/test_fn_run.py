"""Test fn.main: a tool's flags (--compile folder / pointer, --dry-run, --tooldef, --metainfo), its run (defaults, enum, fn.fail, RunFailed, names), and a hook's replies, also through the agent hook engine."""
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
from aos.agentlib import hooks  # noqa: E402

HEAD = "#!/usr/bin/env python3\nimport sys\nsys.path.insert(0, %r)\nfrom aos.py import fn\n" % str(LIB)
TOOL = HEAD + '''
@fn.tool(meta={"deterministic": True}, params=[fn.param("mode", "string", "how", enum=["up", "low"])])
def rep(word: str, times: int = 2, mode: str = "up"):
    """Repeat a word. Example: {"word": "hi"} -> HI HI

    Args:
      word: a word
      times: how many
    """
    if word == "x":
        fn.fail("WordBad", "x is not a word")
    if word == "boom":
        return 1 / 0
    if word == "obj":
        return {"n": times}
    w = word.upper() if mode == "up" else word
    return " ".join([w] * times)


fn.main(rep)
'''
HOOK = HEAD + '''
@fn.hook("before_tool", condition="write")
def no_secrets(event):
    """Stop a write whose arguments mention a secret."""
    text = str(event.get("arguments", ""))
    if "secret" in text:
        return fn.block("the arguments mention a secret")
    if "fix" in text:
        return {"arguments": {"text": "fixed"}}
    if "word" in text:
        return "a string"
    if "boom" in text:
        return 1 / 0
    if "fail" in text:
        fn.fail("NoGood", "told to fail")


fn.main(no_secrets)
'''


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fn-run-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(os.path.realpath(self.temp.name))
        self.dir = self.root / "rep"
        self.dir.mkdir()
        self.put("tool.py", TOOL)

    def put(self, name, text):
        p = self.dir / name
        p.write_text(text)
        p.chmod(0o755)
        return p

    def call(self, *argv, stdin="{}", script="tool.py"):
        return subprocess.run([sys.executable, str(self.dir / script), *argv], input=stdin, text=True,
                              capture_output=True, timeout=30, env=dict(os.environ, AOS_WS=str(self.root)))


class Tool(Base):
    def test_run_defaults_enum_and_errors(self):
        self.assertEqual(self.call(stdin='{"word": "hi"}').stdout, "HI HI\n")
        self.assertEqual(self.call(stdin='{"word": "hi", "times": 1, "mode": "low"}').stdout, "hi\n")
        self.assertEqual(self.call(stdin='{"word": "obj"}').stdout, '{"n": 2}\n')
        for stdin, code in (('{}', "ArgumentsBad missing word"), ('{"word": "a", "zz": 1}', "ArgumentsBad unknown key zz"),
                            ('{"word": "a", "mode": "mid"}', "ArgumentsBad mode must be one of: up, low"),
                            ('{"word": "x"}', "WordBad x is not a word"),
                            ('{"word": "boom"}', "RunFailed rep() raised ZeroDivisionError: division by zero (tool.py line 17)")):
            with self.subTest(stdin=stdin):
                r = self.call(stdin=stdin)
                self.assertEqual(r.returncode, 1)
                self.assertTrue(r.stdout.startswith("rep: error: " + code), r.stdout)
                self.assertEqual(r.stdout, r.stderr)

    def test_zero_timeout_metadata_does_not_prevent_delayed_run(self):
        script = TOOL.replace('    if word == "x":', '    __import__("time").sleep(1)\n    if word == "x":')
        self.put("tool.py", script.replace('{"deterministic": True}', '{"deterministic": True, "timeout_ms": 0}'))
        r = self.call(stdin='{"word": "hi"}')
        self.assertEqual((r.returncode, r.stdout), (0, "HI HI\n"), r.stderr)
        self.assertEqual(json.loads(self.call("--metainfo").stdout)["timeout_ms"], 0)

    def test_flags_list_fail_codes(self):
        td = json.loads(self.call("--tooldef").stdout)
        self.assertEqual(td["errors"], ["ArgumentsBad", "WordBad", "RunFailed"])
        self.assertEqual(td["parameters"]["properties"]["mode"], {"type": "string", "description": "how", "enum": ["up", "low"], "default": "up"})
        help_text = self.call("--help").stdout
        self.assertIn("--times N", help_text)
        self.assertIn("WordBad", help_text)
        self.assertEqual(json.loads(self.call("--metainfo").stdout)["summary"], "Repeat a word")

    def test_plain_run_does_not_read_the_source(self):
        broken = TOOL.replace("from aos.py import fn\n", "from aos.py import fn\nfrom aos import tool_spec\n"
                              "def _no(path):\n    raise RuntimeError('read the source')\ntool_spec.errors_in = _no\n")
        self.put("tool.py", broken)
        self.assertEqual(self.call(stdin='{"word": "hi"}').stdout, "HI HI\n")
        self.assertIn("read the source", self.call("--tooldef").stderr)
        gone = HEAD + "exec(compile(%r, '/no/such/dir/tool.py', 'exec'))\n" % TOOL.split("from aos.py import fn\n", 1)[1]
        self.put("other.py", gone)
        r = self.call(stdin='{"word": "hi"}', script="other.py")
        self.assertEqual((r.returncode, r.stdout), (0, "HI HI\n"), r.stderr)
        self.assertEqual(json.loads(self.call("--tooldef", script="other.py").stdout)["errors"], ["ArgumentsBad", "RunFailed"])

    def test_error_line_names(self):
        self.put("mul.py", TOOL)
        self.assertTrue(self.call(script="mul.py").stdout.startswith("mul: error: ArgumentsBad"))
        self.put("tool.py", TOOL.replace("@fn.tool(", '@fn.tool(name="say", '))
        self.assertTrue(self.call().stdout.startswith("say: error: ArgumentsBad"))

    def test_compile_folder_and_pointer(self):
        dry = self.call("--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["tool.py"])
        dry = json.loads(dry.stdout)
        r = self.call("--compile")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((self.dir / "_tooldef.json").read_text()), dry["_tooldef.json"])
        self.assertEqual(json.loads((self.dir / "_metainfo.json").read_text()), dry["_metainfo.json"])
        for argv in (["--dry-run", "x"], ["--compile", "a", "b"]):
            with self.subTest(argv=argv):
                r = self.call(*argv)
                self.assertEqual(r.returncode, 1)
                self.assertIn("rep: error: ArgumentsBad too many arguments", r.stdout)
        box = self.root / "box.json"
        box.write_text('{"tools": {"rep": {"_entry": ["python3", "rep/tool.py"]}}}')
        r = self.call("--compile", "%s#/tools/rep" % box)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = json.loads(box.read_text())["tools"]["rep"]
        self.assertEqual(got["_tooldef"]["errors"][1], "WordBad")
        self.assertEqual(got["_metainfo"]["summary"], "Repeat a word")

    def test_bad_declaration_is_an_error_line(self):
        self.put("tool.py", TOOL.replace("times: int = 2", "times = 2"))
        r = self.call(stdin='{"word": "a"}')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, 'rep: error: SpecBad parameter times needs a type (str, int, float, bool, list, dict), '
                                   'or fn.param("times", ...) (fix the declaration in tool.py)\n')
        self.put("tool.py", TOOL.replace("@fn.tool(", '@fn.hook("before_tool", '))
        self.assertIn("SpecBad hook rep takes one parameter, the event", self.call().stdout)
        self.put("tool.py", TOOL.replace("fn.main(rep)", "fn.main(len)"))
        self.assertIn("rep: error: SpecBad len is not marked", self.call().stdout)


class Hook(Base):
    def test_replies(self):
        self.put("hook.py", HOOK)
        for args, code, out in (({"text": "hello"}, 0, ""), ({"text": "a secret"}, 10, "the arguments mention a secret\n"),
                                ({"text": "fix"}, 0, '{"arguments": {"text": "fixed"}}\n'),
                                ({"text": "word"}, 1, "hook: error: ReplyBad hook no_secrets returned str; return None, a dict of "
                                                      'the keys to change, or fn.block("why")\n'),
                                ({"text": "boom"}, 1, "hook: error: RunFailed ZeroDivisionError: division by zero (hook.py line 17)\n"),
                                ({"text": "fail"}, 1, "hook: error: NoGood told to fail\n")):
            with self.subTest(args=args):
                r = self.call(stdin=json.dumps({"event": "before_tool", "name": "write", "arguments": args}), script="hook.py")
                self.assertEqual((r.returncode, r.stdout), (code, out), r.stderr)
        r = self.call("--tooldef", script="hook.py")
        self.assertEqual(r.stdout, "hook: error: ArgumentsBad a hook takes no arguments: --tooldef (usage: hook < EVENT.json)\n")
        self.assertIn("a hook handler for before_tool events", self.call("--help", script="hook.py").stdout)
        self.assertIn("ArgumentsBad stdin must be the event JSON object", self.call(stdin="[]", script="hook.py").stdout)
        self.put("bare.py", HOOK.replace('@fn.hook("before_tool", condition="write")', "@fn.hook"))
        self.assertIn('SpecBad hook no_secrets needs the event name, like @fn.hook("before_tool")', self.call(script="bare.py").stdout)

    def test_blocks_through_the_agent_hook_engine(self):
        defn, stack = self.root / "def", self.root / "stack"
        defn.mkdir()
        stack.mkdir()
        (defn / "no_secrets.py").write_text(HOOK)
        (defn / "no_secrets.py").chmod(0o755)
        (defn / "interfaces.json").write_text(json.dumps({"aos-agent": {}, "hookeds": "hookeds.json"}))
        (defn / "hookeds.json").write_text(json.dumps({"no_secrets": {"event": "before_tool", "condition": "write",
                                                                      "handler": "no_secrets.py"}}))
        entries = hooks.load(str(defn), str(stack))
        got = hooks.fire("before_tool", {"name": "write", "arguments": {"text": "a secret"}}, entries, str(stack))
        self.assertEqual((got["blocked"], got["hook"], got["text"]), (True, "no_secrets", "the arguments mention a secret\n"))
        got = hooks.fire("before_tool", {"name": "write", "arguments": {"text": "fix"}}, entries, str(stack))
        self.assertEqual((got["blocked"], got["changed"], got["data"]["arguments"]), (False, ["arguments"], {"text": "fixed"}))
        got = hooks.fire("before_tool", {"name": "read", "arguments": {"text": "a secret"}}, entries, str(stack))
        self.assertFalse(got["blocked"])                                                      # condition write only


if __name__ == "__main__":
    unittest.main()
