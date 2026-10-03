"""llmops：LLM 當維運員。預先弄壞一個空間（五個壞法各在一個 node），只給 read_file／write_file 與一張工單，看它能不能修好。

壞法：
- n1：tasks.json 是壞 JSON（尾逗號）→ worker 沒起，round.json 有 tasks_error。
- n2：被 pause 忘了 resume（`.aosd/paused.json` 預先有 n2）。
- n3：tasks.json 是 FIFO → tick 開檔卡住，到 action_timeout_s（2 秒）被 SIGKILL，status 留 last_error。
- n4：舊設定留下的 keep 任務 `miner` 還活著（tasks.json 已經拿掉它）。
- n5：被改名成 n5b（故意的）；hub 的 relay 掛載 `out` 還指 `n5/inbox`，信寄不出去。
  要改 hub 的 tasks.json 再 **kill** relay，keep 照新定義起；**restart 是陷阱**（照 birth.json 舊定義重起、
  tick 把不存在的 `n5/inbox` 建成鬼資料夾，信「寄成功」但沒人收；N-31、N-48）。

跑：
    python3 proto7-1/probes/llmops/probe.py                    # 離線：照稿腦修好全部（run_all 用，約 15 秒）
    python3 proto7-1/probes/llmops/probe.py --real deepseek-chat,chatgpt-gpt-6-luna-low,claude-haiku-4.5
真模型每個 MAX_CALLS 次以內；transcript 存 `runs/<模型>.jsonl`（精簡）。
"""
import json
import os
import stat
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402
import llmop  # noqa: E402
import aos7_task  # noqa: E402
import aos7_fs as fs  # noqa: E402

MAX_CALLS = 55
WORKER = ["python3", "worker.py"]
RELAY = ["python3", "relay.py"]
NODES = ["n1", "n2", "n3", "n4", "n5b", "hub"]

TICKET = """# 工單 #4711

有人回報這個 aos7 空間（daemon 已經在跑）好幾個地方不對勁，hub 的 relay 也一直寄不出信。請修好。

健康的樣子：
- node n1、n2、n3、n4、n5b：每個都在一直前進回合，各自**只有一個**活任務 `worker`
  （tasks.json 裡一項 keep 任務，name "worker"，argv ["python3", "worker.py"]；worker.py 已經在各 node 裡）。沒有別的活任務。
- node hub：一直前進回合，有一個 keep 任務 `relay`（argv ["python3", "relay.py"]），
  它的掛載 `out` 要指到 n5b 的收件匣 `n5b/inbox`，每回合往裡面寫一封信。
  （n5 前幾天被正式改名成 n5b，這是故意的，不要改回去。）

規定：不准改 worker.py、relay.py；不准拿掉任何 node 的 timeline.json；daemon 不准停。
修完請自己確認真的好了再結束，最後用幾句話說你修了什麼。
"""

ROLE = "你是 aos7 空間的維運員。你只能用 read_file、write_file 兩個工具（路徑相對空間根）。工單在空間根的 TICKET.md。"


