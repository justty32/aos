"""test_memory - proto8/lib/aos/memory（長期記憶庫工具：save／search／read／forget、AOS_HEAP、HeapBad、flock）直接叫。

11-04 前叫 test_meg、還跑 demo/agent-meg（第一題存、換 stack 後第二題靠記憶庫答，連真模型那案也在）；demo 刪了，跑 agent 的案一起刪，工具本體的案留下、改指 lib。
設計：proto8/thinking/2026-10-24-memory.md。不連網。"""
import json, os, subprocess, sys, tempfile, unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, path_with  # noqa: E402
MEMORY_DIR = ROOT / "lib" / "aos" / "memory"         # 11-04 前經 demo/agent-meg/tools/memory 這個捷徑
MEMORY = MEMORY_DIR / "_entry"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_HEAP")


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)
        self.heap = self.ws / ".heap"

    def memory(self, args, heap=None):
        r = run(str(MEMORY), input=json.dumps(args, ensure_ascii=False),
                env={"AOS_HEAP": str(heap or self.heap)})
        return r

    def test_heap_bad_in_tool(self):
        """索引壞了：工具 memory: HeapBad 退 1（回不回給腦由叫它的 agent 決定）。"""
        (self.heap / "facts").mkdir(parents=True)
        (self.heap / "facts" / "index.json").write_text("[]")
        r = self.memory({"op": "search", "query": "x"})
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stderr, r"^memory: HeapBad ")

    def test_heap_location_from_env(self):
        """AOS_HEAP 有設就用它；沒設＝$AOS_WS/.heap/（11-04 前經 agent-meg 跑這案，demo 刪了改直接叫工具）。"""
        shared = self.tmp / "shared-heap"
        args = {"op": "save", "kind": "facts", "title": "f", "text": "內容"}
        self.assertEqual(self.memory(args, heap=shared).returncode, 0)
        self.assertTrue((shared / "facts" / "001.md").exists())
        self.assertFalse(self.heap.exists())
        r = run(str(MEMORY), input=json.dumps(args, ensure_ascii=False), env={"AOS_WS": str(self.ws)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.heap / "facts" / "001.md").exists())

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
        self.assertEqual([(r["kind"], r["counter_active"]) for r in top["rows"]], [("outcomes", "20")])

    def test_context_budget(self):
        """偏好多到超過上限：只附一部分、說還有。"""
        sys.path.insert(0, str(MEMORY_DIR))
        sys.dont_write_bytecode = True                   # 不在庫裡留 __pycache__
        import heap
        h = heap.Heap(str(self.heap))
        for i in range(30):
            h.save("prefs", "偏好 %d" % i, "內容" * 50)
        text = h.context("隨便")
        self.assertIn("偏好太多", text)
        self.assertLess(len(text), 2500)


if __name__ == "__main__":
    unittest.main()
