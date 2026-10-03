"""llmkernel：kernel 的判斷交給 LLM（只給 read_file／write_file＋操作卡），看它能不能只靠檔案把 daemon 用對。

成員 a、b、c（各一個 keep 的 worker，每收到 tock 用量 +5／+5／+30，回合 400 ms），node k 用 spawn 起一次 kernel 任務。
目標：a→b→c 輪流、同時最多一條沒 pause、每條輪到跑 3 回合；輪到前用量 >50 的永久 pause；a、b 各輪到 2 次後全部 pause 住、結束。

    python3 probe.py                      # 離線：照稿腦（理想操作），證明只靠檔案做得到，check 驗 daemon 行為
    python3 probe.py --real deepseek-chat,chatgpt-gpt-6-luna-low,claude-haiku-4.5 [--calls 35]
真模型的 transcript 精簡版存到 runs/<模型>.jsonl，統計印在最後。真模型呼叫上限：每模型 --calls（預設 35），全部合計 ≤ 110。
"""
import datetime
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402
import llmop  # noqa: E402
import aos7_fs as fs  # noqa: E402

PY = sys.executable
RATES = {"a": 5, "b": 5, "c": 30}
BUDGET = 50
TOTAL_CAP = 94   # 110 減掉第一次 deepseek 試跑用掉的 16
MEMBERS = ("a", "b", "c")


def ts(iso):
    return datetime.datetime.fromisoformat(iso).timestamp()


def run_once(model, max_calls, timeout_s):
    """開一個空間跑一次，回 (分析 dict, kernel 任務資料夾的產出)。"""
    with pl.Space("llmkernel") as sp:
        for n, rate in RATES.items():
            sp.node(n, [{"name": "worker", "mode": "keep", "argv": [PY, os.path.join(HERE, "worker.py"), str(rate)]}],
                    interval_ms=400)
        sp.node("k", [], interval_ms=1000,
                files={"llmcfg.json": {"model": model, "max_calls": max_calls, "timeout_s": timeout_s,
                                       "min_turn_s": 0.05 if model == "script" else 0.3},
                       ".aos/spawn/kernel.json": {"name": "kernel", "argv": [PY, os.path.join(HERE, "kernel_task.py")]}})
        fs.write_json(os.path.join(sp.root, ".aosd", "paused.json"), {"paused": list(MEMBERS)})   # 一出生就停著
        sp.start()
        t_start = time.time()
        kdir = sp.wait_for(lambda: _kdir(sp), 15, msg="kernel 任務沒起來")
        try:
            sp.wait_for(lambda: os.path.exists(os.path.join(kdir, "out.json")) or
                        os.path.exists(os.path.join(kdir, "exit.json")), timeout_s + 30, poll=0.2,
                        msg="kernel 沒結束")
        except pl.ProbeTimeout:
            pass
        time.sleep(1.5)            # 讓最後一條的 rounds=3 跑完、自動 pause
        a = analyze(sp, kdir, t_start)
        arte = {}
        for f in ("out.json", "tools.json", "transcript.jsonl", "exit.json", "out.log"):
            p = os.path.join(kdir, f)
            if os.path.exists(p):
                arte[f] = open(p, encoding="utf-8").read()
        return a, arte


def _kdir(sp):
    d = sp.path("k", ".aos", "tasks")
    try:
        names = [n for n in os.listdir(d) if n.startswith("kernel-")]
    except OSError:
        return None
    return os.path.join(d, names[0]) if names else None


def usage_of(sp, n):
    tot = 0
    for d in (sp.path(n, ".aos", "tasks"), sp.path(n, ".aos", "tasks-old")):
        if not os.path.isdir(d):
            continue
        for t in os.listdir(d):
            u = fs.read_json(os.path.join(d, t, "usage.json"), {}) or {}
            tot += u.get("tokens", 0) if isinstance(u.get("tokens"), int) else 0
    return tot


