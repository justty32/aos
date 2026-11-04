"""selfprog：LLM agent 在執行中改自己的時間線——寫 spawn／tasks.json、開子時間線、改 interval、加掛 .aosd 後用 wake 催回合。

node `me` 上的 keep 任務 `agent.py` 跑一個只有 read_file／write_file 的 LLM（檔案工具的根＝自己的 node，S-10），
工單：四個檔算字數（兩個在 me 上各起一個任務，兩個在子時間線 me/sub 上），彙總 result.json，最後 pause 子時間線。

    python3 proto7-1/probes/selfprog/probe.py                      # 離線照稿（run_all 用）
    python3 proto7-1/probes/selfprog/probe.py --real deepseek-chat,claude-haiku-4.5   # 真模型，每個模型一次

真模型：每次最多 30 次呼叫（`--cap N` 可改），紀錄存到 `probes/selfprog/runs/`。
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402
import llmop  # noqa: E402
import aos7_fs as fs  # noqa: E402

PY = sys.executable
WORDS = {"a.txt": 120, "b.txt": 75, "c.txt": 200, "d.txt": 33}
FILE_NODE = {"a.txt": "me", "b.txt": "me", "c.txt": "me/sub", "d.txt": "me/sub"}


def text_of(n, seed):
    return " ".join("w%d_%d" % (seed, k) for k in range(n)) + "\n"


def births(sp, nid):
    out = []
    aos = sp.path(nid, ".aos")
    for tid, d in fs.task_dirs_of(aos):
        b = fs.read_json(os.path.join(d, "birth.json"), {}) or {}
        out.append((tid, d, b))
    return out


def one_run(model, cap, tag):
    r = pl.Result("selfprog" + ("" if model == "script" else "[%s]" % model))
    with pl.Space("selfprog") as sp:
        d = os.path.join(sp.base, "agentlog")
        os.makedirs(d)
        cfg = {"model": model, "cap": cap, "dir": d, "min_turn_s": 0.3 if model == "script" else 0.8,
               "timeout_s": 60 if model == "script" else 420}
        fs.write_json(os.path.join(sp.base, "cfg.json"), cfg)
        files = {"data/" + k: text_of(n, i) for i, (k, n) in enumerate(WORDS.items())}
        with open(os.path.join(HERE, "count.py"), encoding="utf-8") as f:
            files["count.py"] = f.read()
        sp.node("me", [{"name": "agent", "mode": "keep",
                        "argv": [PY, os.path.join(HERE, "agent.py"), os.path.join(sp.base, "cfg.json")]}],
                interval_ms=2000, files=files)
        t0 = time.time()
        sp.start(env={"AOS7_AUDIT": "1"})
        try:
            sp.wait_for(lambda: os.path.exists(os.path.join(d, "done.json")),
                        timeout=cfg["timeout_s"] + 30, poll=0.2, msg="agent 沒跑完")
        except pl.ProbeTimeout as e:
            r.finding("agent 逾時：%s" % e)
        time.sleep(0.6)   # 讓最後的 pause 生效
        done = fs.read_json(os.path.join(d, "done.json"), {}) or {}
        st = sp.status()
        nodes = st.get("nodes", {})

        # ---- 打分 ----
        tl_me = fs.read_json(sp.path("me", ".aos", "timeline.json"), {}) or {}
        tl_sub = fs.read_json(sp.path("me/sub", ".aos", "timeline.json"), {}) or {}
        ctl_done = [fs.read_json(p, {}) or {} for p in sorted(
            __import__("glob").glob(os.path.join(sp.root, ".aosd", "ctl-done", "*.json")))]
        wakes = [c for c in ctl_done if c.get("op") == "wake" and c.get("node") == "me" and (c.get("result") or {}).get("ok")]
        pauses = [c for c in ctl_done if c.get("op") == "pause" and c.get("node") == "me/sub"]
        counts = {}
        for nid in ("me", "me/sub"):
            for tid, td, b in births(sp, nid):
                argv = " ".join(map(str, b.get("argv") or []))
                for fn in WORDS:
                    if fn in argv and "count" in argv:
                        counts.setdefault(fn, []).append(nid)
        outs = {}
        for fn, nid in FILE_NODE.items():
            o = fs.read_json(sp.path(nid, "out", fn.replace(".txt", ".json")), {}) or {}
            outs[fn] = o.get("words")
        res = fs.read_json(sp.path("me", "result.json"), {}) or {}
        want = dict(WORDS, total=sum(WORDS.values()))
        inst = fs.read_jsonl(os.path.join(d, "instances.jsonl"))
        agent_tasks = [t for t, _, b in births(sp, "me") if b.get("name") == "agent"]
        g = {
            "interval_me_300": tl_me.get("interval_ms") == 300,
            "wake_me_ok": bool(wakes),
            "ab_once_on_me": all(counts.get(f) == ["me"] for f in ("a.txt", "b.txt")),
            "sub_node_200": tl_sub.get("interval_ms") == 200 and "me/sub" in nodes,
            "cd_once_on_sub": all(counts.get(f) == ["me/sub"] for f in ("c.txt", "d.txt")),
            "outputs_right": all(outs[f] == WORDS[f] for f in WORDS),
            "result_right": res == want,
            "sub_paused": (nodes.get("me/sub") or {}).get("phase") == "paused",
            "agent_not_killed": len(inst) == 1 and len(agent_tasks) == 1,
        }
        for k, v in g.items():
            if model == "script":
                r.check(k, v)
            else:
                r.measure("目標 " + k, v)
        r.measure("目標達成", "%d/%d" % (sum(g.values()), len(g)))

        # ---- 量 ----
        tl = [json.loads(x) for x in open(os.path.join(d, "transcript.jsonl"), encoding="utf-8")] \
            if os.path.exists(os.path.join(d, "transcript.jsonl")) else []
        tool_recs = [x for x in tl if "tool" in x]
        bad = [x for x in tool_recs if str(x.get("result", "")).startswith("錯誤")]
        r.measure("真模型呼叫", (fs.read_json(os.path.join(d, "calls.json"), {}) or {}).get("calls", 0))
        r.measure("停止原因", done.get("stop"))
        r.measure("輪數／工具呼叫／工具錯誤", [done.get("turns"), len(tool_recs), len(bad)])
        r.measure("每個檔起了幾次（在哪個 node）", counts)
        r.measure("agent 實例數", len(inst))
        r.measure("ctl-done", [(c.get("op"), c.get("node"), (c.get("result") or {}).get("ok")) for c in ctl_done])
        md = []
        for tid in agent_tasks:
            td = os.path.join(sp.path("me", ".aos", "tasks", tid))
            for fn in sorted(os.listdir(os.path.join(td, "mount-done"))) if os.path.isdir(os.path.join(td, "mount-done")) else []:
                o = fs.read_json(os.path.join(td, "mount-done", fn), {}) or {}
                md.append((fn, o.get("path"), (o.get("result") or {}).get("ok")))
        r.measure("加掛回條", md)
        # 寫入紀錄：agent 寫到範圍外（例如子 node 裡）的
        viol = []
        for tid in agent_tasks:
            for w in fs.read_jsonl(os.path.join(sp.path("me", ".aos", "tasks", tid), "writes.jsonl")):
                if not w.get("ok"):
                    viol.append(os.path.relpath(w.get("path", "?"), sp.root))
        r.measure("寫入紀錄 ok:false（agent）", sorted(set(viol)))
        rerr = [x.get("tasks_error") for x in sp.rounds("me") + sp.rounds("me/sub") if x.get("tasks_error")]
        r.measure("tasks_error", rerr[:3])
        r.measure("me 最後回合／sub 最後回合", [sp.round_of("me"), sp.round_of("me/sub")])
        r.measure("秒", round(time.time() - t0, 1))

        if model == "script":
            # 照稿先寫 sub 的 tasks.json、timeline.json（那時 sub 還不是 node：ok），sub 起來後再改 interval（已是巢狀的別的 node）
            r.check("子時間線起來後再改它的 timeline.json，寫入紀錄標成範圍外（spec：自己 node 扣掉巢狀 node）",
                    "me/sub/.aos/timeline.json" in viol, sorted(set(viol)))
        if model != "script":
            out_dir = os.path.join(HERE, "runs")
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "%s-%s.jsonl" % (tag, model)), "w", encoding="utf-8") as f:
                for x in tl:
                    if "result" in x:
                        x = dict(x, result=str(x["result"])[:400])
                    f.write(json.dumps(x, ensure_ascii=False) + "\n")
            fs.write_json(os.path.join(out_dir, "%s-%s.summary.json" % (tag, model)),
                          {"goals": g, "measures": r.measures, "done": done})
        return r


def main():
    models = llmop.model_arg(sys.argv)
    cap = int(sys.argv[sys.argv.index("--cap") + 1]) if "--cap" in sys.argv else 30
    if not models:
        return one_run("script", 10 ** 6, "script").done()
    rc = 0
    tag = time.strftime("%m%d-%H%M")
    for m in models:
        rc |= one_run(m, cap, tag).done()
    return rc


if __name__ == "__main__":
    pl.run_main(main)
