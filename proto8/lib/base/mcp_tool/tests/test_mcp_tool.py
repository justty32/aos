"""mcp_tool 步 2（external-mcp 07）：包檔疊進 tools.json 後 aos-tools 看得到、叫得到外部 stdio server 的工具；isError＝CallFailed、沒有的原名＝ToolUnknown。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ENTRY = HERE.parent / "_entry"
PROTO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "demo.json"
LINE = "mcp_tool: error: "


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AOS_") and k != "FAKE_MODE"}
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AOS_HOME"] = str(PROTO)
    env.update(extra)
    return env


class McpToolThroughAosTools(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mcp-tool-"))
        (self.tmp / "mcp").mkdir()
        (self.tmp / "def").mkdir()
        (self.tmp / "ws").mkdir()
        pack = json.loads(FIXTURE.read_text())
        pack["mcp_server"]["args"] = [str(PROTO / "lib" / "tests" / "fake_mcp_stdio.py")]
        # 量 cwd 用的一格：aos-exec 跑包檔裡那格的 _entry 時，cwd 應是包檔的資料夾
        pack["mcp_tools"]["where"] = {"_entry": ["python3", "-c", "import os; print(os.getcwd())"], "_tooldef": {"description": "Print the cwd."}}
        pack["tools"]["demo_where"] = {"path": "demo.json#/mcp_tools/where"}
        self.pack = self.tmp / "mcp" / "demo.json"
        self.pack.write_text(json.dumps(pack))
        self.reg = self.tmp / "def" / "tools.json"
        self.reg.write_text(json.dumps({"$override": ["../mcp/demo.json"], "tools": {}}))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tools(self, *args, stdin="", **env):
        return subprocess.run(["aos-tools", "--file", str(self.reg)] + list(args), input=stdin, text=True,
                              capture_output=True, cwd=self.tmp / "ws", env=clean_env(AOS_WS=str(self.tmp / "ws"), **env),
                              timeout=60)

    def entry(self, *args, stdin="", cwd=None):
        return subprocess.run([str(ENTRY)] + list(args), input=stdin, text=True, capture_output=True,
                              cwd=cwd or self.tmp / "mcp", env=clean_env(AOS_WS=str(self.tmp / "ws")), timeout=60)

    def test_pack_top_level_keys_accepted(self):
        """(1) aos-tools 讀包檔：mcp_server／mcp_import／mcp_tools 三個頂層鍵放行。"""
        r = self.tools("ls", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("error:", r.stderr)
        names = {t["name"]: t for t in json.loads(r.stdout)}
        self.assertEqual(set(names), {"demo_echo", "demo_fail", "demo_image", "demo_where"})
        self.assertEqual(names["demo_echo"]["tooldef"]["description"], "[MCP server demo] Return the supplied text.")

    def test_relative_path_and_cwd_from_pack_folder(self):
        """(2) tools 裡相對的 demo.json#/mcp_tools/x 從包檔的資料夾算；_entry 的 cwd＝包檔的資料夾。"""
        names = {t["name"]: t for t in json.loads(self.tools("ls", "--json").stdout)}
        self.assertEqual(names["demo_echo"]["path"], "%s#/mcp_tools/echo" % self.pack)
        r = self.tools("call", "demo_where", "{}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(os.path.realpath(r.stdout.strip()), os.path.realpath(self.tmp / "mcp"))

    def test_call_echo(self):
        r = self.tools("call", "demo_echo", stdin='{"text": "hello from fake"}')
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "hello from fake\n", ""))

    def test_call_fail_is_callfailed(self):
        r = self.tools("call", "demo_fail", "{}")
        self.assertEqual(r.returncode, 1)
        line = LINE + "CallFailed the server reported an error"
        self.assertEqual(r.stdout, "the fake tool failed\n" + line + "\n")
        self.assertEqual(r.stderr.strip().splitlines()[-1], line)

    def test_other_content_not_shown(self):
        r = self.tools("call", "demo_image", "{}")
        self.assertEqual((r.returncode, r.stdout), (0, "[image content not shown]\n"), r.stderr)

    def test_tool_unknown(self):
        r = self.entry("--pack", "demo.json", "--tool", "nope")
        self.assertEqual(r.returncode, 1)
        line = LINE + 'ToolUnknown demo.json has no mcp_tools entry "nope"'
        self.assertEqual((r.stdout.strip(), r.stderr.strip()), (line, line))

    def test_empty_stdin_is_empty_object(self):
        r = self.entry("--pack", "demo.json", "--tool", "echo")
        self.assertEqual((r.returncode, r.stdout), (0, "\n"), r.stderr)

    def test_bad_input(self):
        for args, stdin, code in ((["--pack", "demo.json"], "", "ArgumentsBad"),
                                  (["--pack", "demo.json", "--tool", "echo", "--x", "1"], "", "FlagUnknown"),
                                  (["--pack", "demo.json", "--tool", "echo", "extra"], "", "ArgumentsBad"),
                                  (["--pack", "demo.json", "--tool", "echo"], "not json", "ArgumentsBad"),
                                  (["--pack", "demo.json", "--tool", "echo"], "[1]", "ArgumentsBad"),
                                  (["--pack", "none.json", "--tool", "echo"], "", "PackMissing")):
            r = self.entry(*args, stdin=stdin)
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stdout.startswith(LINE + code + " "), (args, r.stdout))
            self.assertEqual(r.stdout, r.stderr)

    def test_bad_timeout_is_packbad(self):
        pack = json.loads(self.pack.read_text())
        pack["mcp_tools"]["echo"]["_metainfo"]["timeout_ms"] = "soon"
        self.pack.write_text(json.dumps(pack))
        r = self.entry("--pack", "demo.json", "--tool", "echo")
        self.assertEqual(r.returncode, 1)
        self.assertIn(LINE + "PackBad ", r.stdout)

    def test_help(self):
        r = self.entry("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("usage: mcp_tool --pack FILE --tool NAME"))
        self.assertIn("CallFailed", r.stdout)

    def test_not_in_any_pack(self):
        """只給包檔的 _entry 用：lib/packs 沒有一份登記它（腦不會從預設包看到它）。"""
        for f in (PROTO / "lib" / "packs").glob("*.json"):
            self.assertNotIn("mcp_tool", f.read_text(), f)


if __name__ == "__main__":
    unittest.main()
