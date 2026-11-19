"""Test py/aos/agent_spec.py and the templates/agent-python skeleton: declarations to definition files, SpecBad before any write, overwrite rules (C and .o), HOOKS / FILES / no-FSM (eca) mode, libraries (std, ag.lib: packs copied in, other libraries prefixed, clashes SpecBad), templates/reviewer rewritten as one agent.py, and the skeleton's committed files matching its agent.py."""
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
std = ag.std
TOOLS = [std.pack("look"), ag.tool("peek", ag.home("/lib/tools/base/peek_now_time")), ag.no("grep")]
LLM = {"model": "luna"}
FSM = std.fsm()
ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM)
'''
GENERATED = ["_entry", "_metainfo.json", "body.json", "fsm.json", "interfaces.json", "llm.json", "loop.json", "system.txt", "tools.json"]
TEMPLATES = PROTO / "templates"
# templates/reviewer written as one agent.py (design 04, third cut's check): compared with the hand-written files, the template is not changed
REVIEWER = '''\
DESCRIPTION = "Review measured definition costs and prescribe a fix or split when model downgrades fail."
META = {"cost": {"time_ms": 60000}, "resource": ["llm"]}
SYSTEM = ag.by_hand("system.txt")

std = ag.std
TOOLS = [std.tool("aos/" + n) for n in ("review_round", "watch", "promote", "rollback", "measure")] \\
      + [std.tool("base/" + n) for n in ("json_get", "json_ls", "json_set", "json_del", "read", "ls")]
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
TOOLS = [ag.std.pack(p) for p in ("gadgets", "events", "self", "def", "mailbox", "json", "jsonx", "index")] + [ag.no("do_task")]
LLM = %(llm)r
HOOKS = ag.std.hooks(%(template)r)
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


def resolve(value, home):
    """a {"$env": "AOS_HOME", "$path": ...} directive (or a plain path) -> the path on this machine."""
    return str(home) + value["$path"] if isinstance(value, dict) else value


