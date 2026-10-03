"""sched：排程型 kernel 用 daemon ctl（pause／resume）管 6 條成員時間線，量 pause／resume 的延遲與精準度。

四段（各一個空間）：
  a1 round-robin（N=2、每 K=3 個 kernel 回合輪替），換人時 pause 與 resume 同時寫（天真）
  a2 同上，但等 status 看到出去的真的停了才 resume（安全）
  b  優先序：高優先 queue 有工作時 pause 低優先
  c  類 cron：每 K 個 kernel 回合讓成員只跑一回合；fast（看到回合前進立刻 pause）／naive（下個 kernel tock 才 pause）／batch（resume、pause 一起寫）
"""
import datetime
import json
import os
import statistics
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402

PY = sys.executable
KERNEL_MS = 100


def ts(iso):
    return datetime.datetime.fromisoformat(iso).timestamp()


def stats(xs, scale=1.0, nd=1):
    xs = [x * scale for x in xs]
    if not xs:
        return None
    return {"n": len(xs), "min": round(min(xs), nd), "med": round(statistics.median(xs), nd), "max": round(max(xs), nd)}


class Sampler(threading.Thread):
    """每 10 ms 讀一次 status.json，記 (t, {node: (phase, paused)})。"""

    def __init__(self, sp):
        super().__init__(daemon=True)
        self.sp, self.samples, self.stop = sp, [], False

    def run(self):
        while not self.stop:
            st = self.sp.status()
            if st.get("nodes"):
                self.samples.append((time.time(), {n: (v.get("phase"), v.get("paused")) for n, v in st["nodes"].items()}))
            time.sleep(0.01)


def build(sp, members, sched, member_cfg, member_ms=100, extra_mounts=None):
    mounts = {"aosd": ".aosd"}
    for m in members:
        mounts["m_" + m] = m + "/.aos"
    mounts.update(extra_mounts or {})
    sp.node("k", [{"name": "sched", "mode": "keep", "argv": [PY, os.path.join(HERE, "kernel.py")], "mounts": mounts}],
            interval_ms=KERNEL_MS, files={"sched.json": sched})
    for m in members:
        ms = member_ms.get(m, 100) if isinstance(member_ms, dict) else member_ms
        sp.node(m, [{"name": "work", "mode": "each", "argv": [PY, os.path.join(HERE, "member.py")]}],
                interval_ms=ms, files={"member.json": member_cfg.get(m, {"work_ms": 10})})


def klog(sp):
    return pl.fs.read_jsonl(os.path.join(pl.aos7_task.task_dir(sp.path("k"), "sched-r1"), "sched.jsonl"))


def work(sp, m):
    return pl.fs.read_jsonl(sp.path(m, "work.jsonl"))


def kernel_round(sp):
    return max([e["kr"] for e in klog(sp) if e["ev"] == "tock"] or [0])


def run_until_kr(sp, kr, timeout):
    sp.wait_for(lambda: kernel_round(sp) >= kr, timeout=timeout, msg="kernel 沒跑到第 %d 回合" % kr)


def ctl_common(r, tag, kl):
    """所有 ctl：回條有沒有、回條延遲、生效延遲。"""
    done = {e["file"]: e for e in kl if e["ev"] == "done"}
    ctls = [e for e in kl if e["ev"] == "ctl"]
    r.check("%s: kernel 寫的每個 ctl 都拿到 ok 回條" % tag, ctls and all(done.get(c["file"], {}).get("ok") for c in ctls),
            "%d 個 ctl" % len(ctls))
    r.measure("%s ctl→回條 ms" % tag, stats([d["dt"] for d in done.values()], 1000))
    eff = [e for e in kl if e["ev"] == "eff"]
    r.measure("%s pause→真停 ms" % tag, stats([e["dt"] for e in eff if e["op"] == "pause"], 1000))
    r.measure("%s resume→回合前進 ms" % tag, stats([e["dt"] for e in eff if e["op"] == "resume"], 1000))
    r.measure("%s pause 寫下後成員又開了幾回合（分布）" % tag,
              dict(sorted(_count(e["extra"] for e in eff if e["op"] == "pause").items())))
    return ctls


def _count(xs):
    c = {}
    for x in xs:
        c[str(x)] = c.get(str(x), 0) + 1
    return c


