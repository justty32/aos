"""Test py/aos/agent_spec.py and the templates/agent-python skeleton: declarations to definition files (defs.Agent(...).dry_run()), SpecBad before any write, hooks and files, and the skeleton's committed files matching its agent.py."""
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


class Declaration(WithHome):
    def test_stock_shape(self):
        files = defs.Agent("Do it.", system="sys\n", tools=[defs.std.pack("look"), defs.tool("x", "tools/x", env={"A": "1"}), defs.drop("grep")],
                           llm={"model": "m"}, fsm=defs.std.fsm()).dry_run()
        self.assertEqual(list(files), ["_entry", "body.json", "loop.json", "fsm.json", "interfaces.json", "tools.json",
                                       "llm.json", "system.txt", "_metainfo.json", "README.md"])
        self.assertEqual(files["_entry"]["argv"], ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}])
        self.assertEqual(files["fsm.json"]["start"], "idle")
        self.assertEqual(list(files["fsm.json"]["states"]), ["idle", "think", "wait", "act"])
        self.assertEqual(files["fsm.json"]["states"]["act"]["exec"]["timeout_ms"], 0)
        self.assertEqual(files["fsm.json"]["states"]["wait"]["exec"]["argv"][1],
                         {"$env": "AOS_HOME", "$path": "/templates/agent-fsm/wait.py"})
        self.assertNotIn("$override", files["tools.json"])                  # the pack is copied in, tool by tool
        self.assertEqual(files["tools.json"]["tools"], dict(look("grep"), x={"path": "tools/x", "env": {"A": "1"}}))
        self.assertIn("std.pack('look')", files["tools.json"]["description"])
        self.assertEqual(files["llm.json"]["model"], "m")
        self.assertEqual(files["_metainfo.json"], {"summary": "Do it."})
        self.assertEqual(files["README.md"], "Do it.\n")

    def test_meta_and_interfaces(self):
        files = agent(meta={"cost": {"time_ms": 1}},
                      interfaces={"aos-observed": {"file": "observed.jsonl"}, "aos-agent": {"history": None}}).dry_run()
        self.assertEqual(files["interfaces.json"]["aos-agent"]["system"], "system.txt")
        self.assertNotIn("history", files["interfaces.json"]["aos-agent"])
        self.assertEqual(files["interfaces.json"]["aos-observed"], {"file": "observed.jsonl"})
        self.assertEqual(files["tools.json"], {"description": defs.WHAT["tools.json"], "tools": {}})
        self.assertEqual(files["_metainfo.json"], {"summary": "D.", "cost": {"time_ms": 1}})

    def test_own_fsm(self):
        f = defs.fsm("a", [defs.state("a", ["python3", "a.py"], {0: "b", "*": "a"}), defs.state("b", ["true"], "a")])
        files = agent(fsm=f).dry_run()
        self.assertEqual(files["fsm.json"]["states"]["a"]["next"], {"0": "b", "*": "a"})
        self.assertEqual(files["fsm.json"]["states"]["b"]["next"], "a")

    def test_spec_bad(self):
        fine = dict(description="D.", system="", tools=[], llm={}, fsm=defs.std.fsm())
        cases = {"empty description": dict(description=" "),
                 "next not in table": dict(fsm=defs.fsm("a", [defs.state("a", ["x"], {0: "nowhere"})])),
                 "start not in table": dict(fsm=defs.fsm("z", [defs.state("a", ["x"], {0: "a"})])),
                 "no 0 or *": dict(fsm=defs.fsm("a", [defs.state("a", ["x"], {1: "a"})])),
                 "code out of range": dict(fsm=defs.fsm("a", [defs.state("a", ["x"], {0: "a", 256: "a"})])),
                 "state twice": dict(fsm=defs.fsm("a", [defs.state("a", ["x"], "a"), defs.state("a", ["y"], "a")])),
                 "empty argv": dict(fsm=defs.fsm("a", [defs.state("a", [], "a")])),
                 "tool without path": dict(tools=[defs.tool("x", None)]),
                 "tool twice": dict(tools=[defs.tool("x", "a"), defs.drop("x")]),
                 "pack twice": dict(tools=[defs.std.pack("look"), defs.std.pack("look")]),
                 "bad pack name": dict(tools=[defs.std.pack("../x")]),
                 "not a tool item": dict(tools=["look"]),
                 "model not a string": dict(llm={"model": 3}),
                 "llm key not in llm_keys": dict(llm={"temp": 1}),
                 "system not a string": dict(system=3),
                 "no fsm and no folder": dict(fsm=None),
                 "interfaces without fsm": dict(fsm=None, interfaces={"x": 1}),
                 "fsm not from defs.fsm": dict(fsm={"start": "a"}),
                 "hook without handler": dict(hooks={"h": {"event": "after_tool"}}),
                 "hook bad name": dict(hooks={".h": {"event": "after_tool", "handler": "x"}}),
                 "hook clock key on other event": dict(hooks={"h": {"event": "after_tool", "handler": "x", "every_ms": 5}}),
                 "hooks not a table": dict(hooks="hooks.json"),
                 "hooks list item not a table": dict(hooks=[{"h": None}, 3]),
                 "hooks holds a tool": dict(hooks=[defs.std.pack("look")]),
                 "stock_hooks bad name": dict(hooks=defs.std.hooks("../x")),
                 "interfaces sets hookeds": dict(hooks={}, interfaces={"hookeds": "h.json"}),
                 "files not a dict": dict(files=["ladder.json"]),
                 "files takes a declared file": dict(files={"tools.json": {}}),
                 "files takes the skeleton": dict(files={"loop.json": {}}),
                 "files takes a runtime file": dict(files={"state.json": {}}),
                 "files takes agent.py": dict(files={"agent.py": "x"}),
                 "files in a sub folder": dict(files={"sub/x.json": {}}),
                 "files hidden": dict(files={".x.json": {}}),
                 "files content a number": dict(files={"x.json": 3}),
                 "meta sets summary": dict(meta={"summary": "x"}),
                 "interfaces sets tools": dict(interfaces={"aos-agent": {"tools": "t.json"}}),
                 "drop without a pack": dict(tools=[defs.tool("a", "x"), defs.drop("b")]),
                 "tool env not strings": dict(tools=[defs.tool("x", "a", env={"A": 1})]),
                 "tool env not a dict": dict(tools=[defs.tool("x", "a", env="A")]),
                 "tool cache true": dict(tools=[defs.tool("x", "a", cache=True)]),
                 "tool bad name": dict(tools=[defs.tool("my tool", "a")]),
                 "directive path not a string": dict(tools=[defs.tool("x", defs.home(None))]),
                 "interfaces removes aos-agent": dict(interfaces={"aos-agent": None}),
                 "not JSON": dict(meta={"tags": {1, 2}}),
                 "NaN": dict(meta={"x": float("nan")})}
        for why, change in cases.items():
            with self.subTest(why=why):
                self.assertRaises(defs.SpecBad, defs.Agent(**dict(fine, **change)).dry_run)

    def test_holes_from_argon_review(self):
        """geng-patch-1119 (thinking/2026-11/19/aos-compile-庚/12, class 1): meta keys, the entry message. (② extern("agent.py") went with
        the link version of defs.extern, cut 4: it is now just a link to agent.py, test_agent_spec_extern.py.)"""
        with self.assertRaisesRegex(defs.SpecBad, "meta keys must be strings"):                  # ① was TypeError
            agent(meta={1: "a"}).dry_run()
        with self.assertRaises(defs.SpecBad) as e:                                                # ⑥ entry cannot take extern
            agent(interfaces={"aos-agent": {"entry": "x.json"}}).dry_run()
        self.assertIn("entry is body.json", str(e.exception))
        self.assertNotIn("extern", str(e.exception))
        with self.assertRaisesRegex(defs.SpecBad, r"use defs.extern"):
            agent(interfaces={"aos-agent": {"llm": "x.json"}}).dry_run()

    def test_rename_order_and_cleanup(self):
        """geng-patch-1119 ③ files pointed at are renamed before the index files; ④ one failed unlink does not stop the cleanup."""
        a = agent()
        out = a.dry_run()
        with tempfile.TemporaryDirectory(prefix="agent-spec-") as d:
            order, replace = [], os.replace
            with unittest.mock.patch("os.replace", lambda a, b: (order.append(os.path.basename(b)), replace(a, b))):
                a.compile(d)
            self.assertEqual(order[-5:], ["loop.json", "body.json", "interfaces.json", "_entry", "_metainfo.json"])
            self.assertLess(order.index("fsm.json"), order.index("loop.json"))
        with tempfile.TemporaryDirectory(prefix="agent-spec-") as d:
            unlink, calls = os.unlink, []

            def flaky(p):
                calls.append(p)
                if len(calls) == 1:
                    raise OSError("unlink fails")
                unlink(p)

            def fail(a, b):
                raise OSError("replace fails")
            with unittest.mock.patch("os.replace", fail), unittest.mock.patch("os.unlink", flaky):
                self.assertRaisesRegex(OSError, "replace fails", a.compile, d)
            self.assertEqual(len(calls), len(out))
            self.assertEqual([p for p in os.listdir(d) if ".tmp-" in p], [os.path.basename(calls[0])])

    def test_hooks_and_files(self):
        mine = {"event": "before_tool", "condition": "shell", "handler": defs.home("/lib/tools/agent/hook_noop")}
        files = agent(hooks=[defs.std.hooks(), {"timer": None, "mine": mine}],
                      files={"ladder.json": {"repeat": 3}, "notes.txt": "plain text\n"}).dry_run()
        stock = json.loads((TEMPLATES / "agent-fsm" / "hookeds.json").read_text())
        self.assertEqual(list(files), ["_entry", "body.json", "loop.json", "fsm.json", "interfaces.json", "tools.json",
                                       "llm.json", "system.txt", "hookeds.json", "ladder.json", "notes.txt", "_metainfo.json",
                                       "README.md"])
        table = {k: v for k, v in stock.items() if k not in ("description", "timer")}   # the list file: {name: entry}, no "hooks" wrap
        table["mine"] = mine
        self.assertEqual({k: v for k, v in files["hookeds.json"].items() if k != "description"}, table)
        self.assertIn("templates/agent-fsm/hookeds.json", files["hookeds.json"]["description"])
        self.assertEqual(list(files["interfaces.json"]["aos-agent"]),
                         ["entry", "tools", "llm", "llm_keys", "history", "system"])   # no hooks / hook_points in the aos-agent cell
        self.assertEqual(files["interfaces.json"]["hookeds"], "hookeds.json")         # the two hook keys are top level
        self.assertEqual(files["interfaces.json"]["hooks"],
                         [{"$env": "AOS_HOME", "$path": "/lib/aos/apps/hook/loop_hooks.json"},
                          {"$env": "AOS_HOME", "$path": "/templates/agent-fsm/hooks.json"}])
        fire = ["aos-hook", "fire", "-q", "--stop-on-nonzero", "--def", {"$env": "AOS_CD"}]
        self.assertEqual(files["loop.json"]["on_start"], {"argv": fire + ["after_start"]})
        self.assertEqual(files["loop.json"]["on_stop"], {"argv": fire + ["after_stop"]})
        self.assertNotIn("on_before_run", files["loop.json"])   # nothing hooked on before_run / after_run: not wired (no flag files)
        self.assertNotIn("on_after_run", files["loop.json"])
        self.assertFalse([k for k in files["loop.json"] if k.endswith("_if")])
        for event in ("before_run", "after_run"):                # a hook on one of them at compile time wires that one only
            with self.subTest(event=event):
                loop = agent(hooks={"h": {"event": event, "handler": "x"}}).dry_run()["loop.json"]
                self.assertEqual(loop["on_" + event], {"argv": fire + [event]})
                self.assertNotIn("on_" + ({"before_run": "after_run", "after_run": "before_run"}[event]), loop)
        self.assertEqual(files["ladder.json"], {"repeat": 3})
        self.assertEqual(files["notes.txt"], "plain text\n")

    def test_hooks_loop_matches_agent_fsm_template(self):
        """with hooks, loop.json is the agent-fsm template's loop.json (apart from its description)."""
        files = agent(hooks={}).dry_run()
        loop = json.loads((TEMPLATES / "agent-fsm" / "loop.json").read_text())
        self.assertEqual(plain(files["loop.json"]), plain(loop))
        self.assertEqual(files["hookeds.json"], {"description": defs.WHAT["hookeds.json"]})

    def test_llm_keys_take_reasoning_effort(self):
        """reasoning_effort (11-21, the brain's thinking level; the agent-fsm cells read it from llm.json) is one of the llm_keys
        the compiler writes, so llm={"reasoning_effort": "high"} compiles and goes into llm.json as given."""
        files = agent(llm={"model": "sol", "reasoning_effort": "high"}).dry_run()
        self.assertEqual(files["interfaces.json"]["aos-agent"]["llm_keys"][:2], ["model", "reasoning_effort"])
        self.assertEqual(files["llm.json"]["reasoning_effort"], "high")
        self.assertRaises(defs.SpecBad, agent(llm={"effort": "high"}).dry_run)   # the old name is gone

    def test_no_hooks_no_hooks_key(self):
        files = agent().dry_run()
        self.assertNotIn("hooks", files["interfaces.json"])
        self.assertNotIn("hookeds", files["interfaces.json"])
        self.assertNotIn("on_start", files["loop.json"])
        self.assertNotIn("on_before_run", files["loop.json"])
        self.assertNotIn("hookeds.json", files)

    def test_stock_hooks_needs_a_home_with_the_template(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AOS_HOME", None)
            self.assertIn("AOS_HOME is not set", defs.std.hooks()["bad"])
        bad = defs.std.hooks("reviewer")
        self.assertIn("templates with hooks: ", bad["bad"])
        self.assertIn("agent-fsm", bad["bad"])
        self.assertRaises(defs.SpecBad, agent(hooks=bad).dry_run)


class Skeleton(unittest.TestCase):
    """templates/agent-python: the committed files are exactly what its agent.py writes today."""

    def test_aos_py_next_to_agent_py_does_not_win(self):
        """an aos.py next to agent.py: with AOS_HOME set, the skeleton still finds the aos package ($AOS_HOME/lib comes first)."""
        with tempfile.TemporaryDirectory(prefix="agent-python-") as tmp:
            home = fake_home(tmp)
            dest = Path(tmp) / "mine"
            dest.mkdir()
            shutil.copy(SKEL / "agent.py", dest)
            (dest / "aos.py").write_text("raise SystemExit('the wrong aos')\n")
            r = run_agent(dest / "agent.py", "--dry-run", home=home)
            self.assertEqual(r.returncode, 0, r.stderr)
            (dest / "aos.py").unlink()
            (home / "lib").unlink()
            (home / "lib").mkdir()
            (home / "lib" / "aos").mkdir()                     # an older lib: aos there, the entry aos.py not yet
            (home / "lib" / "aos" / "__init__.py").write_text("")
            (home / "lib" / "aos" / "agent_spec.py").write_text("from aos.agent_spec_lib import std\n")
            r = run_agent(dest / "agent.py", "--dry-run", home=home)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(r.stderr, "mine: error: ModuleMissing aos.py not found "
                                       "(under $AOS_HOME/lib, or next to agent.py)\n")             # one line, not a traceback
            (home / "lib" / "aos" / "py").symlink_to(LIB / "aos" / "py")   # the entry there, agent_spec_lib not yet
            r = run_agent(dest / "agent.py", "--dry-run", home=home)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(r.stderr, "mine: error: ModuleMissing aos.agent_spec_lib not found "
                                       "(under $AOS_HOME/lib, or next to agent.py)\n")             # defs is found through aos.py.agent: still one line

    def test_files(self):
        self.assertEqual(sorted(p.name for p in SKEL.iterdir()), sorted(SKEL_GENERATED + ["README.md", "agent.py"]))

    def test_declares_empty_hooks(self):
        """the skeleton declares hooks={} (user 11-19 "骨架帶一行空的 HOOKS"): hookeds.json with no hooks, named in interfaces.json, so an agent
        made from it takes breakpoints (aos-gdb) and aos-agent hook without changing anything; still no hook group of a template."""
        self.assertEqual(list(json.loads((SKEL / "hookeds.json").read_text())), ["description"])
        self.assertEqual(json.loads((SKEL / "interfaces.json").read_text())["hookeds"], "hookeds.json")
        self.assertEqual(json.loads((SKEL / "loop.json").read_text())["on_start"]["argv"][:2], ["aos-hook", "fire"])

    def test_built_on_the_skeleton(self):
        """defs.load of the skeleton: its hooks are an empty group; a derived agent.py that gives no hooks gets no hookeds.json, one that gives
        hooks=base.hooks or [base.hooks, {...}] gets those (the inheritance examples keep working)."""
        with tempfile.TemporaryDirectory(prefix="agent-python-") as tmp:
            home = fake_home(tmp)
            base = Path(tmp) / "base"
            base.mkdir()
            shutil.copy(SKEL / "agent.py", base)
            mine = {"event": "after_start", "handler": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/hook_noop"}}
            args = "base.description, system=base.system, tools=[base.tools], llm=base.llm, fsm=base.fsm"
            tails = {"none": "defs.main(defs.Agent(%s))\n" % args,
                     "same": "defs.main(defs.Agent(%s, hooks=base.hooks))\n" % args,
                     "more": "defs.main(defs.Agent(%s, hooks=[base.hooks, {'mine': %r}]))\n" % (args, mine)}
            want = {"none": None, "same": {}, "more": {"mine": mine}}
            text = (SKEL / "agent.py").read_text()
            head = text[:text.index("# ---- your agent")]
            for name, tail in tails.items():
                with self.subTest(derived=name):
                    d = Path(tmp) / name
                    d.mkdir()
                    (d / "agent.py").write_text(head + "base = defs.load('../base')\n" + tail)
                    r = run_agent(d / "agent.py", "--compile", home=home)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    if want[name] is None:
                        self.assertFalse((d / "hookeds.json").exists())
                        self.assertNotIn("hookeds", json.loads((d / "interfaces.json").read_text()))
                    else:
                        got = json.loads((d / "hookeds.json").read_text())
                        got.pop("description")
                        self.assertEqual(got, want[name])

    def test_committed_files_match_agent_py(self):
        with tempfile.TemporaryDirectory(prefix="agent-python-") as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            (home / "lib").symlink_to(LIB)            # AOS_HOME/lib = the py/ source (it holds aos/ and packs/)
            dest = Path(tmp) / "agent-python"
            dest.mkdir()
            shutil.copy(SKEL / "agent.py", dest)
            env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
            env["AOS_HOME"] = str(home)
            r = subprocess.run([sys.executable, str(dest / "agent.py"), "--compile"], capture_output=True, text=True,
                               timeout=30, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            for name in SKEL_GENERATED:
                with self.subTest(name=name):
                    self.assertEqual((dest / name).read_bytes(), (SKEL / name).read_bytes(),
                                     "run python3 agent.py --compile in templates/agent-python")
