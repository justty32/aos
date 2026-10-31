"""test_gus - 跑 demo/agent-gus（小念頭：先規劃 steps → 每步 fork 成同一隻 agent → 只帶回結論 → 彙整回答）。

假 server 用「看 request 決定回什麼」的路由（小念頭會同時打進來，不能用固定順序的劇本），記下每一筆 request。
設計：proto8/thinking/2026-10-24-thoughts.md。連真模型的那個 localhost:4000 連不上就 skip。"""
import http.server, json, os, re, subprocess, tempfile, threading, time, unittest, urllib.request
from pathlib import Path
import own_error  # noqa: E402
own_error.install()

from aos_bins import ROOT, tool, path_with  # noqa: E402
EXEC = tool("aos-exec")
GUS = str(ROOT / "demo" / "agent-gus")
REAL_URL = "http://localhost:4000/v1"
CODES = ("BrainFailed", "ReplyBad", "ToolUnknown", "ArgumentsBad", "ToolFailed", "StackMissing", "QuestionMissing",
         "HistoryBad", "PlanBad", "ThoughtFailed", "StepBad")
CLEAR = ("AOS_WS", "AOS_ENTRY", "AOS_STACK", "AOS_BRAIN_URL", "AOS_BRAIN_MODEL", "AOS_BRAIN_KEY", "AOS_THOUGHT_DEPTH",
         "AOS_THOUGHT_BUDGET", "AOS_THOUGHT_MAX_STEPS", "AOS_THOUGHT_MAX_DEPTH", "AOS_THOUGHT_MAX_TOTAL", "AOS_THOUGHT_PARALLEL",
         "AOS_THOUGHT_TIMEOUT_S", "AOS_THOUGHT_MAX_CHARS")


def run(*args, env=None, **kw):
    e = {k: v for k, v in os.environ.items() if k not in CLEAR}
    e["PATH"] = path_with(e.get("PATH", ""))
    e.update(env or {})
    return subprocess.run(args, capture_output=True, text=True, env=e, **kw)


def gus_errors(stderr):
    found = []
    for line in stderr.splitlines():
        if line.startswith("agent-gus:"):
            m = re.match(r"agent-gus: ([A-Z][A-Za-z]+) \S", line)
            assert m and m.group(1) in CODES, "agent-gus 的錯誤行格式不對：%r" % line
            found.append(m.group(1))
    return found


