"""Test py/aos/agent_spec.py and the templates/agent-python skeleton: declarations to definition files, SpecBad before any write, overwrite rules (C and .o), HOOKS / FILES / no-FSM (eca) mode, templates/reviewer rewritten as one agent.py, and the skeleton's committed files matching its agent.py."""
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
LIB = Path(__file__).resolve().parents[1]
PROTO = LIB.parent
SKEL = PROTO / "templates" / "agent-python"
sys.path.insert(0, str(LIB))
from aos import agent_spec as ag  # noqa: E402

HEAD = "import sys\nsys.path.insert(0, %r)\nfrom aos import agent_spec as ag\n" % str(LIB)
BODY = '''\
DESCRIPTION = "Answer questions about the weather."
SYSTEM = "You answer questions about the weather.\\n"
TOOLS = [ag.pack("look"), ag.tool("peek", ag.home("/lib/tools/base/peek_now_time")), ag.no("grep")]
LLM = {"model": "luna"}
FSM = ag.stock_fsm()
ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM)
'''
GENERATED = ["_entry", "_metainfo.json", "body.json", "fsm.json", "interfaces.json", "llm.json", "loop.json", "system.txt", "tools.json"]
TEMPLATES = PROTO / "templates"
# templates/reviewer written as one agent.py (design 04, third cut's check): compared with the hand-written files, the template is not changed
REVIEWER = '''\
DESCRIPTION = "Review measured definition costs and prescribe a fix or split when model downgrades fail."
META = {"cost": {"time_ms": 60000}, "resource": ["llm"]}
SYSTEM = ag.by_hand("system.txt")

def lib(name):
    return ag.tool(name.rsplit("/", 1)[-1], ag.home("/lib/tools/" + name))

TOOLS = [lib("aos/" + n) for n in ("review_round", "watch", "promote", "rollback", "measure")] \\
      + [lib("base/" + n) for n in ("json_get", "json_ls", "json_set", "json_del", "read", "ls")]
LLM = {}

def cell(name):
    return ["python3", ag.home("/templates/agent-fsm/%s.py" % name)]

FSM = ag.fsm("idle", [
    ag.state("idle",  cell("idle"),  {0: "think", 10: "idle"}),
    ag.state("think", cell("brain"), {0: "wait", 10: "idle"}),
    ag.state("wait",  cell("wait"),  {0: "act", 10: "wait", 11: "think"}),
    ag.state("act",   cell("act"),   {0: "think", 10: "idle"}, timeout_ms=0),
])
INTERFACES = {"aos-observed": {"file": "observed.jsonl"}, "aos-agent": {"history": None}}
FILES = {"ladder.json": {
    "description": "Configure model downgrade trials, quality gates, and post-promotion watching.",
    "ladder": ["sol", "terra", "luna", "local"], "repeat": 3, "min_score": 0.9,
    "watch": {"window": 3, "tolerance": 0.1, "metric": "/token/in", "baseline_cases": 3},
    "promote_by": "self", "max_prompt_tokens_median": 10000, "retire_after_cases": 3,
}}
ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM, meta=META, interfaces=INTERFACES, files=FILES)
'''
# an eca definition copied from its template: agent.py has no FSM and fills only the content files
ECA = '''\
DESCRIPTION = %(summary)r
META = {"cost": {"time_ms": 60000}, "resource": ["llm"]}
SYSTEM = "You are the docs team's writer.\\n"
TOOLS = [ag.pack(p) for p in ("gadgets", "events", "self", "def", "mailbox", "json", "jsonx", "index")] + [ag.no("do_task")]
LLM = %(llm)r
HOOKS = ag.stock_hooks(%(template)r)
ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, meta=META, hooks=HOOKS)
'''


def snapshot(folder):
    return {p.name: p.read_bytes() for p in sorted(Path(folder).iterdir()) if p.is_file()}


def tree(folder):
    """every file under folder (relative path -> bytes)."""
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(Path(folder).rglob("*")) if p.is_file()}


def plain(value):
    """a definition file without its top-level description (the generated sentences differ from the hand-written ones)."""
    return {k: v for k, v in value.items() if k != "description"} if isinstance(value, dict) else value


