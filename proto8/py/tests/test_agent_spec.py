"""Test py/aos/agent_spec.py and the templates/agent-python skeleton: declarations to definition files, SpecBad before any write, overwrite rules (C and .o), HOOKS / FILES / no-FSM (eca) mode, libraries (std, defs.lib: packs copied in, other libraries prefixed, clashes SpecBad), packs linked statically or dynamically (--static / --dynamic, link=), templates/reviewer rewritten as one agent.py, and the skeleton's committed files matching its agent.py."""
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
from aos.py.agent import defs  # noqa: E402 （跟寫 agent.py 的人同一個名字；＝aos.agent_spec）

HEAD = "import sys\nsys.path.insert(0, %r)\nfrom aos.py.agent import defs\n" % str(LIB)
BODY = '''\
DESCRIPTION = "Answer questions about the weather."
SYSTEM = "You answer questions about the weather.\\n"
std = defs.std
TOOLS = [std.pack("look"), defs.tool("peek", defs.home("/lib/tools/base/peek_now_time")), defs.drop("grep")]
LLM = {"model": "luna"}
FSM = std.fsm()
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM)
'''
GENERATED = ["_entry", "_metainfo.json", "body.json", "fsm.json", "interfaces.json", "llm.json", "loop.json", "system.txt", "tools.json"]
SKEL_GENERATED = sorted(GENERATED + ["hooks.json"])   # the skeleton declares HOOKS = {} (user 11-19 "骨架帶一行空的 HOOKS")
TEMPLATES = PROTO / "templates"
# templates/reviewer written as one agent.py (design 04, third cut's check): compared with the hand-written files, the template is not changed
REVIEWER = '''\
DESCRIPTION = "Review measured definition costs and prescribe a fix or split when model downgrades fail."
META = {"cost": {"time_ms": 60000}, "resource": ["llm"]}
SYSTEM = defs.extern("system.txt")

std = defs.std
TOOLS = [std.tool("aos/" + n) for n in ("review_round", "watch", "promote", "rollback", "measure")] \\
      + [std.tool("base/" + n) for n in ("json_get", "json_ls", "json_set", "json_del", "read", "ls")]
LLM = {}

def cell(name):
    return ["python3", defs.home("/templates/agent-fsm/%s.py" % name)]

FSM = defs.fsm("idle", [
    defs.state("idle",  cell("idle"),  {0: "think", 10: "idle"}),
    defs.state("think", cell("brain"), {0: "wait", 10: "idle"}),
    defs.state("wait",  cell("wait"),  {0: "act", 10: "wait", 11: "think"}),
    defs.state("act",   cell("act"),   {0: "think", 10: "idle"}, timeout_ms=0),
])
INTERFACES = {"aos-observed": {"file": "observed.jsonl"}, "aos-agent": {"history": None}}
FILES = {"ladder.json": {
    "description": "Configure model downgrade trials, quality gates, and post-promotion watching.",
    "ladder": ["sol", "terra", "luna", "local"], "repeat": 3, "min_score": 0.9,
    "watch": {"window": 3, "tolerance": 0.1, "metric": "/token/in", "baseline_cases": 3},
    "promote_by": "self", "max_prompt_tokens_median": 10000, "retire_after_cases": 3,
}}
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM, meta=META, interfaces=INTERFACES, files=FILES)
'''
# an eca definition copied from its template: agent.py has no FSM and fills only the content files
ECA = '''\
DESCRIPTION = %(summary)r
META = {"cost": {"time_ms": 60000}, "resource": ["llm"]}
SYSTEM = "You are the docs team's writer.\\n"
TOOLS = [defs.std.pack(p) for p in ("gadgets", "events", "self", "def", "mailbox", "json", "jsonx", "index")] + [defs.drop("do_task")]
LLM = %(llm)r
HOOKS = defs.std.hooks(%(template)r)
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, meta=META, hooks=HOOKS)
'''


def snapshot(folder):
    return {p.name: p.read_bytes() for p in sorted(Path(folder).iterdir()) if p.is_file()}


def tree(folder):
    """every file under folder (relative path -> bytes)."""
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(Path(folder).rglob("*")) if p.is_file()}


def plain(value):
    """a definition file without its top-level description (the compiled sentences differ from the hand-written ones)."""
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


def resolve(value, home):
    """a {"$env": "AOS_HOME", "$path": ...} directive (or a plain path) -> the path on this machine."""
    return str(home) + value["$path"] if isinstance(value, dict) else value


def borrowed(tools_json, home):
    """the tools a hand-written tools.json gives after aos-tools stacks its $override packs (field by field, null = not a tool);
    the compiled tools.json must give the same table without $override."""
    acc = {}
    for base in tools_json.get("$override", []):
        for name, entry in json.loads(Path(resolve(base, home)).read_text())["tools"].items():
            acc[name] = entry
    for name, entry in tools_json.get("tools", {}).items():
        acc[name] = entry if entry is None or name not in acc or acc[name] is None else dict(acc[name], **entry)
    return {n: e for n, e in acc.items() if e is not None}


def look(*drop):
    """the tools of std.pack("look"), as agent.py copies them in."""
    tools = json.loads((LIB / "packs" / "look.json").read_text())["tools"]
    return {n: e for n, e in tools.items() if n not in drop}