def analyze(sp, kdir, t_start):
    log = sp.log()
    st = sp.status()
    # kernel 第一次下的 ctl 起算
    kctl = [e for e in log if e.get("ev") == "ctl"]
    t0 = ts(kctl[0]["at"]) if kctl else None
    t_end = ts(log[-1]["at"]) if log else time.time()
    # 每條 node 沒被 pause 的區間（照 log 的 ctl ok 與 steps-done 重建）
    unp = {n: False for n in MEMBERS}   # 一出生就停著（預寫 paused.json）
    since = {n: ts(log[0]["at"]) if log else 0 for n in MEMBERS}
    spans = {n: [] for n in MEMBERS}
    for e in log:
        n = e.get("node")
        if n not in MEMBERS:
            continue
        if e.get("ev") == "ctl" and e.get("ok") and e.get("op") in ("pause", "resume"):
            want = e["op"] == "resume"
        elif e.get("ev") == "steps-done":
            want = False
        else:
            continue
        if want and not unp[n]:
            unp[n], since[n] = True, ts(e["at"])
        elif not want and unp[n]:
            unp[n] = False
            spans[n].append((since[n], ts(e["at"])))
    for n in MEMBERS:
        if unp[n]:
            spans[n].append((since[n], t_end))
    # 從 t0 起，≥2 條沒 pause 的總時間
    overlap = 0.0
    if t0 is not None:
        pts = sorted({t0, t_end} | {x for n in MEMBERS for s in spans[n] for x in s if t0 <= x <= t_end})
        for x, y in zip(pts, pts[1:]):
            mid = (x + y) / 2
            k = sum(1 for n in MEMBERS for s in spans[n] if s[0] <= mid < s[1])
            if k >= 2:
                overlap += y - x
    # 輪次：t0 之後 tick 的 node 序列，連續同一條算一次
    ticks = [(ts(e["at"]), e["node"]) for e in log if e.get("ev") == "tick" and e.get("node") in MEMBERS
             and (t0 is None or ts(e["at"]) > t0 + 0.05)]
    turns, seq = {n: 0 for n in MEMBERS}, []
    for _, n in ticks:
        if not seq or seq[-1][0] != n:
            seq.append([n, 0])
            turns[n] += 1
        seq[-1][1] += 1
    # 每條超預算（work.jsonl 用量 >50 的那一刻）之後才「開始」的輪次：應該是 0
    over_at, turns_after = {}, {}
    for n in MEMBERS:
        w = fs.read_jsonl(sp.path(n, "work.jsonl"))
        over_at[n] = next((ts(x["at"]) for x in w if x["tokens"] > BUDGET), None)
        turns_after[n] = sum(1 for k, (t, m) in enumerate(ticks)
                             if m == n and over_at[n] and t > over_at[n] and (k == 0 or ticks[k - 1][1] != n))
    paused_end = {n: st.get("nodes", {}).get(n, {}).get("paused") for n in MEMBERS}
    bad_ctl = []
    for f in sorted(os.listdir(os.path.join(sp.root, ".aosd", "ctl-done"))) if os.path.isdir(
            os.path.join(sp.root, ".aosd", "ctl-done")) else []:
        c = fs.read_json(os.path.join(sp.root, ".aosd", "ctl-done", f), {}) or {}
        if not (c.get("result") or {}).get("ok"):
            bad_ctl.append({"file": f, "op": c.get("op"), "node": c.get("node"), "msg": (c.get("result") or {}).get("msg")})
    left_ctl = sorted(os.listdir(os.path.join(sp.root, ".aosd", "ctl"))) if os.path.isdir(
        os.path.join(sp.root, ".aosd", "ctl")) else []
    tl = fs.read_json(os.path.join(kdir, "tools.json"), []) or []
    read_err = [{"path": x.get("path"), "err": x.get("err")} for x in tl if x["tool"] == "read_file" and not x.get("ok")]
    writes = [{"path": x.get("path"), "ok": x.get("ok"), "content": x.get("content")} for x in tl if x["tool"] == "write_file"]
    wrong_place = [w for w in writes if not (w["path"] or "").lstrip("./").startswith(("aosd/ctl/",)) and
                   not (w["path"] or "").startswith((".aosd/ctl/", "./.aosd/ctl/"))]
    bad_json = []
    for w in writes:
        try:
            json.loads(w["content"] or "")
        except ValueError:
            bad_json.append(w["path"])
    out = fs.read_json(os.path.join(kdir, "out.json"), {}) or {}
    return {
        "calls": out.get("calls", 0), "tokens": out.get("tokens", 0), "stop": out.get("stop"),
        "final": (out.get("final") or "")[:600],
        "seq": seq, "turns": turns, "overlap_s": round(overlap, 2),
        "active_s": round((t_end - t0) if t0 else 0, 1),
        "usage": {n: usage_of(sp, n) for n in MEMBERS},
        "over_at_rel": {n: round(over_at[n] - t0, 1) if over_at[n] and t0 else None for n in MEMBERS},
        "turns_after_over": turns_after,
        "paused_end": paused_end, "bad_ctl": bad_ctl, "left_in_ctl": left_ctl,
        "n_reads": sum(1 for x in tl if x["tool"] == "read_file"), "n_writes": len(writes),
        "read_err": read_err, "writes": writes, "wrong_place": wrong_place, "bad_json": bad_json,
        "kernel_exit": fs.read_json(os.path.join(kdir, "exit.json")),
    }


