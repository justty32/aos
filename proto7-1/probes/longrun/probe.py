"""longrun：長任務（不看 tock）與「每回合必須回報」的任務同一條時間線；另一條時間線放「跑比 interval 久的 each 任務」看堆積。

想讓基礎設施露出：tock.json 覆寫只留最新 → 慢一點的任務漏看幾回合；長任務會不會拖住回合；
基礎設施知不知道誰這回合回報了；each 任務堆積多少；kernel 要判斷「該回報沒回報」得讀哪些檔。
"""
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import probelib as pl  # noqa: E402

T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "t.py")
IV_A = 100     # ms
IV_B = 100
SLOW_S = 1.0   # each 任務跑多久（> interval）
LONG_N, LONG_STEP = 50, 0.1

REPORTERS = {               # 名字: (poll 秒, 收到 tock 後做事秒數)
    "rep_fast": (0.01, 0.0),
    "rep_mid": (0.05, 0.06),
    "rep_poll": (0.15, 0.0),     # 輪詢比 interval 慢
    "rep_work": (0.01, 0.15),    # 每回合要做的事比 interval 長
}


def ts(s):
    return datetime.datetime.fromisoformat(s).timestamp() if s else None


def name_of(sp, nid, tid):
    b = sp.task_file(nid, tid, "birth.json") or {}
    return b.get("name")


