"""Test py/aos/fn_spec.py (cut 3): an @fn.tool / @fn.hook function of agent.py compiled into fn/<name>.py - what it may use from outside (each row of design 04's table), the imports it gets, and the program running on its own."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent_spec_helpers import HEAD, WithHome, env_with, run_agent  # noqa: E402

FN_HEAD = HEAD + "from aos.py import fn\n"
ADD = '''
@fn.tool
def add(a: float, b: float) -> float:
    """Add two numbers. Example: {"a": 2, "b": 3} -> 5

    Args:
      a: the first number
      b: the second number
    """
    return a + b
'''
TAIL = '''
agent = defs.Agent("Fn test.", system="S.\\n", tools=[%s], llm={}, fsm=defs.std.fsm(), hooks=[%s])
defs.main(agent)
'''


def body(funcs, tools="add", hooks=""):
    return funcs + TAIL % (tools, hooks)


class FnCase(WithHome):
    """Write agent.py into a folder and run it; programs of fn/ run with AOS_HOME = the fake home."""

    def agent(self, text, name="a", first=""):
        d = self.folder(name) if not (Path(self.temp.name) / name).exists() else Path(self.temp.name) / name
        (d / "agent.py").write_text(first + FN_HEAD + text)
        return d

    def dry(self, text, *more, name="a"):
        d = self.agent(text, name)
        r = run_agent(d / "agent.py", "--dry-run", *more, home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def bad(self, text, piece, name="a"):
        d = self.agent(text, name)
        r = run_agent(d / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("error: SpecBad ", r.stderr)
        self.assertIn(piece, r.stderr)
        self.assertEqual(len(r.stderr.strip().split("\n")), 1, r.stderr)
        self.assertFalse((d / "fn").exists())
        return r.stderr

    def call(self, program, stdin="{}", *argv, cwd=None):
        return subprocess.run([sys.executable, str(program), *argv], input=stdin, text=True, capture_output=True, timeout=30,
                              env=env_with(self.home), cwd=cwd)


class Uses(FnCase):
    """Design 04 "函數用到外面的東西", one row each."""

    def test_builtins_parameters_and_locals_are_fine(self):
        out = self.dry(body(ADD.replace("return a + b", "total = sum([a, b])\n    return float(len(str(total))) * 0 + total")))
        self.assertIn("fn/add.py", out)
        self.assertEqual(out["tools.json"]["tools"]["add"], {"path": "fn/add.py"})

    def test_top_imports_move_one_name_a_line(self):
        out = self.dry("import os, re\nfrom json import dumps as dj, loads\nimport os.path\n" + body(
            ADD.replace("return a + b", "return float(len(re.sub('x', '', dj([a, b])))) * 0 + a + b")))
        prog = out["fn/add.py"]
        self.assertIn("\nimport re\nfrom json import dumps as dj\n\n\n@fn.tool\n", prog)
        for no in ("import os\n", "import os.path", "loads", "import os, re"):
            self.assertNotIn(no, prog.split("# ---- the function ----")[1])

    def test_a_module_next_to_agent_py_is_an_error(self):
        (self.folder("a") / "helpers.py").write_text("def clean(x):\n    return x\n")
        self.bad("import helpers\n" + body(ADD.replace("return a + b", "return helpers.clean(a) + b")),
                 "tool add imports helpers, a module next to agent.py; a compiled function cannot find it at run time")
        self.bad("from helpers import clean\n" + body(ADD.replace("return a + b", "return clean(a) + b")),
                 "tool add imports helpers, a module next to agent.py")
        (self.folder("a/pkg") / "__init__.py").write_text("X = 1\n")
        self.bad("import pkg\n" + body(ADD.replace("return a + b", "return pkg.X + a + b")),
                 "tool add imports pkg, a module next to agent.py")

    def test_fn_is_fine(self):
        out = self.dry(body(ADD.replace("return a + b", "if a < 0:\n        fn.fail(\"Negative\", \"no\")\n    return a + b")))
        self.assertIn('fn.fail("Negative", "no")', out["fn/add.py"])

    def test_the_compile_library_is_an_error(self):
        self.bad(body(ADD.replace("return a + b", "return defs.home('/x') and a + b")),
                 "tool add uses defs, the compile library; at run time use fn.fail / fn.block")
        self.bad("std = defs.std\n" + body(ADD.replace("return a + b", "return std and a + b")),
                 "tool add uses std, the compile library")

    def test_own_constants_functions_classes_are_errors(self):
        for top, use in (("K = 2\n", "K"), ("def helper():\n    return 1\n", "helper()"), ("class C:\n    n = 1\n", "C.n")):
            with self.subTest(top=top):
                self.bad(top + body(ADD.replace("return a + b", "return a + b + %s" % use)),
                         "tool add uses %s, defined at the top of agent.py (line " % use.split("(")[0].split(".")[0])
        msg = self.bad(body(ADD + "\n\n@fn.tool\ndef twice(a: float) -> float:\n    \"\"\"Twice. Example: {\"a\": 1} -> 2\n\n"
                            "    Args:\n      a: a number\n    \"\"\"\n    return add(a, a)\n", tools="add, twice"),
                       "tool twice uses add, defined at the top of agent.py")
        self.assertIn("move it into the function", msg)

    def test_not_a_plain_top_level_def_is_an_error(self):
        plain = "must be a plain def at the top of agent.py with only @fn.tool on it"
        self.bad("import functools\n" + body(ADD.replace("@fn.tool\n", "@fn.tool\n@functools.lru_cache\n")), "is not a function")
        self.bad("def same(f):\n    return f\n" + body(ADD.replace("@fn.tool\n", "@same\n@fn.tool\n")), plain)
        self.bad(body("def make():\n" + "\n".join("    " + x for x in ADD.split("\n")) + "\n    return add\n\n\nadd = make()\n"), plain)
        self.bad(body("class Box:\n" + "\n".join("    " + x for x in ADD.split("\n")) + "\n\n\nadd = Box.add\n"), plain)
        self.bad(body("add = fn.tool(name=\"add\")(lambda a: a)\n"), plain)
        self.bad(body(ADD.replace("def add", "async def add")), plain)

    def test_decorator_line_and_defaults_count(self):
        self.bad("PARAMS = []\n" + body(ADD.replace("@fn.tool\n", "@fn.tool(params=PARAMS)\n")),
                 "tool add uses PARAMS, defined at the top of agent.py (line ")
        self.bad("B = 1.0\n" + body(ADD.replace("b: float)", "b: float = B)")), "tool add uses B, defined at the top")
        self.bad(body(ADD.replace("return a + b", "return a + b + NOWHERE")),
                 "tool add uses NOWHERE, which agent.py neither defines nor imports at the top")

    def test_comprehension_with_and_walrus_are_not_outside_names(self):
        code = ("xs = [i * a for i in range(2) if (j := i) >= 0]\n    with open(__file__) as h:\n        h.read(0)\n"
                "    return a + b + j * 0 + sum(xs) * 0 + len({k: v for k, v in {}.items()})")
        out = self.dry("i = j = h = k = 9\n" + body(ADD.replace("return a + b", code)))
        self.assertIn("fn/add.py", out)
        self.dry("NAMES = ['a']\n" + body(ADD.replace("@fn.tool\n", "@fn.tool(params=[fn.param(n, 'number', 'x') for n in ['a']])\n")),
                 name="b")

    def test_fn_block_in_a_string_does_not_count(self):
        out = self.dry(body(ADD.replace("return a + b", "s = 'fn.block(\"x\")'\n    return a + b + len(s) * 0")))
        self.assertIn("fn/add.py", out)
        self.bad(body(ADD.replace("return a + b", "return fn.block('no')")), "tool add uses fn.block: only a hook can block")

    def test_the_description_checks_of_fn_run_at_compile_time(self):
        nodoc = '@fn.tool\ndef add(a: float, b: float) -> float:\n    return a + b\n'
        self.bad(body(nodoc), "tool add has no description: write a docstring, or description=")
        self.bad(body(ADD.replace("b: float)", "b)")), 'parameter b needs a type (str, int, float, bool, list, dict), or fn.param("b", ...)')
        self.bad(body(ADD.replace("      b: the second number\n", "")), 'parameter b has no description: add "b: ..." under Args:')
        self.bad(body(ADD.replace("b: float)", "*b: float)")), "plain named parameters only")

    def test_unmarked_or_wrong_kind_is_an_error(self):
        self.bad(body("def add(a):\n    return a\n"), "tools: add is a function without a mark: put @fn.tool on it")
        self.bad(body("@fn.hook('before_tool')\ndef add(event):\n    return None\n"), "tools: add is marked @fn.hook; it goes in hooks=[...]")
        self.bad(body(ADD, tools="", hooks="add"), "hooks: add is marked @fn.tool; it goes in tools=[...]")


class Program(FnCase):
    def test_the_program_runs_on_its_own(self):
        d = self.agent("import math\n" + body(ADD.replace("return a + b", "return math.floor(a + b)")),
                       first="from __future__ import annotations\n")
        r = run_agent(d / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        prog = d / "fn" / "add.py"
        self.assertEqual(oct(prog.stat().st_mode & 0o777), "0o755")
        text = prog.read_text()
        self.assertTrue(text.startswith('#!/usr/bin/env python3\n"""add - Add two numbers. Example: {"a": 2, "b": 3} -> 5"""\n'
                                        "from __future__ import annotations\n"), text[:200])
        self.assertTrue(text.endswith("    return math.floor(a + b)\n\n\nfn.main(add)\n"))
        self.assertNotIn("agent.py", text)
        self.assertEqual(self.call(prog, '{"a": 2, "b": 3.5}').stdout, "5\n")
        td = json.loads(self.call(prog, "", "--tooldef").stdout)
        self.assertEqual(sorted(td["parameters"]["properties"]), ["a", "b"])
        r = subprocess.run([sys.executable, str(prog)], input="{}", text=True, capture_output=True, timeout=30,
                           env={k: v for k, v in env_with(None).items()})
        self.assertEqual((r.returncode, r.stdout), (1, "add: error: HomeMissing AOS_HOME is not set (the aos package is found "
                                                       "under $AOS_HOME/lib)\n"))

    def test_a_tool_called_json_does_not_hide_the_json_module(self):
        two = ADD.replace("def add", "def json_ok").replace("return a + b", "return json.dumps(a + b)") + \
            ADD.replace("@fn.tool\n", "@fn.tool(name=\"json\")\n").replace("def add", "def as_json")
        d = self.agent("import json\n" + body(two, tools="json_ok, as_json"))
        r = run_agent(d / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((d / "fn" / "json.py").is_file())
        got = self.call(d / "fn" / "json_ok.py", '{"a": 1, "b": 2}', cwd=d / "fn")
        self.assertEqual((got.returncode, got.stdout), (0, "3\n"), got.stderr)

    @unittest.skipUnless(shutil.which("aos-exec"), "aos-exec is not on PATH (run with an installed tree's bin/)")
    def test_relative_paths_start_at_fn(self):
        d = self.agent(body(ADD.replace("return a + b", "return open('data.txt').read().strip()")))
        self.assertEqual(run_agent(d / "agent.py", "--compile", home=self.home).returncode, 0)
        (d / "fn" / "data.txt").write_text("from fn/\n")
        (d / "data.txt").write_text("from the definition folder\n")
        env = dict(env_with(self.home), AOS_WS=str(d))
        r = subprocess.run(["aos-exec", "fn/add.py"], input='{"a": 1, "b": 2}', text=True, capture_output=True, timeout=30,
                           env=env, cwd=d)
        self.assertEqual(r.stdout, "from fn/\n", r.stderr)               # like any tool: the folder of the program (user 11-20 question 7)


if __name__ == "__main__":
    unittest.main()
