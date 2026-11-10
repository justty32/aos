"""Test aos-agent tools on a fake daemon table (11-10 aos-tools-cli step 4): the first add/rm creates the agent's own registry with "$override" (N2 pointer forms), --replace, reset, and the warning when it overrides another definition."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[4]
BIN = REPO / "proto8" / "cmd" / "aos-agent" / "bin" / "aos-agent"
TOOL = REPO / "proto8" / "lib" / "base" / "wall_clock"


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") and not k.startswith("TC_")}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return env


class ToolsOverride(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-tools-"))
        self.d = self.tmp / "d"
        self.defn = self.tmp / "defs" / "bob"
        self.defn.mkdir(parents=True)
        (self.defn / "interfaces.json").write_text(json.dumps({"aos-agent": {"tools": "tools.json"}}))
        shutil.copytree(TOOL, self.defn / "lib" / "clock")
        shutil.copytree(TOOL, self.tmp / "extra")
        self.reg = self.defn / "tools.json"
        self.reg.write_text(json.dumps({"tools": {"clock": {"path": "lib/clock", "env": {"K": "v"}}}}))
        (self.tmp / "ws").mkdir()
        self.stack = self.d / "procs" / "bob"
        self.stack.mkdir(parents=True)
        self.table({"phase": "stopped", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn)})
        self.own = self.stack / "tools.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def table(self, row):
        (self.d / "procs_state.json").write_text(json.dumps({"procs": {"bob": row}}))

    def agent(self, *args, ok=True, **env):
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "tools", "--target", "bob", *[str(a) for a in args]],
                           env=clean_env(**env), capture_output=True, text=True, timeout=60, cwd=self.tmp)
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def names(self, **env):
        return [l.split("\t")[0] for l in self.agent("ls", **env).stdout.splitlines()]

    def test_first_add_creates_override_relative(self):
        before = self.reg.read_bytes()
        r = self.agent("add", "extra", "extra")
        self.assertIn("created %s" % self.own, r.stderr)
        data = json.loads(self.own.read_text())
        self.assertEqual(data["$override"], os.path.relpath(self.reg, self.stack))
        self.assertEqual(data["tools"], {"extra": {"path": os.path.relpath(self.tmp / "extra", self.stack)}})
        self.assertEqual(self.names(), ["clock", "extra"])
        self.assertEqual(self.reg.read_bytes(), before)

    def test_pointer_follows_env_directive_in_table(self):
        self.table({"phase": "stopped", "stack": "procs/bob", "ws": "../ws", "def": str(self.defn),
                    "as_written": {"def": {"$env": "TC_DEFS", "$path": "/bob"}}})
        self.agent("rm", "clock", TC_DEFS=str(self.defn.parent))
        data = json.loads(self.own.read_text())
        self.assertEqual(data["$override"], {"$env": "TC_DEFS", "$path": "/bob/tools.json"})
        self.assertEqual(data["tools"], {"clock": None})
        self.assertEqual(self.names(TC_DEFS=str(self.defn.parent)), [])

    def test_replace_and_reset(self):
        r = self.agent("add", "clock", "extra", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("add --replace to replace it", r.stderr)
        self.assertFalse(self.own.exists())                      # failed first add leaves no file behind
        self.agent("add", "--replace", "clock", "extra")
        self.assertEqual(json.loads(self.own.read_text())["tools"]["clock"]["env"], None)
        self.agent("reset", "--yes")
        self.assertFalse(self.own.exists())
        self.assertEqual(self.names(), ["clock"])

    def test_old_flag_is_unknown(self):
        r = self.agent("add", "--override", "clock", "extra", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("FlagUnknown", r.stderr)

    def test_warns_when_overriding_another_definition(self):
        other = self.tmp / "defs" / "other.json"
        other.write_text(json.dumps({"tools": {}}))
        self.own.write_text(json.dumps({"$override": "../../../defs/other.json", "tools": {}}))
        r = self.agent("ls")
        self.assertIn("overrides %s, not its definition's %s" % (other, self.reg), r.stderr)

    def test_ctl_state_counts_own_changes(self):
        self.agent("add", "extra", "extra")
        self.agent("rm", "clock")
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "ctl", "state", "--target", "bob"],
                           env=clean_env(), capture_output=True, text=True, timeout=60)
        self.assertIn("own: 1 listed, 1 set to null (+extra, null:clock) over %s" % json.dumps(os.path.relpath(self.reg, self.stack)),
                      p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
