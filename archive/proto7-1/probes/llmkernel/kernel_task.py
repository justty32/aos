"""llmkernel 的 kernel 任務（node k 用 spawn 只起一次，tick 起的）：判斷交給 LLM，只給 read_file／write_file（以空間根為 base）。

設定 `<node>/llmcfg.json`：{"model": "script"|模型名, "max_calls", "min_turn_s", "timeout_s"}。
產出（都在 $AOS7_TASK）：transcript.jsonl（每輪的話與工具呼叫）、tools.json（FileTools.log）、out.json（run_agent 的結果，最後寫）。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import llmop  # noqa: E402

GOAL = """你是 node k 上的 kernel（資源管理、排程）。空間根底下有三個成員 node：a、b、c，各跑一個 keep 任務 worker。
規則：
1. 輪流跑：任何時刻 a、b、c 之中最多只有一條沒被 pause。順序 a → b → c → a → …，每條輪到時跑 3 回合（看它的 round 前進 3），然後 pause 它、換下一條。
2. 預算：每個成員的用量＝它的 worker 任務資料夾裡 usage.json 的 tokens（任務資料夾在 <node>/.aos/tasks/ 底下）。輪到某條之前（每次都要重看），它的用量已經超過 50，就把它永久 pause、以後跳過它。
3. a 和 b 都至少輪到 2 次之後就結束：確定 a、b、c 全都 pause 住了，再回一段文字說明你做了什麼（不要再叫工具）。
現在 a、b、c 都 pause 著。你寫的控制檔請用 "by": "k:kernel"。"""


class GenBrain(llmop.ScriptBrain):
    """照稿腦（離線）：generator 一步一步 yield (tool, args)／"wait"／最後的話（字串）。"""

    def __init__(self, gen_fn):
        super().__init__([])
        self.gen_fn = gen_fn
        self.gen = None

    def step(self, messages):
        if self.gen is None:
            self.gen = self.gen_fn(self.tools)
        try:
            s = next(self.gen)
        except StopIteration:
            return {"content": "（照稿完）", "tool_calls": [], "tokens": 0}
        if s == "wait":
            return {"content": None, "tool_calls": [], "tokens": 0, "wait": True}
        if isinstance(s, str):
            return {"content": s, "tool_calls": [], "tokens": 0}
        tool, args = s
        self.i += 1
        tc = {"id": "s%d" % self.i, "name": tool, "args": args}
        return {"content": None, "tool_calls": [tc], "tokens": 0,
                "raw_msg": {"role": "assistant", "content": "",
                            "tool_calls": [{"id": tc["id"], "type": "function",
                                            "function": {"name": tool, "arguments": json.dumps(args)}}]}}


def ideal(tools):
    """理想的 kernel：先 pause b、c，a 用 resume rounds=3；之後等目前那條真的停住（phase paused、不 pending）才挑下一條。"""
    seq = [0]

    def ctl(op, node, **kw):
        seq[0] += 1
        body = dict(op=op, node=node, by="k:kernel", **kw)
        return ("write_file", {"path": ".aosd/ctl/k-%03d-%s-%s.json" % (seq[0], op, node),
                               "content": json.dumps(body)})

    def status():
        try:
            return json.loads(tools.call("read_file", {"path": ".aosd/status.json"})).get("nodes", {})
        except (OSError, ValueError):
            return {}

    def usage(n):
        tot = 0
        for tid in tools.call("read_file", {"path": "%s/.aos/tasks" % n}).split("\n"):
            tid = tid.rstrip("/")
            try:
                tot += json.loads(tools.call("read_file", {"path": "%s/.aos/tasks/%s/usage.json" % (n, tid)})).get("tokens", 0)
            except (OSError, ValueError):
                pass
        return tot

    yield ctl("pause", "b")
    yield ctl("pause", "c")
    yield ctl("resume", "a", rounds=3)
    turns = {"a": 1, "b": 0, "c": 0}
    dead = set()
    order = ["a", "b", "c"]
    cur = "a"
    while True:
        n = status().get(cur, {})
        if not (n.get("phase") == "paused" and not n.get("pause_pending")):
            yield "wait"
            continue
        if turns["a"] >= 2 and turns["b"] >= 2:
            break
        i = order.index(cur)
        nxt = None
        for k in range(1, 4):
            cand = order[(i + k) % 3]
            if cand in dead:
                continue
            if usage(cand) > 50:
                dead.add(cand)
                yield ctl("pause", cand)     # 已經停著，再寫一次當「永久」的紀錄
                continue
            nxt = cand
            break
        if nxt is None:
            break
        yield ctl("resume", nxt, rounds=3)
        while status().get(nxt, {}).get("paused", True):   # 等 daemon 吃下 resume，免得下一圈看到舊的 paused
            yield "wait"
        turns[nxt] += 1
        cur = nxt
    yield "照稿完：輪了 %s，預算停掉 %s" % (turns, sorted(dead))


def main():
    task = os.environ["AOS7_TASK"]
    node = os.environ["AOS7_NODE"]
    cfg = json.load(open(os.path.join(node, "llmcfg.json")))
    tools = llmop.FileTools(os.environ["AOS7_ROOT"], name="kernel")
    model = cfg.get("model", "script")
    brain = GenBrain(ideal) if model == "script" else llmop.RealBrain(model)
    sysmsg = llmop.system_prompt("你是一個 kernel 程式，只能用 read_file、write_file 兩個工具做事；路徑都相對空間根。")
    try:
        out = llmop.run_agent(brain, tools, sysmsg, GOAL, max_calls=cfg.get("max_calls", 30),
                              min_turn_s=cfg.get("min_turn_s", 0.3), timeout_s=cfg.get("timeout_s", 300),
                              transcript=os.path.join(task, "transcript.jsonl"))
    finally:
        with open(os.path.join(task, "tools.json"), "w", encoding="utf-8") as f:
            json.dump(tools.log, f, ensure_ascii=False, default=str)
    with open(os.path.join(task, ".out.json.tmp"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    os.replace(os.path.join(task, ".out.json.tmp"), os.path.join(task, "out.json"))


if __name__ == "__main__":
    main()
