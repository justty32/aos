"""test_file_tools - 資料夾與檔案的漸進工具：ls、stat、view、json_edit、mkdir、move、copy、trash（原 demo/file-tools，10-24 遷移進 proto8/lib/base），結果一律 JSON。

工具一支一支用 aos-exec 叫；錯照 lib 契約：stderr 一行、stdout 最後一行同一行、退 1（遷移前 stdout 是 {"error": 那行}）。
agent-pip（tools/ 全部掛 lib/base）用 test_dan 的假 server 照劇本逐層看一個 aos agent 資料夾、改 loop.json。
json_edit 經 aos-json（proto8/impls/aos-json）寫檔。不連真模型。設計：proto8/thinking/2026-10-24-pi-tools.md、2026-10-24-tool-lib.md。"""
import json, os, re, shutil, subprocess, tempfile, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
from test_dan import FakeBrain, call, tool_reply, answer  # noqa: E402

EXEC = tool("aos-exec")
TOOLS = ROOT / "lib" / "base"                       # 10-24 遷移前是 demo/file-tools
PIP = str(ROOT / "demo" / "agent-pip")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY")
CODES = ("ArgumentsBad", "WsMissing", "PathBad", "FileMissing", "FileBad", "ReadFailed", "WriteFailed", "MkdirFailed",
         "MoveFailed", "CopyFailed", "PointerBad", "PointerMissing", "LaunchFailed")


def env_with(extra=None):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))           # 含 aos-json（json_edit 用）
    e.update(extra or {})
    return e


