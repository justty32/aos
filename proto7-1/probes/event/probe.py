"""event：外部在任意時刻往 `<node>/inbox/` 丟事件檔，量「丟檔→處理完」的延遲，跟 interval 的關係，以及能不能叫 daemon 提早開回合。

每個 node 一種寫法（同一個 daemon，同時收同一串事件）：
- `watch`（200 ms）：keep 常駐任務自己每 10 ms 輪詢 inbox，不靠 tock。
- `tock200`（200 ms）：keep 常駐任務每收到 tock 才看 inbox。
- `each200`／`each2000`：每回合起一個 each 任務處理 inbox 就結束。
- `ichg`（2000 ms）：丟檔時順手把 timeline.json 改成 50 ms，處理完改回 2000。
- `rescan`（2000 ms）：丟檔時順手寫 daemon ctl rescan＋pause＋resume。
- `poke`（2000 ms）：丟檔時把 timeline.json 暫時改名讓 daemon 以為 node 消失、再改回來（重新出現的 node 會立刻 tick）。
"""
import datetime
import os
import random
import statistics
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402
import aos7_fs as fs  # noqa: E402

PY = sys.executable
N_EVT = 12
H = os.path.join(HERE, "handle.py")
VARIANTS = {  # node: (interval_ms, mode, how)
    "watch": (200, "keep", "watch"),
    "tock200": (200, "keep", "tock"),
    "each200": (200, "each", "once"),
    "each2000": (2000, "each", "once"),
    "ichg": (2000, "each", "once"),
    "rescan": (2000, "each", "once"),
    "poke": (2000, "each", "once"),
}


def ts(s):
    return datetime.datetime.fromisoformat(s).timestamp()


