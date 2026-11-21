"""Test defs.extern as a link (compile-library cut 4, line aos-pylib-k4-1120; design thinking/2026-11/20/aos-pylib-plan-1120/05): the field compiles into a symbolic link holding the path as written, checked against the folder it is compiled into; one test per row of 05's table."""
import json
import os
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agent_spec_helpers import HEAD, WithHome, agent, defs, run_agent  # noqa: E402
from aos import spec_base  # noqa: E402


class Link(WithHome):
    def setUp(self):
        super().setUp()
        self.root = Path(self.temp.name)
        self.shared = self.folder("shared")
        (self.shared / "system.txt").write_text("Shared system text.\n")
        (self.shared / "tools.json").write_text("not even json\n")         # the target's content is not checked
        self.dir = self.folder("defs/bob")

    def test_link_holds_the_path_as_written(self):
        out = agent(system=defs.extern("../../shared/system.txt")).compile(str(self.dir))
        self.assertIn("wrote %s -> ../../shared/system.txt" % (self.dir / "system.txt"), out)
        self.assertEqual(os.readlink(self.dir / "system.txt"), "../../shared/system.txt")
        self.assertEqual((self.dir / "system.txt").read_text(), "Shared system text.\n")
        face = json.loads((self.dir / "interfaces.json").read_text())["aos-agent"]
        self.assertEqual((face["system"], face["tools"]), ("system.txt", "tools.json"))   # the default names, always
        absolute = str(self.shared / "tools.json")
        agent(tools=defs.extern(absolute)).compile(str(self.dir))
        self.assertEqual(os.readlink(self.dir / "tools.json"), absolute)
        self.assertFalse(os.path.islink(self.dir / "system.txt"))          # no extern any more: a plain file again
        self.assertEqual((self.shared / "system.txt").read_text(), "Shared system text.\n")   # the target is never touched
        self.assertEqual((self.shared / "tools.json").read_text(), "not even json\n")

    def test_every_field_and_dry_run(self):
        for what, name in (("system", "system.txt"), ("tools", "tools.json"), ("llm", "llm.json"), ("hooks", "hookeds.json")):
            with self.subTest(what=what):
                (self.shared / name).write_text("{}\n")
                files = agent(**{what: defs.extern("../../shared/" + name)}).dry_run(str(self.dir))
                self.assertIsInstance(files[name], spec_base.Link)
                self.assertEqual(files[name], "../../shared/" + name)
        self.assertIn("on_start", agent(hooks=defs.extern("../../shared/hookeds.json")).dry_run(str(self.dir))["loop.json"])
        (self.dir / "agent.py").write_text(HEAD + "defs.main(defs.Agent('D.', system=defs.extern('../../shared/system.txt'), "
                                           "tools=[], llm={}, fsm=defs.std.fsm()))\n")
        r = run_agent(self.dir / "agent.py", "--dry-run", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["system.txt"], {"$symlink": "../../shared/system.txt"})
        self.assertEqual(sorted(os.listdir(self.dir)), ["agent.py"])

    def test_counted_from_the_folder_compiled_into(self):
        a = agent(system=defs.extern("../shared/system.txt"))
        self.assertRaisesRegex(defs.SpecBad, r"\.\./shared/system.txt does not exist \(seen from .*defs/bob\)", a.dry_run, str(self.dir))
        other = self.folder("other")
        a.compile(str(other))
        self.assertEqual((other / "system.txt").read_text(), "Shared system text.\n")
        self.assertRaisesRegex(defs.SpecBad, "give the folder", a.dry_run)

    def test_spec_bad(self):
        (self.shared / "sub").mkdir()
        (self.dir / "system.txt").write_text("old hand-written\n")
        cases = {"a directive": (dict(system=defs.extern(defs.home("/x"))), "cannot hold defs.env"),
                 "env too": (dict(system=defs.extern(defs.env("AOS_WS", "/x"))), "plain string"),
                 "not a string": (dict(system=defs.extern(3)), "give the path"),
                 "empty": (dict(system=defs.extern("")), "give the path"),
                 "missing": (dict(system=defs.extern("../../shared/nope.txt")), "does not exist"),
                 "a folder": (dict(system=defs.extern("../../shared/sub")), "is a folder"),
                 "itself": (dict(system=defs.extern("system.txt")), r"links system.txt to itself.*system\.hand\.txt"),
                 "itself through ./": (dict(system=defs.extern("./system.txt")), "to itself"),
                 "itself by a way round": (dict(system=defs.extern("../bob/system.txt")), "to itself"),
                 "in a tools list": (dict(tools=[defs.extern("../../shared/tools.json")]), "stands for the whole field"),
                 "in a hooks list": (dict(hooks=[{}, defs.extern("../../shared/tools.json")]), "stands for the whole field"),
                 "fsm in another folder": (dict(fsm=defs.extern("../../shared/system.txt")), "same folder"),
                 "fsm in a sub folder": (dict(fsm=defs.extern("sub/fsm.json")), "same folder")}
        (self.dir / "sub").mkdir()
        (self.dir / "sub" / "fsm.json").write_text("{}\n")
        before = sorted(os.listdir(self.dir))
        for why, (change, line) in cases.items():
            with self.subTest(why=why):
                self.assertRaisesRegex(defs.SpecBad, line, agent(**change).compile, str(self.dir))
                self.assertEqual(sorted(os.listdir(self.dir)), before)      # nothing written
        self.assertEqual((self.dir / "system.txt").read_text(), "old hand-written\n")

    def test_fsm_in_the_same_folder_and_twice(self):
        (self.dir / "fsm.hand.json").write_text(json.dumps({"start": "idle", "states": {}}))
        a = agent(fsm=defs.extern("./fsm.hand.json"), system=defs.extern("../../shared/system.txt"))
        for _ in range(2):                                      # the second time the links are there already: not "to itself"
            a.compile(str(self.dir))
            self.assertEqual(os.readlink(self.dir / "fsm.json"), "./fsm.hand.json")
            self.assertEqual(os.readlink(self.dir / "system.txt"), "../../shared/system.txt")
        self.assertEqual(json.loads((self.dir / "loop.json").read_text())["exec"], "fsm.json")
        self.assertEqual(json.loads((self.dir / "fsm.hand.json").read_text()), {"start": "idle", "states": {}})
        self.assertIn("no table to change", defs.fsm(defs.extern("x"), [])["bad"])


