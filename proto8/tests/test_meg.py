"""test_meg - 跑 demo/agent-meg（有長期記憶庫的問答 agent）：第一題存、換 stack 後第二題靠記憶庫答。

假 server 照劇本回（劇本與假 server 借 test_dan 的）；記憶庫工具 tools/memory 另外直接測。
設計：proto8/thinking/2026-10-24-memory.md。連真模型的那個 localhost:4000 連不上就 skip。"""
import json, os, re, subprocess, sys, tempfile, unittest, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
from test_dan import FakeBrain, call, tool_reply, answer, REAL_URL  # noqa: E402
EXEC = tool("aos-exec")
MEG = ROOT / "demo" / "agent-meg"
MEMORY = MEG / "tools" / "memory" / "_entry"
CODES = ("BrainFailed", "ReplyBad", "ToolUnknown", "ArgumentsBad", "ToolFailed", "StackMissing",
         "QuestionMissing", "HistoryBad", "HeapBad")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_HEAP")

MARK = "## 記憶庫（每題開頭自動附上"
LEARN = "記住：我寫 Python 一律用 4 個空格縮排。另外 aos 專案只能從 repo 根目錄建置。"
ASK = "我寫 Python 縮排用幾個空格？aos 要在哪裡建置？"


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


def meg_errors(stderr):
    found = []
    for line in stderr.splitlines():
        if line.startswith("agent-meg:"):
            m = re.match(r"agent-meg: ([A-Z][A-Za-z]+) \S", line)
            assert m and m.group(1) in CODES, "agent-meg 的錯誤行格式不對：%r" % line
            found.append(m.group(1))
    return found