def stats(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return {"n": len(xs), "min": round(xs[0]), "p50": round(statistics.median(xs)),
            "p90": round(xs[min(len(xs) - 1, int(len(xs) * 0.9))]), "max": round(xs[-1])}


def handled(sp, nid):
    return fs.read_jsonl(sp.path(nid, "handled.jsonl"))


def main():
    r = pl.Result("event")
    rng = random.Random(7)
    with pl.Space("event") as sp:
        for nid, (iv, mode, how) in VARIANTS.items():
            sp.node(nid, [{"name": "h", "mode": mode, "argv": [PY, H, how]}], interval_ms=iv)
        sp.node("pokemid", [{"name": "slow", "argv": ["sleep", "0.4"]}], interval_ms=2000)
        sp.start()
        sp.wait_for(lambda: all(sp.round_of(n) >= 1 for n in VARIANTS), 10, msg="node 沒都起來")
        time.sleep(0.5)

        ichg_pending = []            # 處理完就（另一個 thread）把 interval 改回 2000
        stop = threading.Event()

        def ichg_restore():
            while not stop.wait(0.005):
                if ichg_pending and any(h["n"] == ichg_pending[0] for h in handled(sp, "ichg")):
                    pl.write(sp.path("ichg", ".aos", "timeline.json"), {"interval_ms": 2000})
                    ichg_pending.clear()
        th = threading.Thread(target=ichg_restore, daemon=True)
        th.start()
        poke_ms = []
        for k in range(N_EVT):
            time.sleep(rng.uniform(0.35, 1.2))
            t = time.time()
            for nid in VARIANTS:
                pl.write(sp.path(nid, "inbox", "evt-%02d.json" % k), {"n": k, "t_drop": t})
            # ichg：改 interval
            if not ichg_pending:
                pl.write(sp.path("ichg", ".aos", "timeline.json"), {"interval_ms": 50})
                ichg_pending.append(k)
            # rescan：daemon 現有的 ctl 能不能催
            sp.ctl("rescan")
            sp.ctl("pause", "rescan")
            sp.ctl("resume", "rescan")
            # poke：讓 node 消失再出現
            p0 = time.monotonic()
            tl = sp.path("poke", ".aos", "timeline.json")
            os.rename(tl, tl + ".off")
            try:
                sp.wait_for(lambda: "poke" not in sp.status().get("nodes", {}), 3, poll=0.005, msg="poke 沒消失")
            finally:
                os.rename(tl + ".off", tl)
            poke_ms.append((time.monotonic() - p0) * 1000)

        sp.wait_for(lambda: all(len(handled(sp, n)) >= N_EVT for n in VARIANTS), 8,
                    msg="有事件沒處理完：%s" % {n: len(handled(sp, n)) for n in VARIANTS})
        stop.set()
        th.join()

        # pokemid：回合中途（任務還在跑）催，那回合會怎樣
        def phase(n):
            return sp.status().get("nodes", {}).get(n, {}).get("phase")
        for _ in range(2):
            sp.wait_for(lambda: phase("pokemid") == "idle", 4, poll=0.005, msg="pokemid 沒進 idle")
            sp.wait_for(lambda: phase("pokemid") == "running", 4, poll=0.005, msg="pokemid 沒進 running")
            tl = sp.path("pokemid", ".aos", "timeline.json")
            os.rename(tl, tl + ".off")
            try:
                sp.wait_for(lambda: "pokemid" not in sp.status().get("nodes", {}), 3, poll=0.005, msg="pokemid 沒消失")
            finally:
                os.rename(tl + ".off", tl)
        sp.wait_for(lambda: phase("pokemid") == "idle" and len(sp.rounds("pokemid")) >= 2, 4, msg="pokemid 沒收回合")
        pm_last = sp.round_of("pokemid")
        pm_tocked = [x["round"] for x in sp.rounds("pokemid")]
        r.measure("pokemid：回合數／有 tock 的回合", [pm_last, pm_tocked])
        missing = sorted(set(range(1, pm_last + 1)) - set(pm_tocked))
        r.measure("pokemid：回合中途催，沒有 tock 的回合", missing)
        r.check("pokemid：回合中途催之後時間線照樣在走", len(pm_tocked) >= 1 and pm_last >= 3)
        pl.write(sp.path("ichg", ".aos", "timeline.json"), {"interval_ms": 2000})

        lat = {}
        for nid in VARIANTS:
            hs = handled(sp, nid)
            ns = sorted(h["n"] for h in hs)
            r.check("%s：%d 個事件都處理了、各一次" % (nid, N_EVT), ns == list(range(N_EVT)), ns)
            lat[nid] = [(h["t_done"] - h["t_drop"]) * 1000 for h in hs]
            iv = VARIANTS[nid][0]
            r.measure("%s 延遲 ms（interval %d）" % (nid, iv), stats(lat[nid]))
        r.check("watch（自己輪詢）p50 < 300 ms", stats(lat["watch"])["p50"] < 300, stats(lat["watch"]))
        r.check("each2000 最慢 < interval＋1.5 秒", max(lat["each2000"]) < 3500, round(max(lat["each2000"])))
        r.check("每回合 each 的延遲比常駐輪詢大", statistics.median(lat["each200"]) > statistics.median(lat["watch"]))

        # 回合與 rescan／poke 的副作用
        rows = {n: sp.rounds(n) for n in VARIANTS}
        r.measure("每條時間線跑了幾回合", {n: len(v) for n, v in rows.items()})
        e2 = rows["each200"]
        r.measure("each200 每回合 tick→tock ms（each 任務算 python 啟動）",
                  stats([(ts(x["tock_at"]) - ts(x["tick_at"])) * 1000 for x in e2]))
        t2 = rows["tock200"]
        r.measure("tock200 每回合 tick→tock ms（沒起任務：tock 立刻到）",
                  stats([(ts(x["tock_at"]) - ts(x["tick_at"])) * 1000 for x in t2]))
        log = sp.log()
        r.measure("poke：log 裡 node- / node+ 次數",
                  [sum(1 for e in log if e.get("node") == "poke" and e.get("ev") == ev) for ev in ("node-", "node+")])
        r.measure("poke：外部一次『消失再出現』花 ms", stats(poke_ms))
        last = sp.round_of("poke")
        tocked = {x["round"] for x in rows["poke"]}
        r.measure("poke：沒有 tock 的回合（node 消失時那回合不收）", sorted(set(range(1, last + 1)) - tocked - {last}))
        ticks = sorted(ts(e["at"]) for e in log if e.get("node") == "poke" and e.get("ev") == "tick")
        r.measure("poke：最短的 tick 間隔 ms（interval 2000）",
                  round(min(b - a for a, b in zip(ticks, ticks[1:])) * 1000) if len(ticks) > 1 else None)
        ok_ctl = [e for e in log if e.get("ev") == "ctl" and e.get("op") in ("rescan", "pause", "resume")]
        r.check("rescan／pause／resume 控制檔都執行成功", ok_ctl and all(e["ok"] for e in ok_ctl), len(ok_ctl))
        r.measure("rescan 延遲 ÷ each2000 延遲（p50）",
                  round(statistics.median(lat["rescan"]) / statistics.median(lat["each2000"]), 2))

        r.finding("沒有『現在就開下一回合』的管道：ctl 只有 pause/resume/stop/rescan，rescan、pause+resume 都不縮短 idle 的等待；"
                  "改 timeline.json 的 interval 要等目前這回合的 t_end 才生效")
        r.finding("唯一能催的是 hack：把 timeline.json 改名讓 node 消失再出現，新時間線立刻 tick；代價是 log 多 node-/node+、"
                  "那條時間線的 thread 換掉、回合中途被催會留下沒 tock 的回合")
        r.finding("要低延遲只能寫常駐輪詢任務（不靠 tick-tock），tick-tock 對事件驅動只是『最慢多久會被看一次』的上限")
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
