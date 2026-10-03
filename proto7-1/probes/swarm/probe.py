"""swarm：一條時間線每回合起幾十個短命任務（map／reduce），看 tick、提前 tock、任務資料夾累積、批次完成訊號。

四段（同一個 daemon，一段一個 node，做完 pause 掉）：
- A `each50`：tasks.json 寫 50 個 each 的 map＋同回合 reduce（same）＋下回合 reduce（next）。
- B `disp`：一個常駐的調度任務（用一次性 spawn 起）每批寫 40 個 spawn/*.json，自己判斷上一批收齊。
- N `names`：tid 撞名（同名多份、名字裡帶 -r1、會被換成 _ 的字元）。
- C `bloat`／`clean`：bloat 先塞 4000 個已結束的任務資料夾，比 tick／tock／status 的時間。
"""
import datetime
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402
import aos7_fs as fs  # noqa: E402

PY = sys.executable
N_MAP = 50
A_ROUNDS = 14
B_N, B_BATCHES = 40, 5
BLOAT = 4000


def ts(s):
    return datetime.datetime.fromisoformat(s).timestamp()


def stats(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    xs = sorted(xs)
    return {"n": len(xs), "min": round(xs[0]), "p50": round(statistics.median(xs)),
            "p90": round(xs[min(len(xs) - 1, int(len(xs) * 0.9))]), "max": round(xs[-1])}


def timing(sp, nid):
    """每回合：tick 工作時間（log 的 tick 行 − round.json 的 tick_at）、tock 工作時間、tick→tock、是否提前 tock、回合間隔。"""
    log = [e for e in sp.log() if e.get("node") == nid]
    tick_log = {e["round"]: ts(e["at"]) for e in log if e.get("ev") == "tick"}
    tock_log = {e["round"]: (ts(e["at"]), e.get("early")) for e in log if e.get("ev") == "tock"}
    rows = []
    rs = sp.rounds(nid)
    for i, r in enumerate(rs):
        n = r["round"]
        ta, to = ts(r["tick_at"]), ts(r["tock_at"])
        row = {"round": n, "started": len(r.get("started", [])),
               "tick_ms": (tick_log[n] - ta) * 1000 if n in tick_log else None,
               "tock_ms": (tock_log[n][0] - to) * 1000 if n in tock_log else None,
               "tick_to_tock_ms": (to - ta) * 1000,
               "early": tock_log.get(n, (None, None))[1],
               "period_ms": (ts(rs[i + 1]["tick_at"]) - ta) * 1000 if i + 1 < len(rs) else None}
        rows.append(row)
    return rows


def cpu_s(pid):
    """daemon 程序自己的 CPU 秒數（utime+stime，不含子程序）。"""
    try:
        with open("/proc/%d/stat" % pid) as f:
            rest = f.read().rsplit(")", 1)[1].split()
        return (int(rest[11]) + int(rest[12])) / os.sysconf("SC_CLK_TCK")
    except OSError:
        return None


def status_gaps(sp, dur):
    """取樣 status.json 的 at：daemon 主迴圈多久寫一次（spec：每 ~20 ms）。"""
    seen, end = [], time.monotonic() + dur
    while time.monotonic() < end:
        at = sp.status().get("at")
        if at and (not seen or seen[-1] != at):
            seen.append(at)
        time.sleep(0.003)
    g = [(ts(b) - ts(a)) * 1000 for a, b in zip(seen, seen[1:])]
    return stats(g)


def pause_and_drain(sp, nid, timeout=15):
    sp.ctl("pause", nid)
    sp.wait_for(lambda: sp.status().get("nodes", {}).get(nid, {}).get("phase") == "paused", timeout,
                msg="%s 沒停下" % nid)
    sp.wait_for(lambda: not sp.live(nid), timeout, msg="%s 任務沒收完" % nid)


def du(path):
    n, size = 0, 0
    for d, _, files in os.walk(path):
        for f in files:
            n += 1
            try:
                size += os.lstat(os.path.join(d, f)).st_blocks * 512
            except OSError:
                pass
    return n, size


def phase_a(sp, r):
    items = [{"name": "map", "mode": "each", "argv": [PY, os.path.join(HERE, "map.py"), str(i)]} for i in range(N_MAP)]
    items += [{"name": "reduce", "argv": [PY, os.path.join(HERE, "reduce.py"), "same"]},
              {"name": "rnext", "argv": [PY, os.path.join(HERE, "reduce.py"), "next"]}]
    sp.node("each50", items, interval_ms=300)
    pid = sp.procs[0][1].pid
    c0, w0 = cpu_s(pid), time.monotonic()
    sp.wait_for(lambda: sp.round_of("each50") >= A_ROUNDS // 2, 20, msg="each50 沒跑到一半")
    r.measure("A status.json 寫入間隔 ms（每回合 52 任務時）", status_gaps(sp, 1.0))
    sp.wait_for(lambda: len(sp.rounds("each50")) >= A_ROUNDS, 20, msg="each50 沒跑滿")
    c1, w1 = cpu_s(pid), time.monotonic()
    pause_and_drain(sp, "each50")
    r.measure("A daemon 自己的 CPU 佔比（52 任務／回合）", round((c1 - c0) / (w1 - w0), 3))

    rows = timing(sp, "each50")
    full = [x for x in rows if x["started"] == N_MAP + 2]
    r.check("A 每回合 tick 都起 52 個（50 map＋2 reduce）", len(full) == len(rows) and len(rows) >= A_ROUNDS,
            [x["started"] for x in rows])
    r.measure("A tick 工作時間 ms（起 52 任務）", stats([x["tick_ms"] for x in rows]))
    r.measure("A tock 工作時間 ms", stats([x["tock_ms"] for x in rows]))
    r.measure("A tick→tock ms（interval 300）", stats([x["tick_to_tock_ms"] for x in rows]))
    r.measure("A 提前 tock 的回合比例", "%d/%d" % (sum(1 for x in rows if x["early"]), len(rows)))
    r.measure("A 回合週期 ms", stats([x["period_ms"] for x in rows]))
    half = len(rows) // 2
    r.measure("A tick 工作時間 ms 前半 vs 後半（資料夾累積）",
              [stats([x["tick_ms"] for x in rows[:half]]), stats([x["tick_ms"] for x in rows[half:]])])

    # tid：同名 50 份 → map-rN、map-rN-2 … map-rN-50
    r1 = sp.rounds("each50")[0]
    maps1 = [t for t in r1["started"] if t.startswith("map-")]
    want = ["map-r1"] + ["map-r1-%d" % k for k in range(2, N_MAP + 1)]
    r.check("A 同名 50 份的 tid 是 map-r1、map-r1-2…map-r1-50", maps1 == want, maps1[:3] + ["…"] + maps1[-2:])

    # reduce
    node = sp.path("each50")
    same_ok, next_ok, fail_seen, waited, seen_ms, from_line, alive_tock = 0, 0, 0, [], [], [], []
    last_round = rows[-1]["round"]
    for x in rows:
        n = x["round"]
        exp_fail = sum(1 for i in range(N_MAP) if (n + i) % 23 == 0)
        s = fs.read_json(os.path.join(node, "out", "r%d" % n, "reduce-same.json"))
        if s and len(s["failed"]) == exp_fail and s["ok_files"] + len(s["failed"]) == N_MAP and not s["unknown"]:
            same_ok += 1
            fail_seen += len(s["failed"])
            waited.append(s["waited_ms"])
            seen_ms.append(s["started_seen_ms"])
        nx = fs.read_json(os.path.join(node, "out", "r%d" % n, "reduce-next.json"))
        if nx and len(nx["failed"]) == exp_fail and nx["ok_files"] + len(nx["failed"]) == N_MAP:
            next_ok += 1
            from_line.append(nx["known_from_rounds_line"])
            alive_tock.append(nx["alive_at_tock"])
    r.check("A 同回合 reduce 每回合都收齊 50 個 map、失敗的（rc=3）都看得到", same_ok == len(rows), "%d/%d" % (same_ok, len(rows)))
    r.check("A 下回合 reduce 收齊前一回合（最後一回合沒有下回合）", next_ok >= len(rows) - 2, "%d/%d" % (next_ok, len(rows)))
    r.measure("A reduce(same) 等 round.json 的 started 收齊 ms", stats(seen_ms))
    r.measure("A reduce(same) 從起來到收齊 50 個 exit.json ms", stats(waited))
    r.measure("A reduce(next) 從 rounds.jsonl 那行就知道結局的 map 數（共 50）", stats(from_line))
    r.measure("A reduce(next) 上一回合 tock 時還活著的 map 數", stats(alive_tock))
    r.measure("A map 故意失敗被 reduce 看到的次數", fail_seen)
    ended_codes = [e for x in sp.rounds("each50") for e in x["ended"] if e.get("code") not in (0,)]
    r.measure("A rounds.jsonl ended 裡 code≠0 的筆數", len(ended_codes))

    n_dirs = len(os.listdir(os.path.join(node, ".aos", "tasks")))
    nf, sz = du(os.path.join(node, ".aos", "tasks"))
    r.measure("A 任務資料夾數／檔數／佔用 KB", [n_dirs, nf, sz // 1024])
    rj = os.path.getsize(os.path.join(node, ".aos", "rounds.jsonl"))
    r.measure("A rounds.jsonl 每回合位元組", rj // max(1, len(rows)))
    return last_round


def phase_b(sp, r):
    # 調度用一次性的 spawn 起（不放 tasks.json 的 keep）：keep 的任務做完自己結束，下個 tick 又被起回來從頭再派（D-3）
    sp.node("disp", [], interval_ms=150, files={".aos/spawn/dispatch.json": {
        "name": "dispatch", "argv": [PY, os.path.join(HERE, "dispatch.py"), str(B_N), str(B_BATCHES)]}})
    # N：tid 撞名（同時跑）
    sp.node("names", [{"name": "x", "argv": ["true"]}, {"name": "x", "argv": ["true"]},
                      {"name": "x-r1", "argv": ["true"]}, {"name": "a/b", "argv": ["true"]},
                      {"name": "a_b", "argv": ["true"]}, {"name": "map-r1", "argv": ["true"]}],
            interval_ms=100, files={".aos/spawn/0.json": {"name": "x", "argv": ["true"]}})
    sp.wait_for(lambda: len(sp.rounds("names")) >= 2, 10, msg="names 沒跑兩回合")
    pause_and_drain(sp, "names")
    started = [x["started"] for x in sp.rounds("names")[:2]]
    r.measure("N tid（第 1、2 回合）", started)
    r.check("N 同回合同名不撞（spawn 的 x 先拿 x-r1，任務表的 x 拿 x-r1-2、x-r1-3）",
            started[0][:3] == ["x-r1", "x-r1-2", "x-r1-3"], started[0])
    tids = [t for s in started for t in s]
    r.check("N 兩回合所有 tid 都不重複", len(tids) == len(set(tids)))
    names = {t: (sp.task_file("names", t, "birth.json") or {}).get("name") for t in started[0]}
    sanit = sorted(t for t, nm in names.items() if nm in ("a/b", "a_b"))
    r.measure("N name a/b 與 a_b 的 tid", sanit)

    disp = None
    def batches():
        nonlocal disp
        for t in sp.tasks("disp"):
            if t.startswith("dispatch-"):
                disp = t
        return fs.read_jsonl(os.path.join(sp.path("disp"), ".aos", "tasks", disp, "batches.jsonl")) if disp else []
    sp.wait_for(lambda: len(batches()) >= B_BATCHES, 25, msg="調度沒跑完 %d 批" % B_BATCHES)
    bs = batches()
    pause_and_drain(sp, "disp")
    r.check("B 調度任務寫 spawn 起了 %d 批、每批 %d 個都收齊" % (B_BATCHES, B_N),
            len(bs) == B_BATCHES and all(b["n"] == B_N for b in bs), [b["n"] for b in bs])
    # 調度在 tock 後才寫 40 個 spawn，下個 tick 可能在寫到一半時來：一批被拆成兩回合（沒有「整批一起交」的寫法）
    r.measure("B 每批：寫 spawn 的回合 → 實際起的回合", [(b["written_round"], b["started_rounds"]) for b in bs])
    r.measure("B 被拆成兩回合起的批數", sum(1 for b in bs if len(b["started_rounds"]) > 1))
    r.measure("B 調度：寫 spawn 到看到整批結束的 tock 數", [b["waited_tocks"] for b in bs])
    r.measure("B 調度：寫 spawn 到確認整批結束 ms", stats([b["write_to_done_ms"] for b in bs]))
    r.measure("B 調度：看到的失敗 map", sum(len(b["failed"]) for b in bs))
    # B2：慢一點的調度（每個 spawn 間隔 3 ms，一批約 120 ms），interval 150
    sp.node("disp2", [], interval_ms=150, files={".aos/spawn/dispatch.json": {
        "name": "dispatch", "argv": [PY, os.path.join(HERE, "dispatch.py"), str(B_N), "3", "0.003"]}})
    def batches2():
        ts_ = [t for t in sp.tasks("disp2") if t.startswith("dispatch-")]
        return fs.read_jsonl(os.path.join(sp.path("disp2"), ".aos", "tasks", ts_[0], "batches.jsonl")) if ts_ else []
    sp.wait_for(lambda: len(batches2()) >= 3, 20, msg="disp2 沒跑完 3 批")
    b2 = batches2()
    pause_and_drain(sp, "disp2")
    r.check("B2 慢調度 3 批也都收齊 40 個", all(b["n"] == B_N for b in b2), [b["n"] for b in b2])
    r.measure("B2 慢調度：寫 spawn 的回合 → 實際起的回合", [(b["written_round"], b["started_rounds"]) for b in b2])
    r.measure("B2 慢調度：被拆成兩回合起的批數", sum(1 for b in b2 if len(b["started_rounds"]) > 1))
    rows = timing(sp, "disp")
    big = [x for x in rows if x["started"] >= B_N]
    r.measure("B 起 40 任務的回合：tick 工作 ms／tick→tock ms／提前 tock",
              [stats([x["tick_ms"] for x in big]), stats([x["tick_to_tock_ms"] for x in big]),
               "%d/%d" % (sum(1 for x in big if x["early"]), len(big))])
    idle = [x for x in rows if x["started"] == 0]
    r.measure("B 沒起任務的回合 tick→tock ms（keep 調度在跑，不等它）", stats([x["tick_to_tock_ms"] for x in idle]))


def phase_c(sp, r):
    name = sp.ctl("pause", "bloat")   # 先 pause 再建 node：塞完資料夾才開始走
    sp.wait_for(lambda: os.path.exists(os.path.join(sp.root, ".aosd", "ctl-done", name)), 5, msg="pause 沒生效")
    sp.node("clean", [{"name": "q", "argv": ["true"]}], interval_ms=100)
    n = sp.node("bloat", [{"name": "q", "argv": ["true"]}], interval_ms=100)
    td = os.path.join(n, ".aos", "tasks")
    t0 = time.monotonic()
    for k in range(BLOAT):
        d = os.path.join(td, "old-r%d" % k)
        os.makedirs(d)
        for fn, obj in (("birth.json", {"tid": "old-r%d" % k, "name": "old", "round": 0}),
                        ("exit.json", {"code": 0}), ("ended.json", {"round": 0})):
            with open(os.path.join(d, fn), "w") as f:
                json.dump(obj, f)
    r.measure("C 造 %d 個假任務資料夾 秒" % BLOAT, round(time.monotonic() - t0, 2))
    t0 = time.monotonic()
    import aos7_task
    for _ in range(5):
        aos7_task.live_tasks(n)
    r.measure("C live_tasks()（status.json 每圈都跑）一次 ms，%d 個資料夾" % BLOAT,
              round((time.monotonic() - t0) / 5 * 1000, 1))
    pid = sp.procs[0][1].pid
    r.measure("C status.json 寫入間隔 ms（還沒 bloat 時）", status_gaps(sp, 0.6))
    sp.ctl("resume", "bloat")
    c0, w0 = cpu_s(pid), time.monotonic()
    sp.wait_for(lambda: len(sp.rounds("bloat")) >= 15, 25, msg="bloat 沒跑 15 回合")
    r.measure("C status.json 寫入間隔 ms（bloat 在時）", status_gaps(sp, 0.6))
    c1, w1 = cpu_s(pid), time.monotonic()
    r.measure("C daemon 自己的 CPU 佔比（有 %d 個資料夾的 node）" % BLOAT, round((c1 - c0) / (w1 - w0), 3))
    for nid in ("clean", "bloat"):
        rows = timing(sp, nid)[-12:]
        r.measure("C %s：tick 工作 ms／tock 工作 ms／回合週期 ms（interval 100）" % nid,
                  [stats([x["tick_ms"] for x in rows]), stats([x["tock_ms"] for x in rows]),
                   stats([x["period_ms"] for x in rows])])
    r.check("C 塞了 %d 個資料夾的 node 照樣在走" % BLOAT, len(sp.rounds("bloat")) >= 15)


def main():
    r = pl.Result("swarm")
    with pl.Space("swarm") as sp:
        sp.start()
        phase_a(sp, r)
        phase_b(sp, r)
        phase_c(sp, r)
        r.finding("「這批任務都結束了」沒有訊號：提前 tock 只發 tock.json 給活任務，each 的 reduce 只能自己輪詢每個 exit.json；"
                  "tock.json 也不說這次是提前還是到時（early 只在 daemon 的 log.jsonl）")
        r.finding("一批任務沒有批次 id：reduce 要靠 round.json 的 started（等它出現自己的 tid＝清單完整）或 rounds.jsonl 上一回合那行；"
                  "spawn 起的要靠 argv 自己帶批名")
        r.finding("任務資料夾只增不減，tick（keep 判斷）、tock、daemon 每 20 ms 的 status.json 都全掃；數字見 C")
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