def active_counts(samples, members, t_from=0):
    """每個樣本裡『沒停住』（phase 不是 paused／stopped）的成員數。"""
    return [sum(1 for m in members if s.get(m, ("paused",))[0] not in ("paused", "stopped"))
            for t, s in samples if t >= t_from]


# ---------------------------------------------------------------- (a) round-robin

def scen_rr(r, safe):
    tag = "a2-rr-safe" if safe else "a1-rr"
    members = ["m%d" % i for i in range(1, 7)]
    with pl.Space("sched-" + tag) as sp:
        build(sp, members, {"strategy": "rr", "members": members, "n": 2, "k": 3, "safe": safe}, {})
        smp = Sampler(sp)
        smp.start()
        t_start = time.time()
        sp.start()
        run_until_kr(sp, 25, 15)
        smp.stop = True
        sp.stop_all()
        kl = klog(sp)
        ctl_common(r, tag, kl)
        rot = [e for e in kl if e["ev"] == "rotate"]
        r.check("%s: 輪替了至少 6 次" % tag, len(rot) >= 6, len(rot))
        # 開頭：kernel 第一次 pause 生效前，不該跑的成員跑了幾回合
        first = rot[0]
        out0 = [m for m in members if m not in first["active"]]
        eff0 = {}
        for e in kl:
            if e["ev"] == "eff" and e["op"] == "pause":
                eff0.setdefault(e["node"], e["t"])
        leak = {m: sum(1 for w in work(sp, m) if w["t0"] < eff0.get(m, 1e18)) for m in out0}
        r.measure("%s 開頭沒輪到的成員在 kernel 停住它之前跑了幾回合" % tag, leak)
        r.measure("%s daemon 起來到 kernel 第一次 pause 生效 ms" % tag,
                  round((max(eff0[m] for m in out0 if m in eff0) - t_start) * 1000) if eff0 else None)
        # 穩態（第一次輪替全部生效之後）同時在跑的時間線數
        t_steady = max(eff0.values()) if eff0 else t_start
        ac = active_counts(smp.samples, members, t_steady)
        over = sum(1 for a in ac if a > 2)
        r.measure("%s 穩態 status 樣本裡同時沒停住的成員數（分布）" % tag, dict(sorted(_count(ac).items())))
        r.measure("%s 超過 N=2 的樣本比例" % tag, round(over / max(len(ac), 1), 3))
        drain = sum(1 for t, s in smp.samples if t >= t_steady
                    for m in members if s.get(m, (None, None))[1] and s[m][0] not in ("paused", "stopped"))
        r.measure("%s 穩態 status 樣本裡『paused:true 但 phase 還不是 paused』的次數" % tag, drain)
        # 用 daemon log：成員回合區間（tick 完→tock 完）同時最多幾條
        iv = spans(sp, members, t_steady)
        mo = max_overlap(iv)
        r.measure("%s 穩態成員回合區間（log 的 tick→tock）最多同時幾條" % tag, mo)
        if safe:
            r.measure("%s 安全輪替：等出去的停住才 resume 的等待 ms" % tag,
                      stats([e["wait"] for e in kl if e["ev"] == "safe_go"], 1000))
        got = {m: len(work(sp, m)) for m in members}
        r.check("%s: 每個成員都輪到做事" % tag, all(got.values()), got)
        return {"over": over, "ac_max": max(ac) if ac else None, "span_max": mo}


def spans(sp, members, t_from):
    tick = {}
    out = []
    for e in sp.log():
        if e.get("node") in members and e.get("ev") in ("tick", "tock"):
            k = (e["node"], e.get("round"))
            if e["ev"] == "tick":
                tick[k] = ts(e["at"])
            elif k in tick and tick[k] >= t_from:
                out.append((tick[k], ts(e["at"]), e["node"]))
    return out


def max_overlap(iv):
    ev = []
    for a, b, m in iv:
        ev += [(a, 1, m), (b, -1, m)]
    cur, best, live = 0, 0, {}
    for t, d, m in sorted(ev, key=lambda x: (x[0], x[1])):
        live[m] = live.get(m, 0) + d
        best = max(best, sum(1 for v in live.values() if v > 0))
    return best


# ---------------------------------------------------------------- (b) 優先序