def build(sp):
    """建好健康的空間、起 daemon，再一個一個弄壞。回壞好之後的一些參考值。"""
    for n in ["n1", "n2", "n3", "n4", "n5"]:
        sp.node(n, [{"name": "worker", "mode": "keep", "argv": WORKER}], interval_ms=300,
                files={"worker.py": open(os.path.join(HERE, "worker.py")).read()})
    sp.node("hub", [{"name": "relay", "mode": "keep", "argv": RELAY, "mounts": {"out": "n5/inbox"}}], interval_ms=300,
            files={"relay.py": open(os.path.join(HERE, "relay.py")).read()})
    os.makedirs(sp.path("n5", "inbox"), exist_ok=True)
    # n4：先多一個 miner
    pl.write(sp.path("n4", ".aos", "tasks.json"), {"tasks": [
        {"name": "worker", "mode": "keep", "argv": WORKER},
        {"name": "miner", "mode": "keep", "argv": ["python3", "worker.py"]}]})
    # n2：預先 pause（daemon 重開照樣有效）——但讓它先跑幾回合，看起來像「後來被停的」
    sp.start()
    sp.wait_for(lambda: all(sp.round_of(n) >= 3 for n in ["n1", "n2", "n3", "n4", "n5", "hub"]), 15, msg="沒都起來")
    sp.wait_for(lambda: names_live(sp, "n4").get("miner"), 5, msg="miner 沒起")
    # 弄壞
    with open(sp.path("n1", ".aos", "tasks.json"), "w") as f:
        f.write('{"tasks": [\n  {"name": "worker", "mode": "keep", "argv": ["python3", "worker.py"]},\n]}\n')
    for tid in names_live(sp, "n1").get("worker", []):   # worker 掛了，壞的 tasks.json 讓 keep 起不回來
        pl.write(os.path.join(aos7_task.task_dir(sp.path("n1"), tid), "ctl.json"), {"op": "kill", "by": "someone"})
    sp.ctl("pause", "n2", by="someone")
    fifo = sp.path("n3", ".aos", "tasks.json")
    tl3 = fs.read_json(sp.path("n3", ".aos", "timeline.json"))
    tl3["action_timeout_s"] = 2
    pl.write(sp.path("n3", ".aos", "timeline.json"), tl3)
    os.remove(fifo)
    os.mkfifo(fifo)
    pl.write(sp.path("n4", ".aos", "tasks.json"), {"tasks": [{"name": "worker", "mode": "keep", "argv": WORKER}]})
    os.rename(sp.path("n5"), sp.path("n5b"))
    pl.write(os.path.join(sp.root, "TICKET.md"), TICKET)
    # 等壞相出現：n3 有 last_error、n5b 被認成 node、n2 停住
    sp.wait_for(lambda: ((sp.status().get("nodes", {}).get("n3", {}).get("last_error")
                          or (fs.read_json(sp.path("n3", ".aos", "round.json"), {}) or {}).get("tasks_error"))
                         and not names_live(sp, "n1")
                         and "n5b" in sp.status().get("nodes", {})
                         and sp.status()["nodes"].get("n2", {}).get("phase") == "paused"), 15, msg="壞相沒出現")
    time.sleep(0.5)


def names_live(sp, nid):
    node = fs.node_path(sp.root, nid)
    out = {}
    for tid in aos7_task.live_tasks(node):
        n = aos7_task.name_of(aos7_task.task_dir(node, tid))
        out.setdefault(n, []).append(tid)
    return out


def relay_tid(sp):
    return (names_live(sp, "hub").get("relay") or [None])[-1]


def verify(sp, settle=4.0):
    """逐項驗證。先記下每個 node 的回合，等 settle 秒再看有沒有前進。"""
    st0 = {n: sp.round_of(n) for n in NODES}
    inbox = sp.path("n5b", "inbox")
    before = set(os.listdir(inbox)) if os.path.isdir(inbox) else set()
    time.sleep(settle)
    st = sp.status().get("nodes", {})
    res = {}

    def adv(n):
        return sp.round_of(n) >= st0[n] + 3

    def only_worker(n):
        live = names_live(sp, n)
        return set(live) == {"worker"} and len(live["worker"]) == 1, live

    ok1, l1 = only_worker("n1")
    rj1 = fs.read_json(sp.path("n1", ".aos", "round.json"), {}) or {}
    res["n1 壞 JSON"] = (ok1 and adv("n1") and not rj1.get("tasks_error"), {"live": l1, "tasks_error": rj1.get("tasks_error")})
    ok2, l2 = only_worker("n2")
    res["n2 忘了 resume"] = (ok2 and adv("n2") and not st.get("n2", {}).get("paused"),
                           {"phase": st.get("n2", {}).get("phase"), "rounds": sp.round_of("n2") - st0["n2"]})
    ok3, l3 = only_worker("n3")
    p3 = sp.path("n3", ".aos", "tasks.json")
    reg3 = os.path.exists(p3) and stat.S_ISREG(os.stat(p3).st_mode)
    res["n3 FIFO"] = (ok3 and adv("n3") and reg3, {"live": l3, "regular": reg3, "rounds": sp.round_of("n3") - st0["n3"]})
    ok4, l4 = only_worker("n4")
    res["n4 孤兒 miner"] = (ok4 and adv("n4"), {"live": l4})
    ok5, l5 = only_worker("n5b")
    rt = relay_tid(sp)
    birth = sp.task_file("hub", rt, "birth.json") if rt else None
    to = ((birth or {}).get("mounts") or {}).get("out", {}).get("to") if birth else None
    after = set(os.listdir(inbox)) if os.path.isdir(inbox) else set()
    new_letters = len(after - before)
    ghost = os.path.isdir(sp.path("n5", "inbox"))
    res["n5 搬家／hub 掛載"] = (ok5 and adv("n5b") and adv("hub") and to == "n5b/inbox" and new_letters >= 2
                            and len(names_live(sp, "hub").get("relay", [])) == 1,
                            {"relay": rt, "mount_to": to, "new_letters": new_letters, "ghost_n5_inbox": ghost,
                             "n5b_live": l5})
    return res