class Tools(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws"
        shutil.copytree(ROOT / "demo" / "agent-dan", self.ws / "agent-dan", ignore=shutil.ignore_patterns("__pycache__"))

    def tool(self, name, args):
        """回 (結束碼, stdout 解開的 JSON 或 None, 錯誤代號或 None)；成功時 stdout 是一份 JSON，錯時最後一行＝stderr 那行。"""
        r = subprocess.run([EXEC, str(TOOLS / name)], input=json.dumps(args), capture_output=True, text=True, timeout=30,
                           env=env_with({"AOS_WS": str(self.ws), "AOS_STACK": str(self.tmp / "stack") + "/"}))
        mine = [l for l in r.stderr.splitlines() if l.startswith(name + ": ")]
        if r.returncode == 0:
            self.assertEqual(mine, [], r.stderr)
            return 0, json.loads(r.stdout), None
        self.assertEqual(len(mine), 1, r.stderr)
        m = re.match(r"%s: ([A-Z][A-Za-z]+) \S" % name, mine[0])
        self.assertTrue(m and m.group(1) in CODES, mine[0])
        self.assertEqual(r.stdout.rstrip("\n").splitlines()[-1], mine[0])
        return r.returncode, None, m.group(1)

    def test_ls(self):
        _, res, _ = self.tool("ls", {})
        self.assertEqual(res["items"][0]["name"], "agent-dan")
        self.assertEqual(res["items"][0]["aos"], ["_entry", ".env", "loop.json", "fsm.json"])
        _, res, _ = self.tool("ls", {"path": "agent-dan"})
        items = {i["name"]: i for i in res["items"]}
        self.assertEqual([i["type"] for i in res["items"][:2]], ["dir", "dir"])          # 資料夾在前
        self.assertEqual(items["fsm.json"]["keys"], ["_entry", "start", "states"])
        self.assertEqual((items["idle"]["children"], items["idle"]["aos"]), (1, ["_entry"]))
        self.assertTrue(items["_entry"]["exec"])
        self.assertNotIn(".env", items)
        self.assertEqual(res["hidden"], 1)
        _, res, _ = self.tool("ls", {"path": "agent-dan", "hidden": True})
        self.assertIn(".env", [i["name"] for i in res["items"]])

    def test_ls_pages(self):
        d = self.ws / "many"
        d.mkdir()
        for i in range(250):
            (d / ("f%03d" % i)).write_text("")
        _, res, _ = self.tool("ls", {"path": "many"})
        self.assertEqual((res["total"], len(res["items"]), res["next_offset"]), (250, 100, 100))
        _, res, _ = self.tool("ls", {"path": "many", "offset": 200})
        self.assertEqual((len(res["items"]), res["items"][0]["name"]), (50, "f200"))
        self.assertNotIn("next_offset", res)
        self.assertEqual(self.tool("ls", {"path": "many", "limit": 0})[2], "ArgumentsBad")

    def test_stat(self):
        _, res, _ = self.tool("stat", {"path": "agent-dan/fsm.json"})
        self.assertEqual((res["format"], res["top"]), ("json", {"type": "object", "keys": 3}))
        _, res, _ = self.tool("stat", {"path": "agent-dan/brain.py"})
        self.assertEqual((res["format"], res["text"], res["exec"]), ("python", True, False))
        _, res, _ = self.tool("stat", {"path": "agent-dan/idle"})
        self.assertEqual((res["type"], res["aos"]), ("dir", ["_entry"]))
        # mtime 跟 ls 同一種寫法（UTC、帶 +00:00），10-24 真腦實測前 stat 印本地時間、沒標時區
        ls_items = {i["name"]: i for i in self.tool("ls", {"path": "agent-dan"})[1]["items"]}
        self.assertEqual(res["mtime"], ls_items["idle"]["mtime"])
        (self.ws / "l").symlink_to("agent-dan/loop.json")
        self.assertEqual(self.tool("stat", {"path": "l"})[1]["link_to"], "agent-dan/loop.json")
        self.assertEqual(self.tool("stat", {"path": "nope"})[2], "FileMissing")

    def test_view_json_layers(self):
        big = {"states": {("s%d" % i): {"exec": "x" * 50, "next": "s%d" % (i + 1)} for i in range(40)}, "start": "s0"}
        (self.ws / "big.json").write_text(json.dumps(big))
        _, res, _ = self.tool("view", {"path": "big.json"})
        self.assertNotIn("value", res)                                   # 大的摺起來
        self.assertEqual(res["children"], [{"key": "states", "type": "object", "keys": 40},
                                           {"key": "start", "type": "string", "value": "s0"}])
        _, res, _ = self.tool("view", {"path": "big.json", "pointer": "/states/s3"})
        self.assertEqual(res["value"], {"exec": "x" * 50, "next": "s4"})  # 小的直接給
        _, res, _ = self.tool("view", {"path": "big.json", "pointer": "/states/s3/next"})
        self.assertEqual(res["value"], "s4")
        self.assertEqual(self.tool("view", {"path": "big.json", "pointer": "/states/zz"})[2], "PointerMissing")
        self.assertEqual(self.tool("view", {"path": "agent-dan/brain.py", "pointer": "/a"})[2], "FileBad")
        _, res, _ = self.tool("view", {"path": "big.json", "start": 1, "end": 1})   # 給行號＝當文字看
        self.assertEqual(res["format"], "text")

    def test_view_text_outline_then_segment(self):
        src = "".join("def f%d(x):\n    return x + %d\n\n" % (i, i) for i in range(100))
        (self.ws / "m.py").write_text(src)
        _, res, _ = self.tool("view", {"path": "m.py"})
        self.assertNotIn("text", res)
        self.assertEqual(res["outline"][5], {"line": 16, "end": 17, "name": "f5", "kind": "def"})
        _, res, _ = self.tool("view", {"path": "m.py", "start": 16, "end": 17})
        self.assertEqual(res["text"], "def f5(x):\n    return x + 5\n")
        (self.ws / "d.md").write_text("# A\n" + "x\n" * 300 + "## B\n```\n# not\n```\n")
        _, res, _ = self.tool("view", {"path": "d.md"})
        self.assertEqual(res["outline"], [{"line": 1, "level": 1, "name": "A"}, {"line": 302, "level": 2, "name": "B"}])
        self.assertEqual(self.tool("view", {"path": "m.py", "start": 999})[2], "ArgumentsBad")

    def test_json_edit(self):
        f = self.ws / "agent-dan" / "loop.json"
        _, res, _ = self.tool("json_edit", {"path": "agent-dan/loop.json", "set": {"/max": 80, "/note/who": "pip"}})
        self.assertEqual(res, {"path": "agent-dan/loop.json", "set": 2, "del": 0, "top": ["exec", "max", "note"]})
        self.assertEqual(json.loads(f.read_text()), {"exec": "fsm.json", "max": 80, "note": {"who": "pip"}})
        before = f.read_text()
        self.assertEqual(self.tool("json_edit", {"path": "agent-dan/loop.json", "del": ["/note", "/nope"]})[2],
                         "PointerMissing")
        self.assertEqual(f.read_text(), before)                         # 一個指不到＝都不改
        self.tool("json_edit", {"path": "agent-dan/loop.json", "del": ["/note"]})
        self.assertEqual(json.loads(f.read_text()), {"exec": "fsm.json", "max": 80})
        self.assertEqual(self.tool("json_edit", {"path": "agent-dan/brain.py", "set": {"/a": 1}})[2], "FileBad")
        self.assertEqual(self.tool("json_edit", {"path": "agent-dan/loop.json"})[2], "ArgumentsBad")
        self.assertEqual(self.tool("json_edit", {"path": "agent-dan/loop.json", "del": [""]})[2], "PointerBad")

    def test_folder_changes(self):
        self.assertEqual(self.tool("mkdir", {"path": "a/b"})[1], {"path": "a/b", "created": True})
        self.assertEqual(self.tool("mkdir", {"path": "a/b"})[1]["created"], False)
        self.assertEqual(self.tool("mkdir", {"path": "agent-dan/loop.json"})[2], "FileBad")
        _, res, _ = self.tool("copy", {"from": "agent-dan", "to": "a/agent-x"})
        self.assertEqual(res["files"], len([p for p in (self.ws / "agent-dan").rglob("*") if p.is_file()]))
        self.assertEqual(self.tool("copy", {"from": "agent-dan", "to": "a/agent-x"})[2], "FileBad")    # 不蓋
        self.assertEqual(self.tool("copy", {"from": "agent-dan", "to": "agent-dan/in"})[2], "PathBad")
        self.tool("move", {"from": "a/agent-x/system.txt", "to": "a/agent-x/sys/system.txt"})
        self.assertTrue((self.ws / "a/agent-x/sys/system.txt").exists())
        self.assertEqual(self.tool("move", {"from": "a/agent-x/act.py", "to": "a/agent-x/brain.py"})[2], "FileBad")
        self.assertEqual(self.tool("move", {"from": "nope", "to": "x"})[2], "FileMissing")
        self.assertEqual(sorted(p.name for p in (self.ws / "a").iterdir()), ["agent-x", "b"])     # 沒留暫存

    def test_trash_is_recoverable(self):
        _, res, _ = self.tool("trash", {"path": "agent-dan/system.txt"})
        self.assertFalse((self.ws / "agent-dan/system.txt").exists())
        self.assertTrue(res["to"].startswith(".trash/") and res["to"].endswith("/agent-dan/system.txt"), res)
        self.assertTrue((self.ws / res["to"]).exists())
        self.assertEqual(self.tool("trash", {"path": res["to"]})[2], "PathBad")          # 垃圾桶裡的不再丟
        (self.ws / "agent-dan/system.txt").write_text("新的\n")
        _, res2, _ = self.tool("trash", {"path": "agent-dan/system.txt"})                 # 同一秒再丟也不撞
        self.assertNotEqual(res["to"], res2["to"])
        self.tool("move", {"from": res["to"], "to": "agent-dan/system.txt"})              # 救回來
        self.assertTrue((self.ws / "agent-dan/system.txt").read_text().startswith("你是"))
        self.assertEqual(self.tool("trash", {"path": "."})[2], "PathBad")

    def test_path_escape_blocked(self):
        (self.tmp / "secret.txt").write_text("secret\n")
        (self.ws / "out").symlink_to(self.tmp)
        cases = [("ls", {"path": ".."}), ("ls", {"path": "out"}), ("stat", {"path": "../secret.txt"}),
                 ("view", {"path": "out/secret.txt"}), ("view", {"path": str(self.tmp / "secret.txt")}),
                 ("mkdir", {"path": "../x"}), ("move", {"from": "agent-dan", "to": "../x"}),
                 ("move", {"from": "out/secret.txt", "to": "s.txt"}), ("copy", {"from": "out/secret.txt", "to": "s"}),
                 ("copy", {"from": "agent-dan", "to": "out/x"}), ("trash", {"path": "out/secret.txt"}),
                 ("trash", {"path": "../secret.txt"}), ("json_edit", {"path": "out/x.json", "set": {"/a": 1}})]
        for name, a in cases:
            with self.subTest(tool=name, args=a):
                self.assertEqual(self.tool(name, a)[2], "PathBad")
        self.assertEqual((self.tmp / "secret.txt").read_text(), "secret\n")
        self.assertFalse((self.tmp / "x").exists())
        _, res, _ = self.tool("trash", {"path": "out"})                  # 連結本身可以丟，不跟進去
        self.assertTrue((self.tmp / "secret.txt").exists())

    def test_tool_json_shape(self):
        for d in sorted(TOOLS / n for n in ("ls", "stat", "view", "json_edit", "mkdir", "move", "copy", "trash")):
            if d.is_dir():
                spec = json.loads((d / "tool.json").read_text())
                self.assertEqual(set(spec), {"description", "parameters"}, d.name)


class AgentPipExplores(unittest.TestCase):
    """agent-pip 逐層看一個 aos agent 資料夾、改它的 loop.json（假 server 照劇本）。"""

    def test_explore_and_edit(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            ws = tmp / "ws"
            shutil.copytree(ROOT / "demo" / "agent-dan", ws / "proj" / "agent-dan",
                            ignore=shutil.ignore_patterns("__pycache__"))
            (ws / "new").mkdir()
            (ws / "new" / "q1.txt").write_text("把 proj 底下那隻 agent 的 loop 次數上限改成 80。\n")
            b = FakeBrain([
                tool_reply(call("c1", "ls", {"path": "proj"})),
                tool_reply(call("c2", "view", {"path": "proj/agent-dan/loop.json"})),
                tool_reply(call("c3", "json_edit", {"path": "proj/agent-dan/loop.json", "set": {"/max": 80}})),
                answer("proj/agent-dan/loop.json 的 max 改成 80 了。")])
            self.addCleanup(b.close)
            r = subprocess.run([EXEC, "--ws", "ws", PIP], capture_output=True, text=True, cwd=tmp, timeout=120,
                               env=env_with({"AOS_BRAIN_URL": b.url, "AOS_STACK": str(tmp / "stack") + "/"}))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads((ws / "proj/agent-dan/loop.json").read_text())["max"], 80)
            h = [json.loads(l) for l in (tmp / "stack" / "history.jsonl").read_text().splitlines()]
            tools = {m["tool_call_id"]: json.loads(m["content"]) for m in h if m["role"] == "tool"}
            self.assertEqual(tools["c1"]["items"][0]["aos"], ["_entry", ".env", "loop.json", "fsm.json"])
            self.assertEqual(tools["c2"]["value"], {"exec": "fsm.json", "max": 40})
            names = [t["function"]["name"] for t in b.requests[0]["tools"]]
            self.assertEqual(names, sorted(["read", "write", "edit", "bash", "ls", "stat", "view", "json_edit",
                                            "mkdir", "move", "copy", "trash"]))


if __name__ == "__main__":
    unittest.main()