class Load(WithHome):
    """defs.load of a base with an extern (05; Argon A8): a target outside the base folder is handed over and counted again from the
    folder the derived one is compiled into; one inside it (a file of that folder) cannot be built on."""

    def agent(self, rel, body):
        folder = Path(self.temp.name) / rel
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "agent.py").write_text(HEAD + body)
        return folder

    def test_outside_is_handed_over_and_counted_again(self):
        shared = Path(self.temp.name) / "shared"
        shared.mkdir()
        (shared / "system.txt").write_text("Shared.\n")
        (shared / "llm.json").write_text('{"model": "m"}\n')
        self.agent("base", "defs.main(defs.Agent('B.', system=defs.extern('../shared/system.txt'), tools=[], "
                           "llm=defs.extern(%r), fsm=defs.std.fsm()))\n" % str(shared / "llm.json"))
        deep = self.agent("a/b/derived", "base = defs.load('../../../base')\n"
                                         "defs.main(defs.Agent('D.', system=base.system, tools=[], llm=base.llm, fsm=base.fsm))\n")
        r = run_agent(deep / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.readlink(deep / "system.txt"), "../../../shared/system.txt")
        self.assertEqual(os.readlink(deep / "llm.json"), str(shared / "llm.json"))        # absolute: as written
        top = self.agent("top", "d = defs.load('../a/b/derived')\n"                     # two steps down: still counted right
                                "defs.main(defs.Agent('T.', system=d.system, tools=[], llm={}, fsm=defs.std.fsm()))\n")
        self.assertEqual(run_agent(top / "agent.py", "--compile", home=self.home).returncode, 0)
        self.assertEqual(os.readlink(top / "system.txt"), "../shared/system.txt")
        self.assertEqual((top / "system.txt").read_text(), "Shared.\n")

    def test_inside_cannot_be_built_on(self):
        base = self.agent("base", "defs.main(defs.Agent('B.', system=defs.extern('system.hand.txt'), tools=[], llm={}, "
                                  "fsm=defs.std.fsm()))\n")
        (base / "system.hand.txt").write_text("Mine.\n")
        got = defs.load(str(base))
        self.assertRaisesRegex(defs.SpecBad, "inside that folder", getattr, got, "system")
        self.assertEqual(got.llm, {})                                       # the other fields are fine


if __name__ == "__main__":
    unittest.main()
