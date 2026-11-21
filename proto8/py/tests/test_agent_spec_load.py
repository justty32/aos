"""Test defs.load of py/aos/agent_spec.py (one agent.py built on another: the loaded agent's fields, worked out when agent.py runs, nothing of the base left in the files) and templates/reviewer rewritten as one agent.py."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import unittest.mock

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent_spec_helpers import HEAD, TEMPLATES, WithHome, agent, defs, fake_home, plain, run_agent, snapshot  # noqa: E402

# templates/reviewer written as one agent.py (design 04, third cut's check): compared with the hand-written files, the template is not changed
REVIEWER = '''\
std = defs.std

def cell(name):
    return ["python3", defs.home("/templates/agent-fsm/%s.py" % name)]

agent = defs.Agent(
    "Review measured definition costs and prescribe a fix or split when model downgrades fail.",
    meta={"cost": {"time_ms": 60000}, "resource": ["llm"]},
    system=defs.extern("system.hand.txt"),
    tools=[std.tool("aos/" + n) for n in ("review_round", "watch", "promote", "rollback", "measure")]
        + [std.tool("base/" + n) for n in ("json_get", "json_ls", "json_set", "json_del", "read", "ls")],
    llm={},
    fsm=defs.fsm("idle", [
        defs.state("idle",  cell("idle"),  {0: "think", 10: "idle"}),
        defs.state("think", cell("brain"), {0: "wait", 10: "idle"}),
        defs.state("wait",  cell("wait"),  {0: "act", 10: "wait", 11: "think"}),
        defs.state("act",   cell("act"),   {0: "think", 10: "idle"}, timeout_ms=0),
    ]),
    interfaces={"aos-observed": {"file": "observed.jsonl"}, "aos-agent": {"history": None}},
    files={"ladder.json": {
        "description": "Configure model downgrade trials, quality gates, and post-promotion watching.",
        "ladder": ["sol", "terra", "luna", "local"], "repeat": 3, "min_score": 0.9,
        "watch": {"window": 3, "tolerance": 0.1, "metric": "/token/in", "baseline_cases": 3},
        "promote_by": "self", "max_prompt_tokens_median": 10000, "retire_after_cases": 3,
    }},
)
defs.main(agent)
'''
BASE = '''\
std = defs.std
agent = defs.Agent(
    "Review a change and answer by mail.",
    system="You review changes in the workspace.\\n",
    tools=[std.pack("look"), std.pack("mailbox")],
    llm={"model": "luna"},
    fsm=std.fsm(),
    hooks=std.hooks(),
)
defs.main(agent)
'''
STRICT = '''\
base = defs.load("../reviewer")
strict = defs.Agent(
    "Review a change and refuse anything without a test.",
    system=base.system + "Refuse a change that has no test.\\n",
    tools=[base.tools, defs.drop("grep"), defs.std.tool("base/peek_now_time", name="now")],
    llm=base.llm,
    fsm=base.fsm,
    hooks=[base.hooks, {"timer": {**base.hooks["timer"], "every_ms": 60000}}],
)
defs.main(strict)
'''
PLAIN = "defs.main(defs.Agent('D.', system='', tools=[], llm={}, fsm=defs.std.fsm()))\n"


def derived(change):
    """BASE with agent.py lines put in just before its defs.main(agent)."""
    return BASE.replace("defs.main(agent)", change + "defs.main(agent)")


class Inherit(WithHome):
    """inheritance first cut (aos-inherit-cut1-1119): base = defs.load(folder) runs another agent.py, whose defs.main only hands over its
    agent; worked out when agent.py runs, so the files written are whole and name no base (N-70); the running side is not touched."""

    def agent(self, name, body):
        folder = Path(self.temp.name) / name
        folder.mkdir(exist_ok=True)
        (folder / "agent.py").write_text(HEAD + body)
        return folder

    def run1(self, folder, *argv):
        return run_agent(folder / "agent.py", *(argv or ("--compile",)), home=self.home)

    def assert_one_line(self, r, prog, *parts):
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.startswith(prog + ": error: SpecBad "), r.stderr)
        for p in parts:
            self.assertIn(p, r.stderr)

    def test_strict_reviewer(self):
        base, strict = self.agent("reviewer", BASE), self.agent("strict-reviewer", STRICT)
        self.assertEqual(self.run1(base).returncode, 0)
        before = snapshot(base)
        r = self.run1(strict)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        self.assertEqual(snapshot(base), before)                            # loading the base writes nothing there
        made, want = snapshot(strict), snapshot(base)
        self.assertEqual(sorted(made), sorted(want))
        load = lambda files, name: json.loads(files[name])  # noqa: E731
        for name in ("fsm.json", "loop.json", "llm.json", "_entry", "body.json"):
            self.assertEqual(made[name], want[name], name)                  # whole files, the same as the base's
        self.assertEqual(plain(load(made, "interfaces.json")), plain(load(want, "interfaces.json")))
        tools, base_tools = load(made, "tools.json")["tools"], load(want, "tools.json")["tools"]
        self.assertEqual(sorted(set(base_tools) - set(tools)), ["grep"])
        self.assertEqual(sorted(set(tools) - set(base_tools)), ["now"])
        self.assertEqual(made["system.txt"].decode(), "You review changes in the workspace.\nRefuse a change that has no test.\n")
        hooks, base_hooks = load(made, "hookeds.json"), load(want, "hookeds.json")
        hooks.pop("description"), base_hooks.pop("description")
        self.assertEqual(hooks["timer"], dict(base_hooks["timer"], every_ms=60000))
        self.assertEqual(hooks["timer"]["timeout_ms"], 5000)                 # one field changed, timeout_ms kept
        self.assertEqual({k: v for k, v in hooks.items() if k != "timer"}, {k: v for k, v in base_hooks.items() if k != "timer"})
        for name, data in made.items():                                     # no trace of the base in what was written
            if name != "agent.py":
                for trace in ("reviewer/", "defs.load", self.temp.name, "$override", "extends"):
                    self.assertNotIn(trace, data.decode(), name)

    def test_upstream_change_follows_at_recompile_only(self):
        base, strict = self.agent("reviewer", BASE), self.agent("strict-reviewer", STRICT)
        self.assertEqual(self.run1(strict).returncode, 0)
        first = snapshot(strict)
        self.agent("reviewer", BASE.replace('std.pack("mailbox")]', 'std.pack("mailbox"), std.pack("json")]'))
        self.assertEqual(snapshot(strict), first)                           # nothing follows by itself
        self.assertEqual(self.run1(strict).returncode, 0)                   # recompile the derived one: it follows,
        tools = json.loads((strict / "tools.json").read_text())["tools"]    # though the base's json was never written
        self.assertIn("json_get", tools)
        self.assertFalse((base / "tools.json").exists())

    def test_diamond(self):
        self.agent("base", BASE)
        self.agent("d1", derived("base = defs.load('../base')\nagent.tools = [base.tools, defs.drop('grep')]\n"
                                 "agent.hooks = [base.hooks, {'timer': None}]\n"))
        self.agent("d2", derived("base = defs.load('../base')\nagent.tools = [base.tools]\nagent.hooks = base.hooks\n"))
        d1, d2 = defs.load(str(Path(self.temp.name) / "d1")), defs.load(str(Path(self.temp.name) / "d2"))
        tools = lambda items: agent(tools=items).dry_run()["tools.json"]["tools"]  # noqa: E731
        with self.assertRaisesRegex(defs.SpecBad, r"tool grep is taken out in defs.load\('.*d1'\) but kept in defs.load\('.*d2'\)"):
            tools([d1.tools, d2.tools])                                     # a tool taken out does not come back unseen
        self.assertNotIn("grep", tools([d1.tools, d2.tools, defs.drop("grep")]))
        self.assertIn("grep", tools([d1.tools, d2.tools, defs.tool("grep", defs.home("/lib/tools/base/grep"))]))
        self.assertEqual(sorted(tools([d1.tools, d2.tools, defs.drop("grep")])), sorted(set(tools([d2.tools])) - {"grep"}))
        hooks = lambda h: agent(hooks=h).dry_run()["hookeds.json"]  # noqa: E731
        with self.assertRaisesRegex(defs.SpecBad, "hook timer comes from both"):
            hooks([d1.hooks, d2.hooks])
        self.assertNotIn("timer", hooks([d1.hooks, d2.hooks, {"timer": None}]))
        dest = self.agent("top", "d1 = defs.load('../d1')\nd2 = defs.load('../d2')\n"
                                 "defs.main(defs.Agent('D.', system='', tools=[d1.tools, d2.tools], llm={}, fsm=defs.std.fsm()))\n")
        r = self.run1(dest)
        self.assert_one_line(r, "top", "tool grep is taken out in")
        self.assertEqual(os.listdir(dest), ["agent.py"])

    def test_plain_import_does_not_write_the_base(self):
        """the old pit (aos-inherit-1119/02, finding 5): importing another agent.py ran its defs.main with our argv, wrote into the
        base's folder and exited 0 before our own defs.main. Now defs.main of an imported file says so and does nothing."""
        base = self.agent("reviewer", BASE)
        dest = self.agent("strict", "import importlib.util\n"
                                    "s = importlib.util.spec_from_file_location('reviewer_agent', %r)\n"
                                    "m = importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
                                    "defs.main(defs.Agent('D.', system=m.agent.system, tools=[m.agent.tools[0]], llm={}, fsm=defs.std.fsm()))\n"
                                    % str(base / "agent.py"))
        r = self.run1(dest)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([p for p in os.listdir(base) if p != "__pycache__"], ["agent.py"])
        self.assertIn("fsm.json", os.listdir(dest))
        self.assertIn("reviewer: warning: ", r.stderr)
        self.assertIn("use base = defs.load", r.stderr)

    def test_load_errors_are_one_line(self):
        self.agent("hand", BASE.replace('system="You review changes in the workspace.\\n"', 'system=defs.extern("system.hand.txt")'))
        self.agent("broken", BASE.replace("agent = defs.Agent(", "x = undefined_name\nagent = defs.Agent("))
        self.agent("nomain", BASE.replace("defs.main(agent)", "_ = agent"))
        self.agent("badbase", BASE.replace('std.pack("mailbox")', 'std.pack("nope")'))
        self.agent("a", "b = defs.load('../b')\n" + PLAIN)
        self.agent("b", "a = defs.load('../a')\n" + PLAIN)
        cases = {"no such folder": ("defs.load('../nowhere')", "is not a folder"),
                 "no agent.py there": ("defs.load('../empty')", "there is no"),
                 "an extern field used": ("defs.load('../hand').system", "system of", "is defs.extern('system.hand.txt')", "inside that folder"),
                 "the base fails": ("defs.load('../broken')", "agent.py line 5: NameError"),
                 "the base never calls defs.main": ("defs.load('../nomain')", "never calls defs.main"),
                 "a wrong declaration in the base": ("defs.load('../badbase')", "std.pack('nope')", "fix the declaration in"),
                 "a circle": ("defs.load('../a')", "load each other in a circle"),
                 "no such hook": ("defs.load('../hand').hooks['nope']", "has no hook 'nope'"),
                 "not a path": ("defs.load(3)", "give the folder of another agent.py")}
        (Path(self.temp.name) / "empty").mkdir()
        for why, (expr, *line) in cases.items():
            with self.subTest(why=why):
                dest = self.agent("derived", "base = %s\n" % expr + PLAIN)
                for flag in ("--compile", "--dry-run"):
                    r = self.run1(dest, flag)
                    self.assert_one_line(r, "derived", *line)
                    self.assertEqual(r.stdout, "")
                self.assertEqual(os.listdir(dest), ["agent.py"])
        self.assertTrue(defs.load(str(Path(self.temp.name) / "hand")).tools)    # an extern field stops only when it is used

    def test_base_paths_are_moved_and_modules_put_back(self):
        base = self.agent("base", "import helper\n" + BASE.replace(
            "fsm=std.fsm(),", "fsm=defs.fsm(std.fsm(), [defs.state('act', ['python3', 'act.py'])]),").replace(
            'std.pack("mailbox")]', 'std.pack("mailbox"), defs.tool("mine", "tools/mine", env_file="my.env")]').replace(
            "hooks=std.hooks(),", "hooks=[std.hooks(), {'h': {'event': 'after_tool', 'handler': 'hooks/h'}}],"))
        (base / "helper.py").write_text("WHO = 'base'\n")
        (base / "act.py").write_text("")
        derived_ = self.agent("derived", "base = defs.load('../base')\nimport helper\nassert helper.WHO == 'derived', helper.WHO\n"
                                         "defs.main(defs.Agent('D.', system='', tools=[base.tools], llm={}, fsm=base.fsm, hooks=base.hooks))\n")
        (derived_ / "helper.py").write_text("WHO = 'derived'\n")
        path = list(sys.path)
        r = self.run1(derived_)
        self.assertEqual(r.returncode, 0, r.stderr)
        tools = json.loads((derived_ / "tools.json").read_text())["tools"]
        self.assertEqual(tools["mine"], {"path": str(base / "tools" / "mine"), "env_file": str(base / "my.env")})
        argv = json.loads((derived_ / "fsm.json").read_text())["states"]["act"]["exec"]["argv"]
        self.assertEqual(argv, ["python3", str(base / "act.py")])           # "python3" is a command, not a file of the base
        self.assertEqual(json.loads((derived_ / "hookeds.json").read_text())["h"]["handler"], str(base / "hooks" / "h"))
        sys.modules.pop("helper", None)
        got = defs.load(str(base))                                            # in this process: sys.path and sys.modules put back
        self.assertEqual(sys.path, path)
        self.assertNotIn("helper", sys.modules)
        self.assertEqual(got.fsm["states"]["act"]["exec"]["timeout_ms"], 0)  # the field not given is the base's
        with unittest.mock.patch.dict(os.environ, {"AOS_INHERIT_TEST": self.temp.name}):
            moved = defs.load(defs.env("AOS_INHERIT_TEST", "/base")).tools["tools"]["mine"]["path"]
        self.assertEqual(moved, {"$env": "AOS_INHERIT_TEST", "$path": "/base/tools/mine"})

    def test_fsm_refit(self):
        stock = defs.std.fsm()
        f = defs.fsm(stock, [defs.state("think", ["python3", "think_cached.py"]), defs.state("look", ["true"], "idle")])
        self.assertEqual(f["states"]["think"], {"exec": {"argv": ["python3", "think_cached.py"]}, "next": stock["states"]["think"]["next"]})
        self.assertIn("look", f["states"])
        self.assertEqual(defs.fsm(stock, [defs.state("act", timeout_ms=5)])["states"]["act"]["exec"]["argv"],
                         stock["states"]["act"]["exec"]["argv"])
        self.assertEqual(defs.fsm(stock, [defs.state("wait", next={0: "idle"})], drop=["act"])["states"]["wait"]["next"], {"0": "idle"})
        self.assertEqual(stock, defs.std.fsm())                                # the base is not changed
        for why, value, line in (("next to a dropped state", defs.fsm(stock, [], drop=["act"]), "next state 'act'"),
                                 ("drop the start", defs.fsm(stock, [defs.state("wait", next="wait")], drop=["idle"]), "start state idle"),
                                 ("drop nothing there", defs.fsm(stock, [], drop=["nope"]), "the base has no state nope"),
                                 ("a new state, partly", defs.fsm(stock, [defs.state("new", ["true"])]), "needs both argv and next"),
                                 ("partly, no base", defs.fsm("a", [defs.state("a", ["true"])]), "needs both argv and next"),
                                 ("drop with no base", defs.fsm("a", [defs.state("a", ["true"], "a")], drop=["a"]), "drop= only"),
                                 ("no base (eca)", defs.fsm(None, []), "has fsm None")):
            with self.subTest(why=why):
                self.assertIn(line, value["bad"])

    def test_hook_groups_and_tools_of_a_base(self):
        """two marked hook groups with one name and different entries = SpecBad (tightens the third cut's "a later one wins" for that
        case only; aos-inherit-1119/06 (c) 4); a plain dict you write still wins."""
        eca, stock = defs.std.hooks("eca-claude"), defs.std.hooks()
        both = sorted(n for n in set(eca) & set(stock) if eca[n] != stock[n])       # today: brain_notify, context_wrap
        self.assertTrue(both)
        hooks = lambda h: agent(hooks=h).dry_run()["hookeds.json"]  # noqa: E731
        self.assertRaisesRegex(defs.SpecBad, "hook %s comes from both std.hooks\\('agent-fsm'\\) and std.hooks\\('eca-claude'\\)"
                               % both[0], hooks, [stock, eca])
        mine = {n: stock[n] for n in both}
        self.assertEqual(hooks([stock, eca, mine])[both[0]], stock[both[0]])        # written after them: picked
        self.assertRaises(defs.SpecBad, hooks, [stock, mine, eca])                              # written between: not picked
        self.assertEqual(hooks([defs.std.hooks(), defs.std.hooks()])["description"].count("templates/agent-fsm/hookeds.json"), 1)
        h = defs.std.hooks()["timer"]
        h["every_ms"] = 1
        self.assertNotEqual(defs.std.hooks()["timer"]["every_ms"], 1)
        base = defs.load(str(self.agent("base", BASE.replace("    hooks=std.hooks(),\n", ""))))
        self.assertNotIn("hookeds.json", agent(hooks=base.hooks).dry_run())   # base had no hooks: none
        self.assertEqual(sorted(agent(tools=[base.pack(prefix="r_", exclude=["grep"])]).dry_run()["tools.json"]["tools"]),
                         sorted("r_" + n for n in base.tools["tools"] if n != "grep"))
        self.assertIn("the base has no tool cat", base.pack(rename={"cat": "x"})["bad"])
        self.assertRaisesRegex(defs.SpecBad, "listed twice", agent(tools=[base.tools, base.tools]).dry_run)


