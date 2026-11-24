"""Test cut 3 of the compile library beyond what a function may use: @fn.hook into hookeds.json (events, condition, fn.block, same names), renames and clashing file names, and how function tools meet static / dynamic linking, packs, defs.drop, defs.load, the eca body and old fn/ files."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent_spec_helpers import TEMPLATES, env_with, look, run_agent  # noqa: E402
from test_fn_spec import ADD, FnCase, body  # noqa: E402

HOOK = '''
@fn.hook("before_tool", condition="write", timeout_ms=5000)
def no_secrets(event):
    """Stop a write that mentions a secret."""
    if "secret" in str(event.get("arguments")):
        return fn.block("the arguments mention a secret")
'''
CHECK = ADD.replace("def add", "def check").replace("Add two numbers", "Check two numbers")


class Hooks(FnCase):
    def test_a_function_hook_compiles_and_blocks(self):
        d = self.agent(body(HOOK, tools="", hooks="no_secrets"))
        r = run_agent(d / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        hooks = json.loads((d / "hookeds.json").read_text())
        hooks.pop("description")
        self.assertEqual(hooks, {"no_secrets": {"event": "before_tool", "handler": "fn/no_secrets.py", "condition": "write",
                                                "timeout_ms": 5000}})
        prog = d / "fn" / "no_secrets.py"
        self.assertTrue(prog.read_text().startswith('#!/usr/bin/env python3\n"""no_secrets - Stop a write that mentions a secret."""\n'))
        r = self.call(prog, json.dumps({"event": "before_tool", "name": "write", "arguments": {"t": "a secret"}}))
        self.assertEqual((r.returncode, r.stdout), (10, "the arguments mention a secret\n"), r.stderr)
        self.assertEqual(self.call(prog, json.dumps({"event": "before_tool", "arguments": {}})).returncode, 0)

    def test_events_are_checked(self):
        """11-21 (line top-1121-hooknew): the event name is not checked (a declaration is only a reference), and neither is a
        condition on a point that does not compare it or fn.block where nothing can be blocked; the shape still is."""
        for event in ("before_tol", "after_start", "after_tool"):
            with self.subTest(event=event):
                out = self.dry(body(HOOK.replace('"before_tool"', '"%s"' % event), tools="", hooks="no_secrets"), name=event)
                self.assertEqual(out["hookeds.json"]["no_secrets"]["event"], event)
                self.assertIn("fn/no_secrets.py", out)
        self.bad(body(HOOK.replace('@fn.hook("before_tool", condition="write", timeout_ms=5000)', "@fn.hook"), tools="", hooks="no_secrets"),
                 'hooks: hook no_secrets needs the event name, like @fn.hook("before_tool")')
        self.bad(body(HOOK.replace("(event)", "(event, more)"), tools="", hooks="no_secrets"),
                 "hook no_secrets takes one parameter, the event: def no_secrets(event)")
        self.bad(body(HOOK.replace("timeout_ms=5000", "handler='x.py'"), tools="", hooks="no_secrets"),
                 "@fn.hook sets handler itself")

    def test_name_and_own_keys(self):
        """name= names the hook (and its program); the other keyword arguments go into the entry as written."""
        out = self.dry(body(HOOK.replace("timeout_ms=5000", 'timeout_ms=0, name="guard"'), tools="", hooks="no_secrets"))
        self.assertEqual(out["hookeds.json"]["guard"]["timeout_ms"], 0)
        self.assertEqual(out["hookeds.json"]["guard"]["handler"], "fn/guard.py")
        self.assertIn("fn/guard.py", out)

    def test_same_names(self):
        entry = '{"no_secrets": {"event": "after_start", "handler": "hand.sh"}}'
        out = self.dry(body(HOOK, tools="", hooks=entry + ", no_secrets"))
        self.assertEqual(out["hookeds.json"]["no_secrets"]["handler"], "fn/no_secrets.py")    # later wins (07d opinion 10)
        out = self.dry(body(HOOK, tools="", hooks="no_secrets, " + entry), name="b")
        self.assertEqual(out["hookeds.json"]["no_secrets"]["handler"], "hand.sh")
        self.assertNotIn("fn/no_secrets.py", out)
        two = HOOK + HOOK.replace("timeout_ms=5000", 'name="no_secrets"').replace("def no_secrets", "def other")
        self.bad(body(two, tools="", hooks="no_secrets, other"), "hooks: two functions are both hook no_secrets (no_secrets and other)",
                 name="c")
        both = HOOK + ADD.replace("@fn.tool\n", '@fn.tool(name="no_secrets")\n')
        self.bad(body(both, tools="add", hooks="no_secrets"), "tool no_secrets and hook no_secrets both compile to fn/no_secrets.py",
                 name="d")
        self.bad(body(ADD + ADD.replace("def add", "def plus").replace("@fn.tool\n", '@fn.tool(name="add")\n'), tools="add, plus"),
                 "tool add is listed twice", name="e")


class Links(FnCase):
    def test_static_dynamic_and_a_pack_tool_of_the_same_name(self):
        name = sorted(look())[0]
        mine = ADD.replace("@fn.tool\n", '@fn.tool(name="%s")\n' % name)
        out = self.dry(body(mine, tools='defs.std.pack("look"), add'))
        self.assertEqual(out["tools.json"]["tools"][name], {"path": "fn/%s.py" % name})       # the function wins over the pack's
        self.assertIn("fn/%s.py" % name, out)
        out = self.dry(body(ADD, tools='defs.std.pack("look"), add'), "--dynamic", name="b")
        self.assertIn("$override", out["tools.json"])
        self.assertEqual(out["tools.json"]["tools"], {"add": {"path": "fn/add.py"}})

    def test_drop_derive_rename_and_eca(self):
        base = self.agent(body(CHECK + HOOK, tools="check", hooks="no_secrets"), name="base")
        d = self.agent("base = defs.load('../base')\n" + body(CHECK.replace("Check two", "Check again two"),
                                                                tools="base.pack(prefix='base_'), check", hooks="base.hooks"), name="derived")
        r = run_agent(d / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        tools = json.loads((d / "tools.json").read_text())["tools"]
        self.assertEqual(tools, {"base_check": {"path": "fn/base_check.py"}, "check": {"path": "fn/check.py"}})
        self.assertIn('"""base_check - Check two numbers.', (d / "fn" / "base_check.py").read_text())
        self.assertIn('"""check - Check again two numbers.', (d / "fn" / "check.py").read_text())
        self.assertEqual(json.loads((d / "hookeds.json").read_text())["no_secrets"]["handler"], "fn/no_secrets.py")
        self.assertTrue((d / "fn" / "no_secrets.py").is_file())                                  # pulled out again here, not pointing back
        self.assertFalse((base / "fn").exists())
        self.assertEqual(self.call(d / "fn" / "base_check.py", '{"a": 1, "b": 2}').stdout, "3\n")
        out = self.dry("base = defs.load('../base')\n" + body("", tools="base.tools, defs.drop('check')", hooks="base.hooks"), name="dropped")
        self.assertEqual(out["tools.json"]["tools"], {})
        self.assertNotIn("fn/check.py", out)
        eca = Path(self.temp.name) / "eca"
        shutil.copytree(TEMPLATES / "agents" / "eca-claude", eca)
        self.agent(ADD + '\nagent = defs.Agent("Eca with a function.", system="S.\\n", tools=[add], llm={})\ndefs.main(agent)\n', name="eca")
        r = run_agent(eca / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        names = json.loads((eca / "interfaces.json").read_text())["aos-agent"]
        self.assertEqual(json.loads((eca / names["tools"]).read_text())["tools"]["add"]["path"],
                         os.path.relpath("fn/add.py", os.path.dirname(names["tools"]) or "."))
        self.assertTrue((eca / "fn" / "add.py").is_file())

    def test_old_programs_stay(self):
        d = self.agent(body(ADD + CHECK, tools="add, check"))
        self.assertEqual(run_agent(d / "agent.py", "--compile", home=self.home).returncode, 0)
        self.agent(body(ADD, tools="add"))
        self.assertEqual(run_agent(d / "agent.py", "--compile", home=self.home).returncode, 0)
        self.assertTrue((d / "fn" / "check.py").is_file())                                       # compiling deletes nothing
        self.assertEqual(sorted(json.loads((d / "tools.json").read_text())["tools"]), ["add"])

    def test_build_script_and_check(self):
        d = self.agent("import os\n" + ADD + HOOK + '\nfor n in ("x", "y"):\n    defs.Agent("Built " + n, system="S.\\n", tools=[add], llm={}, '
                       'fsm=defs.std.fsm(), hooks=[no_secrets]).compile(os.path.join(os.path.dirname(__file__), n))\n', name="build")
        for n in ("x", "y"):
            (d / n).mkdir()
        r = subprocess.run([sys.executable, str(d / "agent.py")], text=True, capture_output=True, timeout=30, env=env_with(self.home))
        self.assertEqual(r.returncode, 0, r.stderr)
        for n in ("x", "y"):
            self.assertTrue((d / n / "fn" / "add.py").is_file() and (d / n / "fn" / "no_secrets.py").is_file())


if __name__ == "__main__":
    unittest.main()