def fake_home(tmp):
    """AOS_HOME for tests: lib = the py/ source (aos/, packs/), templates = the repo's templates."""
    home = Path(tmp) / "home"
    home.mkdir()
    (home / "lib").symlink_to(LIB)
    (home / "templates").symlink_to(TEMPLATES)
    return home


def env_with(home):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}
    if home:
        env["AOS_HOME"] = str(home)
    return env


def run_agent(script, *argv, home=None):
    return subprocess.run([sys.executable, str(script), *argv], text=True, capture_output=True, timeout=30, env=env_with(home))


class Declaration(unittest.TestCase):
    def test_stock_shape(self):
        files = ag.defs("Do it.", "sys\n", [ag.pack("look"), ag.tool("x", "tools/x", env={"A": "1"}), ag.no("grep")],
                        {"model": "m"}, ag.stock_fsm())
        self.assertEqual(list(files), ["_entry", "body.json", "loop.json", "fsm.json", "interfaces.json", "tools.json",
                                       "llm.json", "system.txt", "_metainfo.json", "README.md"])
        self.assertEqual(files["_entry"]["argv"], ["aos-agent", "ctl", "add", {"$env": "AOS_CD"}])
        self.assertEqual(files["fsm.json"]["start"], "idle")
        self.assertEqual(list(files["fsm.json"]["states"]), ["idle", "think", "wait", "act"])
        self.assertEqual(files["fsm.json"]["states"]["act"]["exec"]["timeout_ms"], 0)
        self.assertEqual(files["fsm.json"]["states"]["wait"]["exec"]["argv"][1],
                         {"$env": "AOS_HOME", "$path": "/templates/agent-fsm/wait.py"})
        self.assertEqual(files["tools.json"]["$override"], [{"$env": "AOS_HOME", "$path": "/lib/packs/look.json"}])
        self.assertEqual(files["tools.json"]["tools"], {"x": {"path": "tools/x", "env": {"A": "1"}}, "grep": None})
        self.assertEqual(files["llm.json"]["model"], "m")
        self.assertEqual(files["_metainfo.json"], {"summary": "Do it."})
        self.assertEqual(files["README.md"], "Do it.\n")

    def test_by_hand_meta_and_interfaces(self):
        files = ag.defs("D.", ag.by_hand("prompt.txt"), [], {}, ag.stock_fsm(), meta={"cost": {"time_ms": 1}},
                        interfaces={"aos-observed": {"file": "observed.jsonl"}, "aos-agent": {"history": None}})
        self.assertNotIn("system.txt", files)
        self.assertEqual(files["interfaces.json"]["aos-agent"]["system"], "prompt.txt")
        self.assertNotIn("history", files["interfaces.json"]["aos-agent"])
        self.assertEqual(files["interfaces.json"]["aos-observed"], {"file": "observed.jsonl"})
        self.assertEqual(files["tools.json"], {"description": ag.WHAT["tools.json"], "tools": {}})
        self.assertEqual(files["_metainfo.json"], {"summary": "D.", "cost": {"time_ms": 1}})

    def test_own_fsm(self):
        f = ag.fsm("a", [ag.state("a", ["python3", "a.py"], {0: "b", "*": "a"}), ag.state("b", ["true"], "a")])
        files = ag.defs("D.", "", [], {}, f)
        self.assertEqual(files["fsm.json"]["states"]["a"]["next"], {"0": "b", "*": "a"})
        self.assertEqual(files["fsm.json"]["states"]["b"]["next"], "a")

    def test_spec_bad(self):
        fine = dict(description="D.", system="", tools=[], llm={}, fsm=ag.stock_fsm())
        cases = {"empty description": dict(description=" "),
                 "next not in table": dict(fsm=ag.fsm("a", [ag.state("a", ["x"], {0: "nowhere"})])),
                 "start not in table": dict(fsm=ag.fsm("z", [ag.state("a", ["x"], {0: "a"})])),
                 "no 0 or *": dict(fsm=ag.fsm("a", [ag.state("a", ["x"], {1: "a"})])),
                 "code out of range": dict(fsm=ag.fsm("a", [ag.state("a", ["x"], {0: "a", 256: "a"})])),
                 "state twice": dict(fsm=ag.fsm("a", [ag.state("a", ["x"], "a"), ag.state("a", ["y"], "a")])),
                 "empty argv": dict(fsm=ag.fsm("a", [ag.state("a", [], "a")])),
                 "tool without path": dict(tools=[ag.tool("x", None)]),
                 "tool twice": dict(tools=[ag.tool("x", "a"), ag.no("x")]),
                 "pack twice": dict(tools=[ag.pack("look"), ag.pack("look")]),
                 "bad pack name": dict(tools=[ag.pack("../x")]),
                 "not a tool item": dict(tools=["look"]),
                 "model not a string": dict(llm={"model": 3}),
                 "llm key not in llm_keys": dict(llm={"temp": 1}),
                 "system not a string": dict(system=3),
                 "no FSM and no folder": dict(fsm=None),
                 "INTERFACES without FSM": dict(fsm=None, interfaces={"x": 1}),
                 "FSM not from ag.fsm": dict(fsm={"start": "a"}),
                 "hook bad event": dict(hooks={"h": {"event": "on_lunch", "handler": "x"}}),
                 "hook without handler": dict(hooks={"h": {"event": "after_tool"}}),
                 "hook bad name": dict(hooks={".h": {"event": "after_tool", "handler": "x"}}),
                 "hook clock key on other event": dict(hooks={"h": {"event": "after_tool", "handler": "x", "every_ms": 5}}),
                 "HOOKS not a table": dict(hooks="hooks.json"),
                 "HOOKS list item not a table": dict(hooks=[{"h": None}, 3]),
                 "HOOKS holds a tool": dict(hooks=[ag.pack("look")]),
                 "stock_hooks bad name": dict(hooks=ag.stock_hooks("../x")),
                 "interfaces sets hooks": dict(hooks={}, interfaces={"aos-agent": {"hooks": "h.json"}}),
                 "by_hand hooks clashes": dict(hooks=ag.by_hand("loop.json")),
                 "FILES not a dict": dict(files=["ladder.json"]),
                 "FILES takes a declared file": dict(files={"tools.json": {}}),
                 "FILES takes the skeleton": dict(files={"loop.json": {}}),
                 "FILES takes a runtime file": dict(files={"state.json": {}}),
                 "FILES takes agent.py": dict(files={"agent.py": "x"}),
                 "FILES takes a by_hand file": dict(system=ag.by_hand("prompt.txt"), files={"prompt.txt": "x"}),
                 "FILES in a sub folder": dict(files={"sub/x.json": {}}),
                 "FILES hidden": dict(files={".x.json": {}}),
                 "FILES content a number": dict(files={"x.json": 3}),
                 "meta sets summary": dict(meta={"summary": "x"}),
                 "meta sets lineage": dict(meta={"lineage": {}}),
                 "interfaces sets tools": dict(interfaces={"aos-agent": {"tools": "t.json"}}),
                 "by_hand clashes": dict(system=ag.by_hand("tools.json")),
                 "by_hand outside": dict(system=ag.by_hand("../x.txt")),
                 "by_hand ./ clashes": dict(system=ag.by_hand("./tools.json")),
                 "by_hand runtime file": dict(system=ag.by_hand("history.jsonl")),
                 "no without a pack": dict(tools=[ag.tool("a", "x"), ag.no("b")]),
                 "tool env not strings": dict(tools=[ag.tool("x", "a", env={"A": 1})]),
                 "tool env not a dict": dict(tools=[ag.tool("x", "a", env="A")]),
                 "tool cache true": dict(tools=[ag.tool("x", "a", cache=True)]),
                 "tool bad name": dict(tools=[ag.tool("my tool", "a")]),
                 "directive path not a string": dict(tools=[ag.tool("x", ag.home(None))]),
                 "interfaces removes aos-agent": dict(interfaces={"aos-agent": None}),
                 "not JSON": dict(meta={"tags": {1, 2}}),
                 "NaN": dict(meta={"x": float("nan")})}
        for why, change in cases.items():
            with self.subTest(why=why):
                self.assertRaises(ag.SpecBad, ag.defs, **dict(fine, **change))

    def test_hooks_and_files(self):
        with tempfile.TemporaryDirectory(prefix="agent-spec-") as tmp, \
                unittest.mock.patch.dict(os.environ, {"AOS_HOME": str(fake_home(tmp))}):
            mine = {"event": "before_tool", "condition": "shell", "handler": ag.home("/lib/tools/agent/hook_noop")}
            files = ag.defs("D.", "", [], {}, ag.stock_fsm(), hooks=[ag.stock_hooks(), {"timer": None, "mine": mine}],
                            files={"ladder.json": {"repeat": 3}, "notes.txt": "plain text\n"})
            stock = json.loads((TEMPLATES / "agent-fsm" / "hooks.json").read_text())["hooks"]
        self.assertEqual(list(files), ["_entry", "body.json", "loop.json", "fsm.json", "interfaces.json", "tools.json",
                                       "llm.json", "system.txt", "hooks.json", "ladder.json", "notes.txt", "_metainfo.json",
                                       "README.md"])
        table = dict(stock)
        del table["timer"]
        table["mine"] = mine
        self.assertEqual(files["hooks.json"]["hooks"], table)
        self.assertIn("templates/agent-fsm/hooks.json", files["hooks.json"]["description"])
        self.assertEqual(list(files["interfaces.json"]["aos-agent"]),
                         ["entry", "tools", "llm", "llm_keys", "history", "hooks", "system"])
        self.assertEqual(files["interfaces.json"]["aos-agent"]["hooks"], "hooks.json")
        fire = {"$env": "AOS_HOME", "$path": "/lib/tools/agent/hook_fire/_entry"}
        self.assertEqual(files["loop.json"]["on_start"], {"argv": [fire, "after_start", {"$env": "AOS_CD"}]})
        self.assertEqual(files["loop.json"]["on_stop"], {"argv": [fire, "after_stop", {"$env": "AOS_CD"}]})
        self.assertEqual(files["ladder.json"], {"repeat": 3})
        self.assertEqual(files["notes.txt"], "plain text\n")

    def test_hooks_loop_matches_agent_fsm_template(self):
        """with HOOKS, loop.json is the agent-fsm template's loop.json (apart from its description)."""
        files = ag.defs("D.", "", [], {}, ag.stock_fsm(), hooks={})
        loop = json.loads((TEMPLATES / "agent-fsm" / "loop.json").read_text())
        self.assertEqual(plain(files["loop.json"]), plain(loop))
        self.assertEqual(files["hooks.json"]["hooks"], {})

    def test_no_hooks_no_hooks_key(self):
        files = ag.defs("D.", "", [], {}, ag.stock_fsm())
        self.assertNotIn("hooks", files["interfaces.json"]["aos-agent"])
        self.assertNotIn("on_start", files["loop.json"])
        self.assertNotIn("hooks.json", files)

    def test_by_hand_hooks(self):
        files = ag.defs("D.", "", [], {}, ag.stock_fsm(), hooks=ag.by_hand("my_hooks.json"))
        self.assertNotIn("my_hooks.json", files)
        self.assertEqual(files["interfaces.json"]["aos-agent"]["hooks"], "my_hooks.json")
        self.assertIn("on_start", files["loop.json"])

    def test_stock_hooks_needs_a_home_with_the_template(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AOS_HOME", None)
            self.assertIn("AOS_HOME is not set", ag.stock_hooks()["bad"])
        with tempfile.TemporaryDirectory(prefix="agent-spec-") as tmp, \
                unittest.mock.patch.dict(os.environ, {"AOS_HOME": str(fake_home(tmp))}):
            bad = ag.stock_hooks("reviewer")
            self.assertIn("templates with hooks: ", bad["bad"])
            self.assertIn("agent-fsm", bad["bad"])
            self.assertRaises(ag.SpecBad, ag.defs, "D.", "", [], {}, ag.stock_fsm(), hooks=bad)


class Script(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-spec-")
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name) / "weather"
        self.dir.mkdir()
        self.write(BODY)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_")}

    def write(self, body):
        (self.dir / "agent.py").write_text(HEAD + body)

    def call(self, *argv, script=None):
        return subprocess.run([sys.executable, str(script or self.dir / "agent.py"), *argv], text=True,
                              capture_output=True, timeout=30, env=self.env)

    def test_write_twice_is_identical_and_has_no_machine_facts(self):
        r = self.call("--write-defs")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), sorted(GENERATED + ["README.md", "agent.py"]))
        first = snapshot(self.dir)
        r = self.call("--write-defs")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(snapshot(self.dir), first)
        for name, data in first.items():
            if name == "agent.py":
                continue
            text = data.decode()
            for fact in (self.temp.name, str(PROTO), socket.gethostname(), os.environ.get("USER", "\0")):
                self.assertNotIn(fact, text, name)

    def test_defs_prints_what_write_writes(self):
        printed = json.loads(self.call("--defs").stdout)
        self.assertEqual(os.listdir(self.dir), ["agent.py"])
        self.call("--write-defs")
        for name, value in printed.items():
            text = (self.dir / name).read_text()
            self.assertEqual(text, value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def test_spec_bad_is_one_line_and_writes_nothing(self):
        self.assertEqual(self.call("--write-defs").returncode, 0)
        (self.dir / "tools.json").write_text("{}\n")      # a hand change that must survive a failed run
        before = snapshot(self.dir)
        del before["agent.py"]
        cases = {"next state not in the table":
                     ('FSM = ag.stock_fsm()', 'FSM = ag.fsm("idle", [ag.state("idle", ["true"], {0: "thnik"})])',
                      "SpecBad state idle: next state 'thnik' is not one of the states (idle)"),
                 "tool without a path":
                     ('ag.tool("peek", ag.home("/lib/tools/base/peek_now_time"))', 'ag.tool("peek", "")',
                      "SpecBad tool peek must have a path"),
                 "model not a string":
                     ('{"model": "luna"}', '{"model": 7}', "SpecBad LLM model must be a non-empty string")}
        for why, (old, new, line) in cases.items():
            with self.subTest(why=why):
                self.assertIn(old, BODY)
                self.write(BODY.replace(old, new))
                for flag in ("--write-defs", "--defs"):
                    r = self.call(flag)
                    self.assertEqual(r.returncode, 1)
                    self.assertEqual(r.stdout, "")
                    self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
                    self.assertTrue(r.stderr.startswith("weather: error: " + line), r.stderr)
                    self.assertTrue(r.stderr.rstrip().endswith("(fix the declaration in agent.py)"), r.stderr)
                after = snapshot(self.dir)
                del after["agent.py"]
                self.assertEqual(after, before)

    def test_overwrite_rules(self):
        self.assertEqual(self.call("--write-defs").returncode, 0)
        made = snapshot(self.dir)
        (self.dir / "tools.json").write_text('{"tools": {"hand": {"path": "x"}}}\n')     # hand change: overwritten, no word
        meta = json.loads((self.dir / "_metainfo.json").read_text())
        meta["lineage"] = {"template": "agent-python"}                                   # someone else's key: kept
        (self.dir / "_metainfo.json").write_text(json.dumps(meta, indent=2) + "\n")
        (self.dir / "README.md").write_text("My own readme.\n")                          # already there: not touched
        (self.dir / "notes.txt").write_text("mine\n")                                    # not declared: not touched
        r = self.call("--write-defs")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        self.assertEqual((self.dir / "tools.json").read_bytes(), made["tools.json"])
        self.assertEqual(json.loads((self.dir / "_metainfo.json").read_text()),
                         {"summary": "Answer questions about the weather.", "lineage": {"template": "agent-python"}})
        self.assertEqual((self.dir / "README.md").read_text(), "My own readme.\n")
        self.assertEqual((self.dir / "notes.txt").read_text(), "mine\n")
        self.assertIn("kept", r.stdout)

    def test_by_hand_file_is_not_touched(self):
        self.write(BODY.replace('SYSTEM = "You answer questions about the weather.\\n"', 'SYSTEM = ag.by_hand("system.txt")'))
        (self.dir / "system.txt").write_text("Written by hand.\n")
        r = self.call("--write-defs")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.dir / "system.txt").read_text(), "Written by hand.\n")
        self.assertEqual(json.loads((self.dir / "interfaces.json").read_text())["aos-agent"]["system"], "system.txt")

    def test_broken_metainfo_is_def_bad_and_writes_nothing(self):
        (self.dir / "_metainfo.json").write_text("not json")
        r = self.call("--write-defs")
        self.assertEqual(r.returncode, 1)
        self.assertIn("weather: error: DefBad", r.stderr)
        self.assertEqual(sorted(os.listdir(self.dir)), ["_metainfo.json", "agent.py"])

    def test_usage(self):
        r = self.call()
        self.assertEqual(r.returncode, 1)
        self.assertIn("weather: error: ArgumentsBad", r.stderr)
        self.assertIn("usage: python3 agent.py --write-defs [FOLDER]", r.stderr)
        self.assertEqual(self.call("--nope").returncode, 1)
        r = self.call("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("--write-defs [FOLDER]", r.stdout)

    def test_write_into_another_folder(self):
        other = Path(self.temp.name) / "other"
        other.mkdir()
        r = self.call("--write-defs", str(other))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.listdir(self.dir), ["agent.py"])
        self.assertIn("fsm.json", os.listdir(other))