def save(cid, kind, title, text):
    return call(cid, "memory", {"op": "save", "kind": kind, "title": title, "text": text})


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)
        self.heap = self.ws / ".heap"

    def brain(self, *script):
        b = FakeBrain(script)
        self.addCleanup(b.close)
        return b

    def meg(self, question, url=None, stack=".stack", env=None, name="q.txt"):
        (self.ws / "new" / name).write_text(question)
        e = {"AOS_STACK": str(self.ws / stack) + "/"}
        if url:
            e["AOS_BRAIN_URL"] = url
        e.update(env or {})
        return run(EXEC, "--ws", "ws", str(MEG), env=e, cwd=self.tmp, timeout=60)

    def memory(self, args, heap=None):
        r = run(str(MEMORY), input=json.dumps(args, ensure_ascii=False),
                env={"AOS_HEAP": str(heap or self.heap)})
        return r

    def system_of(self, request):
        return next((m["content"] for m in request["messages"] if m["role"] == "system"), "")

    def test_learn_then_recall_with_new_stack(self):
        """第一題存兩筆；換一個全新的 stack（對話清空）問第二題：system 裡附了那兩筆，history 只有第二題。"""
        b1 = self.brain(tool_reply(save("c1", "prefs", "Python 縮排", "寫 Python 一律用 4 個空格縮排。"),
                                   save("c2", "facts", "aos 建置位置", "aos 專案只能從 repo 根目錄建置。")),
                        answer("記住了。"))
        r = self.meg(LEARN, b1.url, stack="s1", name="q1.txt")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(meg_errors(r.stderr), [])
        self.assertIn("memory", [t["function"]["name"] for t in b1.requests[0]["tools"]])
        self.assertNotIn(MARK, self.system_of(b1.requests[0]))          # 第一題時庫是空的：不附
        self.assertIn("已存 prefs/001", [m.get("content") for m in b1.requests[1]["messages"]
                                         if m["role"] == "tool"][0])
        self.assertIn(MARK, self.system_of(b1.requests[1]))               # 剛存的，同一題下一輪就附上
        self.assertTrue((self.heap / "prefs" / "001.md").exists())
        self.assertTrue((self.heap / "facts" / "001.md").exists())

        b2 = self.brain(answer("4 個空格；在 repo 根目錄建置。"))
        r = self.meg(ASK, b2.url, stack="s2", name="q2.txt")
        self.assertEqual(r.returncode, 0, r.stderr)
        sys_text = self.system_of(b2.requests[0])
        self.assertIn("[prefs/001] Python 縮排", sys_text)                 # 偏好全附
        self.assertIn("[facts/001] aos 建置位置", sys_text)                # 事實照題目找到
        self.assertEqual([m["role"] for m in b2.requests[0]["messages"] if m["role"] != "system"], ["user"])
        hist = (self.ws / "s2" / "history.jsonl").read_text()
        self.assertNotIn(MARK, hist)                                   # 記憶只在 system，不進 history
        self.assertEqual((self.ws / "out" / "q2.txt").read_text(), "4 個空格；在 repo 根目錄建置。\n")

    def test_heap_location_from_env(self):
        """AOS_HEAP 有設就用它（兩隻 agent 指同一個＝共用）；沒設＝$AOS_WS/.heap/。"""
        shared = self.tmp / "shared-heap"
        b = self.brain(tool_reply(save("c1", "facts", "f", "內容")), answer("ok"))
        r = self.meg("q", b.url, env={"AOS_HEAP": str(shared)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((shared / "facts" / "001.md").exists())
        self.assertFalse(self.heap.exists())

    def test_fake_brain_without_url(self):
        r = self.meg("hi")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("FAKE ANSWER to: hi（附了記憶 0 字）", (self.ws / "out" / "q.txt").read_text())

    def test_heap_bad_stops_brain(self):
        """索引壞了：think 一開頭就 HeapBad、退 1、history 不接腦的回覆。"""
        (self.heap / "facts").mkdir(parents=True)
        (self.heap / "facts" / "index.json").write_text("{壞")
        b = self.brain(answer("不該到這"))
        r = self.meg("q", b.url)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("HeapBad", meg_errors(r.stderr))
        self.assertEqual(b.requests, [])

    def test_heap_bad_in_tool(self):
        """索引壞了：工具 memory: HeapBad 退 1（10-24 遷移後 agent-meg 的 act 把它回給腦、不停；think 一開頭就會先 HeapBad 停下）。"""
        (self.heap / "facts").mkdir(parents=True)
        (self.heap / "facts" / "index.json").write_text("[]")
        r = self.memory({"op": "search", "query": "x"})
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^memory: HeapBad ")

    # ---- 工具本體 ----
    def test_upsert_search_read_forget(self):
        self.assertIn("已存 prefs/001", self.memory({"op": "save", "kind": "prefs", "title": "縮排",
                                                     "text": "4 個空格", "tags": ["python"]}).stdout)
        out = self.memory({"op": "save", "kind": "prefs", "title": "縮排", "text": "2 個空格"}).stdout
        self.assertIn("已更新 prefs/001", out)
        self.assertIn("舊內容：4 個空格", out)                              # 衝突時把舊的給模型看
        self.assertIn("2 個空格", self.memory({"op": "read", "id": "prefs/001"}).stdout)
        self.assertIn("prefs/001", self.memory({"op": "search", "query": "縮排要幾個空格"}).stdout)
        self.assertIn("已忘記", self.memory({"op": "forget", "id": "prefs/001", "reason": "錯"}).stdout)
        self.assertTrue((self.heap / "archive" / "prefs" / "001.md").exists())
        self.assertIn("沒有找到", self.memory({"op": "search", "query": "縮排"}).stdout)
        rows = json.loads((self.heap / "prefs" / "index.json").read_text())["rows"]
        self.assertEqual((rows[0]["status"], rows[0]["reason"]), ("forgotten", "錯"))
        self.assertIn("已存 prefs/002", self.memory({"op": "save", "kind": "prefs", "title": "縮排",
                                                     "text": "4"}).stdout)   # 忘了的不再被覆蓋、號碼不重用

    def test_model_mistakes_are_one_line_errors(self):
        """模型用錯：照 lib 契約 stderr 與 stdout 各一行「memory: 代號 原因」、退 1（10-24 遷移前是 stdout「錯誤：…」退 0）。"""
        for args, code in (({"op": "nope"}, "OpUnknown"), ({"op": "save", "kind": "x", "title": "t", "text": "t"}, "ArgumentsBad"),
                           ({"op": "save", "kind": "facts", "title": "", "text": "t"}, "ArgumentsBad"),
                           ({"op": "save", "kind": "facts", "title": "t", "text": "x" * 5000}, "ArgumentsBad"),
                           ({"op": "read", "id": "../../etc/passwd"}, "MemoryMissing"),
                           ({"op": "forget", "id": "facts/999"}, "MemoryMissing")):
            r = self.memory(args)
            self.assertEqual(r.returncode, 1, args)
            self.assertTrue(r.stderr.startswith("memory: %s " % code), (args, r.stderr))
            self.assertEqual(r.stdout.strip(), r.stderr.strip())

    def test_model_mistake_fed_back_to_brain(self):
        """agent-meg 叫 memory 用錯：act 把那行回給腦、不停（同 agent-pip），腦改對再存、答完。"""
        b = self.brain(tool_reply(call("c1", "memory", {"op": "keep"})),
                       tool_reply(save("c2", "facts", "埠號", "服務跑在 8080。")),
                       answer("記住了。"))
        r = self.meg("記住服務跑在 8080。", b.url)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ToolFailed", meg_errors(r.stderr))
        tools = [m["content"] for m in b.requests[1]["messages"] if m["role"] == "tool"]
        self.assertTrue(tools[0].startswith("memory: OpUnknown "), tools[0])
        self.assertTrue(tools[0].endswith("(工具 memory 結束碼 1)\n"), tools[0])
        self.assertTrue((self.heap / "facts" / "001.md").exists())

    def test_parallel_saves_do_not_clobber(self):
        """20 個行程同時寫同一類：20 筆都在、號碼不重複（flock）。"""
        def one(i):
            return self.memory({"op": "save", "kind": "outcomes", "title": "事 %d" % i, "text": "結論 %d" % i})
        with ThreadPoolExecutor(10) as ex:
            rs = list(ex.map(one, range(20)))
        self.assertTrue(all(r.returncode == 0 for r in rs))
        rows = json.loads((self.heap / "outcomes" / "index.json").read_text())["rows"]
        self.assertEqual(len(rows), 20)
        self.assertEqual(len({r["id"] for r in rows}), 20)
        top = json.loads((self.heap / "index.json").read_text())
        self.assertEqual(top["contract"], "wf-table/1")
        self.assertEqual([(r["kind"], r["count"]) for r in top["rows"]], [("outcomes", "20")])

    def test_context_budget(self):
        """偏好多到超過上限：只附一部分、說還有。"""
        sys.path.insert(0, str(MEG / "tools" / "memory"))
        sys.dont_write_bytecode = True                   # tools/memory 是捷徑 → lib/aos/memory：不在庫裡留 __pycache__
        import heap
        h = heap.Heap(str(self.heap))
        for i in range(30):
            h.save("prefs", "偏好 %d" % i, "內容" * 50)
        text = h.context("隨便")
        self.assertIn("偏好太多", text)
        self.assertLess(len(text), 2500)

    @unittest.skipUnless(os.environ.get("AOS_REAL_MODEL"), "真模型：設 AOS_REAL_MODEL=1 才跑")
    def test_real_model(self):
        try:
            urllib.request.urlopen(REAL_URL + "/models", timeout=3)
        except OSError:
            self.skipTest("LiteLLM 沒開")
        r = self.meg(LEARN, REAL_URL, stack="s1", name="q1.txt")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.meg(ASK, REAL_URL, stack="s2", name="q2.txt")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = (self.ws / "out" / "q2.txt").read_text()
        self.assertTrue(("4" in out or "四" in out) and "根目錄" in out, out)   # 真模型會寫「四個空格」（10-24 實測）


if __name__ == "__main__":
    unittest.main()
