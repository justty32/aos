"""test_kai - 跑 demo/agent-kai（按意圖組 context 的 agent-dan）：假 server 照劇本回，驗送給腦的「工作 context」怎麼組、
history.jsonl 照舊完整、recall 工具查得到舊題與當時工具的原始輸出、短的時候全送、接上 agent-meg 的記憶庫。

設計：proto8/thinking/2026-10-24-intent-context.md。"""
import json, os, re, shutil, subprocess, tempfile, unittest, urllib.request
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
from test_dan import FakeBrain, answer, call, tool_reply  # noqa: E402

EXEC = tool("aos-exec")
KAI = ROOT / "demo" / "agent-kai"
RECALL = KAI / "tools" / "recall" / "_entry"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_HEAP",
         "AOS_KAI_FULL_UNDER", "AOS_RECALL_HISTORY")
CODES = ("BrainFailed", "ReplyBad", "ToolUnknown", "ArgumentsBad", "ToolFailed", "StackMissing",
         "QuestionMissing", "HistoryBad")


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


def kai_errors(stderr):
    found = []
    for line in stderr.splitlines():
        if line.startswith("agent-kai:"):
            m = re.match(r"agent-kai: ([A-Z][A-Za-z]+) \S", line)
            assert m and m.group(1) in CODES, "agent-kai 的錯誤行格式不對：%r" % line
            found.append(m.group(1))
    return found