def borrowed(tools_json, home):
    """the tools a hand-written tools.json gives after aos-tools stacks its $override packs (field by field, null = not a tool);
    the generated tools.json must give the same table without $override."""
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
        files = ag.defs("Do it.", "sys\n", [ag.std.pack("look"), ag.tool("x", "tools/x", env={"A": "1"}), ag.no("grep")],
                        {"model": "m"}, ag.std.fsm())
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

    def test_by_hand_meta_and_interfaces(self):
        files = ag.defs("D.", ag.by_hand("prompt.txt"), [], {}, ag.std.fsm(), meta={"cost": {"time_ms": 1}},
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
        fine = dict(description="D.", system="", tools=[], llm={}, fsm=ag.std.fsm())
        cases = {"empty description": dict(description=" "),
                 "next not in table": dict(fsm=ag.fsm("a", [ag.state("a", ["x"], {0: "nowhere"})])),
                 "start not in table": dict(fsm=ag.fsm("z", [ag.state("a", ["x"], {0: "a"})])),
                 "no 0 or *": dict(fsm=ag.fsm("a", [ag.state("a", ["x"], {1: "a"})])),
                 "code out of range": dict(fsm=ag.fsm("a", [ag.state("a", ["x"], {0: "a", 256: "a"})])),
                 "state twice": dict(fsm=ag.fsm("a", [ag.state("a", ["x"], "a"), ag.state("a", ["y"], "a")])),
                 "empty argv": dict(fsm=ag.fsm("a", [ag.state("a", [], "a")])),
                 "tool without path": dict(tools=[ag.tool("x", None)]),
                 "tool twice": dict(tools=[ag.tool("x", "a"), ag.no("x")]),
                 "pack twice": dict(tools=[ag.std.pack("look"), ag.std.pack("look")]),
                 "bad pack name": dict(tools=[ag.std.pack("../x")]),
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
                 "HOOKS holds a tool": dict(hooks=[ag.std.pack("look")]),
                 "stock_hooks bad name": dict(hooks=ag.std.hooks("../x")),
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

    def test_holes_from_argon_review(self):
        """geng-patch-1119 (thinking/2026-11/19/aos-compile-庚/12, class 1): META keys, by_hand("agent.py"), the entry message."""
        fine = dict(description="D.", system="", tools=[], llm={}, fsm=ag.std.fsm())
        with self.assertRaisesRegex(ag.SpecBad, "META keys must be strings"):                  # ① was TypeError
            ag.defs(**dict(fine, meta={1: "a"}))
        for what in ("system", "fsm", "tools", "llm", "hooks"):                                 # ② agent.py is not a by_hand file
            with self.subTest(what=what), self.assertRaisesRegex(ag.SpecBad, r"by_hand\('agent.py'\)"):
                ag.defs(**dict(fine, **{what: ag.by_hand("agent.py")}))
        with self.assertRaises(ag.SpecBad) as e:                                                # ⑥ entry cannot take by_hand
            ag.defs(**dict(fine, interfaces={"aos-agent": {"entry": "x.json"}}))
        self.assertIn("entry is body.json", str(e.exception))
        self.assertNotIn("by_hand", str(e.exception))
        with self.assertRaisesRegex(ag.SpecBad, r"use ag.by_hand"):
            ag.defs(**dict(fine, interfaces={"aos-agent": {"llm": "x.json"}}))

    def test_rename_order_and_cleanup(self):
        """geng-patch-1119 ③ files pointed at are renamed before the index files; ④ one failed unlink does not stop the cleanup."""
        out = ag.defs("D.", "", [], {}, ag.std.fsm())
        with tempfile.TemporaryDirectory(prefix="agent-spec-") as d:
            order, replace = [], os.replace
            with unittest.mock.patch("os.replace", lambda a, b: (order.append(os.path.basename(b)), replace(a, b))):
                ag.write_defs(d, out)
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
                self.assertRaisesRegex(OSError, "replace fails", ag.write_defs, d, out)
            self.assertEqual(len(calls), len(out))
            self.assertEqual([p for p in os.listdir(d) if ".tmp-" in p], [os.path.basename(calls[0])])

    def test_hooks_and_files(self):
        with tempfile.TemporaryDirectory(prefix="agent-spec-") as tmp, \
                unittest.mock.patch.dict(os.environ, {"AOS_HOME": str(fake_home(tmp))}):
            mine = {"event": "before_tool", "condition": "shell", "handler": ag.home("/lib/tools/agent/hook_noop")}
            files = ag.defs("D.", "", [], {}, ag.std.fsm(), hooks=[ag.std.hooks(), {"timer": None, "mine": mine}],
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
        files = ag.defs("D.", "", [], {}, ag.std.fsm(), hooks={})
        loop = json.loads((TEMPLATES / "agent-fsm" / "loop.json").read_text())
        self.assertEqual(plain(files["loop.json"]), plain(loop))
        self.assertEqual(files["hooks.json"]["hooks"], {})

    def test_no_hooks_no_hooks_key(self):
        files = ag.defs("D.", "", [], {}, ag.std.fsm())
        self.assertNotIn("hooks", files["interfaces.json"]["aos-agent"])
        self.assertNotIn("on_start", files["loop.json"])
        self.assertNotIn("hooks.json", files)

    def test_by_hand_hooks(self):
        files = ag.defs("D.", "", [], {}, ag.std.fsm(), hooks=ag.by_hand("my_hooks.json"))
        self.assertNotIn("my_hooks.json", files)
        self.assertEqual(files["interfaces.json"]["aos-agent"]["hooks"], "my_hooks.json")
        self.assertIn("on_start", files["loop.json"])

    def test_stock_hooks_needs_a_home_with_the_template(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AOS_HOME", None)
            self.assertIn("AOS_HOME is not set", ag.std.hooks()["bad"])
        with tempfile.TemporaryDirectory(prefix="agent-spec-") as tmp, \
                unittest.mock.patch.dict(os.environ, {"AOS_HOME": str(fake_home(tmp))}):
            bad = ag.std.hooks("reviewer")
            self.assertIn("templates with hooks: ", bad["bad"])
            self.assertIn("agent-fsm", bad["bad"])
            self.assertRaises(ag.SpecBad, ag.defs, "D.", "", [], {}, ag.std.fsm(), hooks=bad)


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
                     ('FSM = std.fsm()', 'FSM = ag.fsm("idle", [ag.state("idle", ["true"], {0: "thnik"})])',
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

    def test_unreadable_metainfo_is_write_failed_and_writes_nothing(self):
        """geng-patch-1119 ⑤: cannot read _metainfo.json (here: it is a folder) = an I/O error, WriteFailed; not DefBad."""
        (self.dir / "_metainfo.json").mkdir()
        r = self.call("--write-defs")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
        self.assertIn("weather: error: WriteFailed", r.stderr)
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
                self.assertNotIn("$override", load("tools.json", after))      # packs copied in: the same tools as the template's
                self.assertEqual(load("tools.json", after)["tools"], borrowed(load("tools.json", before), self.home))
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


class Namespace(WithHome):
    """namespace first cut (aos-ns-cut1-1119): ag.std and ag.lib; packs copied in tool by tool; another library's tools get
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
        return ag.defs("D.", "", items, {}, ag.std.fsm())["tools.json"]["tools"]

    def test_two_reads_each_its_own(self):
        root = self.make_lib()
        my = ag.lib("my", str(root))
        got = self.tools([ag.std.pack("look"), my.pack("look")])
        self.assertEqual(got["read"], {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}})
        self.assertEqual(got["my_read"], {"path": str(root / "tools" / "read")})
        self.assertEqual(list(got), list(look()) + ["my_read"])
        with unittest.mock.patch.dict(os.environ, {"AOS_NS_TEST_WS": self.temp.name}):       # root as a directive: written as one
            got = self.tools([ag.lib("my", ag.env("AOS_NS_TEST_WS", "/mylib")).pack("look")])
        self.assertEqual(got, {"my_read": {"path": {"$env": "AOS_NS_TEST_WS", "$path": "/mylib/tools/read"}}})

    def test_lib_tool_and_names(self):
        my = ag.lib("my", str(self.make_lib()))
        self.assertEqual(self.tools([ag.std.tool("base/read"), my.tool("read"), my.tool("read", name="other", env={"A": "1"})]),
                         {"read": {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}},
                          "my_read": {"path": str(self.temp.name) + "/mylib/tools/read"},
                          "other": {"path": str(self.temp.name) + "/mylib/tools/read", "env": {"A": "1"}}})
        got = self.tools([my.pack("look", prefix="x-"), ag.std.pack("look", prefix="s_", exclude=["grep"], rename={"read": "cat"})])
        self.assertEqual(sorted(got), sorted(["x-read", "cat"] + ["s_" + n for n in look("read", "grep")]))

    def test_clash_is_spec_bad_and_the_ways_out(self):
        my = ag.lib("my", str(self.make_lib()))
        with self.assertRaisesRegex(ag.SpecBad, r"tool read comes from both std.pack\('look'\) and my.pack\('look'\)"):
            self.tools([ag.std.pack("look"), my.pack("look", prefix="")])
        mine = {"path": str(Path(self.temp.name) / "mylib" / "tools" / "read")}
        std_read = {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}}
        self.assertEqual(self.tools([ag.std.pack("look"), my.pack("look", prefix="", exclude=["read"])])["read"], std_read)
        self.assertEqual(self.tools([ag.std.pack("look"), my.pack("look", prefix="", rename={"read": "read2"})])["read2"], mine)
        self.assertEqual(self.tools([ag.std.pack("look"), my.pack("look", prefix=""), ag.tool("read", my.tool("read"))])["read"], mine)
        self.assertNotIn("read", self.tools([ag.std.pack("look"), my.pack("look", prefix=""), ag.no("read")]))

    def test_same_entry_from_two_packs_is_one_tool(self):
        """a diamond: both packs point at the same tool, with the same entry -> not a clash."""
        same = self.make_lib("same", {"look": {"read": {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"}}}})
        got = self.tools([ag.std.pack("look"), ag.lib("same", str(same)).pack("look", prefix="")])
        self.assertEqual(list(got), list(look()))
        other = self.make_lib("other", {"look": {"read": {"path": {"$env": "AOS_HOME", "$path": "/lib/tools/base/read"},
                                                          "env": {"A": "1"}}}})
        self.assertRaises(ag.SpecBad, self.tools, [ag.std.pack("look"), ag.lib("other", str(other)).pack("look", prefix="")])

    def test_spec_bad(self):
        my = ag.lib("my", str(self.make_lib()))
        odd = ag.lib("odd", str(self.make_lib("odd", {"base": {"$override": "x.json", "tools": {}},
                                                       "out": {"read": {"path": "../../elsewhere/read"}}})))
        cases = {"root is not a folder": ([ag.lib("my", str(Path(self.temp.name) / "nowhere")).pack("look")], "is not a folder"),
                 "root variable not set": ([ag.lib("my", ag.env("AOS_NS_TEST_UNSET", "/x")).tool("read")], "AOS_NS_TEST_UNSET is not set"),
                 "root relative": ([ag.lib("my", "mylib").pack("look")], "must be an absolute path"),
                 "library named std": ([ag.lib("std", str(self.temp.name)).pack("look")], "std comes with aos"),
                 "bad library name": ([ag.lib("My lib", "/").pack("look")], "library name must be"),
                 "no such pack": ([my.pack("net")], r"there is no .*/packs/net.json \(packs of my: look\)"),
                 "pack with $override": ([odd.pack("base")], "no \\$override"),
                 "pack path leaves the root": ([odd.pack("out")], "leaves the library root"),
                 "prefix with a dot": ([my.pack("look", prefix="my.")], "prefix must be letters"),
                 "rename an unknown tool": ([my.pack("look", rename={"cat": "x"})], "the pack has no tool cat"),
                 "exclude an unknown tool": ([ag.std.pack("look", exclude=["cat"])], "the pack has no tool cat"),
                 "rename and exclude": ([my.pack("look", rename={"read": "x"}, exclude=["read"])], "in both rename and exclude"),
                 "name too long": ([my.pack("look", prefix="p" * 64)], "must be 1-64 letters"),
                 "no such tool folder": ([ag.std.tool("base/nope")], "there is no tool folder \\$AOS_HOME/lib/tools/base/nope"),
                 "tool folder outside": ([my.tool("../read")], "relative to the library's tools folder"),
                 "ag.no of nothing": ([ag.std.pack("look"), ag.no("cat")], r"ag.no\('cat'\).*no pack in TOOLS has a tool cat"),
                 "same pack twice": ([my.pack("look"), my.pack("look")], r"my.pack\('look'\) is listed twice"),
                 "a library is not a tool": ([my], "each item of TOOLS")}
        for why, (items, line) in cases.items():
            with self.subTest(why=why):
                self.assertRaisesRegex(ag.SpecBad, line, self.tools, items)
        self.assertRaisesRegex(ag.SpecBad, "std has one state machine", ag.defs, "D.", "", [], {}, ag.std.fsm("eca"))
        with unittest.mock.patch.dict(os.environ, {}):
            os.environ.pop("AOS_HOME")
            self.assertIn("AOS_HOME is not set", ag.std.pack("look")["bad"])
            self.assertIn("AOS_HOME is not set", ag.std.tool("base/read")["bad"])

    def test_clash_through_agent_py_is_one_line_and_writes_nothing(self):
        dest = Path(self.temp.name) / "clash"
        dest.mkdir()
        (dest / "agent.py").write_text(HEAD + BODY.replace(
            "std = ag.std\n", "std = ag.std\nmy = ag.lib(\"my\", %r)\n" % str(self.make_lib())).replace(
            'std.pack("look"), ', 'std.pack("look"), my.pack("look", prefix=""), '))
        r = run_agent(dest / "agent.py", "--write-defs", home=self.home)
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
