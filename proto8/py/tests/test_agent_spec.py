"""Test py/aos/agent_spec.py and the templates/agent-python skeleton: declarations to definition files, SpecBad before any write, overwrite rules (C and .o), and the skeleton's committed files matching its agent.py."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

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


def snapshot(folder):
    return {p.name: p.read_bytes() for p in sorted(Path(folder).iterdir()) if p.is_file()}


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
                 "fsm not declared": dict(fsm=None),
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
