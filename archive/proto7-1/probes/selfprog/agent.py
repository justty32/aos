"""selfprog 的 agent 任務：tick 起的 keep 任務，裡面跑 llmop.run_agent（只給 read_file／write_file，根是自己的 node）。

    python3 agent.py <cfg.json>

cfg（放在空間根外面，LLM 看不到）：{"model": "script" 或模型名, "cap": 真模型呼叫上限, "dir": 紀錄資料夾}。
- 呼叫數記在 `<dir>/calls.json`（被 kill 重起的新實例接著扣，總數不超過 cap）。
- 跑完寫 `<dir>/done.json`，然後睡到被 kill（keep 任務結束會被 tick 再起；探針只看 done.json）。
- 已有 done.json 的新實例直接睡（不再問 LLM）。
"""
import json
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import llmop  # noqa: E402

NODE = os.environ.get("AOS7_NODE", ".")
TID = os.environ.get("AOS7_TID", "?")
TASKREL = os.path.relpath(os.environ.get("AOS7_TASK", "."), NODE)

ROLE = "你是住在 aos 空間裡的一個 agent（一個由 tick 起的任務）。你只有兩個工具：read_file、write_file。"

GOAL = """工單（你的 node id 是 `me`）：

**你的檔案工具的根是你自己的 node 資料夾 `me`，不是空間根。** 路徑一律相對 `me`（`.` 就是 me）。空間根和它的 `.aosd/`
你直接看不到；要寫 daemon 控制檔，得先把 `.aosd` 掛進你的任務資料夾。
- 你自己這個任務：tid `{tid}`，任務資料夾是 `{task}/`（裡面有 `tock.json`、`birth.json`）。
- 執行中加掛：寫 `{task}/mount-req/<名字>.json`＝`{{"name": "<名字>", "path": "<空間路徑>", "why": "..."}}`。
  下一個 tick 審核，回條在 `{task}/mount-done/<名字>.json`；給了之後 `{task}/mnt/<名字>` 就是那個資料夾。
  例：path 寫 `.aosd` → `{task}/mnt/<名字>/ctl/x.json` 就是 daemon 控制檔。
- `me` 的 interval 現在是 2000 ms（很慢）。
- `count.py` 在 me 裡：`python3 count.py <輸入檔> <輸出檔>` 算字數，寫 `{{"file": 檔名, "words": N}}` 到輸出檔（路徑相對任務的 cwd，也就是任務所在的 node）。

要做的：
1. 把 `me` 的 interval 改成 300 ms，並用 daemon 控制檔 `wake`（node `me`）讓它馬上生效。
2. 在 `me` 上**各起一個任務**算 `data/a.txt`、`data/b.txt`（輸出放 `out/a.json`、`out/b.json`），兩個平行，每個檔只算一次。
3. 開一條**子時間線**：node `me/sub`（資料夾 `sub/`），interval 200 ms；在 sub 上各起一個任務算 `data/c.txt`、`data/d.txt`（輸出放 `sub/out/c.json`、`sub/out/d.json`）。每個檔只算一次。
4. 四個都算完後，寫 `result.json`＝`{{"a.txt": N, "b.txt": N, "c.txt": N, "d.txt": N, "total": N}}`（N 照各輸出檔的 words）。
5. 最後讓子時間線 `me/sub` 停下來（pause），自己確認它真的停了。
6. 不要弄死自己（你就是 tasks.json 裡那個 `agent` keep 任務；它被 kill 或 restart，你這段對話就沒了）。
做完回一句總結（不再叫工具）。"""