def scen_prio(r):
    tag = "b-prio"
    highs, lows = ["h1", "h2"], ["l1", "l2", "l3", "l4"]
    members = highs + lows
    mcfg = {h: {"work_ms": 30, "queue": True} for h in highs}
    mcfg.update({lo: {"work_ms": 160} for lo in lows})        # 低優先的工作比回合長：pause 時常在回合中途
    with pl.Space("sched-" + tag) as sp:
        build(sp, members, {"strategy": "prio", "highs": highs, "lows": lows}, mcfg,
              extra_mounts={"q_" + h: h + "/queue" for h in highs})
        for h in highs:
            os.makedirs(sp.path(h, "queue"), exist_ok=True)
        sp.start()
        run_until_kr(sp, 5, 10)
        inj = []
        for i, (h, n) in enumerate([("h1", 3), ("h2", 2), ("h1", 1)]):
            for j in range(n):
                name = "job-%d-%d.json" % (i, j)
                inj.append((h, name, time.time()))
                pl.write(sp.path(h, "queue", name), {"n": j})
            sp.wait_for(lambda h=h: not os.listdir(sp.path(h, "queue")), timeout=8, msg="%s 的工作沒做完" % h)
            run_until_kr(sp, kernel_round(sp) + 4, 5)
        sp.stop_all()
        kl = klog(sp)
        ctl_common(r, tag, kl)
        hw = {w["job"]: w for h in highs for w in work(sp, h) if w["job"]}
        r.check("%s: 每個工作都被高優先做掉" % tag, all(n in hw for _, n, _ in inj), sorted(hw))
        lat = [hw[n]["t0"] - t for _, n, t in inj if n in hw]
        r.measure("%s 工作放進 queue→高優先開始做 ms" % tag, stats(lat, 1000))
        r.measure("%s 同上，換算成 kernel 回合" % tag, stats(lat, 1000.0 / KERNEL_MS))
        hiv = [(w["t0"], w["t1"]) for w in hw.values()]
        lw = [w for lo in lows for w in work(sp, lo)]
        ov = [lo for lo in lw if any(lo["t0"] < b and a < lo["t1"] for a, b in hiv)]
        r.measure("%s 低優先任務區間跟高優先工作重疊的個數／低優先總數" % tag, "%d/%d" % (len(ov), len(lw)))
        # 低優先 pause 生效（status paused）後還在跑的任務：pause 不停回合中途的任務
        peff = [e for e in kl if e["ev"] == "eff" and e["op"] == "pause" and e["node"] in lows]
        after = 0
        for e in peff:
            after += sum(1 for w in work(sp, e["node"]) if w["t0"] < e["t"] < w["t1"])
        r.measure("%s 低優先 pause 生效時仍在跑的任務數（pause 生效次數）" % tag, "%d（%d）" % (after, len(peff)))
        # 停著時結束的任務：要等 resume 後的 tock 才記進 rounds.jsonl 的 ended
        lag = []
        for lo in lows:
            seen = {}
            for rd in sp.rounds(lo):
                for x in rd.get("ended", []):
                    seen.setdefault(x["tid"], ts(rd["tock_at"]))
            for tid in sp.tasks(lo):
                ex = sp.task_file(lo, tid, "exit.json") or {}
                if tid in seen and ex.get("at"):
                    lag.append(seen[tid] - ts(ex["at"]))
        r.measure("%s 低優先任務結束→記進 rounds.jsonl ended 的延遲 ms" % tag, stats(lag, 1000))
        idle = sum(1 for h in highs for w in work(sp, h) if w["idle"])
        r.measure("%s 高優先沒工作卻被排上的空回合" % tag, idle)
        return {"overlap": len(ov), "after": after}


# ---------------------------------------------------------------- (c) 類 cron

