"""Test the objects of defs: Fsm compiled alone, build scripts with .compile(folder), .dry_run() equal to what .compile() writes, one object in two agents, defs.main taking one object, the names that are gone."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
import unittest.mock


sys.dont_write_bytecode = True
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from agent_spec_helpers import *  # noqa: E402,F401,F403


TWO_FOLDERS = '''\
import os
std = defs.std
for name, what in (("one", "Answer the first kind of question."), ("two", "Answer the second kind of question.")):
    folder = os.path.join(sys.argv[1], name)
    os.makedirs(folder)
    a = defs.Agent(what, system="You answer questions.\\n", tools=[std.pack("look")], llm={}, fsm=std.fsm(), hooks=std.hooks())
    for line in a.compile(folder):
        print(line)
'''
FSM_ONLY = '''\
defs.main(defs.fsm("a", [defs.state("a", ["true"], {0: "b", "*": "a"}), defs.state("b", ["false"], {0: "a", 1: "a"})]))
'''
A_FSM = defs.fsm("a", [defs.state("a", ["true"], {0: "b", "*": "a"}), defs.state("b", ["false"], {0: "a", 1: "a"})])


class Objects(WithHome):
    """writing a definition is objects (aos-pylib-k2-1120, user 11-20 ".compile(夾) 寫檔、.dry_run() 只算"): defs.Agent and the Fsm of
    defs.fsm take what they are given and check it at .dry_run() / .compile(folder); compiling changes none of the things put in;
    defs.main takes one object; the old defs.compile / defs.write and the upper-case fields are gone."""

    def test_fsm_compiles_alone(self):
        d = self.folder("f")
        self.assertEqual(A_FSM.compile(str(d)), ["wrote %s" % (d / "fsm.json")])
        self.assertEqual(os.listdir(d), ["fsm.json"])
        whole = agent(fsm=A_FSM).dry_run()["fsm.json"]
        self.assertEqual(json.loads((d / "fsm.json").read_text()), whole)       # the same as an agent with this fsm compiles
        self.assertEqual(A_FSM.dry_run(), {"fsm.json": whole})
        self.assertEqual((d / "fsm.json").read_text(), as_text(whole))
        # what aos-fsm reads: start, states, each state's exec.argv and next
        self.assertEqual(whole["_entry"], ["aos-fsm", {"$env": "AOS_CF"}])
        self.assertEqual(whole["start"], "a")
        self.assertEqual(whole["states"], {"a": {"exec": {"argv": ["true"]}, "next": {"0": "b", "*": "a"}},
                                           "b": {"exec": {"argv": ["false"]}, "next": {"0": "a", "1": "a"}}})
        e = self.folder("named")
        A_FSM.compile(str(e), name="x.json")
        self.assertEqual(os.listdir(e), ["x.json"])
        for bad in ("a/b", "", ".x.json", " x.json", 3):
            with self.subTest(name=bad):
                self.assertRaisesRegex(defs.SpecBad, "give one plain file name", A_FSM.compile, str(e), name=bad)
        self.assertEqual(os.listdir(e), ["x.json"])
        self.assertRaisesRegex(defs.SpecBad, "give the folder", A_FSM.compile, None)

    @unittest.skipUnless(shutil.which("aos-fsm"), "aos-fsm is not on PATH (run under an installed tree)")
    def test_aos_fsm_runs_the_fsm_json(self):
        """aos-fsm has no check-only flag, so run it: one step per call, the state kept in $AOS_STACK/stage.txt."""
        d, stack = self.folder("f"), self.folder("stack")
        A_FSM.compile(str(d))
        step = lambda: subprocess.run(["aos-fsm", "fsm.json"], cwd=d, text=True, capture_output=True, timeout=30,  # noqa: E731
                                      env=dict(env_with(self.home), AOS_STACK=str(stack)))
        for want in ("b", "a"):                    # a runs true (0 -> b); b runs false (1 -> a)
            r = step()
            self.assertEqual((r.returncode, r.stderr), (0, ""))
            self.assertEqual((stack / "stage.txt").read_text().strip(), want)

    def test_a_build_script_compiles_two_folders(self):
        root, out = self.folder("build"), self.folder("out")
        (root / "build.py").write_text(HEAD + TWO_FOLDERS)
        r = run_agent(root / "build.py", str(out), home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        one, two = snapshot(out / "one"), snapshot(out / "two")
        for made in (one, two):
            self.assertEqual(sorted(made), sorted(GENERATED + ["hookeds.json", "README.md"]))
        self.assertEqual(json.loads(one["_metainfo.json"]), {"summary": "Answer the first kind of question."})
        self.assertEqual(json.loads(two["_metainfo.json"]), {"summary": "Answer the second kind of question."})
        for name in ("fsm.json", "tools.json", "hookeds.json", "loop.json", "system.txt", "llm.json"):
            self.assertEqual(one[name], two[name], name)
        self.assertEqual(os.listdir(root), ["build.py"])

    def test_dry_run_is_what_compile_writes(self):
        a = agent(tools=[defs.std.pack("look")], hooks=defs.std.hooks(), meta={"cost": {"time_ms": 1}},
                  files={"ladder.json": {"repeat": 3}, "notes.txt": "plain text\n"})
        out, d = a.dry_run(), self.folder("d")
        lines = a.compile(str(d))
        self.assertEqual(sorted(os.listdir(d)), sorted(out))
        for name, value in out.items():
            self.assertEqual((d / name).read_text(), as_text(value), name)
        self.assertEqual(lines, ["wrote %s" % (d / n) for n in out])
        # the write rules: README.md is kept when it is there, _metainfo.json keeps the keys agent.py does not set
        (d / "README.md").write_text("Mine.\n")
        (d / "_metainfo.json").write_text(json.dumps({"summary": "old", "note": {"template": "x"}}))
        lines = a.compile(str(d))
        self.assertEqual((d / "README.md").read_text(), "Mine.\n")
        self.assertEqual(json.loads((d / "_metainfo.json").read_text()), dict(out["_metainfo.json"], note={"template": "x"}))
        self.assertIn("kept %s (it is already there)" % (d / "README.md"), lines)
        for name, value in out.items():
            if name not in ("README.md", "_metainfo.json"):
                self.assertEqual((d / name).read_text(), as_text(value), name)

    def test_wrong_is_spec_bad_at_dry_run_not_when_made(self):
        d = self.folder("d")
        a = defs.Agent(" ", system=3, tools=["look"], llm={"model": 3}, fsm={"start": "a"}, files=3)   # takes it, says nothing
        self.assertEqual((a.system, a.tools, a.fsm), (3, ["look"], {"start": "a"}))
        self.assertRaises(defs.SpecBad, a.dry_run)
        self.assertRaises(defs.SpecBad, a.compile, str(d))
        f = defs.fsm("z", [defs.state("a", ["x"], {0: "a"})])
        self.assertEqual(type(f).__name__, "Fsm")
        self.assertIn("fsm start 'z' is not one of the states", f["bad"])
        self.assertRaisesRegex(defs.SpecBad, "fsm start 'z'", f.dry_run)
        self.assertRaisesRegex(defs.SpecBad, "fsm start 'z'", f.compile, str(d))
        self.assertRaisesRegex(defs.SpecBad, "fsm start 'z'", agent(fsm=f).dry_run)
        self.assertEqual(os.listdir(d), [])

    def test_eca_needs_its_folder(self):
        dest = Path(self.temp.name) / "eca-pi"
        shutil.copytree(TEMPLATES / "eca-pi", dest, symlinks=True)
        a = agent("S.", fsm=None, llm={"model": "m"})
        self.assertRaisesRegex(defs.SpecBad, "give its folder", a.dry_run)
        self.assertEqual(sorted(a.dry_run(str(dest))), ["README.md", "_metainfo.json", "llm.json", "system.txt", "tools.json"])

    def shared(self, base):
        """the things two agents share: an fsm, tools (with the tools of defs.load), hooks (with std.hooks())."""
        loaded = defs.load(str(base))
        fsm = defs.fsm(defs.std.fsm(), [defs.state("act", timeout_ms=5)])
        tools = [loaded.tools, defs.std.pack("json", exclude=["json_del"]), defs.drop("glob"),
                 defs.tool("now", defs.home("/lib/tools/base/peek_now_time"))]
        hooks = [defs.std.hooks(), {"timer": {**defs.std.hooks()["timer"], "every_ms": 5}}]
        return loaded, fsm, tools, hooks

    def test_one_fsm_and_tools_in_two_agents(self):
        base = self.folder("base")
        (base / "agent.py").write_text(HEAD + BODY)
        second = lambda fsm, tools, hooks: defs.Agent("Two.", system="Two.\n", tools=tools, llm={"model": "m"},  # noqa: E731
                                                      fsm=fsm, hooks=hooks, files={"x.json": {"a": [1]}})
        _, *alone = self.shared(base)
        want = second(*alone).dry_run()
        loaded, fsm, tools, hooks = self.shared(base)
        seen = lambda: json.dumps([loaded.tools, loaded.fsm, loaded.hooks, fsm, tools, hooks], sort_keys=True)  # noqa: E731
        before = seen()
        first = defs.Agent("One.", system="", tools=tools, llm={}, fsm=fsm, hooks=hooks)
        first.dry_run()
        first._files(None, lambda msg: None, link="dynamic")                   # (its warnings: not shown here)
        first.compile(str(self.folder("one")))
        two = second(fsm, tools, hooks)
        self.assertEqual(two.dry_run(), want)
        d = self.folder("two")
        two.compile(str(d))
        self.assertEqual(snapshot(d), {n: as_text(v).encode() for n, v in want.items()})
        self.assertEqual(seen(), before)                                       # nothing put in was changed
        self.assertEqual(loaded.compile(str(self.folder("again")))[0].split()[0], "wrote")
        self.assertEqual(seen(), before)

    def test_agent_py_with_an_fsm(self):
        d = self.folder("machine")
        (d / "agent.py").write_text(HEAD + FSM_ONLY)
        for argv in (("--dry-run", "--static"), ("--compile", "--dynamic")):
            r = run_agent(d / "agent.py", *argv, home=self.home)
            self.assertEqual(r.returncode, 1)
            self.assertTrue(r.stderr.startswith("machine: error: FlagUnknown %s (usage: python3 agent.py --compile [FOLDER]" % argv[1]),
                            r.stderr)
        r = run_agent(d / "agent.py", "--dry-run", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), A_FSM.dry_run())
        r = run_agent(d / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(os.listdir(d)), ["agent.py", "fsm.json"])
        self.assertEqual(json.loads((d / "fsm.json").read_text()), A_FSM.dry_run()["fsm.json"])
        (d / "agent.py").write_text(HEAD + FSM_ONLY.replace('"a", [', '"z", [', 1))
        r = run_agent(d / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("machine: error: SpecBad fsm start 'z'"), r.stderr)

    def test_main_takes_one_object(self):
        cases = {"the old five": ('defs.main("D.", "", [], {}, defs.std.fsm())', "got 5 arguments"),
                 "a string": ('defs.main("D.")', "got a value of type str"),
                 "nothing": ("defs.main()", "got 0 arguments"),
                 "a keyword": ("defs.main(agent=defs.Agent('D.', system='', tools=[], llm={}, fsm=defs.std.fsm()))", "got keyword arguments agent=")}
        for why, (line, got) in cases.items():
            with self.subTest(why=why):
                d = self.folder(why.replace(" ", "-"))
                (d / "agent.py").write_text(HEAD + line + "\n")
                for flag in ("--compile", "--dry-run"):
                    r = run_agent(d / "agent.py", flag, home=self.home)
                    self.assertEqual((r.returncode, r.stdout), (1, ""))
                    self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
                    self.assertTrue(r.stderr.startswith("%s: error: SpecBad defs.main takes one thing to compile: " % d.name), r.stderr)
                    self.assertIn(got, r.stderr)
                    self.assertTrue(r.stderr.rstrip().endswith("(fix the declaration in agent.py)"), r.stderr)
                self.assertEqual(os.listdir(d), ["agent.py"])
        old = self.folder("old")
        (old / "agent.py").write_text(HEAD + cases["the old five"][0] + "\n")
        machine = self.folder("machine")
        (machine / "agent.py").write_text(HEAD + FSM_ONLY)
        for base, said in (("old", "defs.main takes one thing to compile"), ("machine", "hands defs.main a Fsm, not an agent")):
            with self.subTest(loaded=base):
                d = self.folder("on-" + base)
                (d / "agent.py").write_text(HEAD + "base = defs.load('../%s')\n"
                                                   "defs.main(defs.Agent('D.', system='', tools=[], llm={}, fsm=defs.std.fsm()))\n" % base)
                r = run_agent(d / "agent.py", "--compile", home=self.home)
                self.assertEqual(r.returncode, 1)
                self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
                self.assertTrue(r.stderr.startswith("on-%s: error: SpecBad defs.load('../%s'): " % (base, base)), r.stderr)
                self.assertIn(said, r.stderr)
                self.assertEqual(os.listdir(d), ["agent.py"])
        self.assertEqual(sorted(os.listdir(old)), ["agent.py"])

    def test_fields_are_plain_but_typos_are_caught(self):
        a = agent(tools=[defs.std.pack("look")])
        a.tools = []                                                          # a field can be changed
        self.assertEqual(a.dry_run()["tools.json"]["tools"], {})
        for name in ("TOOLS", "tool"):
            with self.subTest(name=name), self.assertRaisesRegex(AttributeError, "has no field %s \\(fields: description, system, " % name):
                setattr(a, name, [])

    def test_old_names_are_gone(self):
        for name in ("compile", "write"):
            with self.subTest(name=name), self.assertRaisesRegex(AttributeError, r"defs has no %s \(it has Agent, main, " % name):
                getattr(defs, name)
        base = self.folder("base")
        (base / "agent.py").write_text(HEAD + BODY)
        loaded = defs.load(str(base))
        for name in ("TOOLS", "SYSTEM", "FSM", "HOOKS", "LLM", "DESCRIPTION"):
            with self.subTest(name=name), self.assertRaisesRegex(AttributeError, r"has no %s \(it has description, system, " % name):
                getattr(loaded, name)
        r = run_agent(base / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = self.folder("copy")
        loaded.compile(str(d))                                                 # the loaded agent compiles as it is
        made, want = snapshot(d), snapshot(base)
        self.assertEqual(sorted(made), sorted(n for n in want if n != "agent.py"))
        self.assertEqual(json.loads(made["tools.json"])["tools"], json.loads(want["tools.json"])["tools"])
        for name in ("fsm.json", "llm.json", "system.txt", "_metainfo.json", "loop.json", "body.json", "_entry"):
            self.assertEqual(made[name], want[name], name)


if __name__ == "__main__":
    unittest.main()