def answer(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def plan_reply(steps, context="背景"):
    return answer(json.dumps({"context": context, "steps": steps}, ensure_ascii=False))


def is_plan(body):
    return any(m["role"] == "system" and "【規劃】" in m["content"] for m in body["messages"])


def depth_of(body):
    return int(re.search(r"第 (\d+) 層", next(m["content"] for m in body["messages"]
                                               if m["role"] == "system" and "【規劃】" in m["content"])).group(1))


def goal_of(body):
    first = next(m["content"] for m in body["messages"] if m["role"] == "user")
    m = re.search(r"^你的目標：(.*)$", first, re.M)
    return m.group(1) if m else None


class FakeBrain:
    """假的 OpenAI 相容 server：route(body) 回 dict（200）或 (狀態碼, 字串) 或 ("sleep", 秒, dict)。"""

    def __init__(self, route):
        self.route, self.requests, self.lock = route, [], threading.Lock()
        brain = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                with brain.lock:
                    brain.requests.append(body)
                item = brain.route(body)
                if isinstance(item, tuple) and item[0] == "sleep":
                    time.sleep(item[1])
                    item = item[2]
                status, text = (200, json.dumps(item)) if isinstance(item, dict) else item
                data = text.encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def plans(self):
        return [b for b in self.requests if is_plan(b)]


def two_steps(body):
    """第 0 層拆 a、b（b 要 a 的結論），小念頭不拆；小念頭答「結論:<目標>」，母體最後答「總結」。"""
    if is_plan(body):
        if depth_of(body) == 0:
            return plan_reply([{"id": "a", "goal": "甲", "needs": []}, {"id": "b", "goal": "乙", "needs": ["a"]}])
        return plan_reply([], "")
    g = goal_of(body)
    return answer("結論:" + g if g else "總結")


class T(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = Path(self._t.name)
        self.addCleanup(self._t.cleanup)
        self.ws = self.tmp / "ws"
        (self.ws / "new").mkdir(parents=True)
        self.stack = self.ws / ".stack"

    def brain(self, route):
        b = FakeBrain(route)
        self.addCleanup(b.close)
        return b

    def ask(self, question="比較甲乙"):
        (self.ws / "new" / "q1.txt").write_text(question)

    def gus(self, url=None, timeout=120, **env):
        e = dict(env)
        if url:
            e["AOS_BRAIN_URL"] = url
        return run(EXEC, "--ws", "ws", GUS, env=e, cwd=self.tmp, timeout=timeout)

    def history(self, stack=None):
        p = (stack or self.stack) / "history.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()]

    def states(self, stack=None):
        return [json.loads(l)["state"] for l in ((stack or self.stack) / "trace.jsonl").read_text().splitlines()]

    def test_fake_brain(self):
        """沒設 URL＝假腦：第 0 層拆兩步、b 的題目帶 a 的結論；母體 history＝題目＋兩則結論＋回答。"""
        self.ask()
        r = self.gus()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.states(), ["idle", "plan", "fork", "think", "act", "idle"])
        h = self.history()
        self.assertEqual([m["role"] for m in h], ["user", "user", "user", "assistant"])
        self.assertTrue(h[1]["content"].startswith("小念頭 s1 的結論"))
        task = (self.stack / "thoughts" / "s2" / "ws" / "done" / "s2.txt").read_text()
        self.assertIn("FAKE CONCLUSION: 說出題目的重點", task)
        self.assertIn("彙整了 2 個", (self.ws / "out" / "q1.txt").read_text())
        self.assertFalse((self.stack / "steps.json").exists())          # 收進 plans/
        self.assertEqual(len(list((self.stack / "plans").iterdir())), 1)

    def test_split_and_conclusions_only(self):
        """真腦路：小念頭各問自己的腦；母體最後一次問腦只看到題目＋結論（看不到小念頭的過程）。"""
        b = self.brain(two_steps)
        self.ask()
        r = self.gus(b.url)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(gus_errors(r.stderr), [])
        self.assertEqual((self.ws / "out" / "q1.txt").read_text(), "總結\n")
        final = [x for x in b.requests if not is_plan(x) and goal_of(x) is None][-1]
        users = [m["content"] for m in final["messages"] if m["role"] == "user"]
        self.assertEqual(users[0], "比較甲乙")
        self.assertEqual(users[1], "小念頭 a 的結論（目標：甲）：\n結論:甲")
        self.assertEqual(users[2], "小念頭 b 的結論（目標：乙）：\n結論:乙")
        b_task = [x for x in b.requests if not is_plan(x) and goal_of(x) == "乙"][0]
        self.assertIn("- a（甲）：結論:甲", b_task["messages"][1]["content"])
        self.assertEqual(len(b.plans()), 3)        # 母體一次、兩個小念頭各一次
        self.assertEqual(len(self.history(self.stack / "thoughts" / "a" / "stack")), 2)

    def test_direct(self):
        """腦說不拆：不開 thoughts/，就是 agent-dan 的想 → 答。"""
        b = self.brain(lambda body: plan_reply([], "") if is_plan(body) else answer("直接答"))
        self.ask()
        r = self.gus(b.url)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.ws / "out" / "q1.txt").read_text(), "直接答\n")
        self.assertFalse((self.stack / "thoughts").exists())
        self.assertEqual([m["role"] for m in self.history()], ["user", "assistant"])

    def test_depth_limit_skips_planning(self):
        """AOS_THOUGHT_MAX_DEPTH=1：小念頭（第 1 層）不再問腦規劃，直接做。"""
        b = self.brain(two_steps)
        self.ask()
        r = self.gus(b.url, AOS_THOUGHT_MAX_DEPTH="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([depth_of(x) for x in b.plans()], [0])
        plan = json.loads(next((self.stack / "thoughts" / "a" / "stack" / "plans").iterdir()).read_text())
        self.assertEqual(plan["direct"], "depth")

    def test_recursive_and_budget(self):
        """小念頭還能再拆（遞迴）；整棵樹額度用完，下一層就不拆（不問腦規劃）。"""
        def route(body):
            if is_plan(body):
                d = depth_of(body)
                if d < 2:
                    return plan_reply([{"id": "x%d" % d, "goal": "x%d" % d}, {"id": "y%d" % d, "goal": "y%d" % d}])
                return plan_reply([])
            g = goal_of(body)
            return answer("結論:" + g if g else "總結")
        b = self.brain(route)
        self.ask()
        r = self.gus(b.url, AOS_THOUGHT_MAX_TOTAL="4")
        self.assertEqual(r.returncode, 0, r.stderr)
        # 第 0 層用 2、x0 那棵再用 2；y0 輪到時剩 0 → 不拆、不問腦規劃（x0 先起或 y0 先起都一樣：兩個第 1 層只有一個能拆）
        reasons = []
        for s in ("x0", "y0"):
            p = json.loads(next((self.stack / "thoughts" / s / "stack" / "plans").iterdir()).read_text())
            reasons.append(p["direct"])
        self.assertEqual(sorted(reasons, key=str), sorted([None, "budget"], key=str))
        budget = next((self.stack / "budgets").iterdir())
        self.assertEqual(len([f for f in budget.iterdir() if not f.name.startswith(".")]), 4)
        # 兩個第 1 層同時規劃時，兩個都可能先問了腦、搶額度時才有一個落空（白問一次）；依序時只問一次
        self.assertIn([depth_of(x) for x in b.plans()].count(1), (1, 2))
        deep = [p for p in self.stack.glob("thoughts/*/stack/thoughts/*/stack/history.jsonl")]
        self.assertEqual(len(deep), 2)

    def test_plan_bad_then_rerun(self):
        """規劃繞圈＝PlanBad、退 1、steps.json 不寫；修好再跑，題目不重接。"""
        bad = [True]

        def route(body):
            if is_plan(body) and bad[0]:
                return plan_reply([{"id": "a", "goal": "甲", "needs": ["b"]}, {"id": "b", "goal": "乙", "needs": ["a"]}])
            return two_steps(body)
        b = self.brain(route)
        self.ask()
        r = self.gus(b.url)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(gus_errors(r.stderr), ["PlanBad"])
        self.assertFalse((self.stack / "steps.json").exists())
        bad[0] = False
        r = self.gus(b.url)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([m["content"] for m in self.history()].count("比較甲乙"), 1)

    def test_plan_errors(self):
        """太多步、needs 指錯：都是 PlanBad。"""
        for steps in ([{"id": "s%d" % i, "goal": "g"} for i in range(5)], [{"id": "a", "goal": "g", "needs": ["z"]}]):
            with self.subTest(steps=steps):
                (self.ws / ".stack").exists() and __import__("shutil").rmtree(self.ws / ".stack")
                for d in ("cur", "new"):
                    (self.ws / d).mkdir(exist_ok=True)
                    for f in (self.ws / d).iterdir():
                        f.unlink()
                b = self.brain(lambda body, s=steps: plan_reply(s))
                self.ask()
                r = self.gus(b.url)
                self.assertEqual((r.returncode, gus_errors(r.stderr)), (1, ["PlanBad"]))

    def test_plan_prose_is_direct(self):
        """規劃那次腦回的不是規劃（散文、或散文裡夾著 {…}）＝當不拆、自己做，不是 PlanBad（10-24 真腦實測：
        小念頭回「沒有 Python 工具可用」、或答案裡寫了 `{i: i for i in range(1000)}`）；think 那次帶 tools 再問。"""
        for i, prose in enumerate(("沒有工具可用，無法實測", "用 `{i: i for i in range(9)}` 測", '結果是 {"n": 3}')):
            with self.subTest(prose=prose):
                q = "q%d.txt" % (i + 2)
                (self.ws / "new" / q).write_text("比較甲乙\n", encoding="utf-8")
                b = self.brain(lambda body, p=prose: answer(p) if is_plan(body) else answer("自己答"))
                r = self.gus(b.url)
                self.assertEqual((r.returncode, gus_errors(r.stderr)), (0, []), r.stderr)
                self.assertEqual((self.ws / "out" / q).read_text(), "自己答\n")
                self.assertTrue(any(t.get("tools") for t in b.requests if not is_plan(t)))
                plan = json.loads(sorted((self.ws / ".stack" / "plans").glob("*.json"))[-1].read_text())
                self.assertEqual((plan["direct"], plan["steps"]), ("prose", []))

    def test_thought_failed_back_to_brain(self):
        """一個小念頭的腦壞了：另一個照樣做完；失敗那步當結論（「小念頭 b 失敗了」）接進母體 history、不停，
        母體的腦看得到、自己決定怎麼答（10-24 代定，原本 ThoughtFailed 停住）。"""
        def route(body):
            if not is_plan(body) and goal_of(body) == "乙":
                return (500, "壞了")
            if is_plan(body) and depth_of(body) == 0:
                return plan_reply([{"id": "a", "goal": "甲"}, {"id": "b", "goal": "乙"}])
            return two_steps(body)
        b = self.brain(route)
        self.ask()
        r = self.gus(b.url)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(gus_errors(r.stderr), ["ThoughtFailed"])     # 人在 stderr 看得到
        steps = {s["id"]: s for s in json.loads((self.stack / "plans" / os.listdir(self.stack / "plans")[0])
                                                 .read_text())["steps"]}
        self.assertEqual((steps["a"]["status"], steps["b"]["status"]), ("done", "failed"))
        concl = [m["content"] for m in self.history() if str(m["content"]).startswith("小念頭 ")]
        self.assertEqual(concl[0], "小念頭 a 的結論（目標：甲）：\n結論:甲")
        self.assertTrue(concl[1].startswith("小念頭 b 失敗了（目標：乙）：\n結束碼 1（現場在 "), concl[1])
        last = [x for x in b.requests if not is_plan(x) and goal_of(x) is None][-1]  # 母體彙整那次看得到失敗
        self.assertIn(concl[1], [m["content"] for m in last["messages"]])
        self.assertEqual((self.ws / "out" / "q1.txt").read_text(), "總結\n")

    def test_thought_failed_needs_not_started(self):
        """b 要 a 的結論、a 失敗了：b 不起，結論寫「沒起」；兩則都回給母體的腦。"""
        def route(body):
            if not is_plan(body) and goal_of(body) == "甲":
                return (500, "壞了")
            return two_steps(body)
        b = self.brain(route)
        self.ask()
        r = self.gus(b.url)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([x for x in b.requests if goal_of(x) == "乙"], [])
        concl = [m["content"] for m in self.history() if str(m["content"]).startswith("小念頭 ")]
        self.assertTrue(concl[0].startswith("小念頭 a 失敗了"), concl)
        self.assertEqual(concl[1], "小念頭 b 失敗了（目標：乙）：\n沒起：要先拿到 a 的結論，但它失敗了")

    def test_thought_timeout(self):
        """小念頭超過 AOS_THOUGHT_TIMEOUT_S：整群收掉、那步當失敗回給母體的腦。"""
        def route(body):
            if is_plan(body):
                return two_steps(body)
            return ("sleep", 4, answer("慢")) if goal_of(body) == "甲" else two_steps(body)
        b = self.brain(route)
        self.ask()
        t0 = time.time()
        r = self.gus(b.url, AOS_THOUGHT_TIMEOUT_S="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ThoughtFailed", gus_errors(r.stderr))
        self.assertIn("逾時", r.stderr)
        self.assertTrue(any(str(m["content"]).startswith("小念頭 a 失敗了（目標：甲）：\n逾時")
                            for m in self.history()))
        self.assertLess(time.time() - t0, 15)

    def test_conclusion_capped(self):
        """結論超過 AOS_THOUGHT_MAX_CHARS 截斷，全文留在小念頭的 out/。"""
        def route(body):
            if not is_plan(body) and goal_of(body):
                return answer("長" * 50)
            return two_steps(body)
        b = self.brain(route)
        self.ask()
        r = self.gus(b.url, AOS_THOUGHT_MAX_CHARS="10")
        self.assertEqual(r.returncode, 0, r.stderr)
        c = [m["content"] for m in self.history() if str(m["content"]).startswith("小念頭 a")][0]
        self.assertIn("長" * 10 + "…（截斷", c)
        self.assertNotIn("長" * 11, c)

    def test_thought_entry(self):
        """別的程式叫一個小念頭：stdin {goal, context, needs} → stdout 只有結論；每次新的 runs/NNN/。"""
        b = self.brain(two_steps)
        st = self.tmp / "cell"
        step = {"goal": "甲", "context": "背景", "needs": [{"id": "k", "goal": "找 key", "conclusion": "/a/b"}]}
        r = run(EXEC, GUS + "/thought.json", input=json.dumps(step),
                env={"AOS_STACK": str(st) + "/", "AOS_BRAIN_URL": b.url}, cwd=self.tmp, timeout=60)
        self.assertEqual((r.returncode, r.stdout), (0, "結論:甲\n"), r.stderr)
        task = (st / "runs" / "001" / "ws" / "done" / "step.txt").read_text()
        self.assertIn("- k（找 key）：/a/b", task)
        self.assertIn("背景：背景", task)
        r = run(EXEC, GUS + "/thought.json", input=json.dumps(step),
                env={"AOS_STACK": str(st) + "/", "AOS_BRAIN_URL": b.url}, cwd=self.tmp, timeout=60)
        self.assertTrue((st / "runs" / "002").is_dir())
        r = run(EXEC, GUS + "/thought.json", input="{}", env={"AOS_STACK": str(st) + "/"}, cwd=self.tmp)
        self.assertEqual((r.returncode, gus_errors(r.stderr)), (1, ["StepBad"]))

    def test_real_model(self):
        """真模型（本機 LiteLLM）：連不上就 skip。"""
        try:
            urllib.request.urlopen(REAL_URL + "/models", timeout=3).read()
        except Exception as e:  # noqa: BLE001
            self.skipTest("LiteLLM 連不上：%s" % e)
        self.ask("用工具跑 Python 算出 2**20 和 3**13，再說哪個大。")
        r = self.gus(REAL_URL, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.ws / "out" / "q1.txt").read_text().strip())


if __name__ == "__main__":
    unittest.main()
