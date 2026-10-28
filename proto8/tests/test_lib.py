"""test_lib - proto8/lib（agent 的函式庫）：每個工具的形狀照 lib/README 的契約檢查，base 七個各自的行為，demo/agent-liv 經捷徑用庫的工具。

工具一支一支用 aos-exec 叫（arguments 從 stdin 進、stdout 是結果）；agent-liv 用內建假腦（不設 AOS_BRAIN_URL），不連真模型。
設計：proto8/thinking/2026-10-24-tool-lib.md。"""
import json, os, re, stat, subprocess, tempfile, unittest
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402

EXEC = tool("aos-exec")
LIB = ROOT / "lib"
BASE = LIB / "base"
LIV = ROOT / "demo" / "agent-liv"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY")
CODES = ("ArgumentsBad", "WsMissing", "PathBad", "FileMissing", "FileBad", "ReadFailed", "WriteFailed",
         "MkdirFailed", "MoveFailed", "CopyFailed", "TextMissing", "TextBad", "PointerBad", "PointerMissing",
         "CommandFailed", "LaunchFailed", "ExprBad", "StackMissing")
META_KEYS = ("summary", "time_ms", "resource", "side_effect", "idempotent", "deterministic", "interrupt", "parallel")
NO_WS = ("math", "clock", "run_python")                     # 不碰工作區：沒有路徑參數、不跑在 $AOS_WS
KEY_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")       # C-54：全小寫加底線


def env_with(extra=None):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(extra or {})
    return e


# agent 自己的格（10-28 agent-round）不是給腦叫的工具，沒有 _tooldef.json／_metainfo：lib/endpoint/ 整層、lib/agent/ 底下這幾個
PARTS = {"agent": ("act", "queue", "history", "round", "compact")}
PART_LAYERS = ("endpoint",)


def lib_tools():
    """lib/<層>/<名>/ 每一個工具資料夾（有 _entry 的；agent 的格除外）。"""
    return sorted(p for layer in LIB.iterdir() if layer.is_dir() and layer.name not in PART_LAYERS
                  for p in layer.iterdir() if p.is_dir() and (p / "_entry").exists()
                  and p.name not in PARTS.get(layer.name, ()))


class Shape(unittest.TestCase):
    """lib/README「一個工具長什麼樣」：三個檔、NAME 行、_tooldef.json 與 _metainfo 的形、錯誤行的格式。"""

    def test_library_has_tools(self):
        self.assertGreaterEqual(len(lib_tools()), 7)

    def test_three_files_and_name_line(self):
        for t in lib_tools():
            with self.subTest(tool=t.name):
                entry = t / "_entry"
                self.assertTrue(entry.stat().st_mode & stat.S_IXUSR, "%s 的 _entry 沒有 +x" % t.name)
                lines = entry.read_text(encoding="utf-8").splitlines()
                self.assertTrue(lines[0].startswith("#!"), "%s 的 _entry 第一行要是 shebang" % t.name)
                self.assertTrue(lines[1].startswith("# %s - " % t.name), "%s 的 _entry 第二行要是「# 名 - 一句話」" % t.name)
                spec = json.loads((t / "_tooldef.json").read_text(encoding="utf-8"))
                self.assertIsInstance(spec.get("description"), str)
                self.assertTrue(spec["description"].strip())
                params = spec.get("parameters")
                self.assertEqual(params.get("type"), "object", "%s 的 parameters 要是 object" % t.name)
                for k in (params.get("properties") or {}):
                    self.assertRegex(k, KEY_RE, "%s 的參數名 %s 不合 C-54" % (t.name, k))
                meta = json.loads((t / "_metainfo").read_text(encoding="utf-8"))
                self.assertIsInstance(meta.get("summary"), str)
                for k in META_KEYS:
                    self.assertIn(k, meta, "%s 的 _metainfo 少了 %s" % (t.name, k))
                for k in meta:
                    self.assertRegex(k, KEY_RE)

    def test_bad_stdin_is_one_line_on_both_streams(self):
        with tempfile.TemporaryDirectory() as ws:
            for t in lib_tools():
                with self.subTest(tool=t.name):
                    r = subprocess.run([EXEC, str(t)], input="not json", capture_output=True, text=True,
                                       env=env_with({"AOS_WS": ws, "AOS_STACK": ws + "/.stack/"}))
                    self.assertEqual(r.returncode, 1)
                    mine = [l for l in r.stderr.splitlines() if l.startswith(t.name + ": ")]
                    self.assertEqual(len(mine), 1, r.stderr)
                    m = re.match(r"%s: ([A-Z][A-Za-z]+) \S" % t.name, mine[0])
                    self.assertTrue(m and m.group(1) == "ArgumentsBad", mine[0])
                    self.assertEqual(r.stdout.rstrip("\n").splitlines()[-1], mine[0])

    def test_without_workspace_is_ws_missing(self):
        """直接叫 _entry（不經 aos-exec，aos-exec 一定會設 AOS_WS）：沒 AOS_WS＝WsMissing。不碰工作區的三個（math、clock、run_python）除外。"""
        for t in lib_tools():
            if t.parent.name != "base" or t.name in NO_WS:
                continue
            with self.subTest(tool=t.name):
                e = {k: v for k, v in os.environ.items() if k not in CLEAR}
                r = subprocess.run([str(t / "_entry")], input="{}", capture_output=True, text=True, env=e)
                self.assertEqual(r.returncode, 1)
                self.assertTrue(r.stderr.startswith("%s: WsMissing " % t.name), r.stderr)