def script_steps(task):
    """離線照稿：示範「只靠檔案做得到」的一條路。"""
    def wait_file(rel):
        def f(t):
            return None if os.path.exists(os.path.join(NODE, rel)) else "wait"
        return f
    ctl = task + "/mnt/aosd/ctl/"
    steps = [
        ("read_file", {"path": "."}),
        ("read_file", {"path": ".aos/tasks.json"}),
        ("write_file", {"path": task + "/mount-req/aosd.json",
                        "content": json.dumps({"name": "aosd", "path": ".aosd", "why": "寫 daemon ctl"})}),
        ("write_file", {"path": ".aos/timeline.json", "content": json.dumps({"interval_ms": 300})}),
        ("write_file", {"path": ".aos/spawn/ab.json", "content": json.dumps({"batch": [
            {"name": "count-a", "argv": ["python3", "count.py", "data/a.txt", "out/a.json"]},
            {"name": "count-b", "argv": ["python3", "count.py", "data/b.txt", "out/b.json"]}]})}),
        wait_file(task + "/mount-done/aosd.json"),
        ("read_file", {"path": task + "/mount-done/aosd.json"}),
        ("write_file", {"path": ctl + "wake-me.json", "content": json.dumps({"op": "wake", "node": "me", "by": "me:" + TID})}),
        ("write_file", {"path": "sub/.aos/spawn/cd.json", "content": json.dumps({"batch": [
            {"name": "count-c", "argv": ["python3", "../count.py", "../data/c.txt", "out/c.json"]},
            {"name": "count-d", "argv": ["python3", "../count.py", "../data/d.txt", "out/d.json"]}]})}),
        ("write_file", {"path": "sub/.aos/tasks.json", "content": json.dumps({"tasks": []})}),
        ("write_file", {"path": "sub/.aos/timeline.json", "content": json.dumps({"interval_ms": 1000})}),
        wait_file("sub/.aos/round.json"),
        # 子時間線起來之後再改它的 interval：這時 sub 已是巢狀的別的 node（寫入紀錄會標範圍外）
        ("write_file", {"path": "sub/.aos/timeline.json", "content": json.dumps({"interval_ms": 200})}),
        wait_file("out/a.json"), wait_file("out/b.json"), wait_file("sub/out/c.json"), wait_file("sub/out/d.json"),
    ]

    def result(t):
        w = {}
        for rel in ("out/a.json", "out/b.json", "sub/out/c.json", "sub/out/d.json"):
            with open(os.path.join(NODE, rel), encoding="utf-8") as f:
                o = json.load(f)
            w[o["file"]] = o["words"]
        w["total"] = sum(w.values())
        return ("write_file", {"path": "result.json", "content": json.dumps(w)})
    steps += [result,
              ("write_file", {"path": ctl + "pause-sub.json", "content": json.dumps({"op": "pause", "node": "me/sub", "by": "me:" + TID})}),
              ("read_file", {"path": ctl.replace("/ctl/", "/") + "status.json"}),
              "照稿完：四個檔算完、sub 已 pause。"]
    return steps


class Counted:
    """每打一次真模型就先把累計數寫進 calls.json（被 kill 也不會少算）。"""

    def __init__(self, brain, path, used):
        self.brain, self.path, self.n = brain, path, used

    def step(self, messages):
        self.n += 1
        with open(self.path, "w") as f:
            json.dump({"calls": self.n}, f)
        return self.brain.step(messages)


def main():
    cfg_path = sys.argv[1]
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    d = cfg["dir"]
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    inst = llmop._log  # 共用寫 jsonl
    inst(os.path.join(d, "instances.jsonl"), {"tid": TID, "at": time.time()})
    if not os.path.exists(os.path.join(d, "done.json")):
        calls_file = os.path.join(d, "calls.json")
        used = 0
        if os.path.exists(calls_file):
            with open(calls_file) as f:
                used = json.load(f)["calls"]
        tools = llmop.FileTools(NODE, name="me")
        if cfg["model"] == "script":
            brain = llmop.ScriptBrain(script_steps(TASKREL))
        else:
            brain = Counted(llmop.RealBrain(cfg["model"]), calls_file, used)
        out = llmop.run_agent(brain, tools, llmop.system_prompt(ROLE), GOAL.format(tid=TID, task=TASKREL),
                              max_calls=max(0, cfg["cap"] - used), min_turn_s=cfg.get("min_turn_s", 0.3),
                              timeout_s=cfg.get("timeout_s", 420), transcript=os.path.join(d, "transcript.jsonl"))
        with open(os.path.join(d, "toollog.jsonl"), "a", encoding="utf-8") as f:
            for x in tools.log:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
        with open(os.path.join(d, "done.json"), "w") as f:
            json.dump(dict(out, tid=TID), f, ensure_ascii=False)
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
