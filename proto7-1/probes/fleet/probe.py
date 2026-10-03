"""fleet：一個 daemon 管 100～200 條時間線，看哪裡先撐不住。

量：daemon 每圈（handle_ctl＋scan＋write_status）多久、各時間線回合實際間隔 vs interval、status.json 大小、
daemon 的 CPU 與 thread 數、任務程序的記憶體、pause 一條的延遲、stop --kill 收完多久。

環境變數：FLEET_N（node 數，預設 150）、FLEET_WINDOW（量測窗秒數，預設 8）。
"""
import datetime
import os
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import probelib as pl  # noqa: E402
import aos7_daemon  # noqa: E402
import aos7_task  # noqa: E402
from aos7_fs import node_path, read_json  # noqa: E402

N = int(os.environ.get("FLEET_N", "150"))
WINDOW = float(os.environ.get("FLEET_WINDOW", "5"))
HZ = os.sysconf("SC_CLK_TCK")


def nid(i):
    return "g%d/n%03d" % (i % 10, i)


def interval_of(i):
    return 100 + (i * 97) % 401          # 100～500 ms，決定性


def cpu(pid):
    """(自己的 utime+stime, 收過的子程序 cutime+cstime) 秒。"""
    with open("/proc/%d/stat" % pid) as f:
        rest = f.read().rsplit(")", 1)[1].split()
    return (int(rest[11]) + int(rest[12])) / HZ, (int(rest[13]) + int(rest[14])) / HZ


def threads(pid):
    with open("/proc/%d/status" % pid) as f:
        for line in f:
            if line.startswith("Threads:"):
                return int(line.split()[1])
    return 0


def rss_kb(pid):
    try:
        with open("/proc/%d/status" % pid) as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except OSError:
        pass
    return 0


def is_runner(pid):
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            return b"aos7-run" in f.read()
    except OSError:
        return False


def iso(s):
    return datetime.datetime.fromisoformat(s).timestamp()


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))] if xs else None


class StatusWatcher(threading.Thread):
    """每 5 ms 讀 status.json 的 at，記下每次換新的時間（daemon 每圈寫一次）。"""

    def __init__(self, sp):
        super().__init__(daemon=True)
        self.sp, self.stop_ev = sp, threading.Event()
        self.ats, self.sizes = [], []
        self.path = os.path.join(sp.root, ".aosd", "status.json")

    def run(self):
        last = None
        while not self.stop_ev.is_set():
            st = read_json(self.path) or {}
            at = st.get("at")
            if at and at != last:
                last = at
                self.ats.append(iso(at))
                try:
                    self.sizes.append(os.path.getsize(self.path))
                except OSError:
                    pass
            time.sleep(0.005)