def verdict(a):
    """成功＝輪流（重疊 <0.3 秒）、a／b 各 ≥2 次、c 超預算後沒再輪到、結束時三條都 pause。"""
    return {
        "輪流（≥2 條同時沒 pause 的時間 <0.3 秒）": a["overlap_s"] < 0.3,
        "a、b 各輪到 ≥2 次": a["turns"]["a"] >= 2 and a["turns"]["b"] >= 2,
        "超預算的沒再輪到": not any(a["turns_after_over"].values()),
        "結束時 a、b、c 都 pause": all(a["paused_end"].values()),
    }


def main(argv):
    models = llmop.model_arg(argv)
    calls = int(argv[argv.index("--calls") + 1]) if "--calls" in argv else 35
    if not models:
        r = pl.Result("llmkernel")
        a, _ = run_once("script", 999, 40)
        for what, ok in verdict(a).items():
            r.check(what, ok, {"overlap_s": a["overlap_s"], "turns": a["turns"], "paused_end": a["paused_end"],
                               "turns_after_over": a["turns_after_over"]})
        r.check("沒有被拒的控制檔、沒有留在 ctl/ 沒處理的", not a["bad_ctl"] and not a["left_in_ctl"], a["bad_ctl"])
        r.check("照稿腦只寫 .aosd/ctl/*.json、都是合法 JSON", not a["wrong_place"] and not a["bad_json"])
        r.measure("輪次序列 [node, 回合數]", a["seq"])
        r.measure("用量", a["usage"])
        r.measure("讀／寫次數", [a["n_reads"], a["n_writes"]])
        r.finding("理想操作要靠 `resume rounds:3`＋等 status 的 phase=paused 且不 pending 才換人；只看回條會重疊（同 sched）。")
        return r.done()
    total = 0
    os.makedirs(os.path.join(HERE, "runs"), exist_ok=True)
    results = []
    for m in models:
        if total + calls > TOTAL_CAP:
            print("跳過 %s：總呼叫會超過 %d" % (m, TOTAL_CAP))
            continue
        a, arte = run_once(m, calls, 420)
        total += a["calls"]
        v = verdict(a)
        results.append({"model": m, "verdict": v, "ok": all(v.values()), **a})
        safe = m.replace("/", "_")
        with open(os.path.join(HERE, "runs", safe + ".json"), "w", encoding="utf-8") as f:
            json.dump(results[-1], f, ensure_ascii=False, indent=1)
        with open(os.path.join(HERE, "runs", safe + ".transcript.jsonl"), "w", encoding="utf-8") as f:
            f.write(arte.get("transcript.jsonl", "")[:190000])
        print(json.dumps({k: results[-1][k] for k in ("model", "ok", "verdict", "calls", "stop", "seq", "turns",
                                                       "overlap_s", "usage", "turns_after_over", "paused_end",
                                                       "bad_ctl", "left_in_ctl", "read_err", "wrong_place",
                                                       "bad_json")}, ensure_ascii=False))
    print("真模型呼叫合計：%d" % total)
    return 0


if __name__ == "__main__":
    pl.run_main(lambda: main(sys.argv[1:]))
