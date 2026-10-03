"""llmteam 的 A：node `lab` 裡 tick 起的任務，裡面跑一個只會讀寫檔的 LLM（或離線照稿腦），要用路一開子 daemon。

    python3 a_task.py <模型|script> <最多呼叫數>

只准寫 `lab/` 底下（路徑相對空間根）。逐字紀錄寫 `$AOS7_TASK/transcript.jsonl`，結果寫 `$AOS7_TASK/result.json`。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import llmop  # noqa: E402

ROLE = """你是 node `lab` 裡的一個任務（由 lab 的時間線 tick 起的），你的 node id 是 `lab`。
你只有 read_file、write_file 兩個工具，路徑都相對空間根。你只准寫 `lab/` 底下的檔。
沒有 sleep 工具：要等什麼，就再讀一次相關的檔（每讀一次大約過一兩秒）。"""

GOAL = """目標：
1. 在你的 node 底下的 `lab/sub` 開一個子 daemon（路一），讓它管兩個 worker node：w1、w2（在子 daemon 裡的 node id 就是 `w1`、`w2`）。每個 worker 每回合起一個 `true` 任務，interval 150 ms。
2. 兩個 worker 都在子 daemon 裡真的跑起來（回合在前進）之後，寫 `lab/READY.json`（內容自訂，說明子根與 node）。
3. 之後外面有個維運員會只用子 daemon 的控制檔管它，最後會把子 daemon 停掉（停是維運員的事，你不要自己停它）。停掉之後它必須保持停住（不能又被起來），而 lab 本身照常運作。
確認都做到了才結束；結束前把你做了什麼、遇到什麼寫在 `lab/A-NOTES.md`。"""


class LabTools(llmop.FileTools):
    """只准寫 lab/ 底下。"""

    def write_file(self, path, content):
        r = self.rel(self._resolve(path))
        if not (r == "lab" or r.startswith("lab/")):
            raise OSError("你只准寫 lab/ 底下：%s" % r)
        return super().write_file(path, content)


def _j(tools, rel):
    try:
        with open(os.path.join(tools.base, rel), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def script(naive=False):
    """離線照稿：做對的那條路（naive＝寫完 READY 就收工，不管 stop 之後會不會被 keep 起回來）。等待用 callable 回 "wait"。"""
    sub_st = "lab/sub/.aosd/status.json"

    def wait_sub_up(t):
        return None if _j(t, sub_st) else "wait"

    def wait_workers(t):
        st = _j(t, sub_st) or {}
        n = st.get("nodes") or {}
        return None if all((n.get(w) or {}).get("round", 0) >= 2 for w in ("w1", "w2")) else "wait"

    seen = {}

    def wait_stopped(t):
        st = _j(t, sub_st) or {}
        if st.get("stopped"):
            seen["gen"] = st.get("gen")
            return None
        return "wait"

    def kill_restarted(t):
        """tasks.json 拿掉 subd 只擋得住之後的 tick；若 keep 已經把它起回來了，再對新的 subd 寫 kill。"""
        live = [x for x in os.listdir(os.path.join(t.base, "lab/.aos/tasks"))
                if x.startswith("subd-") and not os.path.exists(os.path.join(t.base, "lab/.aos/tasks", x, "exit.json"))]
        seen["restarted"] = live
        if not live:
            return None
        return ("write_file", {"path": "lab/.aos/tasks/%s/ctl.json" % live[0],
                               "content": json.dumps({"op": "kill", "by": "lab:A", "why": "外面已 stop，不要再起"})})

    tl = json.dumps({"interval_ms": 150})
    notes = ("write_file", {"path": "lab/A-NOTES.md", "content": "照稿：開子 daemon、建 w1 w2%s。\n" % ("" if naive else "、外面 stop 後拿掉 subd")})
    wt = json.dumps({"tasks": [{"name": "q", "mode": "each", "argv": ["true"]}]})
    return [
        ("read_file", {"path": "lab/.aos/tasks.json"}),
        ("write_file", {"path": "lab/.aos/tasks.json", "content": json.dumps(
            {"tasks": [{"name": "subd", "mode": "keep", "argv": ["aos7-daemon", "sub"], "subroot": "lab/sub"}]})}),
        wait_sub_up,                                    # tick 先建 lab/sub/.aosd/，子 daemon 起來寫 status
        ("write_file", {"path": "lab/sub/w1/.aos/tasks.json", "content": wt}),
        ("write_file", {"path": "lab/sub/w1/.aos/timeline.json", "content": tl}),
        ("write_file", {"path": "lab/sub/w2/.aos/tasks.json", "content": wt}),
        ("write_file", {"path": "lab/sub/w2/.aos/timeline.json", "content": tl}),
        wait_workers,
        ("write_file", {"path": "lab/READY.json", "content": json.dumps(
            {"subroot": "lab/sub", "ctl": "lab/sub/.aosd/ctl/", "nodes": ["w1", "w2"]})}),
    ] + ([notes, "做完了。"] if naive else [
        wait_stopped,
        ("write_file", {"path": "lab/.aos/tasks.json", "content": json.dumps({"tasks": []})}),
        kill_restarted,
        notes,
        "做完了。",
    ])


def main(argv):
    model, cap = argv[0], int(argv[1])
    task = os.environ["AOS7_TASK"]
    tools = LabTools(os.environ["AOS7_ROOT"], name="A")
    brain = llmop.ScriptBrain(script(model == "script-naive")) if model.startswith("script") else llmop.RealBrain(model)
    out = llmop.run_agent(brain, tools, llmop.system_prompt(ROLE), GOAL, max_calls=cap,
                          min_turn_s=0.05 if model.startswith("script") else 0.3, timeout_s=480,
                          transcript=os.path.join(task, "transcript.jsonl"))
    out["tool_log"] = tools.log
    out["model"] = model
    with open(os.path.join(task, ".result.tmp"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, default=str)
    os.replace(os.path.join(task, ".result.tmp"), os.path.join(task, "result.json"))
    print(json.dumps({k: out[k] for k in ("calls", "tokens", "turns", "stop")}))


if __name__ == "__main__":
    main(sys.argv[1:])