def contents(req):
    return [m.get("content") or "" for m in req["messages"]]


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)
        self.stack = self.ws / ".stack"
        self.n = 0

    def brain(self, *script):
        b = FakeBrain(script)
        self.addCleanup(b.close)
        return b

    def ask(self, url, question, agent=KAI, full_under="0", extra=None):
        """放一題、跑到答完；回 aos-exec 的結果。full_under 預設 0＝一律按意圖組（測短對話全送的另外測）。"""
        self.n += 1
        (self.ws / "new" / ("q%02d.txt" % self.n)).write_text(question)
        env = {"AOS_BRAIN_URL": url, "AOS_KAI_FULL_UNDER": full_under}
        env.update(extra or {})
        r = run(EXEC, "--ws", "ws", str(agent), env=env, cwd=self.tmp, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(kai_errors(r.stderr), [])
        return r

    def history(self):
        return [json.loads(l) for l in (self.stack / "history.jsonl").read_text().splitlines()]

    def contexts(self):
        return [json.loads(l) for l in (self.stack / "context.jsonl").read_text().splitlines()]

    def test_old_tool_output_stays_out(self):
        """舊題的工具原始輸出不再送給腦（只送問題與結論），但 history.jsonl 照舊全留；目錄列每一題。"""
        b = self.brain(tool_reply(call("c1", "math", {"expr": "2**40"})), answer("算好了，是個很大的數。"),
                       answer("台北今天晴。"), answer("好"))
        self.ask(b.url, "2 的 40 次方是多少？")
        self.ask(b.url, "台北天氣怎樣？")
        self.ask(b.url, "隨便聊聊")
        third = b.requests[-1]
        self.assertFalse(any("1099511627776" in c for c in contents(third)))
        self.assertIn("1099511627776\n", [m.get("content") for m in self.history()])     # 原始紀錄還在
        sysmsg = third["messages"][0]
        self.assertEqual(sysmsg["role"], "system")
        self.assertIn("## 先前對話的目錄（共 2 題", sysmsg["content"])
        self.assertIn("#1 問：2 的 40 次方是多少？ → 答：算好了，是個很大的數。（用了 math）", sysmsg["content"])
        self.assertIn("#2 問：台北天氣怎樣？", sysmsg["content"])
        roles = [m["role"] for m in third["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])                  # 上一題展開＋這題
        self.assertEqual(third["messages"][1:], [{"role": "user", "content": "台北天氣怎樣？"},
                                                 {"role": "assistant", "content": "台北今天晴。"},
                                                 {"role": "user", "content": "隨便聊聊"}])
        self.assertEqual([c["picked"] for c in self.contexts()][-1], [[2, "上一題"]])
        self.assertEqual(len(self.history()), 8)

    def test_current_question_keeps_its_tool_results(self):
        """這題自己的工具來回照原樣送（不然 tool_calls 的協定接不上）。"""
        b = self.brain(answer("你好"), tool_reply(call("c1", "math", {"expr": "6*7"})), answer("42"))
        self.ask(b.url, "嗨")
        self.ask(b.url, "6*7？")
        last = b.requests[-1]["messages"]
        self.assertEqual([m["role"] for m in last], ["system", "user", "assistant", "user", "assistant", "tool"])
        self.assertEqual(last[-1], {"role": "tool", "tool_call_id": "c1", "content": "42\n"})

    def test_intent_picks(self):
        """指代詞→上兩題；「第 N 題」→那題；字面重疊→那題；無關的不展開。"""
        b = self.brain(answer("收到，Momo 三歲。"), answer("PostgreSQL 16"), answer("今天星期五"),
                       answer("ok"), answer("Momo"), answer("ok"), answer("ok"))
        self.ask(b.url, "我的貓叫 Momo，三歲。")
        self.ask(b.url, "藍鯨專案的資料庫是哪一套？")
        self.ask(b.url, "今天星期幾？")
        self.ask(b.url, "剛剛那個再說一次")
        self.ask(b.url, "我的貓叫什麼？")
        self.ask(b.url, "第二題的答案是什麼？")
        picked = [c["picked"] for c in self.contexts()]
        self.assertEqual(picked[3], [[2, "指代"], [3, "上一題"]])
        self.assertTrue(any(p[0] == 1 and p[1].startswith("字面重疊") for p in picked[4]), picked[4])
        self.assertEqual([p[0] for p in picked[5]], [2, 5])
        msgs = contents(b.requests[5])
        self.assertIn("藍鯨專案的資料庫是哪一套？", msgs)
        self.assertNotIn("今天星期幾？", msgs)                                            # 無關的只在目錄裡

    def test_recall_through_act(self):
        """腦用 recall 看舊題的工具原始輸出：act 給工具的 AOS_RECALL_HISTORY 指到自己的 history.jsonl。"""
        b = self.brain(tool_reply(call("c1", "math", {"expr": "2**40"})), answer("算好了"),
                       answer("嗯"),
                       tool_reply(call("c2", "recall", {"op": "read", "no": 1, "detail": True})), answer("1099511627776"))
        self.ask(b.url, "2 的 40 次方？")
        self.ask(b.url, "聊點別的")
        self.ask(b.url, "第一次算出來的數字到底是多少？")
        tool_msg = b.requests[-1]["messages"][-1]
        self.assertEqual(tool_msg["role"], "tool")
        self.assertIn("〔叫工具 math", tool_msg["content"])
        self.assertIn("1099511627776", tool_msg["content"])
        self.assertTrue((self.stack / "recall").is_dir())                                 # 工具自己的小格

    def test_recall_tool_direct(self):
        h = self.tmp / "h.jsonl"
        h.write_text("\n".join(json.dumps(m, ensure_ascii=False) for m in [
            {"role": "user", "content": "讀 docs/a.md"},
            {"role": "assistant", "content": None, "tool_calls": [call("c1", "read", {"path": "docs/a.md"})]},
            {"role": "tool", "tool_call_id": "c1", "content": "負責人：林小雨"},
            {"role": "assistant", "content": "讀完了"},
            {"role": "user", "content": "貓叫什麼"}, {"role": "assistant", "content": "Momo"},
            {"role": "user", "content": "還沒答完的題"}]) + "\n")

        def recall(args, env=None):
            return run(str(RECALL), input=json.dumps(args), env=env if env is not None else {"AOS_RECALL_HISTORY": str(h)})
        r = recall({"op": "search", "query": "docs 讀"})
        self.assertEqual(r.stdout.strip(), "#1 問：讀 docs/a.md → 答：讀完了（用了 read）")
        r = recall({"op": "read", "no": 1})
        self.assertIn("加 detail=true", r.stdout)
        self.assertNotIn("林小雨", r.stdout)
        self.assertIn("林小雨", recall({"op": "read", "no": 1, "detail": True}).stdout)
        self.assertIn("no 要是 1～2", recall({"op": "read", "no": 3}).stdout)             # 沒答完的那題不算
        self.assertIn("沒有找到（共 2 題）", recall({"op": "search", "query": "天氣"}).stdout)
        r = recall({"op": "search"}, env={})
        self.assertEqual((r.returncode, r.stderr.strip()), (1, "recall: HistoryMissing 沒設定 AOS_RECALL_HISTORY"))

    def test_short_history_sent_whole(self):
        """整份還很短（粗估 ≤ AOS_KAI_FULL_UNDER）就全送，跟 agent-dan 一樣；超過才按意圖組。"""
        b = self.brain(answer("a1"), answer("a2"), answer("a3"))
        self.ask(b.url, "q1", full_under="")
        self.ask(b.url, "q2", full_under="")
        self.ask(b.url, "q3", full_under="0")
        self.assertEqual([c["mode"] for c in self.contexts()], ["full", "full", "intent"])
        self.assertEqual([(c["counter_turns"], c["counter_history_messages"]) for c in self.contexts()], [(0, 1), (1, 3), (2, 5)])   # 計數叫 counter_*（10-25）
        self.assertTrue(all("sent_at" in c and "at" not in c for c in self.contexts()))   # 組好送出的時間（10-25 前叫 at）
        self.assertEqual([m["role"] for m in b.requests[1]["messages"]], ["system", "user", "assistant", "user"])
        self.assertNotIn("## 先前對話的目錄", b.requests[1]["messages"][0]["content"])
        self.assertIn("## 先前對話的目錄", b.requests[2]["messages"][0]["content"])

    def test_memory_from_agent_meg(self):
        """tools/memory 接 agent-meg 的記憶庫工具（登記進 tools.json）、記憶庫在：每題自動附上 search 到的幾筆（不進 history）。"""
        meg = ROOT / "demo" / "agent-meg" / "tools" / "memory"
        if not (meg / "_tooldef.json").exists():
            self.skipTest("agent-meg 的記憶庫工具不在")
        agent = self.tmp / "agent-kai"
        shutil.copytree(KAI, agent, ignore=shutil.ignore_patterns("__pycache__"))
        (agent / "tools" / "memory").symlink_to(meg)
        reg = json.loads((agent / "tools.json").read_text(encoding="utf-8"))      # 登記進 tools.json 才算工具
        reg["tools"]["memory"] = {"path": "tools/memory"}
        (agent / "tools.json").write_text(json.dumps(reg), encoding="utf-8")
        heap = self.tmp / "heap"
        save = {"op": "save", "kind": "facts", "title": "藍鯨專案的資料庫", "text": "藍鯨專案用 PostgreSQL 16。"}
        r = run(EXEC, str(meg), input=json.dumps(save, ensure_ascii=False), env={"AOS_HEAP": str(heap)},
                cwd=self.tmp, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        b = self.brain(answer("PostgreSQL 16"))
        self.ask(b.url, "藍鯨專案的資料庫是哪一套？", agent=agent, extra={"AOS_HEAP": str(heap)})
        sysmsg = b.requests[0]["messages"][0]["content"]
        self.assertIn("## 記憶庫裡跟這題可能有關的", sysmsg)
        self.assertIn("PostgreSQL 16", sysmsg)
        self.assertTrue(self.contexts()[0]["memory"])
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant"])

    def test_brain_failed_then_rerun(self):
        """腦失敗照 agent-dan：停在 think、只接了題目；再跑接著做、不重複接題。"""
        b = self.brain((500, "boom"), answer("好了"))
        (self.ws / "new" / "q1.txt").write_text("hi")
        env = {"AOS_BRAIN_URL": b.url}
        r = run(EXEC, "--ws", "ws", str(KAI), env=env, cwd=self.tmp, timeout=60)
        self.assertEqual(r.returncode, 1)
        self.assertIn("BrainFailed", kai_errors(r.stderr))
        r = run(EXEC, "--ws", "ws", str(KAI), env=env, cwd=self.tmp, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant"])

    def test_fake_brain_demo(self):
        """沒設 AOS_BRAIN_URL＝假腦（同 agent-dan：叫一次 clock 再答）。"""
        (self.ws / "new" / "q1.txt").write_text("幾點？")
        r = run(EXEC, "--ws", "ws", str(KAI), cwd=self.tmp, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex((self.ws / "out" / "q1.txt").read_text(), r"^FAKE ANSWER to: 幾點？（clock said: ")

    def test_real_model(self):
        """真模型（本機 LiteLLM）：舊題只在目錄與 recall 裡也答得出來；連不上就 skip。"""
        url = "http://localhost:4000/v1"
        try:
            urllib.request.urlopen(url + "/models", timeout=2).read()
        except OSError as e:
            self.skipTest("LiteLLM 連不上：%s" % e)
        for q in ("順便記一下行程：我下週二早上搭華航飛大阪參加客戶的年度檢討會，住在難波車站旁邊的飯店，房號是 1207，記住就好，回一句收到。",
                  "請用工具算 17*23。", "現在 UTC 幾點？"):
            self.ask(url, q)
        self.ask(url, "我住的房間號碼是多少？")
        self.assertIn("1207", (self.ws / "out" / "q04.txt").read_text())


if __name__ == "__main__":
    unittest.main()