class NoFsm(unittest.TestCase):
    """no FSM (eca bodies): agent.py fills the content files of a definition copied from a template, under the names its interfaces.json gives."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-spec-")
        self.addCleanup(self.temp.cleanup)
        self.home = fake_home(self.temp.name)

    def copy(self, template):
        dest = Path(self.temp.name) / template
        shutil.copytree(TEMPLATES / template, dest, symlinks=True)
        return dest

    def test_eca_templates(self):
        for template, llm in (("eca-claude", {"model": "sonnet"}), ("eca-pi", {})):
            with self.subTest(template=template):
                dest = self.copy(template)
                meta = json.loads((dest / "_metainfo.json").read_text())
                (dest / "agent.py").write_text(HEAD + ECA % {"summary": meta["summary"], "llm": llm, "template": template})
                before = tree(dest)
                r = run_agent(dest / "agent.py", "--write-defs", home=self.home)
                self.assertEqual(r.returncode, 0, r.stderr)
                after = tree(dest)
                written = {"tools.json", "llm.json", "system.txt", "hooks.json", "_metainfo.json"}
                for name in set(before) | set(after):          # the skeleton, cli.json, screen/, README.md: not touched
                    if name not in written:
                        self.assertEqual(after.get(name), before.get(name), name)
                load = lambda name, files: json.loads(files[name])  # noqa: E731
                self.assertEqual(plain(load("tools.json", after)), plain(load("tools.json", before)))
                self.assertEqual(plain(load("llm.json", after)), plain(load("llm.json", before)))
                self.assertEqual(load("hooks.json", after)["hooks"], load("hooks.json", before)["hooks"])
                self.assertEqual(load("_metainfo.json", after), load("_metainfo.json", before))
                self.assertEqual(after["system.txt"], b"You are the docs team's writer.\n")
                printed = json.loads(run_agent(dest / "agent.py", "--defs", home=self.home).stdout)
                self.assertEqual(sorted(printed), sorted(written | {"README.md"}))

    def test_no_skeleton_is_def_bad_and_writes_nothing(self):
        dest = Path(self.temp.name) / "empty"
        dest.mkdir()
        (dest / "agent.py").write_text(HEAD + ECA % {"summary": "S.", "llm": {}, "template": "eca-pi"})
        for flag in ("--write-defs", "--defs"):
            r = run_agent(dest / "agent.py", flag, home=self.home)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
            self.assertIn("empty: error: DefBad", r.stderr)
            self.assertIn("has no interfaces.json", r.stderr)
        self.assertEqual(os.listdir(dest), ["agent.py"])

    def test_interfaces_without_a_hooks_file_is_def_bad(self):
        dest = self.copy("eca-pi")
        face = json.loads((dest / "interfaces.json").read_text())
        del face["aos-agent"]["hooks"]
        (dest / "interfaces.json").write_text(json.dumps(face))
        (dest / "agent.py").write_text(HEAD + ECA % {"summary": "S.", "llm": {}, "template": "eca-pi"})
        before = tree(dest)
        r = run_agent(dest / "agent.py", "--write-defs", home=self.home)
        self.assertEqual(r.returncode, 1)
        self.assertIn("DefBad", r.stderr)
        self.assertIn("declares no hooks file", r.stderr)
        self.assertEqual(tree(dest), before)

    def test_names_come_from_interfaces(self):
        dest = self.copy("eca-pi")
        face = json.loads((dest / "interfaces.json").read_text())
        face["aos-agent"]["system"] = "prompt.md"
        (dest / "interfaces.json").write_text(json.dumps(face))
        files = ag.defs("S.", "Hi.\n", [], {"model": "m"}, folder=str(dest))
        self.assertEqual(sorted(files), ["README.md", "_metainfo.json", "llm.json", "prompt.md", "tools.json"])
        self.assertRaises(ag.SpecBad, ag.defs, "S.", "", [], {"temperature": 1}, folder=str(dest))   # eca's llm_keys: model only
        self.assertRaises(ag.SpecBad, ag.defs, "S.", ag.by_hand("system.txt"), [], {}, folder=str(dest))
        self.assertNotIn("prompt.md", ag.defs("S.", ag.by_hand("prompt.md"), [], {}, folder=str(dest)))
        # FILES may write a file the skeleton does not declare (cli.json); not one interfaces.json declares, nor a skeleton name
        self.assertEqual(ag.defs("S.", "", [], {}, folder=str(dest), files={"cli.json": {"a": 1}})["cli.json"], {"a": 1})
        self.assertRaises(ag.SpecBad, ag.defs, "S.", "", [], {}, folder=str(dest), files={"prompt.md": "x"})
        self.assertRaises(ag.SpecBad, ag.defs, "S.", "", [], {}, folder=str(dest), files={"loop.json": {}})


class Reviewer(unittest.TestCase):
    """templates/reviewer written as one agent.py gives the same definition as the hand-written files (third cut's check)."""

    def test_same_as_the_template(self):
        with tempfile.TemporaryDirectory(prefix="agent-spec-") as tmp:
            dest = Path(tmp) / "reviewer"
            dest.mkdir()
            shutil.copy(TEMPLATES / "reviewer" / "system.txt", dest)
            (dest / "agent.py").write_text(HEAD + REVIEWER)
            r = run_agent(dest / "agent.py", "--write-defs", home=fake_home(tmp))
            self.assertEqual(r.returncode, 0, r.stderr)
            made = snapshot(dest)
        want = snapshot(TEMPLATES / "reviewer")
        self.assertEqual(sorted(made), sorted(list(want) + ["agent.py"]))
        self.assertEqual(made["system.txt"], want["system.txt"])
        for name in sorted(want):
            if name in ("README.md", "system.txt"):
                continue
            with self.subTest(name=name):
                self.assertEqual(plain(json.loads(made[name])), plain(json.loads(want[name])))
        self.assertEqual(json.loads(made["ladder.json"]), json.loads(want["ladder.json"]))


class Skeleton(unittest.TestCase):
    """templates/agent-python: the committed files are exactly what its agent.py writes today."""

    def test_files(self):
        self.assertEqual(sorted(p.name for p in SKEL.iterdir()), sorted(GENERATED + ["README.md", "agent.py"]))

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
            r = subprocess.run([sys.executable, str(dest / "agent.py"), "--write-defs"], capture_output=True, text=True,
                               timeout=30, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            for name in GENERATED:
                with self.subTest(name=name):
                    self.assertEqual((dest / name).read_bytes(), (SKEL / name).read_bytes(),
                                     "run python3 agent.py --write-defs in templates/agent-python")


if __name__ == "__main__":
    unittest.main()