class Tools(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws"
        self.ws.mkdir()

    def tool(self, name, args, timeout=30):
        """叫 lib/base/<名>；回 (結束碼, stdout, 錯誤代號或 None)。錯誤時 stderr 那行與 stdout 最後一行要一樣、格式對。"""
        stdin = args if isinstance(args, str) else json.dumps(args)
        r = subprocess.run([EXEC, str(BASE / name)], input=stdin, capture_output=True, text=True, timeout=timeout,
                           env=env_with({"AOS_WS": str(self.ws), "AOS_STACK": str(self.tmp / "stack") + "/"}))
        mine = [l for l in r.stderr.splitlines() if l.startswith(name + ": ")]
        if r.returncode == 0:
            self.assertEqual(mine, [], r.stderr)
            return 0, r.stdout, None
        self.assertEqual(len(mine), 1, r.stderr)
        m = re.match(r"%s: ([A-Z][A-Za-z]+) \S" % name, mine[0])
        self.assertTrue(m and m.group(1) in CODES, mine[0])
        self.assertEqual(r.stdout.rstrip("\n").splitlines()[-1], mine[0])
        return r.returncode, r.stdout, m.group(1)

    def put(self, rel, text):
        p = self.ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    # ---- read
    def test_read_and_paging(self):
        self.put("a.py", "one\ntwo\nthree\n")
        self.assertEqual(self.tool("read", {"path": "a.py"}), (0, "one\ntwo\nthree\n", None))
        _, out, _ = self.tool("read", {"path": "a.py", "offset": 2, "max_lines": 1})
        self.assertEqual(out, "two\n\n[檔案還有 1 行。用 offset=3 接著讀。]\n")
        self.put("big.txt", "".join("%d\n" % i for i in range(1, 3001)))
        _, out, _ = self.tool("read", {"path": "big.txt"})
        self.assertEqual(out.splitlines()[1999], "2000")
        self.assertIn("用 offset=2001 接著讀", out)
        self.assertEqual(self.tool("read", {"path": "nope"})[2], "FileMissing")
        self.assertEqual(self.tool("read", {"path": "."})[2], "FileBad")

    # ---- write
    def test_write_creates_dirs_and_keeps_mode(self):
        self.assertEqual(self.tool("write", {"path": "sub/n.txt", "content": "hi\n"})[0], 0)
        self.assertEqual((self.ws / "sub" / "n.txt").read_text(), "hi\n")
        p = self.put("run.sh", "#!/bin/sh\n")
        p.chmod(0o755)
        self.assertEqual(self.tool("write", {"path": "run.sh", "content": "#!/bin/sh\necho x\n"})[0], 0)
        self.assertTrue(p.stat().st_mode & stat.S_IXUSR)
        self.assertEqual(self.tool("write", {"path": "a"})[2], "ArgumentsBad")
        self.assertEqual(self.tool("write", {"path": ".", "content": ""})[2], "PathBad")

    # ---- edit
    def test_edit_all_or_nothing(self):
        self.put("a.py", "x = 1\ny = 2\nz = 3\n")
        code, out, _ = self.tool("edit", {"path": "a.py", "edits": [{"old_text": "x = 1", "new_text": "x = 10"},
                                                                     {"old_text": "z = 3", "new_text": "z = 30"}]})
        self.assertEqual(code, 0, out)
        self.assertEqual((self.ws / "a.py").read_text(), "x = 10\ny = 2\nz = 30\n")
        self.assertEqual(self.tool("edit", {"path": "a.py", "edits": [{"old_text": "y = 2", "new_text": "y = 20"},
                                                                       {"old_text": "nope", "new_text": "n"}]})[2],
                         "TextMissing")
        self.assertEqual((self.ws / "a.py").read_text(), "x = 10\ny = 2\nz = 30\n")      # 一處不合就都沒改
        self.put("b.txt", "a\na\n")
        self.assertEqual(self.tool("edit", {"path": "b.txt", "edits": [{"old_text": "a", "new_text": "b"}]})[2], "TextBad")
        self.assertEqual(self.tool("edit", {"path": "b.txt", "edits": [{"old_text": "a\na", "new_text": "a\na"}]})[2], "TextBad")
        self.assertEqual(self.tool("edit", {"path": "new.txt", "edits": [{"old_text": "a", "new_text": "b"}]})[2], "FileMissing")

    # ---- bash
    def test_bash_output_exit_code_and_timeout(self):
        self.put("a.txt", "")
        code, out, _ = self.tool("bash", {"command": "ls; echo err >&2; exit 3"})
        self.assertEqual(code, 0)
        self.assertIn("a.txt", out)
        self.assertIn("err", out)
        self.assertIn("[結束碼 3]", out)
        code, out, err = self.tool("bash", {"command": "echo before; sleep 5; echo after", "timeout_s": 1})
        self.assertEqual(err, "CommandFailed")
        self.assertIn("before", out)
        self.assertNotIn("after", out)
        self.assertEqual(self.tool("bash", {"command": "true", "timeout_s": 999})[2], "ArgumentsBad")
        self.assertEqual(self.tool("bash", {"command": "true", "timeout": 5})[0], 0)     # 不認得的 key 忽略（C-48）

    # ---- ls
    def test_ls_paging_and_hidden(self):
        for n in ("b.txt", "a.txt", ".h"):
            self.put(n, "")
        (self.ws / "d").mkdir()
        os.symlink("a.txt", self.ws / "l")
        _, out, _ = self.tool("ls", {})
        res = json.loads(out)
        self.assertEqual([i["name"] for i in res["items"]], ["d", "a.txt", "b.txt", "l"])    # 資料夾在前
        self.assertEqual([i["type"] for i in res["items"]], ["dir", "file", "file", "link"])
        self.assertEqual(res["items"][3]["link_to"], "a.txt")
        self.assertEqual((res["counter_items"], res["counter_hidden"]), (4, 1))
        self.assertNotIn("next_offset", res)
        res = json.loads(self.tool("ls", {"max_items": 2})[1])
        self.assertEqual(res["next_offset"], 2)
        res = json.loads(self.tool("ls", {"offset": 2, "max_items": 2})[1])
        self.assertEqual([i["name"] for i in res["items"]], ["b.txt", "l"])
        res = json.loads(self.tool("ls", {"hidden": True})[1])
        self.assertIn(".h", [i["name"] for i in res["items"]])
        self.assertEqual(self.tool("ls", {"path": "a.txt"})[2], "FileBad")
        self.assertEqual(self.tool("ls", {"path": "zz"})[2], "FileMissing")
        self.assertEqual(self.tool("ls", {"max_items": 0})[2], "ArgumentsBad")

    # ---- json_read
    def test_json_read_folds_and_pointer(self):
        self.put("c.json", json.dumps({"a": {"b": [1, 2, 3], "c": {"d": 1}}, "s": "x" * 600, "n": 5}))
        res = json.loads(self.tool("json_read", {"path": "c.json"})[1])
        self.assertEqual(res["value"]["a"], {"type": "object", "keys": ["b", "c"]})
        self.assertEqual(res["value"]["s"]["type"], "string")
        self.assertEqual(res["value"]["s"]["counter_chars"], 600)
        self.assertEqual(res["value"]["n"], 5)
        res = json.loads(self.tool("json_read", {"path": "c.json", "pointer": "/a", "depth": 2})[1])
        self.assertEqual(res["value"], {"b": [1, 2, 3], "c": {"d": 1}})
        res = json.loads(self.tool("json_read", {"path": "c.json", "pointer": "/a/b/1"})[1])
        self.assertEqual(res["value"], 2)
        self.assertEqual(self.tool("json_read", {"path": "c.json", "pointer": "/a/zz"})[2], "PointerMissing")
        self.assertEqual(self.tool("json_read", {"path": "c.json", "pointer": "a"})[2], "PointerBad")
        self.put("bad.json", "{")
        self.assertEqual(self.tool("json_read", {"path": "bad.json"})[2], "FileBad")

    # ---- json_edit
    def test_json_edit_all_or_nothing(self):
        self.put("c.json", json.dumps({"a": {"b": [1, 2]}, "c": "x"}))
        res = json.loads(self.tool("json_edit", {"path": "c.json", "set": {"/a/b/-": 3, "/d/e": True, "/a/b/0": 0},
                                                 "del": ["/c"]})[1])
        self.assertEqual((res["counter_set"], res["counter_del"]), (3, 1))
        self.assertEqual(json.loads((self.ws / "c.json").read_text()), {"a": {"b": [0, 2, 3]}, "d": {"e": True}})
        before = (self.ws / "c.json").read_text()
        self.assertEqual(self.tool("json_edit", {"path": "c.json", "set": {"/a/b/9": 1}, "del": ["/d"]})[2], "PointerMissing")
        self.assertEqual((self.ws / "c.json").read_text(), before)                          # 一處不合整份不寫
        self.assertEqual(self.tool("json_edit", {"path": "c.json", "del": ["/zz"]})[2], "PointerMissing")
        self.assertEqual(self.tool("json_edit", {"path": "c.json", "set": {"": 1}})[2], "PointerBad")
        self.assertEqual(self.tool("json_edit", {"path": "c.json"})[2], "ArgumentsBad")
        self.assertEqual(self.tool("json_edit", {"path": "nope.json", "set": {"/a": 1}})[2], "FileMissing")

    # ---- 沙盒
    def test_paths_cannot_leave_workspace(self):
        outside = self.tmp / "secret.txt"
        outside.write_text("s")
        os.symlink(outside, self.ws / "link_out")
        for name, args in (("read", {"path": "../secret.txt"}), ("read", {"path": "link_out"}),
                           ("write", {"path": "../x", "content": ""}), ("edit", {"path": "../secret.txt", "edits": [{"old_text": "s", "new_text": "t"}]}),
                           ("ls", {"path": ".."}), ("json_read", {"path": "../secret.txt"}),
                           ("json_edit", {"path": "../secret.txt", "set": {"/a": 1}})):
            with self.subTest(tool=name):
                self.assertEqual(self.tool(name, args)[2], "PathBad")
        self.assertEqual(outside.read_text(), "s")
        self.assertEqual(self.tool("read", {"path": str(self.ws / "link_out")})[2], "PathBad")     # 絕對路徑也一樣


class Liv(unittest.TestCase):
    """demo/agent-liv：tools/ 裡是捷徑、指到 lib/base；假腦叫一次 ls，答案帶 total；小格落在 $AOS_STACK/ls/。"""

    def test_tools_are_relative_links_into_lib(self):
        links = {p.name: p for p in (LIV / "tools").iterdir() if p.is_symlink()}
        self.assertEqual(set(links), {"read", "write", "edit", "bash", "ls", "json_read", "json_edit"})
        for name, p in links.items():
            self.assertFalse(os.readlink(p).startswith("/"), "%s 要是相對捷徑" % name)
            self.assertEqual(p.resolve(), (BASE / name).resolve())
        self.assertTrue((LIV / "tools" / "clock").is_dir() and not (LIV / "tools" / "clock").is_symlink())
        self.assertTrue((LIV / "_metainfo").exists())

    def test_fake_brain_uses_library_ls_through_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            (ws / "new").mkdir(parents=True)
            (ws / "new" / "q1.txt").write_text("工作區裡有幾個檔？\n", encoding="utf-8")
            (ws / "x.txt").write_text("")
            r = subprocess.run([EXEC, "--ws", str(ws), str(LIV)], capture_output=True, text=True, timeout=120,
                               env=env_with())
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stderr, "")
            answer = (ws / "out" / "q1.txt").read_text(encoding="utf-8")
            self.assertTrue(answer.startswith("FAKE ANSWER to: 工作區裡有幾個檔？（ls said: "), answer)
            history = [json.loads(l) for l in (ws / ".stack" / "history.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([m["role"] for m in history], ["user", "assistant", "tool", "assistant"])
            listed = json.loads(history[2]["content"])
            self.assertIn("x.txt", [i["name"] for i in listed["items"]])
            self.assertTrue((ws / ".stack" / "ls").is_dir())                 # 工具的小格（P-17）
            self.assertEqual(list((ws / "new").iterdir()), [])
            self.assertEqual(sorted(p.name for p in (ws / "done").iterdir()), ["q1.txt"])

    def test_tool_error_goes_back_to_brain(self):
        """庫的工具退非 0（edit 找不到原文）：act 不停，把 stdout 加結束碼接成 tool 訊息；叫了沒有的工具也一樣（10-24 真腦實測前是 ToolFailed 停下、重跑永遠卡同一個）。"""
        with tempfile.TemporaryDirectory() as tmp:
            ws, st = Path(tmp) / "ws", Path(tmp) / "st"
            ws.mkdir(); st.mkdir()
            (ws / "a.txt").write_text("hi\n")
            calls = [{"id": "c1", "type": "function", "function": {"name": "edit", "arguments": json.dumps(
                {"path": "a.txt", "edits": [{"old_text": "hello", "new_text": "bye"}]})}},
                     {"id": "c2", "type": "function", "function": {"name": "nope", "arguments": "{}"}}]
            (st / "history.jsonl").write_text(json.dumps({"role": "user", "content": "q"}) + "\n" + json.dumps(
                {"role": "assistant", "content": None, "tool_calls": calls}) + "\n", encoding="utf-8")
            r = subprocess.run(["python3", "act.py"], cwd=LIV, capture_output=True, text=True, timeout=60,
                               env=env_with({"AOS_STACK": str(st) + "/", "AOS_WS": str(ws)}))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("agent-liv: ToolFailed edit 結束碼 1（回給腦）", r.stderr)
            tools = [json.loads(l) for l in (st / "history.jsonl").read_text(encoding="utf-8").splitlines()][2:]
            self.assertEqual([m["tool_call_id"] for m in tools], ["c1", "c2"])
            self.assertTrue(tools[0]["content"].startswith("edit: TextMissing "), tools[0]["content"])
            self.assertTrue(tools[0]["content"].endswith("(工具 edit 結束碼 1)\n"), tools[0]["content"])
            self.assertTrue(tools[1]["content"].startswith("act: ToolUnknown nope（能叫的："), tools[1]["content"])
            self.assertEqual((ws / "a.txt").read_text(), "hi\n")


if __name__ == "__main__":
    unittest.main()