def main():
    r = pl.Result("longrun")
    with pl.Space("longrun") as sp:
        tasks_a = [{"name": n, "mode": "keep", "argv": [pl.PY, T, "report", str(p), str(w)]}
                   for n, (p, w) in REPORTERS.items()]
        sp.node("a", tasks_a, interval_ms=IV_A,
                files={".aos/spawn/long.json": {"name": "long", "argv": [pl.PY, T, "long", str(LONG_N), str(LONG_STEP)]}})
        sp.node("b", [{"name": "slow", "mode": "each", "argv": [pl.PY, T, "slow", str(SLOW_S)]}], interval_ms=IV_B)
        sp.start()

        def long_done():
            return any(t.startswith("long-") and os.path.exists(sp.path("a", ".aos", "tasks", t, "exit.json"))
                       for t in sp.tasks("a"))
        sp.wait_for(lambda: long_done() and len(sp.rounds("a")) >= 40 and len(sp.rounds("b")) >= 30,
                    timeout=25, msg="a 跑完長任務且 40 回合、b 30 回合")
        sp.ctl("pause", node="a")
        sp.ctl("pause", node="b")
        sp.wait_for(lambda: sp.status().get("nodes", {}).get("a", {}).get("phase") == "paused"
                    and sp.status().get("nodes", {}).get("b", {}).get("phase") == "paused", timeout=10)
        time.sleep(0.4)   # 讓報告任務把最後一個 tock 處理完

        ra = sp.rounds("a")
        rb = sp.rounds("b")
        log = sp.log()
        names = {t: name_of(sp, "a", t) for t in sp.tasks("a")}
        long_tid = [t for t, n in names.items() if n == "long"][0]

        # ---- 長任務 ----
        prog = pl.fs.read_jsonl(sp.path("a", ".aos", "tasks", long_tid, "progress.jsonl"))
        long_end = [e for x in ra for e in x["ended"] if e["tid"] == long_tid]
        r.check("長任務寫滿進度並以 0 結束", len(prog) == LONG_N and long_end and long_end[0]["code"] == 0,
                {"progress": len(prog), "ended": long_end})
        long_rounds = [x["round"] for x in ra if long_tid in x["alive"]]
        r.measure("長任務跨了幾回合", len(long_rounds))
        dur_a = {x["round"]: round((ts(x["tock_at"]) - ts(x["tick_at"])) * 1000) for x in ra}
        early_a = {e["round"]: e.get("early") for e in log if e.get("ev") == "tock" and e.get("node") == "a"}
        during = [k for k in long_rounds if k >= 2]
        r.check("長任務活著期間，第 2 回合起 tick 都沒再起它（started 不含長任務，所以提前 tock 不等它）",
                all(long_tid not in x["started"] for x in ra if x["round"] >= 2))
        r.measure("a 第 1 回合 tick→tock ms（起了長任務＋報告任務，等滿 interval）", dur_a.get(1))
        r.measure("a 長任務活著期間 tick→tock ms 中位數", sorted(dur_a[k] for k in during)[len(during) // 2] if during else None)
        r.measure("a 長任務活著期間提前 tock 比例", "%d/%d" % (sum(1 for k in during if early_a.get(k)), len(during)))
        r.measure("tock.json 寫給長任務的次數（它從不看）", len(long_rounds))

        # ---- 回報任務 ----
        last_round = ra[-1]["round"]
        tock_at = {x["round"]: ts(x["tock_at"]) for x in ra}
        tick_at = {x["round"]: ts(x["tick_at"]) for x in ra}
        rep = {}
        for tid, n in names.items():
            if n not in REPORTERS:
                continue
            tdir = sp.path("a", ".aos", "tasks", tid)
            expect = [x["round"] for x in ra if tid in x["alive"]]
            got = {}
            for fn in os.listdir(tdir):
                if fn.startswith("report-") and fn.endswith(".json"):
                    o = pl.fs.read_json(os.path.join(tdir, fn)) or {}
                    got[o.get("round")] = o
            missed = [k for k in expect if k not in got]
            late_tick = [k for k, o in got.items() if (o.get("node_round_at_write") or 0) > k]
            # kernel 的視角：在下一回合 tock 時去看，第 k 回合的報告在不在
            late_next_tock = [k for k, o in got.items() if k + 1 in tock_at and o["t"] > tock_at[k + 1]]
            lat = sorted(round((o["t"] - tock_at[k]) * 1000) for k, o in got.items() if k in tock_at)
            gaps = pl.fs.read_json(os.path.join(tdir, "gaps.json"), []) or []
            rep[n] = {"該回報回合": len(expect), "漏": len(missed),
                      "漏率%": round(100 * len(missed) / max(1, len(expect))),
                      "自己看到的跳號次數": len(gaps),
                      "報告寫時已過下一個 tick": len(late_tick),
                      "報告晚於下一回合 tock": len(late_next_tock),
                      "tock→報告 ms 中位數": lat[len(lat) // 2] if lat else None}
            r.check("%s 至少寫出一份報告" % n, len(got) >= 1)
        for n in REPORTERS:
            r.measure("回報 " + n + " " + str(REPORTERS[n]), rep.get(n))
        fast = rep.get("rep_fast", {})
        if fast.get("漏"):
            r.finding("連最快的回報任務（10 ms 輪詢、不做事）也漏了 %d 回合：tock.json 覆寫，tock 之後下一個 tick 在 interval 內就到" % fast["漏"])
        r.finding("tock 沒有『回應』管道：rounds.jsonl 只記 alive／ended，看不出誰這回合回報了；"
                  "kernel 要判斷違約只能自己對 rounds.jsonl 的 alive × 任務資料夾裡自訂的 report-<N>.json，還得自己定寬限（報告常晚於下一個 tick）")

        # ---- each 堆積 ----
        slow_alive = [sum(1 for t in x["alive"] if t.startswith("slow-")) for x in rb]
        dirs_b = len(sp.tasks("b"))
        dur_b = sorted(round((ts(x["tock_at"]) - ts(x["tick_at"])) * 1000) for x in rb)
        early_b = [e.get("early") for e in log if e.get("ev") == "tock" and e.get("node") == "b"]
        r.check("跑比 interval 久的 each 任務會堆積（同時活著 ≥ 2）", max(slow_alive) >= 2, max(slow_alive))
        r.check("b 的 tock 從不提前（本回合起的 each 都還沒結束）", not any(early_b), early_b.count(True))
        r.measure("b 同時活著的 slow 最多", max(slow_alive))
        r.measure("b 穩定期同時活著的 slow（後半中位數）", sorted(slow_alive[len(slow_alive) // 2:])[len(slow_alive[len(slow_alive) // 2:]) // 2])
        r.measure("b 任務資料夾數／回合數", "%d/%d" % (dirs_b, len(rb)))
        r.measure("b tick→tock ms 中位數（interval %d）" % IV_B, dur_b[len(dur_b) // 2])
        r.measure("b 回合實際週期 ms（tick 到下一個 tick 中位數）",
                  sorted(round((ts(rb[i + 1]["tick_at"]) - ts(rb[i]["tick_at"])) * 1000) for i in range(len(rb) - 1))[len(rb) // 2])
        r.finding("each 沒有『上一個還在跑就跳過』或並行上限：%.1f 秒的任務在 %d ms 回合下穩定堆到約 %d 個" %
                  (SLOW_S, IV_B, max(slow_alive)))
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
