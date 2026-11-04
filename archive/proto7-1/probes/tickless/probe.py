"""tickless：一百個大多閒著的 agent node，kernel 在沒人按回合等待時 pause、有信才 resume（NO_HZ 啟發，D-16）。

n/000～n/094 是收信的 agent（idle_safe 宣告），n/095～n/099 是每 3 回合做事的 cron（永遠不能停）。interval 都是 1 秒。
k 是 kernel（掛 .aosd 與 100 個 node），兩段：
  A（照回合）：kernel 不動，跑 PHASE 秒，期間隨機丟 LETTERS 封信
  B（tickless）：kernel 開始管：閒著的 pause、有信 resume rounds 1；等它停好 95 條後一樣跑 PHASE 秒、丟 LETTERS 封
  C（tickless＋wake）：同 B，但 resume 後緊接一個 wake
量：tick／tock 程序數、daemon（含它等的 tick／tock 子程序）與 kernel 的 CPU、信從寫入到處理的延遲（毫秒、回合）。
"""
import os
import random
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402

PY = pl.PY
TL = os.path.join(HERE, "tl.py")
N, CRON = 100, 5
PHASE = 3.0
LETTERS = 15
HZ = os.sysconf("SC_CLK_TCK")


def nid(i):
    return "n/%03d" % i


def cpu(pid, children=False):
    try:
        with open("/proc/%d/stat" % pid) as f:
            x = f.read().rsplit(")", 1)[1].split()
    except OSError:
        return None
    v = int(x[11]) + int(x[12]) + ((int(x[13]) + int(x[14])) if children else 0)   # utime stime [cutime cstime]
    return v / HZ


