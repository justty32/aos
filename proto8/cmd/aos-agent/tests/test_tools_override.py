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
TOOL = REPO / "proto8" / "lib" / "base" / "peek_now_time"


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

    def test_ls_default_is_brief(self):
        """11-10 深夜使用者「默認是給出短板，然後用-l才是給長版」：不帶旗標＝名 TAB 說明第一句；-b 拿掉。"""
        self.assertEqual(self.agent("ls").stdout, "clock\tGet the current time.\n")
        self.assertIn("FlagUnknown", self.agent("ls", "-b", ok=False).stderr)

    def test_first_add_creates_override_relative(self):
        before = self.reg.read_bytes()
        r = self.agent("add", "extra")
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

    def test_rm_by_path_and_long_shows_null(self):
        """11-10 晚使用者「2.統一」「3.顯示」：rm 收路徑（同 aos-tools rm）；ls -l 列被設成 null 的格與它蓋掉的那支。"""
        self.agent("rm", "defs/bob/lib/clock")
        self.assertEqual(json.loads(self.own.read_text())["tools"], {"clock": None})
        self.assertEqual(self.names(), [])
        rows = [l.split("\t") for l in self.agent("ls", "-l").stdout.splitlines()]
        self.assertEqual(rows, [["clock", "null", str(self.defn / "lib" / "clock"), "%s#/tools/clock" % self.own, "null", "-"]])

    def test_replace_and_reset(self):
        r = self.agent("add", "--name", "clock", "extra", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("add --replace to replace it", r.stderr)
        self.assertFalse(self.own.exists())                      # failed first add leaves no file behind
        self.agent("add", "--replace", "--name", "clock", "extra")
        self.assertEqual(json.loads(self.own.read_text())["tools"]["clock"]["env"], None)
        self.agent("reset", "--yes")
        self.assertFalse(self.own.exists())
        self.assertEqual(self.names(), ["clock"])

    def test_old_flag_is_unknown(self):
        r = self.agent("add", "--override", "--name", "clock", "extra", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("FlagUnknown", r.stderr)

    def test_add_same_flags_as_aos_tools(self):
        secrets = self.tmp / "s.env"
        secrets.write_text("TC_K=1\n")
        self.agent("add", "-n", "c2", "--envs", "A=1", "--envs", "B=2", "--env-file", "s.env", "extra")
        self.agent("add", "--name", "c3", "--path-json", json.dumps({"$env": "TC_X", "$path": "/extra"}), TC_X=str(self.tmp))
        tools = json.loads(self.own.read_text())["tools"]
        self.assertEqual(tools["c2"], {"path": os.path.relpath(self.tmp / "extra", self.stack), "env": {"A": "1", "B": "2"},
                                       "env_file": os.path.relpath(secrets, self.stack)})
        self.assertEqual(tools["c3"]["path"], {"$env": "TC_X", "$path": "/extra"})

    def test_old_two_positional_form_is_bad(self):
        r = self.agent("add", "clock2", "extra", ok=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ArgumentsBad", r.stderr)

    def test_flags_after_xxx(self):
        """11-10 cli-sweep Q1（使用者「1.收。」）：XXX 後的旗標也收（今天下午的「flags go before XXX」拿掉）。"""
        self.agent("add", "extra", "--name", "x")
        self.assertIn("x", json.loads(self.own.read_text())["tools"])

    def test_warns_when_overriding_another_definition(self):
        other = self.tmp / "defs" / "other.json"
        other.write_text(json.dumps({"tools": {}}))
        self.own.write_text(json.dumps({"$override": "../../../defs/other.json", "tools": {}}))
        r = self.agent("ls")
        self.assertIn("overrides %s, not its definition's %s" % (other, self.reg), r.stderr)

    def test_ctl_state_counts_own_changes(self):
        self.agent("add", "extra")
        self.agent("rm", "clock")
        p = subprocess.run([str(BIN), "--daemon", str(self.d), "ctl", "state", "--target", "bob"],
                           env=clean_env(), capture_output=True, text=True, timeout=60)
        self.assertIn("own: 1 listed, 1 set to null (+extra, null:clock) over %s" % json.dumps(os.path.relpath(self.reg, self.stack)),
                      p.stdout + p.stderr)


@unittest.skipUnless(shutil.which("aos-directive"), "aos-directive not on PATH")
class CheckPointerAt(unittest.TestCase):
    """11-13 線址二：$override 陣列裡的指示詞照它的位置 /$override/i 解，#./、#../ 從所在物件算。"""
    @classmethod
    def setUpClass(cls):
        paths = [str(REPO / "proto8" / "cmd" / "aos-agent"), str(REPO / "proto8" / "py"), str(REPO / "proto8" / "lib")]
        sys.path[:0] = paths
        try:
            from aos_agent import tools
        finally:
            del sys.path[:len(paths)]
        cls.tools = tools

    def notes(self, doc, orig):
        with tempfile.TemporaryDirectory() as d:
            d = os.path.realpath(d)
            over = os.path.join(d, "tools.json")
            with open(over, "w") as f:
                json.dump(doc, f)
            said, old = [], self.tools.note
            self.tools.note = said.append
            try:
                self.tools.check_pointer(over, os.path.join(d, orig))
            finally:
                self.tools.note = old
            return said

    def test_dot_in_list(self):
        self.assertEqual(self.notes({"$override": [{"$ref": "#./1"}, "def.json"]}, "def.json"), [])
        self.assertEqual(len(self.notes({"$override": [{"$ref": "#./1"}, "def.json"]}, "other.json")), 1)

    def test_dotdot_in_list(self):
        self.assertEqual(self.notes({"$override": [{"$ref": "#../alt"}], "alt": "def.json"}, "def.json"), [])


if __name__ == "__main__":
    unittest.main()