def scen_cron(r):
    tag = "c-cron"
    jobs = [{"node": "c1", "every": 3, "how": "fast"}, {"node": "c2", "every": 3, "how": "naive"},
            {"node": "c3", "every": 2, "how": "fast"}, {"node": "c4", "every": 4, "how": "batch"}]
    crons = [j["node"] for j in jobs]
    bg = ["b1", "b2"]
    members = crons + bg
    ms = {"c1": 100, "c2": 100, "c3": 30, "c4": 100, "b1": 70, "b2": 130}
    with pl.Space("sched-" + tag) as sp:
        build(sp, members, {"strategy": "cron", "jobs": jobs}, {}, member_ms=ms)
        # 開頭就停住：只能預寫 daemon 自己的 .aosd/paused.json（沒有別的宣告方式）
        pl.write(os.path.join(sp.root, ".aosd", "paused.json"), {"paused": crons})
        sp.start()
        sp.wait_for(lambda: sp.status().get("nodes"), timeout=5)
        ghost = sp.ctl("pause", node="ghost/nope")
        run_until_kr(sp, 26, 15)
        sp.stop_all()
        kl = klog(sp)
        ctl_common(r, tag, kl)
        st = [e for e in kl if e["ev"] == "settled"]
        by = {}
        for e in st:
            by.setdefault("%s(%s,每%d)" % (e["node"], e["how"], next(j["every"] for j in jobs if j["node"] == e["node"])),
                          []).append(e["ran"])
        r.measure("%s 每次『只跑一回合』實際跑了幾回合" % tag, by)
        fast = [e["ran"] for e in st if e["how"] == "fast"]
        r.check("%s: fast 每次至少跑到 1 回合、最後停得住" % tag, fast and min(fast) >= 1, fast)
        r.measure("%s 只跑一回合精準（ran==1）的比例" % tag,
                  {h: "%d/%d" % (sum(1 for e in st if e["how"] == h and e["ran"] == 1),
                                 sum(1 for e in st if e["how"] == h)) for h in ("fast", "naive", "batch")})
        # 回合不同步：kernel 回合長度、背景成員每個 kernel 回合跑了幾回合
        kt = [e["t"] for e in kl if e["ev"] == "tock"]
        r.measure("%s kernel 回合實際長度 ms（設 %d）" % (tag, KERNEL_MS), stats([b - a for a, b in zip(kt, kt[1:])], 1000))
        for b in bg:
            ws = [w["t0"] for w in work(sp, b)]
            per = [sum(1 for t in ws if a <= t < c) for a, c in zip(kt, kt[1:])]
            r.measure("%s %s（interval %d ms）每個 kernel 回合跑了幾回合（分布）" % (tag, b, ms[b]), dict(sorted(_count(per).items())))
        # fast：從 kernel tock 到成員那一回合真的開始（成員 tick）要多久
        steps = [e for e in kl if e["ev"] == "step"]
        sl = []
        for e in steps:
            ws = [w["t0"] for w in work(sp, e["node"]) if w["t0"] > e["t"]]
            if ws:
                sl.append(min(ws) - e["t"])
        r.measure("%s kernel 決定 step→成員任務開始 ms" % tag, stats(sl, 1000))
        gd = pl.fs.read_json(os.path.join(sp.root, ".aosd", "ctl-done", ghost), {}) or {}
        r.measure("%s pause 一個不存在的 node 的回條" % tag, gd.get("result", {}).get("ok"))
        r.measure("%s 結束時 ctl-done/ 累積檔數" % tag, len(os.listdir(os.path.join(sp.root, ".aosd", "ctl-done"))))
        return {"by": by, "ghost_ok": gd.get("result", {}).get("ok")}


def main():
    r = pl.Result("sched")
    a1 = scen_rr(r, False)
    a2 = scen_rr(r, True)
    b = scen_prio(r)
    c = scen_cron(r)
    if a1["over"] or a1["span_max"] > 2:
        r.finding("round-robin 換人時 pause 與 resume 一起寫：pause 要等對方回合結束才生效、resume 20 ms 內就生效，"
                  "同時在跑的時間線會短暫超過 N（status 樣本最多 %s 條、回合區間最多 %s 條）" % (a1["ac_max"], a1["span_max"]))
    r.finding("安全輪替要 kernel 自己輪詢 status.json 的 phase=='paused' 才 resume；ctl-done 回條只代表『收到並改了 paused 清單』，不代表停住")
    if b["after"]:
        r.finding("優先序的 pause 不搶佔：低優先 pause 生效時還有 %d 個任務在跑，跟高優先工作重疊 %d 個；要真的讓位只能 kill（而 pause 的 node 上 kill 不執行，D-4）"
                  % (b["after"], b["overlap"]))
    if c["ghost_ok"]:
        r.finding("pause 一個不存在的 node 回條是 ok:true（打錯 node id 不會被發現）")
    r.finding("『只跑一回合』要 kernel 自己看 round.json 前進再補 pause；daemon 沒有 step／跑 N 回合後自動停的 op")
    r.finding("要讓 node 一開始就停著，只能預寫 daemon 的 .aosd/paused.json，或趕在 node 出現前寫 pause ctl")
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
