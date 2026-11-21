"""Test agent.py run as a script (defs.main(object): --compile / --dry-run, one-line SpecBad, overwrite rules) and the no-fsm (eca) mode."""
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
            self.assertEqual((self.dir / name).read_text(), as_text(value))

    def test_spec_bad_is_one_line_and_writes_nothing(self):
        self.assertEqual(self.call("--compile").returncode, 0)
        (self.dir / "tools.json").write_text("{}\n")      # a hand change that must survive a failed run
        before = snapshot(self.dir)
        del before["agent.py"]
        cases = {"next state not in the table":
                     ('fsm=std.fsm()', 'fsm=defs.fsm("idle", [defs.state("idle", ["true"], {0: "thnik"})])',
                      "SpecBad state idle: next state 'thnik' is not one of the states (idle)"),
                 "tool without a path":
                     ('defs.tool("peek", defs.home("/lib/tools/base/peek_now_time"))', 'defs.tool("peek", "")',
                      "SpecBad tool peek must have a path"),
                 "model not a string":
                     ('{"model": "luna"}', '{"model": 7}', "SpecBad llm model must be a non-empty string")}
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
        meta["note"] = {"template": "agent-python"}                                      # someone else's key: kept
        (self.dir / "_metainfo.json").write_text(json.dumps(meta, indent=2) + "\n")
        (self.dir / "README.md").write_text("My own readme.\n")                          # already there: not touched
        (self.dir / "notes.txt").write_text("mine\n")                                    # not declared: not touched
        r = self.call("--compile")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        self.assertEqual((self.dir / "tools.json").read_bytes(), made["tools.json"])
        self.assertEqual(json.loads((self.dir / "_metainfo.json").read_text()),
                         {"summary": "Answer questions about the weather.", "note": {"template": "agent-python"}})
        self.assertEqual((self.dir / "README.md").read_text(), "My own readme.\n")
        self.assertEqual((self.dir / "notes.txt").read_text(), "mine\n")
        self.assertIn("kept", r.stdout)

    def test_extern_file_is_not_touched(self):
        """cut 4: a file kept by hand in the same folder under another name; compiling makes system.txt a link to it, twice over."""
        self.write(BODY.replace('system="You answer questions about the weather.\\n"', 'system=defs.extern("system.hand.txt")'))
        (self.dir / "system.hand.txt").write_text("Written by hand.\n")
        for _ in range(2):                                      # the second compile finds the link there: not "links to itself"
            r = self.call("--compile")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("wrote %s -> system.hand.txt" % (self.dir / "system.txt"), r.stdout)
            self.assertEqual(os.readlink(self.dir / "system.txt"), "system.hand.txt")
            self.assertEqual((self.dir / "system.hand.txt").read_text(), "Written by hand.\n")
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
    """no fsm (eca bodies): agent.py fills the content files of a definition copied from a template, under the names its interfaces.json gives."""

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
                written = {"tools.json", "llm.json", "system.txt", "hookeds.json", "_metainfo.json"}
                for name in set(before) | set(after):          # the skeleton, cli.json, screen/, README.md: not touched
                    if name not in written:
                        self.assertEqual(after.get(name), before.get(name), name)
                load = lambda name, files: json.loads(files[name])  # noqa: E731
                self.assertNotIn("$override", load("tools.json", after))      # packs copied in: the same tools as the template's
                self.assertEqual(load("tools.json", after)["tools"], borrowed(load("tools.json", before), self.home))
                self.assertEqual(plain(load("llm.json", after)), plain(load("llm.json", before)))
                entries = lambda files: {k: v for k, v in load("hookeds.json", files).items() if k != "description"}  # noqa: E731
                self.assertEqual(entries(after), entries(before))
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
        del face["hookeds"]                                   # the list of what is hooked: top level (11-21)
        (dest / "interfaces.json").write_text(json.dumps(face))
        (dest / "agent.py").write_text(HEAD + ECA % {"summary": "S.", "llm": {}, "template": "eca-pi"})
        before = tree(dest)
        r = run_agent(dest / "agent.py", "--compile", home=self.home)
        self.assertEqual(r.returncode, 1)
        self.assertIn("DefBad", r.stderr)
        self.assertIn("names no hookeds file", r.stderr)
        self.assertIn('"hookeds"', r.stderr)                 # the fix it names: the top-level key, not one in the aos-agent cell
        self.assertEqual(tree(dest), before)

    def test_names_come_from_interfaces(self):
        dest = self.copy("eca-pi")
        face = json.loads((dest / "interfaces.json").read_text())
        face["aos-agent"]["system"] = "prompt.md"
        (dest / "interfaces.json").write_text(json.dumps(face))
        eca = lambda **kw: agent("S.", fsm=None, **kw).dry_run(str(dest))  # noqa: E731
        files = eca(system="Hi.\n", llm={"model": "m"})
        self.assertEqual(sorted(files), ["README.md", "_metainfo.json", "llm.json", "prompt.md", "tools.json"])
        self.assertRaises(defs.SpecBad, eca, llm={"temperature": 1})                  # eca's llm_keys: model only
        (dest / "prompt.hand.md").write_text("Hi by hand.\n")
        self.assertEqual(eca(system=defs.extern("prompt.hand.md"))["prompt.md"], "prompt.hand.md")    # the link sits on the declared name
        self.assertRaisesRegex(defs.SpecBad, "links prompt.md to itself", eca, system=defs.extern("prompt.md"))
        # files may write a file the skeleton does not declare (cli.json); not one interfaces.json declares, nor a skeleton name
        self.assertEqual(eca(files={"cli.json": {"a": 1}})["cli.json"], {"a": 1})
        self.assertRaises(defs.SpecBad, eca, files={"prompt.md": "x"})
        self.assertRaises(defs.SpecBad, eca, files={"loop.json": {}})