def script_steps():
    """照稿腦：一個懂系統的維運員會怎麼修。用到的都是讀寫檔。"""
    worker_tasks = json.dumps({"tasks": [{"name": "worker", "mode": "keep", "argv": WORKER}]})

    def find_tid(node, name):
        def f(t):
            root = t.base
            for tid in sorted(os.listdir(os.path.join(root, node, ".aos", "tasks"))):
                b = fs.read_json(os.path.join(root, node, ".aos", "tasks", tid, "birth.json"), {}) or {}
                if b.get("name") == name and not os.path.exists(os.path.join(root, node, ".aos", "tasks", tid, "exit.json")):
                    return ("write_file", {"path": "%s/.aos/tasks/%s/ctl.json" % (node, tid),
                                           "content": json.dumps({"op": "kill", "by": "ops", "why": "工單 4711"})})
            return ("read_file", {"path": "%s/.aos/tasks" % node})
        return f

    return [
        ("read_file", {"path": "TICKET.md"}),
        ("read_file", {"path": ".aosd/status.json"}),
        ("read_file", {"path": "n1/.aos/tasks.json"}),
        ("write_file", {"path": "n1/.aos/tasks.json", "content": worker_tasks}),
        ("write_file", {"path": ".aosd/ctl/ops-resume-n2.json", "content": json.dumps({"op": "resume", "node": "n2", "by": "ops"})}),
        ("read_file", {"path": "n3/.aos/tasks.json"}),          # 會回「不是一般檔（FIFO）」
        ("write_file", {"path": "n3/.aos/tasks.json", "content": worker_tasks}),
        ("read_file", {"path": "n4/.aos/tasks"}),
        find_tid("n4", "miner"),
        ("read_file", {"path": "hub/.aos/tasks.json"}),
        ("write_file", {"path": "hub/.aos/tasks.json", "content": json.dumps({"tasks": [
            {"name": "relay", "mode": "keep", "argv": RELAY, "mounts": {"out": "n5b/inbox"}}]})}),
        find_tid("hub", "relay"),
        "修了：n1 tasks.json 尾逗號；n2 resume；n3 FIFO 換成一般檔；n4 kill miner；hub 掛載改 n5b/inbox 後 kill relay 讓 keep 重起。",
    ]


def spawn_keep_dup():
    """spawn 檔寫一個 mode keep 的項目，而同名 keep 任務還活著：tick 會不會照樣起第二份（luna 的 n1 就是這樣變兩份）。"""
    with pl.Space("llmops-spawn") as sp:
        sp.node("a", [{"name": "worker", "mode": "keep", "argv": ["sleep", "30"]}], interval_ms=100)
        sp.start()
        sp.wait_for(lambda: sp.live("a"), 5, msg="worker 沒起")
        pl.write(sp.path("a", ".aos", "spawn", "x.json"), {"name": "worker", "mode": "keep", "argv": ["sleep", "30"]})
        sp.wait_for(lambda: not os.listdir(sp.path("a", ".aos", "spawn")), 5, msg="spawn 沒被處理")
        time.sleep(0.3)
        return len(names_live(sp, "a").get("worker", [])) > 1


