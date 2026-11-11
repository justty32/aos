"""檔案工具拿掉工作區限制（11-10 tool-packs，使用者「3.對」）：相對從 $AOS_WS、絕對照用，工作區外也能讀寫改搬。"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1] / "base"


class OutsideTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ws, self.out = self.root / "ws", self.root / "out"
        self.ws.mkdir()
        self.out.mkdir()
        self.env = dict(os.environ, AOS_WS=str(self.ws))
        aos_json = BASE.parents[1] / "impls/aos-json/bin"
        self.env["PATH"] = "%s:%s" % (aos_json, self.env.get("PATH", ""))

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, tool, **args):
        r = subprocess.run([str(BASE / tool / "_entry")], input=json.dumps(args), text=True,
                           capture_output=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_every_file_tool_reaches_outside(self):
        f = str(self.out / "a.txt")
        self.call("write", path=f, content="one\n")
        self.assertEqual(self.call("read", path="../out/a.txt"), "one\n")
        self.call("edit", path=f, edits=[{"old_text": "one", "new_text": "two"}])
        self.assertEqual((self.out / "a.txt").read_text(), "two\n")
        self.assertEqual(json.loads(self.call("stat", path=f))["path"], f)
        self.assertEqual(json.loads(self.call("view", path=f))["text"], "two\n")
        self.assertEqual(self.call("ls", path="../out"), "a.txt\tfile\n")               # default: NAME TAB TYPE
        self.assertEqual(self.call("ls", path="../out", long=True).split("\t")[:3], ["a.txt", "file", "4"])
        self.assertEqual(json.loads(self.call("ls", path="../out", json=True))["items"][0]["name"], "a.txt")
        self.call("mkdir", path=str(self.out / "d"))
        self.call("copy", **{"from": f, "to": "b.txt"})
        self.call("move", **{"from": "b.txt", "to": str(self.out / "c.txt")})
        self.assertEqual(json.loads(self.call("trash", path=str(self.out / "c.txt")))["to"].split("/", 2)[2],
                         str(self.out / "c.txt").lstrip("/"))
        self.call("write", path="../out/j.json", content='{"a": 1}')
        self.call("json_write", path="../out/j.json", set={"/b": 2})
        self.assertEqual(json.loads(self.call("json_read", path=str(self.out / "j.json")))["value"], {"a": 1, "b": 2})
        self.assertTrue(self.call("shell", command="cat ../out/a.txt").startswith("two\n"))

    def test_json_write_quoted_pointer_is_unwrapped(self):
        for key in ("'/n'", '"/n"'):                     # 11-11 晚 gemma 把鍵包上引號：剝掉引號照用
            (self.ws / "q.json").write_text('{"n": 1}')
            self.call("json_write", path="q.json", set={key: 2})
            self.assertEqual(json.loads((self.ws / "q.json").read_text()), {"n": 2})
        r = subprocess.run([str(BASE / "json_write" / "_entry")], input=json.dumps({"path": "q.json", "set": {"'n'": 2}}),
                           text=True, capture_output=True, env=self.env)
        self.assertIn("PointerBad pointer must start with /", r.stdout)

    def test_relative_needs_workspace(self):
        env = {k: v for k, v in self.env.items() if k != "AOS_WS"}
        r = subprocess.run([str(BASE / "read" / "_entry")], input='{"path": "a.txt"}', text=True, capture_output=True, env=env)
        self.assertIn("error: WsMissing", r.stdout)
        (self.out / "x").write_text("x\n")
        r = subprocess.run([str(BASE / "read" / "_entry")], input=json.dumps({"path": str(self.out / "x")}), text=True, capture_output=True, env=env)
        self.assertEqual(r.stdout, "x\n")


if __name__ == "__main__":
    unittest.main()