class Reviewer(unittest.TestCase):
    """templates/reviewer written as one agent.py gives the same definition as the hand-written files (third cut's check)."""

    def test_same_as_the_template(self):
        with tempfile.TemporaryDirectory(prefix="agent-spec-") as tmp:
            dest = Path(tmp) / "reviewer"
            dest.mkdir()
            shutil.copy(TEMPLATES / "reviewer" / "system.txt", dest / "system.hand.txt")
            (dest / "agent.py").write_text(HEAD + REVIEWER)
            r = run_agent(dest / "agent.py", "--compile", home=fake_home(tmp))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(os.readlink(dest / "system.txt"), "system.hand.txt")     # cut 4: a link to the file kept by hand
            made = snapshot(dest)
        want = snapshot(TEMPLATES / "reviewer")
        self.assertEqual(sorted(made), sorted(list(want) + ["agent.py", "system.hand.txt"]))
        self.assertEqual(made["system.txt"], want["system.txt"])
        for name in sorted(want):
            if name in ("README.md", "system.txt"):
                continue
            with self.subTest(name=name):
                self.assertEqual(plain(json.loads(made[name])), plain(json.loads(want[name])))
        self.assertEqual(json.loads(made["ladder.json"]), json.loads(want["ladder.json"]))


if __name__ == "__main__":
    unittest.main()