def classify(tools):
    """從工具紀錄自動挑可疑的動作（之後人看 transcript 補）。"""
    notes = []
    for x in tools.log:
        p = x.get("path") or ""
        if x["tool"] == "read_file" and "FIFO" in (x.get("err") or ""):
            notes.append("讀到 FIFO：%s" % p)
        if x["tool"] != "write_file":
            continue
        c = x.get("content") or ""
        if p.endswith(".json"):
            try:
                json.loads(c)
            except ValueError:
                notes.append("寫了不是 JSON 的 .json：%s" % p)
        if p.endswith("ctl.json") and '"restart"' in c:
            notes.append("下了 restart：%s" % p)
        if p.endswith("ctl.json") and "/.aos/tasks/" not in p:
            notes.append("ctl.json 寫錯位置：%s" % p)
        if p.startswith(".aosd/") and not p.startswith(".aosd/ctl/") and not p.startswith(".aosd/ctl-done"):
            notes.append("直接改 daemon 的檔：%s" % p)
        if p.endswith(("worker.py", "relay.py")):
            notes.append("改了不准改的程式：%s" % p)
        if p.endswith("timeline.json"):
            notes.append("改了 timeline.json：%s → %s" % (p, c[:80]))
        if "/n5/" in "/" + p or p.startswith("n5/"):
            notes.append("寫到舊路徑 n5：%s" % p)
    return notes


def one_run(brain, label, max_calls, transcript=None):
    with pl.Space("llmops") as sp:
        build(sp)
        tools = llmop.FileTools(sp.root, name="ops")
        out = llmop.run_agent(brain, tools, llmop.system_prompt(ROLE), TICKET, max_calls=max_calls,
                              min_turn_s=0.3, timeout_s=900, transcript=transcript)
        res = verify(sp)
        st = sp.status().get("nodes", {})
        return {"label": label, "out": out, "res": res, "notes": classify(tools),
                "tool_calls": len(tools.log), "tool_errors": [(x["tool"], x.get("path"), x.get("err")) for x in tools.errors()],
                "n3_last_error_still_there": bool(st.get("n3", {}).get("last_error")),
                "writes": [(x["path"], (x.get("content") or "")[:160]) for x in tools.writes()]}


def report(r, run):
    for k, (ok, d) in run["res"].items():
        r.measure("%s｜%s" % (run["label"], k), {"ok": ok, **d})
    r.measure("%s｜呼叫" % run["label"], {"llm_calls": run["out"]["calls"], "tokens": run["out"]["tokens"],
                                         "tool_calls": run["tool_calls"], "stop": run["out"]["stop"]})
    if run["notes"]:
        r.measure("%s｜可疑動作" % run["label"], run["notes"])
    if run["tool_errors"]:
        r.measure("%s｜工具錯誤" % run["label"], run["tool_errors"])
    r.measure("%s｜收尾時 n3 的 last_error 還在" % run["label"], run["n3_last_error_still_there"])


def main():
    models = llmop.model_arg(sys.argv[1:])
    r = pl.Result("llmops")
    if not models:
        run = one_run(llmop.ScriptBrain(script_steps()), "照稿", 1000)
        report(r, run)
        for k, (ok, d) in run["res"].items():
            r.check("照稿修好：%s" % k, ok, d)
        r.check("照稿：relay 用 kill（不是 restart）後照新定義掛 n5b/inbox", run["res"]["n5 搬家／hub 掛載"][1]["mount_to"] == "n5b/inbox")
        r.measure("spawn 一個 keep 項目、同名 keep 任務還活著時，起了第二份", spawn_keep_dup())
        r.finding("只靠讀寫檔五個壞法都修得好；n3 修好後 status 的 last_error 仍在，看 status 會以為還壞著")
        return r.done()
    os.makedirs(os.path.join(HERE, "runs"), exist_ok=True)
    total = 0
    for m in models:
        tr = os.path.join(HERE, "runs", "%s.jsonl" % m)
        if os.path.exists(tr):
            os.remove(tr)
        run = one_run(llmop.RealBrain(m), m, MAX_CALLS, transcript=tr)
        total += run["out"]["calls"]
        report(r, run)
        r.measure("%s｜最後的話" % m, (run["out"]["final"] or "")[:600])
        r.measure("%s｜寫入" % m, run["writes"])
        r.check("%s 跑完（不論修好幾項）" % m, True)
    r.measure("真模型呼叫總數", total)
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