def main():
    r = pl.Result("fleet")
    r.measure("node 數", N)
    with pl.Space("fleet") as sp:
        ids = []
        for i in range(N):
            item = {"name": "k", "mode": "keep", "argv": ["sleep", "60"]} if i % 2 == 0 \
                else {"name": "e", "mode": "each", "argv": ["true"]}
            sp.node(nid(i), [item], interval_ms=interval_of(i))
            ids.append(nid(i))
        t0 = time.monotonic()
        p = sp.start()
        dpid = p.pid

        spath = os.path.join(sp.root, ".aosd", "status.json")
        sp.wait_for(lambda: os.path.exists(spath), timeout=40, msg="status.json 沒出現")
        t_first = time.monotonic() - t0
        sp.wait_for(lambda: len(sp.status().get("nodes", {})) >= N, timeout=30, msg="status 沒列滿全部 node")
        t_seen = time.monotonic() - t0
        sp.wait_for(lambda: all(sp.round_of(n) >= 1 for n in ids), timeout=30, msg="不是每條都跑到第 1 回合")
        t_r1 = time.monotonic() - t0
        r.check("status.json 列出全部 %d 條時間線" % N, len(sp.status().get("nodes", {})) == N)
        r.check("每條時間線都跑到第 1 回合", True)
        r.measure("daemon 第一次寫出 status.json 的秒數（之前控制檔也沒人處理）", round(t_first, 2))
        r.measure("全部出現在 status 的秒數", round(t_seen, 2))
        adds = sorted(iso(ev["at"]) for ev in sp.log() if ev.get("ev") == "node+")
        r.measure("第一次掃描起完 %d 條迴圈花的秒數（log 第一個到最後一個 node+）" % N, round(adds[-1] - adds[0], 2))
        r.measure("全部跑到第 1 回合的秒數", round(t_r1, 2))

        # ---------- 量測窗 ----------
        w = StatusWatcher(sp)
        w.start()
        c0, wall0 = cpu(dpid), time.monotonic()
        wall_t0 = time.time()
        max_thr, max_rss_tasks, max_procs, run_rss = 0, 0, 0, []
        while time.monotonic() - wall0 < WINDOW:
            max_thr = max(max_thr, threads(dpid))
            procs = pl.our_procs(sp.base)
            max_procs = max(max_procs, len(procs))
            max_rss_tasks = max(max_rss_tasks, sum(rss_kb(x) for x in procs))
            run_rss += [rss_kb(x) for x in procs if is_runner(x)]
            time.sleep(0.5)
        c1, wall1 = cpu(dpid), time.monotonic()
        wall_t1 = time.time()
        w.stop_ev.set()
        w.join()
        dt = wall1 - wall0
        r.measure("daemon 自己 CPU 佔一核的比例", round((c1[0] - c0[0]) / dt, 3))
        r.measure("daemon 收過的子程序（tick／tock）CPU 核數", round((c1[1] - c0[1]) / dt, 2))
        r.measure("daemon thread 數（最多）", max_thr)
        r.measure("daemon RSS KB", rss_kb(dpid))
        r.measure("空間裡的程序數（最多，含 aos7-run 與任務）", max_procs)
        r.measure("空間裡程序 RSS 合計 MB（最多）", round(max_rss_tasks / 1024, 1))
        r.measure("一個 aos7-run 包裝程序 RSS MB（中位）", round(statistics.median(run_rss) / 1024, 1) if run_rss else None)

        gaps = [b - a for a, b in zip(w.ats, w.ats[1:])]
        r.measure("daemon 主迴圈一圈 ms（status 改寫間隔：中位、p90、最大）",
                  [round(1000 * statistics.median(gaps), 1), round(1000 * pct(gaps, 0.9), 1),
                   round(1000 * max(gaps), 1)] if gaps else None)
        r.measure("status.json 大小 bytes（最大）", max(w.sizes) if w.sizes else None)

        # 回合間隔 vs interval：用 log.jsonl 的 tick 事件
        ticks = {}
        for ev in sp.log():
            if ev.get("ev") == "tick":
                t = iso(ev["at"])
                if wall_t0 <= t <= wall_t1:
                    ticks.setdefault(ev["node"], []).append(t)
        ratios = {"keep": [], "each": []}
        total_rounds = 0
        for i, n in enumerate(ids):
            ts = ticks.get(n, [])
            total_rounds += len(ts)
            iv = interval_of(i) / 1000.0
            ratios["keep" if i % 2 == 0 else "each"] += [(b - a) / iv for a, b in zip(ts, ts[1:])]
        for k, xs in ratios.items():
            r.measure("回合實際間隔 / interval（%s：中位、p90、最大）" % k,
                      [round(statistics.median(xs), 2), round(pct(xs, 0.9), 2), round(max(xs), 2)] if xs else None)
        want = sum(1000.0 / interval_of(i) for i in range(N)) * dt
        r.measure("量測窗內回合數 實際/照 interval 該有", [total_rounds, round(want)])
        r.measure("每秒 tick+tock 程序數（每回合 2 個 python）", round(2 * total_rounds / dt, 1))
        per = (c1[1] - c0[1]) / max(1, 2 * total_rounds) * 1000
        r.measure("一個 tick／tock 程序平均 CPU ms", round(per, 1))
        starved = [n for n in ids if len(ticks.get(n, [])) == 0]
        r.measure("量測窗內一回合都沒有的時間線數", len(starved))

        # 在探針裡重做 daemon 每圈的兩件事，量單次花多久（任務資料夾已累積）
        ntask = sum(len(aos7_task.list_tasks(node_path(sp.root, n))) for n in ids)
        t = time.perf_counter()
        for _ in range(3):
            aos7_daemon.scan_nodes(sp.root)
        r.measure("scan_nodes 一次 ms", round((time.perf_counter() - t) / 3 * 1000, 1))
        t = time.perf_counter()
        for _ in range(3):
            for n in ids:
                aos7_task.live_tasks(node_path(sp.root, n))
        r.measure("write_status 的 live_tasks 全掃一次 ms（任務資料夾 %d 個）" % ntask,
                  round((time.perf_counter() - t) / 3 * 1000, 1))

        # ---------- pause 一條的延遲 ----------
        target = nid(0)          # interval 100 ms
        tw = time.time()
        tm = time.monotonic()
        name = sp.ctl("pause", node=target)
        done = os.path.join(sp.root, ".aosd", "ctl-done", name)
        sp.wait_for(lambda: os.path.exists(done), timeout=10, msg="pause 沒被處理")
        t_done = time.monotonic() - tm
        sp.wait_for(lambda: sp.status().get("nodes", {}).get(target, {}).get("paused"), timeout=10,
                    msg="status 沒顯示 paused")
        t_status = time.monotonic() - tm
        done_at = iso(read_json(done)["result"]["at"])
        time.sleep(1.0)
        after = [ev for ev in sp.log() if ev.get("ev") == "tick" and ev.get("node") == target
                 and iso(ev["at"]) > done_at]
        r.check("pause 後該條最多再開 1 回合", len(after) <= 1, len(after))
        r.measure("pause：寫控制檔→ctl-done ms", round(t_done * 1000))
        r.measure("pause：寫控制檔→status 顯示 paused ms", round(t_status * 1000))
        r.measure("pause：寫控制檔→daemon 讀到（ctl-done 的 at − 寫入時刻）ms", round((done_at - tw) * 1000))

        # ---------- stop --kill ----------
        live_before = sum(len(sp.live(n)) for n in ids)
        tm = time.monotonic()
        sp.ctl("stop", kill=True)
        try:
            rc = p.wait(40)
        except Exception:
            rc = None
        t_stop = time.monotonic() - tm
        r.check("stop --kill 後 daemon 在 40 秒內退出", rc == 0, rc)
        r.measure("stop --kill：活任務數", live_before)
        r.measure("stop --kill：寫控制檔→daemon 退出 秒", round(t_stop, 2))
        kills = [ev for ev in sp.log() if ev.get("ev") == "kill"]
        r.measure("stop --kill：log 裡的 kill 筆數 / 失敗", [len(kills), sum(1 for k in kills if not k.get("ok"))])
        left = pl.our_procs(sp.base)
        r.check("stop --kill 後沒有留下任務程序", not left, left[:5])

        r.finding("每回合 tick、tock 各起一個 Python 程序（平均 %.0f ms CPU），%d 條時間線每秒要起 %.0f 個、吃掉 %.1f 核；"
                  "機器忙到 daemon 主迴圈與時間線 thread 排不到 CPU，回合只跑到該有的 %d%%"
                  % (per, N, 2 * total_rounds / dt, (c1[1] - c0[1]) / dt, 100 * total_rounds / max(1, want)))
        r.finding("第一次掃描在主迴圈裡依序起 %d 條迴圈要 %.1f 秒，期間 status.json 不寫、控制檔（含 stop）不處理"
                  % (N, adds[-1] - adds[0]))
        r.finding("status.json 每圈對全部 node 做 live_tasks（每個任務讀 pid.json＋/proc），任務資料夾只增不減（P-12），"
                  "主迴圈一圈從 20 ms 變成上百 ms，pause／stop 生效跟著變慢")
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
