"""test_compact - 跑 demo/agent-hal/compact（土法 compact：工具呼叫各一句 → 逐段總結＋保留行 → 最後修飾）與 agent-hal（idle → compact → think → act）。

假 server 照「第幾步」回（system 訊息裡寫著第 1／2／3 步；其他＝agent 的腦）。設計：proto8/thinking/2026-10-24-compact.md。"""
import http.server, json, os, subprocess, tempfile, threading, unittest
from pathlib import Path

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
HAL = ROOT / "demo" / "agent-hal"
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "COMPACT_URL",
         "COMPACT_OVER_KB", "COMPACT_SEG_KB", "COMPACT_KEEP_TURNS", "COMPACT_KEEP_MAX", "COMPACT_KEEP_FINAL_MAX",
         "COMPACT_KEEP_LINE_MAX", "COMPACT_RESULT_CUT", "COMPACT_MODEL_NOTE", "COMPACT_MODEL_SEG", "COMPACT_MODEL_FINAL")


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


def stage(body):
    s = body["messages"][0]["content"] if body["messages"][0]["role"] == "system" else ""
    for n, name in (("（第 1 步", "note"), ("（第 2 步", "segment"), ("（第 3 步", "final")):
        if n in s:
            return name
    return "agent"


def ok(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10}}


def default_reply(kind, body):
    """照字面回：note＝每個 id 一句；segment＝每段一句、keep 第一行 user；final＝摘要接起來、全留。"""
    user = body["messages"][-1]["content"]
    if kind == "note":
        ids = [l.split("=", 1)[1] for l in user.splitlines() if l.startswith("呼叫 id=")]
        return ok(json.dumps({"notes": [{"id": i, "ok": True, "line": "NOTE " + i} for i in ids]}))
    if kind == "segment":
        ns = [int(l.split()[0][1:]) for l in user.splitlines() if l.startswith("L") and " user：" in l]
        return ok(json.dumps({"summary": "SEG " + user.splitlines()[0][:20],
                              "keep": [{"n": ns[0], "tag": "user_words", "why": "原話"}] if ns else []}))
    if kind == "final":
        ids = [l[1:].split()[0] for l in user.split("## 候選保留行")[-1].splitlines() if l.startswith("[")]
        return ok(json.dumps({"summary": "FINAL SUMMARY", "keep": ids}))
    return ok("ANSWER")