def main():
    r = pl.Result("tickless")
    rnd = random.Random(7)
    with pl.Space("tickless") as sp:
        for i in range(N):
            role = "cron" if i >= N - CRON else "idle"
            sp.node(nid(i), [{"name": role, "mode": "keep", "argv": [PY, TL, role]}], interval_ms=1000)
        mounts = {"aosd": ".aosd"}
        mounts.update({"n%03d" % i: nid(i) for i in range(N)})
        sp.node("k", [{"name": "kern", "mode": "keep", "argv": [PY, TL, "kern"], "mounts": mounts}], interval_ms=1000,
                files={"mode.json": {"active": False}})
        d = sp.start()
        sp.wait_for(lambda: all(os.path.exists(sp.path(nid(i), "idle.json")) for i in range(N)), timeout=20,
                    msg="100 個 node 都跑過一回合")

        def rounds_total():
            return sum(sp.round_of(nid(i)) for i in range(N))

        def phase(tag):
            sent = []
            t0, r0, c0, s0 = time.time(), rounds_total(), cpu(d.pid, children=True), cpu(d.pid)
            plan = sorted(rnd.uniform(0.2, PHASE - 0.6) for _ in range(LETTERS))
            for k, at in enumerate(plan):
                while time.time() - t0 < at:
                    time.sleep(0.005)
                i = rnd.randrange(N - CRON)
                name = "%s-%02d.json" % (tag, k)
                pl.write(sp.path(nid(i), "inbox", name), {"t": time.time(), "round": sp.round_of(nid(i))})
                sent.append((i, name))
            while time.time() - t0 < PHASE:
                time.sleep(0.01)
            dt = time.time() - t0
            rs, cc, sc = rounds_total() - r0, cpu(d.pid, children=True) - c0, cpu(d.pid) - s0
            sp.wait_for(lambda: all(any(x["letter"] == n for x in pl.fs.read_jsonl(sp.path(nid(i), "done.jsonl")))
                                    for i, n in sent), timeout=8, msg="%s 的信都處理完" % tag)
            done = {x["letter"]: x for i in range(N) for x in pl.fs.read_jsonl(sp.path(nid(i), "done.jsonl"))}
            lat = [round((done[n]["t"] - done[n]["sent_t"]) * 1000) for _, n in sent]
            lr = [done[n]["round"] - done[n]["sent_round"] for _, n in sent]
            res = {"秒": round(dt, 2), "每秒回合（100 條合計）": round(rs / dt, 1),
                   "每秒 tick＋tock 程序": round(2 * rs / dt, 1),
                   "daemon＋子程序 CPU 秒／秒": round(cc / dt, 2), "daemon 本身 CPU 秒／秒": round(sc / dt, 2),
                   "信延遲 ms 中位／最大": [round(statistics.median(lat)), max(lat)],
                   "信延遲超過 200 ms 的封數": sum(1 for x in lat if x > 200),
                   "信延遲 回合 中位／最大（處理的回合 − 寄出時的回合）": [statistics.median(lr), max(lr)]}
            return res, lat, lr

        a, lat_a, _ = phase("A")
        r.measure("A 照回合", a)

        pl.write(sp.path("k", "mode.json"), {"active": True})
        t_on = time.time()
        idle_ids = [nid(i) for i in range(N - CRON)]
        sp.wait_for(lambda: all(sp.status().get("nodes", {}).get(x, {}).get("paused") for x in idle_ids),
                    timeout=15, msg="kernel 把 95 條閒線都 pause")
        r.measure("B：kernel 開始管到 95 條都停好（秒）", round(time.time() - t_on, 2))
        cron_r0 = [sp.round_of(nid(i)) for i in range(N - CRON, N)]
        kt = [t for t in sp.live("k")]
        kpid = (sp.task_file("k", kt[0], "pid.json") or {}).get("pid") if kt else None
        k0 = cpu(kpid) if kpid else None
        b, lat_b, lr_b = phase("B")
        k1 = cpu(kpid) if kpid else None
        r.measure("B tickless（只 resume）", b)
        if k0 is not None and k1 is not None:
            r.measure("B：kernel 自己輪詢的 CPU 秒／秒", round((k1 - k0) / b["秒"], 2))
        pl.write(sp.path("k", "mode.json"), {"active": True, "wake": True})
        c, lat_c, lr_c = phase("C")
        r.measure("C tickless（resume＋wake）", c)
        klog = pl.fs.read_jsonl(sp.path("k", "kern.jsonl"))
        r.measure("B＋C：kernel 下的 pause／resume 數", {"pause": sum(1 for x in klog if x["op"] == "pause"),
                                                   "resume": sum(1 for x in klog if x["op"] == "resume")})
        cron_r1 = [sp.round_of(nid(i)) for i in range(N - CRON, N)]
        r.check("B、C：信全部處理了（沒有睡死的 node）", len(lat_b) == len(lat_c) == LETTERS)
        r.check("B：cron（idle_safe false）沒被 pause，照樣有回合", all(y > x for x, y in zip(cron_r0, cron_r1)),
                list(zip(cron_r0, cron_r1)))
        r.check("B：每秒 tick＋tock 程序比 A 少一半以上", b["每秒 tick＋tock 程序"] < a["每秒 tick＋tock 程序"] / 2,
                [a["每秒 tick＋tock 程序"], b["每秒 tick＋tock 程序"]])
        r.check("B、C：信在被 resume 的那一回合就處理（回合延遲中位 ≤ 1）",
                statistics.median(lr_b) <= 1 and statistics.median(lr_c) <= 1, [lr_b, lr_c])
        r.check("C：resume＋wake 的信都在 300 ms 內處理（不等上一回合剩下的 interval）", max(lat_c) < 300,
                {"B 最大": max(lat_b), "C 最大": max(lat_c)})
        r.finding("沒有事件來源：kernel 只能常駐、每 20 ms 掃 100 個 inbox 與 status.json 才知道信到了；"
                  "D-16 要的 watch／wake reason 不在 daemon")
        r.finding("wake 對 paused 的 node 沒用，要 resume；resume rounds 1 剛好當『只跑一回合收信，然後自己停回去』用。"
                  "但 resume 不打斷『等上一回合 interval 滿』的睡眠：剛停不到一個 interval 就來信的，要再補一個 wake（B 對 C 的最大延遲）")
        r.finding("idle_safe 是 kernel 跟 agent 自己約的檔；daemon 不知道哪條線可以跳過回合，pause 也不分『沒事』和『被罰』")
        r.finding("全停時 daemon 主迴圈照樣每 20 ms 一圈、每圈寫 101 個 node 的 status.json（量在 B 的 CPU 裡）")
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