class WithHome(unittest.TestCase):
    """AOS_HOME = a fake home (lib = py/, templates = the repo's), as std.pack / std.tool / std.hooks read it when agent.py runs."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-spec-")
        self.addCleanup(self.temp.cleanup)
        self.home = fake_home(self.temp.name)
        patch = unittest.mock.patch.dict(os.environ, {"AOS_HOME": str(self.home)})
        patch.start()
        self.addCleanup(patch.stop)


class Declaration(WithHome):
    def test_stock_shape(self):
        files = defs.compile("Do it.", "sys\n", [defs.std.pack("look"), defs.tool("x", "tools/x", env={"A": "1"}), defs.drop("grep")],
                        {"model": "m"}, defs.std.fsm())
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

    def test_extern_meta_and_interfaces(self):
        files = defs.compile("D.", defs.extern("prompt.txt"), [], {}, defs.std.fsm(), meta={"cost": {"time_ms": 1}},
                        interfaces={"aos-observed": {"file": "observed.jsonl"}, "aos-agent": {"history": None}})
        self.assertNotIn("system.txt", files)
        self.assertEqual(files["interfaces.json"]["aos-agent"]["system"], "prompt.txt")
        self.assertNotIn("history", files["interfaces.json"]["aos-agent"])
        self.assertEqual(files["interfaces.json"]["aos-observed"], {"file": "observed.jsonl"})
        self.assertEqual(files["tools.json"], {"description": defs.WHAT["tools.json"], "tools": {}})
        self.assertEqual(files["_metainfo.json"], {"summary": "D.", "cost": {"time_ms": 1}})

    def test_own_fsm(self):
        f = defs.fsm("a", [defs.state("a", ["python3", "a.py"], {0: "b", "*": "a"}), defs.state("b", ["true"], "a")])
        files = defs.compile("D.", "", [], {}, f)
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
                 "no FSM and no folder": dict(fsm=None),
                 "INTERFACES without FSM": dict(fsm=None, interfaces={"x": 1}),
                 "FSM not from defs.fsm": dict(fsm={"start": "a"}),
                 "hook bad event": dict(hooks={"h": {"event": "on_lunch", "handler": "x"}}),
                 "hook without handler": dict(hooks={"h": {"event": "after_tool"}}),
                 "hook bad name": dict(hooks={".h": {"event": "after_tool", "handler": "x"}}),
                 "hook clock key on other event": dict(hooks={"h": {"event": "after_tool", "handler": "x", "every_ms": 5}}),
                 "HOOKS not a table": dict(hooks="hooks.json"),
                 "HOOKS list item not a table": dict(hooks=[{"h": None}, 3]),
                 "HOOKS holds a tool": dict(hooks=[defs.std.pack("look")]),
                 "stock_hooks bad name": dict(hooks=defs.std.hooks("../x")),
                 "interfaces sets hooks": dict(hooks={}, interfaces={"aos-agent": {"hooks": "h.json"}}),
                 "extern hooks clashes": dict(hooks=defs.extern("loop.json")),
                 "FILES not a dict": dict(files=["ladder.json"]),
                 "FILES takes a declared file": dict(files={"tools.json": {}}),
                 "FILES takes the skeleton": dict(files={"loop.json": {}}),
                 "FILES takes a runtime file": dict(files={"state.json": {}}),
                 "FILES takes agent.py": dict(files={"agent.py": "x"}),
                 "FILES takes an extern file": dict(system=defs.extern("prompt.txt"), files={"prompt.txt": "x"}),
                 "FILES in a sub folder": dict(files={"sub/x.json": {}}),
                 "FILES hidden": dict(files={".x.json": {}}),
                 "FILES content a number": dict(files={"x.json": 3}),
                 "meta sets summary": dict(meta={"summary": "x"}),
                 "meta sets lineage": dict(meta={"lineage": {}}),
                 "interfaces sets tools": dict(interfaces={"aos-agent": {"tools": "t.json"}}),
                 "extern clashes": dict(system=defs.extern("tools.json")),
                 "extern outside": dict(system=defs.extern("../x.txt")),
                 "extern ./ clashes": dict(system=defs.extern("./tools.json")),
                 "extern runtime file": dict(system=defs.extern("history.jsonl")),
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
                self.assertRaises(defs.SpecBad, defs.compile, **dict(fine, **change))

    def test_holes_from_argon_review(self):
        """geng-patch-1119 (thinking/2026-11/19/aos-compile-庚/12, class 1): META keys, extern("agent.py"), the entry message."""
        fine = dict(description="D.", system="", tools=[], llm={}, fsm=defs.std.fsm())
        with self.assertRaisesRegex(defs.SpecBad, "META keys must be strings"):                  # ① was TypeError
            defs.compile(**dict(fine, meta={1: "a"}))
        for what in ("system", "fsm", "tools", "llm", "hooks"):                                 # ② agent.py is not an extern file
            with self.subTest(what=what), self.assertRaisesRegex(defs.SpecBad, r"extern\('agent.py'\)"):
                defs.compile(**dict(fine, **{what: defs.extern("agent.py")}))
        with self.assertRaises(defs.SpecBad) as e:                                                # ⑥ entry cannot take extern
            defs.compile(**dict(fine, interfaces={"aos-agent": {"entry": "x.json"}}))
        self.assertIn("entry is body.json", str(e.exception))
        self.assertNotIn("extern", str(e.exception))
        with self.assertRaisesRegex(defs.SpecBad, r"use defs.extern"):
            defs.compile(**dict(fine, interfaces={"aos-agent": {"llm": "x.json"}}))

    def test_rename_order_and_cleanup(self):
        """geng-patch-1119 ③ files pointed at are renamed before the index files; ④ one failed unlink does not stop the cleanup."""
        out = defs.compile("D.", "", [], {}, defs.std.fsm())
        with tempfile.TemporaryDirectory(prefix="agent-spec-") as d:
            order, replace = [], os.replace
            with unittest.mock.patch("os.replace", lambda a, b: (order.append(os.path.basename(b)), replace(a, b))):
                defs.write(d, out)
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
                self.assertRaisesRegex(OSError, "replace fails", defs.write, d, out)
            self.assertEqual(len(calls), len(out))
            self.assertEqual([p for p in os.listdir(d) if ".tmp-" in p], [os.path.basename(calls[0])])

    def test_hooks_and_files(self):
        with tempfile.TemporaryDirectory(prefix="agent-spec-") as tmp, \
                unittest.mock.patch.dict(os.environ, {"AOS_HOME": str(fake_home(tmp))}):
            mine = {"event": "before_tool", "condition": "shell", "handler": defs.home("/lib/tools/agent/hook_noop")}
            files = defs.compile("D.", "", [], {}, defs.std.fsm(), hooks=[defs.std.hooks(), {"timer": None, "mine": mine}],
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
        files = defs.compile("D.", "", [], {}, defs.std.fsm(), hooks={})
        loop = json.loads((TEMPLATES / "agent-fsm" / "loop.json").read_text())
        self.assertEqual(plain(files["loop.json"]), plain(loop))
        self.assertEqual(files["hooks.json"]["hooks"], {})

    def test_no_hooks_no_hooks_key(self):
        files = defs.compile("D.", "", [], {}, defs.std.fsm())
        self.assertNotIn("hooks", files["interfaces.json"]["aos-agent"])
        self.assertNotIn("on_start", files["loop.json"])
        self.assertNotIn("hooks.json", files)

    def test_extern_hooks(self):
        files = defs.compile("D.", "", [], {}, defs.std.fsm(), hooks=defs.extern("my_hooks.json"))
        self.assertNotIn("my_hooks.json", files)
        self.assertEqual(files["interfaces.json"]["aos-agent"]["hooks"], "my_hooks.json")
        self.assertIn("on_start", files["loop.json"])

    def test_stock_hooks_needs_a_home_with_the_template(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AOS_HOME", None)
            self.assertIn("AOS_HOME is not set", defs.std.hooks()["bad"])
        with tempfile.TemporaryDirectory(prefix="agent-spec-") as tmp, \
                unittest.mock.patch.dict(os.environ, {"AOS_HOME": str(fake_home(tmp))}):
            bad = defs.std.hooks("reviewer")
            self.assertIn("templates with hooks: ", bad["bad"])
            self.assertIn("agent-fsm", bad["bad"])
            self.assertRaises(defs.SpecBad, defs.compile, "D.", "", [], {}, defs.std.fsm(), hooks=bad)


class Script(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agent-spec-")
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name) / "weather"
        self.dir.mkdir()
        self.write(BODY)
        self.env = env_with(fake_home(self.temp.name))

    def write(self, body):
        (self.dir / "agent.py").write_text(HEAD + body)

    def call(self, *argv, script=None):
        return subprocess.run([sys.executable, str(script or self.dir / "agent.py"), *argv], text=True,
                              capture_output=True, timeout=30, env=self.env)

    def test_write_twice_is_identical_and_has_no_machine_facts(self):
        r = self.call("--compile")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), sorted(GENERATED + ["README.md", "agent.py"]))
        first = snapshot(self.dir)
        r = self.call("--compile")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(snapshot(self.dir), first)
        for name, data in first.items():
            if name == "agent.py":
                continue
            text = data.decode()
            for fact in (self.temp.name, str(PROTO), socket.gethostname(), os.environ.get("USER", "\0")):
                self.assertNotIn(fact, text, name)

    def test_defs_prints_what_write_writes(self):
        printed = json.loads(self.call("--dry-run").stdout)
        self.assertEqual(os.listdir(self.dir), ["agent.py"])
        self.call("--compile")
        for name, value in printed.items():
            text = (self.dir / name).read_text()
            self.assertEqual(text, value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def test_spec_bad_is_one_line_and_writes_nothing(self):
        self.assertEqual(self.call("--compile").returncode, 0)
        (self.dir / "tools.json").write_text("{}\n")      # a hand change that must survive a failed run
        before = snapshot(self.dir)
        del before["agent.py"]
        cases = {"next state not in the table":
                     ('FSM = std.fsm()', 'FSM = defs.fsm("idle", [defs.state("idle", ["true"], {0: "thnik"})])',
                      "SpecBad state idle: next state 'thnik' is not one of the states (idle)"),
                 "tool without a path":
                     ('defs.tool("peek", defs.home("/lib/tools/base/peek_now_time"))', 'defs.tool("peek", "")',
                      "SpecBad tool peek must have a path"),
                 "model not a string":
                     ('{"model": "luna"}', '{"model": 7}', "SpecBad LLM model must be a non-empty string")}
        for why, (old, new, line) in cases.items():
            with self.subTest(why=why):
                self.assertIn(old, BODY)
                self.write(BODY.replace(old, new))
                for flag in ("--compile", "--dry-run"):
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
        self.assertEqual(self.call("--compile").returncode, 0)
        made = snapshot(self.dir)
        (self.dir / "tools.json").write_text('{"tools": {"hand": {"path": "x"}}}\n')     # hand change: overwritten, no word
        meta = json.loads((self.dir / "_metainfo.json").read_text())
        meta["lineage"] = {"template": "agent-python"}                                   # someone else's key: kept
        (self.dir / "_metainfo.json").write_text(json.dumps(meta, indent=2) + "\n")
        (self.dir / "README.md").write_text("My own readme.\n")                          # already there: not touched
        (self.dir / "notes.txt").write_text("mine\n")                                    # not declared: not touched
        r = self.call("--compile")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        self.assertEqual((self.dir / "tools.json").read_bytes(), made["tools.json"])
        self.assertEqual(json.loads((self.dir / "_metainfo.json").read_text()),
                         {"summary": "Answer questions about the weather.", "lineage": {"template": "agent-python"}})
        self.assertEqual((self.dir / "README.md").read_text(), "My own readme.\n")
        self.assertEqual((self.dir / "notes.txt").read_text(), "mine\n")
        self.assertIn("kept", r.stdout)

    def test_extern_file_is_not_touched(self):
        self.write(BODY.replace('SYSTEM = "You answer questions about the weather.\\n"', 'SYSTEM = defs.extern("system.txt")'))
        (self.dir / "system.txt").write_text("Written by hand.\n")
        r = self.call("--compile")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.dir / "system.txt").read_text(), "Written by hand.\n")
        self.assertEqual(json.loads((self.dir / "interfaces.json").read_text())["aos-agent"]["system"], "system.txt")

    def test_broken_metainfo_is_def_bad_and_writes_nothing(self):
        (self.dir / "_metainfo.json").write_text("not json")
        r = self.call("--compile")
        self.assertEqual(r.returncode, 1)
        self.assertIn("weather: error: DefBad", r.stderr)
        self.assertEqual(sorted(os.listdir(self.dir)), ["_metainfo.json", "agent.py"])

    def test_unreadable_metainfo_is_write_failed_and_writes_nothing(self):
        """geng-patch-1119 ⑤: cannot read _metainfo.json (here: it is a folder) = an I/O error, WriteFailed; not DefBad."""
        (self.dir / "_metainfo.json").mkdir()
        r = self.call("--compile")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertIn("weather: error: WriteFailed", r.stderr)
        self.assertEqual(sorted(os.listdir(self.dir)), ["_metainfo.json", "agent.py"])

    def test_usage(self):
        r = self.call()
        self.assertEqual(r.returncode, 1)
        self.assertIn("weather: error: ArgumentsBad", r.stderr)
        self.assertIn("usage: python3 agent.py --compile [--static | --dynamic] [FOLDER]", r.stderr)
        self.assertEqual(self.call("--nope").returncode, 1)
        r = self.call("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("--compile [FOLDER]", r.stdout)

    def test_write_into_another_folder(self):
        other = Path(self.temp.name) / "other"
        other.mkdir()
        r = self.call("--compile", str(other))
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
                r = run_agent(dest / "agent.py", "--compile", home=self.home)
                self.assertEqual(r.returncode, 0, r.stderr)
                after = tree(dest)
                written = {"tools.json", "llm.json", "system.txt", "hooks.json", "_metainfo.json"}
                for name in set(before) | set(after):          # the skeleton, cli.json, screen/, README.md: not touched
                    if name not in written:
                        self.assertEqual(after.get(name), before.get(name), name)
                load = lambda name, files: json.loads(files[name])  # noqa: E731
                self.assertNotIn("$override", load("tools.json", after))      # packs copied in: the same tools as the template's
                self.assertEqual(load("tools.json", after)["tools"], borrowed(load("tools.json", before), self.home))
                self.assertEqual(plain(load("llm.json", after)), plain(load("llm.json", before)))
                self.assertEqual(load("hooks.json", after)["hooks"], load("hooks.json", before)["hooks"])
                self.assertEqual(load("_metainfo.json", after), load("_metainfo.json", before))
                self.assertEqual(after["system.txt"], b"You are the docs team's writer.\n")
                printed = json.loads(run_agent(dest / "agent.py", "--dry-run", home=self.home).stdout)
                self.assertEqual(sorted(printed), sorted(written | {"README.md"}))

    def test_no_skeleton_is_def_bad_and_writes_nothing(self):
        dest = Path(self.temp.name) / "empty"
        dest.mkdir()
        (dest / "agent.py").write_text(HEAD + ECA % {"summary": "S.", "llm": {}, "template": "eca-pi"})
        for flag in ("--compile", "--dry-run"):
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
        r = run_agent(dest / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 1)
        self.assertIn("DefBad", r.stderr)
        self.assertIn("declares no hooks file", r.stderr)
        self.assertEqual(tree(dest), before)

    def test_names_come_from_interfaces(self):
        dest = self.copy("eca-pi")
        face = json.loads((dest / "interfaces.json").read_text())
        face["aos-agent"]["system"] = "prompt.md"
        (dest / "interfaces.json").write_text(json.dumps(face))
        files = defs.compile("S.", "Hi.\n", [], {"model": "m"}, folder=str(dest))
        self.assertEqual(sorted(files), ["README.md", "_metainfo.json", "llm.json", "prompt.md", "tools.json"])
        self.assertRaises(defs.SpecBad, defs.compile, "S.", "", [], {"temperature": 1}, folder=str(dest))   # eca's llm_keys: model only
        self.assertRaises(defs.SpecBad, defs.compile, "S.", defs.extern("system.txt"), [], {}, folder=str(dest))
        self.assertNotIn("prompt.md", defs.compile("S.", defs.extern("prompt.md"), [], {}, folder=str(dest)))
        # FILES may write a file the skeleton does not declare (cli.json); not one interfaces.json declares, nor a skeleton name
        self.assertEqual(defs.compile("S.", "", [], {}, folder=str(dest), files={"cli.json": {"a": 1}})["cli.json"], {"a": 1})
        self.assertRaises(defs.SpecBad, defs.compile, "S.", "", [], {}, folder=str(dest), files={"prompt.md": "x"})
        self.assertRaises(defs.SpecBad, defs.compile, "S.", "", [], {}, folder=str(dest), files={"loop.json": {}})


class Namespace(WithHome):
    """namespace first cut (aos-ns-cut1-1119): defs.std and defs.lib; packs copied in tool by tool; another library's tools get
    "<library>_"; two packs giving one name with different entries = SpecBad; a library root that cannot be read = SpecBad."""

    def make_lib(self, name="mylib", packs=None, tools=("read",)):
        root = Path(self.temp.name) / name
        for t in tools:
            (root / "tools" / t).mkdir(parents=True)
        (root / "packs").mkdir(parents=True)
        for pack, table in (packs or {"look": {"read": {"path": "../tools/read"}}}).items():
            (root / "packs" / (pack + ".json")).write_text(json.dumps(table if "tools" in table or "$override" in table
                                                                      else {"tools": table}))
        return root

    def tools(self, items):
        return defs.compile("D.", "", items, {}, defs.std.fsm())["tools.json"]["tools"]

    def test_two_reads_each_its_own(self):
        root = self.make_lib()
        my = defs.lib("my", str(root))
        got = self.tools([defs.std.pack("look"), my.pack("look")])
        self.assertEqual(got["read"], {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}})
        self.assertEqual(got["my_read"], {"path": str(root / "tools" / "read")})
        self.assertEqual(list(got), list(look()) + ["my_read"])
        with unittest.mock.patch.dict(os.environ, {"AOS_NS_TEST_WS": self.temp.name}):       # root as a directive: written as one
            got = self.tools([defs.lib("my", defs.env("AOS_NS_TEST_WS", "/mylib")).pack("look")])
        self.assertEqual(got, {"my_read": {"path": {"$env": "AOS_NS_TEST_WS", "$path": "/mylib/tools/read"}}})

    def test_lib_tool_and_names(self):
        my = defs.lib("my", str(self.make_lib()))
        self.assertEqual(self.tools([defs.std.tool("base/read"), my.tool("read"), my.tool("read", name="other", env={"A": "1"})]),
                         {"read": {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}},
                          "my_read": {"path": str(self.temp.name) + "/mylib/tools/read"},
                          "other": {"path": str(self.temp.name) + "/mylib/tools/read", "env": {"A": "1"}}})
        got = self.tools([my.pack("look", prefix="x-"), defs.std.pack("look", prefix="s_", exclude=["grep"], rename={"read": "cat"})])
        self.assertEqual(sorted(got), sorted(["x-read", "cat"] + ["s_" + n for n in look("read", "grep")]))

    def test_clash_is_spec_bad_and_the_ways_out(self):
        my = defs.lib("my", str(self.make_lib()))
        with self.assertRaisesRegex(defs.SpecBad, r"tool read comes from both std.pack\('look'\) and my.pack\('look'\)"):
            self.tools([defs.std.pack("look"), my.pack("look", prefix="")])
        mine = {"path": str(Path(self.temp.name) / "mylib" / "tools" / "read")}
        std_read = {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}}
        self.assertEqual(self.tools([defs.std.pack("look"), my.pack("look", prefix="", exclude=["read"])])["read"], std_read)
        self.assertEqual(self.tools([defs.std.pack("look"), my.pack("look", prefix="", rename={"read": "read2"})])["read2"], mine)
        self.assertEqual(self.tools([defs.std.pack("look"), my.pack("look", prefix=""), defs.tool("read", my.tool("read"))])["read"], mine)
        self.assertNotIn("read", self.tools([defs.std.pack("look"), my.pack("look", prefix=""), defs.drop("read")]))

    def test_same_entry_from_two_packs_is_one_tool(self):
        """a diamond: both packs point at the same tool, with the same entry -> not a clash."""
        same = self.make_lib("same", {"look": {"read": {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}}}})
        got = self.tools([defs.std.pack("look"), defs.lib("same", str(same)).pack("look", prefix="")])
        self.assertEqual(list(got), list(look()))
        other = self.make_lib("other", {"look": {"read": {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"},
                                                          "env": {"A": "1"}}}})
        self.assertRaises(defs.SpecBad, self.tools, [defs.std.pack("look"), defs.lib("other", str(other)).pack("look", prefix="")])

    def test_spec_bad(self):
        my = defs.lib("my", str(self.make_lib()))
        odd = defs.lib("odd", str(self.make_lib("odd", {"base": {"$override": "x.json", "tools": {}},
                                                       "out": {"read": {"path": "../../elsewhere/read"}}})))
        cases = {"root is not a folder": ([defs.lib("my", str(Path(self.temp.name) / "nowhere")).pack("look")], "is not a folder"),
                 "root variable not set": ([defs.lib("my", defs.env("AOS_NS_TEST_UNSET", "/x")).tool("read")], "AOS_NS_TEST_UNSET is not set"),
                 "root relative": ([defs.lib("my", "mylib").pack("look")], "must be an absolute path"),
                 "library named std": ([defs.lib("std", str(self.temp.name)).pack("look")], "std comes with aos"),
                 "bad library name": ([defs.lib("My lib", "/").pack("look")], "library name must be"),
                 "no such pack": ([my.pack("net")], r"there is no .*/packs/net.json \(packs of my: look\)"),
                 "pack with $override": ([odd.pack("base")], "no \\$override"),
                 "pack path leaves the root": ([odd.pack("out")], "leaves the library root"),
                 "prefix with a dot": ([my.pack("look", prefix="my.")], "prefix must be letters"),
                 "rename an unknown tool": ([my.pack("look", rename={"cat": "x"})], "the pack has no tool cat"),
                 "exclude an unknown tool": ([defs.std.pack("look", exclude=["cat"])], "the pack has no tool cat"),
                 "rename and exclude": ([my.pack("look", rename={"read": "x"}, exclude=["read"])], "in both rename and exclude"),
                 "name too long": ([my.pack("look", prefix="p" * 64)], "must be 1-64 letters"),
                 "no such tool folder": ([defs.std.tool("base/nope")], "there is no tool folder \\$AOS_HOME/lib/tools/base/nope"),
                 "tool folder outside": ([my.tool("../read")], "relative to the library's tools folder"),
                 "defs.drop of nothing": ([defs.std.pack("look"), defs.drop("cat")], r"defs.drop\('cat'\).*no pack in TOOLS has a tool cat"),
                 "same pack twice": ([my.pack("look"), my.pack("look")], r"my.pack\('look'\) is listed twice"),
                 "a library is not a tool": ([my], "each item of TOOLS")}
        for why, (items, line) in cases.items():
            with self.subTest(why=why):
                self.assertRaisesRegex(defs.SpecBad, line, self.tools, items)
        self.assertRaisesRegex(defs.SpecBad, "std has one state machine", defs.compile, "D.", "", [], {}, defs.std.fsm("eca"))
        with unittest.mock.patch.dict(os.environ, {}):
            os.environ.pop("AOS_HOME")
            self.assertIn("AOS_HOME is not set", defs.std.pack("look")["bad"])
            self.assertIn("AOS_HOME is not set", defs.std.tool("base/read")["bad"])

    def test_clash_through_agent_py_is_one_line_and_writes_nothing(self):
        dest = Path(self.temp.name) / "clash"
        dest.mkdir()
        (dest / "agent.py").write_text(HEAD + BODY.replace(
            "std = defs.std\n", "std = defs.std\nmy = defs.lib(\"my\", %r)\n" % str(self.make_lib())).replace(
            'std.pack("look"), ', 'std.pack("look"), my.pack("look", prefix=""), '))
        r = run_agent(dest / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("clash: error: SpecBad tool read comes from both"), r.stderr)
        self.assertEqual(os.listdir(dest), ["agent.py"])


class Reviewer(unittest.TestCase):
    """templates/reviewer written as one agent.py gives the same definition as the hand-written files (third cut's check)."""

    def test_same_as_the_template(self):
        with tempfile.TemporaryDirectory(prefix="agent-spec-") as tmp:
            dest = Path(tmp) / "reviewer"
            dest.mkdir()
            shutil.copy(TEMPLATES / "reviewer" / "system.txt", dest)
            (dest / "agent.py").write_text(HEAD + REVIEWER)
            r = run_agent(dest / "agent.py", "--compile", home=fake_home(tmp))
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


BASE = '''\
DESCRIPTION = "Review a change and answer by mail."
SYSTEM = "You review changes in the workspace.\\n"
std = defs.std
TOOLS = [std.pack("look"), std.pack("mailbox")]
LLM = {"model": "luna"}
FSM = std.fsm()
HOOKS = std.hooks()
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM, hooks=HOOKS)
'''
STRICT = '''\
base = defs.load("../reviewer")
DESCRIPTION = "Review a change and refuse anything without a test."
SYSTEM = base.SYSTEM + "Refuse a change that has no test.\\n"
TOOLS = [base.TOOLS, defs.drop("grep"), defs.std.tool("base/peek_now_time", name="now")]
HOOKS = [base.HOOKS, {"timer": {**base.HOOKS["timer"], "every_ms": 60000}}]
defs.main(DESCRIPTION, SYSTEM, TOOLS, base.LLM, base.FSM, hooks=HOOKS)
'''


class Inherit(WithHome):
    """inheritance first cut (aos-inherit-cut1-1119): base = defs.load(folder) runs another agent.py, whose defs.main only hands over its
    fields; worked out when agent.py runs, so the files written are whole and name no base (N-70); the running side is not touched."""

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
        hooks, base_hooks = load(made, "hooks.json")["hooks"], load(want, "hooks.json")["hooks"]
        self.assertEqual(hooks["timer"], dict(base_hooks["timer"], every_ms=60000))
        self.assertEqual(hooks["timer"]["on_error"], "continue")             # one field changed, on_error kept
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
        self.agent("d1", BASE.replace("defs.main(", "base = defs.load('../base')\nTOOLS = [base.TOOLS, defs.drop('grep')]\n"
                                      "HOOKS = [base.HOOKS, {'timer': None}]\ndefs.main("))
        self.agent("d2", BASE.replace("defs.main(", "base = defs.load('../base')\nTOOLS = [base.TOOLS]\nHOOKS = base.HOOKS\ndefs.main("))
        d1, d2 = defs.load(str(Path(self.temp.name) / "d1")), defs.load(str(Path(self.temp.name) / "d2"))
        tools = lambda items: defs.compile("D.", "", items, {}, defs.std.fsm())["tools.json"]["tools"]  # noqa: E731
        with self.assertRaisesRegex(defs.SpecBad, r"tool grep is taken out in defs.load\('.*d1'\) but kept in defs.load\('.*d2'\)"):
            tools([d1.TOOLS, d2.TOOLS])                                     # a tool taken out does not come back unseen
        self.assertNotIn("grep", tools([d1.TOOLS, d2.TOOLS, defs.drop("grep")]))
        self.assertIn("grep", tools([d1.TOOLS, d2.TOOLS, defs.tool("grep", defs.home("/lib/tools/base/grep"))]))
        self.assertEqual(sorted(tools([d1.TOOLS, d2.TOOLS, defs.drop("grep")])), sorted(set(tools([d2.TOOLS])) - {"grep"}))
        hooks = lambda h: defs.compile("D.", "", [], {}, defs.std.fsm(), hooks=h)["hooks.json"]["hooks"]  # noqa: E731
        with self.assertRaisesRegex(defs.SpecBad, "hook timer comes from both"):
            hooks([d1.HOOKS, d2.HOOKS])
        self.assertNotIn("timer", hooks([d1.HOOKS, d2.HOOKS, {"timer": None}]))
        dest = self.agent("top", "d1 = defs.load('../d1')\nd2 = defs.load('../d2')\n"
                                 "defs.main('D.', '', [d1.TOOLS, d2.TOOLS], {}, defs.std.fsm())\n")
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
                                    "defs.main('D.', m.SYSTEM, [m.TOOLS[0]], {}, defs.std.fsm())\n" % str(base / "agent.py"))
        r = self.run1(dest)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([p for p in os.listdir(base) if p != "__pycache__"], ["agent.py"])
        self.assertIn("fsm.json", os.listdir(dest))
        self.assertIn("reviewer: warning: ", r.stderr)
        self.assertIn("use base = defs.load", r.stderr)

    def test_load_errors_are_one_line(self):
        self.agent("hand", BASE.replace('SYSTEM = "You review changes in the workspace.\\n"', 'SYSTEM = defs.extern("system.txt")'))
        self.agent("broken", BASE.replace("LLM = ", "x = undefined_name\nLLM = "))
        self.agent("nomain", BASE.replace("defs.main(", "_ = (").replace("hooks=HOOKS", "HOOKS"))
        self.agent("badbase", BASE.replace('std.pack("mailbox")', 'std.pack("nope")'))
        self.agent("a", "b = defs.load('../b')\ndefs.main('D.', '', [], {}, defs.std.fsm())\n")
        self.agent("b", "a = defs.load('../a')\ndefs.main('D.', '', [], {}, defs.std.fsm())\n")
        cases = {"no such folder": ("defs.load('../nowhere')", "is not a folder"),
                 "no agent.py there": ("defs.load('../empty')", "there is no"),
                 "an extern field used": ("defs.load('../hand').SYSTEM", "SYSTEM of", "is defs.extern('system.txt')"),
                 "the base fails": ("defs.load('../broken')", "agent.py line 8: NameError"),
                 "the base never calls defs.main": ("defs.load('../nomain')", "never calls defs.main"),
                 "a wrong declaration in the base": ("defs.load('../badbase')", "std.pack('nope')", "fix the declaration in"),
                 "a circle": ("defs.load('../a')", "load each other in a circle"),
                 "no such hook": ("defs.load('../hand').HOOKS['nope']", "has no hook 'nope'"),
                 "not a path": ("defs.load(3)", "give the folder of another agent.py")}
        (Path(self.temp.name) / "empty").mkdir()
        for why, (expr, *line) in cases.items():
            with self.subTest(why=why):
                dest = self.agent("derived", "base = %s\ndefs.main('D.', '', [], {}, defs.std.fsm())\n" % expr)
                for flag in ("--compile", "--dry-run"):
                    r = self.run1(dest, flag)
                    self.assert_one_line(r, "derived", *line)
                    self.assertEqual(r.stdout, "")
                self.assertEqual(os.listdir(dest), ["agent.py"])
        self.assertTrue(defs.load(str(Path(self.temp.name) / "hand")).TOOLS)    # an extern field stops only when it is used

    def test_base_paths_are_moved_and_modules_put_back(self):
        base = self.agent("base", "import helper\n" + BASE.replace(
            "FSM = std.fsm()", "FSM = defs.fsm(std.fsm(), [defs.state('act', ['python3', 'act.py'])])").replace(
            'std.pack("mailbox")]', 'std.pack("mailbox"), defs.tool("mine", "tools/mine", env_file="my.env")]').replace(
            "HOOKS = std.hooks()", "HOOKS = [std.hooks(), {'h': {'event': 'after_tool', 'handler': 'hooks/h'}}]"))
        (base / "helper.py").write_text("WHO = 'base'\n")
        (base / "act.py").write_text("")
        derived = self.agent("derived", "base = defs.load('../base')\nimport helper\nassert helper.WHO == 'derived', helper.WHO\n"
                                        "defs.main('D.', '', [base.TOOLS], {}, base.FSM, hooks=base.HOOKS)\n")
        (derived / "helper.py").write_text("WHO = 'derived'\n")
        path = list(sys.path)
        r = self.run1(derived)
        self.assertEqual(r.returncode, 0, r.stderr)
        tools = json.loads((derived / "tools.json").read_text())["tools"]
        self.assertEqual(tools["mine"], {"path": str(base / "tools" / "mine"), "env_file": str(base / "my.env")})
        argv = json.loads((derived / "fsm.json").read_text())["states"]["act"]["exec"]["argv"]
        self.assertEqual(argv, ["python3", str(base / "act.py")])           # "python3" is a command, not a file of the base
        self.assertEqual(json.loads((derived / "hooks.json").read_text())["hooks"]["h"]["handler"], str(base / "hooks" / "h"))
        sys.modules.pop("helper", None)
        got = defs.load(str(base))                                            # in this process: sys.path and sys.modules put back
        self.assertEqual(sys.path, path)
        self.assertNotIn("helper", sys.modules)
        self.assertEqual(got.FSM["states"]["act"]["exec"]["timeout_ms"], 0)  # the field not given is the base's
        with unittest.mock.patch.dict(os.environ, {"AOS_INHERIT_TEST": self.temp.name}):
            moved = defs.load(defs.env("AOS_INHERIT_TEST", "/base")).TOOLS["tools"]["mine"]["path"]
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
                                 ("no base (eca)", defs.fsm(None, []), "has FSM None")):
            with self.subTest(why=why):
                self.assertIn(line, value["bad"])

    def test_hook_groups_and_tools_of_a_base(self):
        """two marked hook groups with one name and different entries = SpecBad (tightens the third cut's "a later one wins" for that
        case only; aos-inherit-1119/06 (c) 4); a plain dict you write still wins."""
        eca, stock = defs.std.hooks("eca-claude"), defs.std.hooks()
        both = sorted(n for n in set(eca) & set(stock) if eca[n] != stock[n])       # today: brain_notify, context_wrap
        self.assertTrue(both)
        hooks = lambda h: defs.compile("D.", "", [], {}, defs.std.fsm(), hooks=h)["hooks.json"]  # noqa: E731
        self.assertRaisesRegex(defs.SpecBad, "hook %s comes from both std.hooks\\('agent-fsm'\\) and std.hooks\\('eca-claude'\\)"
                               % both[0], hooks, [stock, eca])
        mine = {n: stock[n] for n in both}
        self.assertEqual(hooks([stock, eca, mine])["hooks"][both[0]], stock[both[0]])        # written after them: picked
        self.assertRaises(defs.SpecBad, hooks, [stock, mine, eca])                              # written between: not picked
        self.assertEqual(hooks([defs.std.hooks(), defs.std.hooks()])["description"].count("templates/agent-fsm/hooks.json"), 1)
        h = defs.std.hooks()["timer"]
        h["every_ms"] = 1
        self.assertNotEqual(defs.std.hooks()["timer"]["every_ms"], 1)
        base = defs.load(str(self.agent("base", BASE.replace(", hooks=HOOKS", ""))))
        self.assertNotIn("hooks.json", defs.compile("D.", "", [], {}, defs.std.fsm(), hooks=base.HOOKS))   # base had no HOOKS: none
        self.assertEqual(sorted(defs.compile("D.", "", [base.tools(prefix="r_", exclude=["grep"])], {}, defs.std.fsm())["tools.json"]["tools"]),
                         sorted("r_" + n for n in base.TOOLS["tools"] if n != "grep"))
        self.assertIn("the base has no tool cat", base.tools(rename={"cat": "x"})["bad"])
        self.assertRaisesRegex(defs.SpecBad, "listed twice", defs.compile, "D.", "", [base.TOOLS, base.TOOLS], {}, defs.std.fsm())


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
        """the skeleton declares HOOKS = {} (user 11-19 "骨架帶一行空的 HOOKS"): hooks.json with no hooks, named in interfaces.json, so an agent
        made from it takes breakpoints (aos-gdb) and aos-agent hook without changing anything; still no hook group of a template."""
        self.assertEqual(json.loads((SKEL / "hooks.json").read_text())["hooks"], {})
        self.assertEqual(json.loads((SKEL / "interfaces.json").read_text())["aos-agent"]["hooks"], "hooks.json")
        self.assertIn("hook_fire", (SKEL / "loop.json").read_text())

    def test_built_on_the_skeleton(self):
        """defs.load of the skeleton: its HOOKS is an empty group; a derived agent.py that writes no HOOKS gets no hooks.json, one that writes
        HOOKS = base.HOOKS or [base.HOOKS, {...}] gets those (the inheritance examples keep working)."""
        with tempfile.TemporaryDirectory(prefix="agent-python-") as tmp:
            home = fake_home(tmp)
            base = Path(tmp) / "base"
            base.mkdir()
            shutil.copy(SKEL / "agent.py", base)
            mine = {"event": "after_start", "handler": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/hook_fire"}}
            args = "base.DESCRIPTION, base.SYSTEM, [base.TOOLS], base.LLM, base.FSM"
            tails = {"none": "defs.main(%s)\n" % args,
                     "same": "defs.main(%s, hooks=base.HOOKS)\n" % args,
                     "more": "defs.main(%s, hooks=[base.HOOKS, {'mine': %r}])\n" % (args, mine)}
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
                        self.assertFalse((d / "hooks.json").exists())
                        self.assertNotIn("hooks", json.loads((d / "interfaces.json").read_text())["aos-agent"])
                    else:
                        self.assertEqual(json.loads((d / "hooks.json").read_text())["hooks"], want[name])

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


def at_run_time(tools_json, home, folder):
    """what aos-tools makes of a tools.json when the agent runs: its $override packs, then its own table, merged field by field
    (aos.apps.tools.registry.patch itself; null = not a tool), each path made absolute from the file that wrote it."""
    from aos.apps.tools import registry
    acc = {}
    for base in tools_json.get("$override", []):
        f = resolve(base, home)
        registry.patch(acc, json.loads(Path(f).read_text())["tools"], f)
    own = {n: (dict(e, path=resolve(e["path"], home)) if e else e) for n, e in tools_json.get("tools", {}).items()}
    registry.patch(acc, own, str(Path(folder) / "tools.json"))
    out = {}
    for name, t in acc.items():
        if "null" in t:
            continue
        e = dict(t["entry"])
        p = e["path"]
        e["path"] = os.path.normpath(os.path.join(os.path.dirname(t["origin"]["path"]), resolve(p, home)))
        out[name] = e
    return out


class Linking(WithHome):
    """tool packs linked statically (copied into tools.json, the default) or dynamically ($override, read when the agent runs):
    a compile option, like gcc (user 11-19 "或者說，用選項吧，gcc那樣"; default static: "預設靜態 (Recommended)" picked). Whatever the option,
    the agent gets the same tools when it runs; what dynamic linking cannot give is SpecBad or a warning, never a silent change."""

    make_lib = Namespace.make_lib

    def compile(self, items, link="static"):
        said = []
        out = defs.compile("D.", "", items, {}, defs.std.fsm(), link=link, warn=said.append)["tools.json"]
        return out, said

    def same_at_run_time(self, items, link="dynamic"):
        static, _ = self.compile(items)
        dyn, said = self.compile(items, link)
        self.assertEqual(at_run_time(dyn, self.home, self.temp.name), at_run_time(static, self.home, self.temp.name))
        return dyn, said

    def test_dynamic_names_the_packs_and_gives_the_same_tools(self):
        dyn, said = self.same_at_run_time([defs.std.pack("look"), defs.std.pack("mailbox"), defs.std.pack("json")])
        self.assertEqual(dyn["$override"], [{"$env": "AOS_HOME", "$path": "/lib/packs/%s.json" % p} for p in ("look", "mailbox", "json")])
        self.assertEqual(dyn["tools"], {})
        self.assertIn("links std.pack('look'), std.pack('mailbox'), std.pack('json') dynamically", dyn["description"])
        self.assertNotIn("copied in", dyn["description"])
        self.assertEqual(said, [])
        static, _ = self.compile([defs.std.pack("look")])
        self.assertNotIn("$override", static)                                           # the default: static, as before

    def test_one_pack_can_say_how(self):
        dyn, _ = self.same_at_run_time([defs.std.pack("look", link="dynamic"), defs.std.pack("mailbox")], link="static")
        self.assertEqual(dyn["$override"], [{"$env": "AOS_HOME", "$path": "/lib/packs/look.json"}])
        self.assertIn("mailbox_send", dyn["tools"])
        self.assertIn("copied in the tools of std.pack('mailbox')", dyn["description"])
        dyn, _ = self.same_at_run_time([defs.std.pack("look", link="static"), defs.std.pack("mailbox")])
        self.assertEqual(dyn["$override"], [{"$env": "AOS_HOME", "$path": "/lib/packs/mailbox.json"}])
        self.assertIn("read", dyn["tools"])

    def test_left_out_tools_are_null(self):
        dyn, _ = self.same_at_run_time([defs.std.pack("look", exclude=["grep"]), defs.drop("glob")])
        self.assertEqual(dyn["tools"], {"grep": None, "glob": None})

    def test_replacing_a_tool_of_a_dynamic_pack(self):
        peek = defs.home("/lib/tools/base/peek_now_time")
        dyn, _ = self.same_at_run_time([defs.std.pack("look"), defs.tool("read", peek)])
        self.assertEqual(dyn["tools"], {"read": {"path": peek}})
        rich = self.make_lib("rich", {"look": {"read": {"path": "../tools/read", "env": {"A": "1"}}}})
        items = [defs.lib("rich", str(rich)).pack("look", prefix="", link="dynamic"), defs.tool("read", peek)]
        self.compile(items[:1] + [defs.tool("read", peek, env={"A": "1"})])            # every field given: the merge gives just that
        with self.assertRaisesRegex(defs.SpecBad, r"tool read: with rich.pack\('look'\) linked dynamically, aos would merge .*"
                                                  r"field by field.*link it statically"):
            self.compile(items)
        self.compile([defs.lib("rich", str(rich)).pack("look", prefix=""), defs.tool("read", peek)])   # static: replaced as a whole

    def test_renamed_tools_need_static_linking(self):
        root = self.make_lib()
        my = defs.lib("my", str(root))
        dyn, said = self.same_at_run_time([defs.std.pack("look"), my.pack("look"), defs.std.pack("json", rename={"json_get": "query"})])
        self.assertEqual(dyn["$override"], [{"$env": "AOS_HOME", "$path": "/lib/packs/look.json"}])
        self.assertEqual(sorted(dyn["tools"]), sorted(["my_read", "query"] + [n for n in json.loads(
            (LIB / "packs" / "json.json").read_text())["tools"] if n != "json_get"]))
        self.assertEqual(len(said), 2)
        self.assertIn("my.pack('look') is linked statically: its tools are renamed", said[0])
        self.assertIn("std.pack('json') is linked statically", said[1])
        with self.assertRaisesRegex(defs.SpecBad, r"my.pack\('look'\): link=\"dynamic\" cannot rename its tools"):
            self.compile([my.pack("look", link="dynamic")])
        dyn, said = self.compile([my.pack("look", prefix="", link="dynamic")])           # no prefix: the pack as it is
        self.assertEqual(dyn["$override"], [str(root / "packs" / "look.json")])
        self.assertEqual(at_run_time(dyn, self.home, self.temp.name), {"read": {"path": str(root / "tools" / "read")}})

    def test_clashes_are_still_spec_bad(self):
        my = defs.lib("my", str(self.make_lib()))
        with self.assertRaisesRegex(defs.SpecBad, r"tool read comes from both std.pack\('look'\) and my.pack\('look'\)"):
            self.compile([defs.std.pack("look"), my.pack("look", prefix="")], link="dynamic")
        dyn, _ = self.compile([defs.std.pack("look"), my.pack("look", prefix="", exclude=["read"])], link="dynamic")
        self.assertEqual(at_run_time(dyn, self.home, self.temp.name)["read"]["path"], str(self.home) + "/lib/tools/base/read")
        self.assertEqual(dyn["tools"], {"read": {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}}})  # both packs give read: written

    def test_bad_link(self):
        with self.assertRaisesRegex(defs.SpecBad, "link must be \"static\" or \"dynamic\""):
            self.compile([defs.std.pack("look", link="shared")])
        with self.assertRaisesRegex(defs.SpecBad, "link must be \"static\" or \"dynamic\""):
            self.compile([defs.std.pack("look")], link="shared")

    def test_the_options_of_agent_py(self):
        folder = Path(self.temp.name) / "w"
        folder.mkdir()
        (folder / "agent.py").write_text(HEAD + BODY)
        call = lambda *argv: run_agent(folder / "agent.py", *argv, home=self.home)  # noqa: E731
        r = call("--compile", "--dynamic")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((folder / "tools.json").read_text())["$override"],
                         [{"$env": "AOS_HOME", "$path": "/lib/packs/look.json"}])
        self.assertNotIn("$override", json.loads(call("--dry-run", "--static").stdout)["tools.json"])
        self.assertNotIn("$override", json.loads(call("--dry-run").stdout)["tools.json"])
        self.assertIn("$override", json.loads(call("--dry-run", "--dynamic").stdout)["tools.json"])
        other = Path(self.temp.name) / "other"
        other.mkdir()
        self.assertEqual(call("--compile", "--dynamic", str(other)).returncode, 0)
        self.assertEqual(call("--compile", str(other), "--static").returncode, 0)
        self.assertNotIn("$override", json.loads((other / "tools.json").read_text()))
        r = call("--compile", "--static", "--dynamic")
        self.assertEqual((r.returncode, r.stderr.split(" (")[0]), (1, "w: error: ArgumentsBad give one of --static and --dynamic, not --static --dynamic"))
        r = call("--compile", "--shared")
        self.assertEqual(r.returncode, 1)
        self.assertIn("w: error: FlagUnknown --shared", r.stderr)
        self.assertEqual(call("--dry-run", "--dynamic", str(other)).returncode, 1)          # --dry-run takes no folder

    def test_the_tools_of_defs_load_are_linked_statically(self):
        base = Path(self.temp.name) / "base"
        base.mkdir()
        (base / "agent.py").write_text(HEAD + BODY)
        strict = Path(self.temp.name) / "strict"
        strict.mkdir()
        (strict / "agent.py").write_text(HEAD + 'base = defs.load("../base")\n'
                                         'defs.main("Strict.", base.SYSTEM, [base.TOOLS, defs.std.pack("json")], base.LLM, base.FSM)\n')
        r = run_agent(strict / "agent.py", "--dry-run", "--dynamic", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("strict: warning: defs.load('../base') is linked statically: it is the tools of another agent.py", r.stderr)
        tools_json = json.loads(r.stdout)["tools.json"]
        self.assertEqual(tools_json["$override"], [{"$env": "AOS_HOME", "$path": "/lib/packs/json.json"}])
        self.assertIn("peek", tools_json["tools"])
        self.assertNotIn("grep", tools_json["tools"])                                    # the base took grep out of std.pack("look")

if __name__ == "__main__":
    unittest.main()