class Fake:
    """假的 OpenAI 相容 server：reply(kind, body) 回 dict（200）或 (狀態碼, 字串)；記下每個 (kind, body)。"""

    def __init__(self, reply=None):
        self.reply, self.requests = reply or default_reply, []
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                kind = stage(body)
                fake.requests.append((kind, body))
                item = fake.reply(kind, body)
                status, text = (200, json.dumps(item)) if isinstance(item, dict) else item
                data = text.encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def kinds(self):
        return [k for k, _ in self.requests]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def build(turns, unfinished=False):
    """合成 history：每題 user → assistant(tool_calls) → tool（大輸出）→ assistant 答。"""
    h = []
    for i in range(turns):
        h.append({"role": "user", "content": "第 %d 題：算 %d*7" % (i + 1, i)})
        h.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": "c%d" % i, "type": "function", "function": {"name": "math", "arguments": json.dumps({"expr": "%d*7" % i})}}]})
        h.append({"role": "tool", "tool_call_id": "c%d" % i, "content": ("%d\n" % (i * 7)) + "x" * 1500})
        h.append({"role": "assistant", "content": "答案是 %d" % (i * 7)})
    if unfinished:
        h.append({"role": "user", "content": "還沒答完的題"})
        h.append({"role": "assistant", "content": None, "tool_calls": [
            {"id": "cz", "type": "function", "function": {"name": "clock", "arguments": "{}"}}]})
        h.append({"role": "tool", "tool_call_id": "cz", "content": "2026-10-24T00:00:00Z"})
    return "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in h)


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)
        self.stack = self.ws / ".stack"
        self.stack.mkdir()
        self.hist = self.stack / "history.jsonl"

    def fake(self, reply=None):
        f = Fake(reply)
        self.addCleanup(f.close)
        return f

    def compact(self, url=None, force=True, **env):
        e = {"AOS_BRAIN_URL": url} if url else {}
        e.update({k: str(v) for k, v in env.items()})
        return run(EXEC, "--ws", "ws", str(HAL / "compact"), *(["--force"] if force else []), env=e, cwd=self.tmp,
                   timeout=60)

    def hal(self, url=None, **env):
        e = {"AOS_BRAIN_URL": url} if url else {}
        e.update({k: str(v) for k, v in env.items()})
        return run(EXEC, "--ws", "ws", str(HAL), env=e, cwd=self.tmp, timeout=60)

    def lines(self):
        return [json.loads(l) for l in self.hist.read_text().splitlines()]

    def runs(self):
        d = self.stack / "compact"
        return sorted(p.name for p in d.iterdir() if p.is_dir() and p.name[0].isdigit()) if d.exists() else []

    def report(self, run):
        return json.loads((self.stack / "compact" / run / "report.json").read_text())

    def test_under_threshold_noop(self):
        """沒超過門檻、沒 --force：不問腦、不動 history、不開 compact/。"""
        self.hist.write_text(build(2))
        before = self.hist.read_bytes()
        f = self.fake()
        r = self.compact(f.url, force=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.hist.read_bytes(), before)
        self.assertEqual(f.requests, [])
        self.assertFalse((self.stack / "compact").exists())

    def test_three_stages(self):
        """10 題、留最近 1 題：note 9 次（每次叫工具一次）、segment 每段一次、final 一次；新 history＝摘要一對＋最後一題原樣；原檔原封收進 orig。"""
        text = build(10)
        self.hist.write_text(text)
        f = self.fake()
        r = self.compact(f.url, COMPACT_KEEP_TURNS=1, COMPACT_SEG_KB=1)
        self.assertEqual(r.returncode, 0, r.stderr)
        run_id, = self.runs()
        rep = self.report(run_id)
        kinds = f.kinds()
        self.assertEqual(kinds.count("note"), 9)
        self.assertEqual(kinds.count("segment"), rep["stages"]["segment"]["counter_segments"])
        self.assertGreater(rep["stages"]["segment"]["counter_segments"], 1)
        self.assertEqual(kinds.count("final"), 1)
        self.assertEqual(rep["stages"]["note"]["counter_calls"], 9)
        self.assertEqual(rep["stages"]["note"]["prompt_tokens"], 900)
        self.assertFalse(rep["stages"]["note"]["estimated"])
        models = {k: b["model"] for k, b in f.requests}
        self.assertEqual(models, {"note": "chatgpt-gpt-6-luna-low", "segment": "chatgpt-gpt-6-luna-low",
                                  "final": "chatgpt-gpt-6-sol"})
        # 第 1 步看得到工具結果；第 2 步看不到原始結果，只看到那一句
        self.assertIn("x" * 100, f.requests[0][1]["messages"][1]["content"])
        for k, b in f.requests:
            if k == "segment":
                self.assertNotIn("x" * 100, b["messages"][1]["content"])
                self.assertIn("NOTE c", b["messages"][1]["content"])
        h = self.lines()
        self.assertTrue(h[0]["content"].startswith("【compact】run=" + run_id))
        self.assertIn("FINAL SUMMARY", h[0]["content"])
        self.assertIn('[L1 user_words：原話] {"role": "user", "content": "第 1 題：算 0*7"}', h[0]["content"])
        self.assertEqual(h[1]["role"], "assistant")
        self.assertEqual(self.hist.read_text().splitlines()[2:], text.splitlines()[-4:])   # 最後一題原樣
        self.assertEqual((self.stack / "compact" / run_id / "orig.jsonl").read_text(), text)
        self.assertEqual(rep["before"]["counter_messages"], 40)
        self.assertEqual(rep["after"]["counter_messages"], 6)
        self.assertLess(rep["after"]["bytes"], rep["before"]["bytes"])
        log = (self.stack / "compact" / "log.jsonl").read_text().splitlines()
        self.assertEqual(json.loads(log[-1])["run"], run_id)

    def test_unfinished_turn_kept(self):
        """還沒答完的那題（叫了工具、結果回來了、還沒答）原樣留在最後；KEEP_TURNS=0 時更早的全壓。"""
        text = build(3, unfinished=True)
        self.hist.write_text(text)
        f = self.fake()
        r = self.compact(f.url, COMPACT_KEEP_TURNS=0)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.hist.read_text().splitlines()[2:], text.splitlines()[-3:])
        self.assertEqual(self.lines()[-1]["role"], "tool")

    def test_keep_validation(self):
        """保留行：不在這段的、重複的、太長的、超過每段上限的都不收，記在 dropped；tag 不認得＝other。"""
        self.hist.write_text(build(4))

        def reply(kind, body):
            if kind == "segment":
                return ok(json.dumps({"summary": "S", "keep": [
                    {"n": 999, "tag": "user_words"}, {"n": 1, "tag": "weird", "why": "w"}, {"n": 1, "tag": "number"},
                    {"n": 2, "tag": "number"}, {"n": 5, "tag": "decision"}, {"n": 4, "tag": "open"}]}))
            return default_reply(kind, body)
        f = self.fake(reply)
        r = self.compact(f.url, COMPACT_KEEP_TURNS=0, COMPACT_SEG_KB=64, COMPACT_KEEP_MAX=2, COMPACT_KEEP_LINE_MAX=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        rep = self.report(self.runs()[0])
        self.assertEqual(rep["keep"]["final"], ["L1 other", "L5 decision"])
        why = {d["n"]: d["why"] for d in rep["keep"]["dropped"]}
        self.assertEqual(why[999], "不在這段")
        self.assertIn("太長", why[2])           # L2＝叫工具那行，第 1 步後是一行 tool_note（約 80 字 > 60）
        self.assertIn("上限", why[4])

    def test_resume_after_failure(self):
        """第 2 步腦掛掉：退 1、history 不動、run/ 留著；修好重跑，第 1 步不再問。"""
        text = build(4)
        self.hist.write_text(text)
        bad = self.fake(lambda k, b: (500, "boom") if k == "segment" else default_reply(k, b))
        r = self.compact(bad.url, COMPACT_KEEP_TURNS=0)
        self.assertEqual(r.returncode, 1)
        self.assertIn("compact: BrainFailed", r.stderr)
        self.assertEqual(self.hist.read_text(), text)
        self.assertTrue((self.stack / "compact" / "run" / "notes.json").exists())
        self.assertEqual(bad.kinds().count("note"), 4)
        good = self.fake()
        r = self.compact(good.url, COMPACT_KEEP_TURNS=0)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(good.kinds().count("note"), 0)
        rep = self.report(self.runs()[0])
        self.assertEqual(rep["stages"]["note"]["counter_calls"], 4)     # 前一次花的也算進來
        self.assertEqual((self.stack / "compact" / self.runs()[0] / "orig.jsonl").read_text(), text)

    def test_recompact(self):
        """壓縮再壓縮：第二次把上一次的摘要當「更早的摘要」、上一次的保留行當候選（old:），第 2 次。"""
        self.hist.write_text(build(3))
        f = self.fake()
        self.assertEqual(self.compact(f.url, COMPACT_KEEP_TURNS=0).returncode, 0)
        with open(self.hist, "a") as fh:
            fh.write(build(2).replace("c0", "d0").replace("c1", "d1"))
        r = self.compact(f.url, COMPACT_KEEP_TURNS=0)
        self.assertEqual(r.returncode, 0, r.stderr)
        first, second = self.runs()
        final_req = [b for k, b in f.requests if k == "final"][-1]["messages"][1]["content"]
        self.assertIn("## 更早一次壓縮留下的摘要\nFINAL SUMMARY", final_req)
        self.assertIn("[old:L1 user_words", final_req)
        self.assertEqual(self.report(second)["round"], 2)
        self.assertNotIn("【compact】run=%s " % first, self.hist.read_text())
        self.assertIn("第 2 次壓縮", self.lines()[0]["content"])
        self.assertTrue((self.stack / "compact" / second / "orig.jsonl").read_text().startswith('{"role": "user", "content": "【compact】run=' + first))

    def test_summary_empty(self):
        """第 3 步回空摘要：不換上去、退 1（SummaryEmpty）。"""
        text = build(3)
        self.hist.write_text(text)
        f = self.fake(lambda k, b: ok(json.dumps({"summary": "  ", "keep": []})) if k == "final" else default_reply(k, b))
        r = self.compact(f.url, COMPACT_KEEP_TURNS=0)
        self.assertEqual(r.returncode, 1)
        self.assertIn("compact: SummaryEmpty", r.stderr)
        self.assertEqual(self.hist.read_text(), text)

    def test_segment_summary_empty(self):
        """第 2 步某段回空摘要：那段整個會不見，所以停下（SummaryEmpty），history 不動。"""
        text = build(3)
        self.hist.write_text(text)
        f = self.fake(lambda k, b: ok(json.dumps({"summary": "", "keep": []})) if k == "segment" else default_reply(k, b))
        r = self.compact(f.url, COMPACT_KEEP_TURNS=0)
        self.assertEqual(r.returncode, 1)
        self.assertIn("compact: SummaryEmpty 第 1 段", r.stderr)
        self.assertEqual(self.hist.read_text(), text)

    def test_not_json_fallback(self):
        """便宜模型沒回 JSON：第 1 步照字面拼一句、第 2 步整段回覆當摘要；退路次數記在報告。"""
        self.hist.write_text(build(2))
        f = self.fake(lambda k, b: ok("這段在算乘法") if k in ("note", "segment") else default_reply(k, b))
        r = self.compact(f.url, COMPACT_KEEP_TURNS=0)
        self.assertEqual(r.returncode, 0, r.stderr)
        rep = self.report(self.runs()[0])
        self.assertEqual(rep["stages"]["note"]["counter_fallbacks"], 2)
        self.assertEqual(rep["stages"]["segment"]["counter_fallbacks"], 1)
        seg = [b for k, b in f.requests if k == "segment"][0]["messages"][1]["content"]
        self.assertIn("叫 math", seg)
        final = [b for k, b in f.requests if k == "final"][0]["messages"][1]["content"]
        self.assertIn("這段在算乘法", final)

    def test_history_changed(self):
        """壓的期間 history 被接了一行：不換（HistoryChanged）；下一次把半成品收成 stale-*、重新壓。"""
        self.hist.write_text(build(3))

        def reply(kind, body):
            if kind == "final" and not getattr(reply, "done", False):
                reply.done = True
                with open(self.hist, "a") as fh:
                    fh.write(json.dumps({"role": "user", "content": "插隊"}, ensure_ascii=False) + "\n")
            return default_reply(kind, body)
        f = self.fake(reply)
        r = self.compact(f.url, COMPACT_KEEP_TURNS=0)
        self.assertEqual(r.returncode, 1)
        self.assertIn("compact: HistoryChanged", r.stderr)
        self.assertEqual(self.lines()[-1]["content"], "插隊")
        r = self.compact(f.url, COMPACT_KEEP_TURNS=0)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(any(p.name.startswith("stale-") for p in (self.stack / "compact").iterdir()))
        self.assertEqual(self.lines()[-1]["content"], "插隊")      # 沒答完的那題原樣留著

    def test_nosave(self):
        """壓完沒變小就不換；同一份 history 在 fsm 裡（沒 --force）不再花錢壓。"""
        text = build(2)
        self.hist.write_text(text)
        f = self.fake(lambda k, b: ok(json.dumps({"summary": "很長" * 20000, "keep": []})) if k == "final"
                      else default_reply(k, b))
        r = self.compact(f.url, COMPACT_KEEP_TURNS=0)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.hist.read_text(), text)
        self.assertTrue(any(p.name.startswith("nosave-") for p in (self.stack / "compact").iterdir()))
        n = len(f.requests)
        r = self.compact(f.url, force=False, COMPACT_KEEP_TURNS=0, COMPACT_OVER_KB=1)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(f.requests), n)

    def test_agent_hal_end_to_end(self):
        """agent-hal：history 超過門檻 → compact 格先壓 → think 送出去的是摘要＋這題；答完照常寫 out/。"""
        self.hist.write_text(build(6))
        (self.ws / "new" / "q9.txt").write_text("第 1 題算的是什麼？")
        f = self.fake()
        r = self.hal(f.url, COMPACT_OVER_KB=4)
        self.assertEqual(r.returncode, 0, r.stderr)
        states = [json.loads(l)["state"] for l in (self.stack / "trace.jsonl").read_text().splitlines()]
        self.assertEqual(states, ["idle", "compact", "think", "act", "idle"])
        self.assertEqual((self.ws / "out" / "q9.txt").read_text(), "ANSWER\n")
        agent = [b for k, b in f.requests if k == "agent"]
        self.assertEqual(len(agent), 1)
        msgs = agent[0]["messages"]
        self.assertEqual(msgs[0]["role"], "system")
        self.assertTrue(msgs[1]["content"].startswith("【compact】"))
        self.assertEqual(msgs[-1], {"role": "user", "content": "第 1 題算的是什麼？"})
        ids = [m.get("tool_call_id") for m in msgs if m.get("role") == "tool"]
        self.assertEqual(ids, ["c4", "c5"])     # 舊題的工具大結果不在了，只剩最近 2 題原樣
        self.assertEqual(len(msgs), 1 + 2 + 8 + 1)

    def test_fake_brain_mode(self):
        """沒設網址＝假腦：agent-hal 也走得完（compact 照字面拼，腦叫 clock 再答）。"""
        self.hist.write_text(build(6))
        (self.ws / "new" / "q9.txt").write_text("現在幾點？")
        r = self.hal(COMPACT_OVER_KB=4)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("compact: ", r.stdout + r.stderr)
        self.assertTrue(self.lines()[0]["content"].startswith("【compact】"))
        self.assertTrue((self.ws / "out" / "q9.txt").read_text().startswith("FAKE ANSWER"))
        rep = self.report(self.runs()[0])
        self.assertTrue(rep["stages"]["final"]["estimated"])


if __name__ == "__main__":
    unittest.main()
