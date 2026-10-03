"""nest3：路一三層——根 daemon D0 的時間線 L0 用 tick 起子 daemon D1，D1 的 L1 再起 D2，D2 的 L2 跑普通任務（S-21 路一）。

三段：
1. 主場（子根先建 `.aosd/`）：三層起得來、回合數、pause L0 往不往下傳、上層看不看得到下層、
   中間層 D1 被 ctl kill（SIGTERM）與 kill -9 時 D2 怎樣、最上層 stop --kill 收得乾不乾淨。
2. 頑固任務：L2 有不理 SIGTERM 的任務時，最上層 stop --kill 夠不夠（kill 寬限 1 秒，P-04）。
3. 不先建 `.aosd/`（P-11 三層）：只量，看誰最後管哪個 node。
"""
import glob
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402
from aos7_fs import read_json, read_jsonl  # noqa: E402

T = pl.aos7_task
SLEEP = ["sleep", "1000"]
STUB = ["sh", "-c", "trap '' TERM; sleep 1000"]


def daemons_under(base):
    """{pid: 命令列裡的根} — base 底下所有活著的 aos7-daemon。"""
    out = {}
    for pid in pl.daemon_procs(base):
        try:
            with open("/proc/%d/cmdline" % pid, "rb") as f:
                argv = [a.decode(errors="replace") for a in f.read().split(b"\0") if a]
        except OSError:
            continue
        if T.pid_alive(pid):
            out[pid] = argv[-1]
    return out


def comms(pids):
    out = set()
    for p in pids:
        try:
            with open("/proc/%d/comm" % p) as f:
                out.add(f.read().strip())
        except OSError:
            pass
    return sorted(out)


def leftovers(base):
    return sorted(p for p in set(pl.our_procs(base) + pl.daemon_procs(base)) if T.pid_alive(p))


def layout(sp, l2_tasks, markers=True):
    """建三層的資料夾，回 (L1 的實際路徑, L2 的實際路徑, D1 根, D2 根)。"""
    R = sp.root
    d1root = os.path.join(R, "L0", "d1root")
    d2root = os.path.join(d1root, "L1", "d2root")
    if markers:
        os.makedirs(os.path.join(d1root, ".aosd"))
        os.makedirs(os.path.join(d2root, ".aosd"))
    sp.node("L0", [{"name": "d1", "mode": "keep", "argv": ["aos7-daemon", "$AOS7_TASK/mnt/d1"],
                    "mounts": {"d1": "L0/d1root"}}], interval_ms=100)
    sp.node("L1", [{"name": "d2", "mode": "keep", "argv": ["aos7-daemon", "$AOS7_TASK/mnt/d2"],
                    "mounts": {"d2": "L1/d2root"}}], interval_ms=100, root=d1root)
    sp.node("L2", l2_tasks, interval_ms=100, root=d2root)
    return os.path.join(d1root, "L1"), os.path.join(d2root, "L2"), d1root, d2root


def rnd(node):
    return (read_json(os.path.join(node, ".aos", "round.json"), {}) or {}).get("round", 0)


def st(root):
    return read_json(os.path.join(root, ".aosd", "status.json"), {}) or {}


def live_named(node, name):
    return [t for t in T.live_tasks(node) if t.startswith(name + "-")]


def main_scene(r):
    with pl.Space("nest3") as sp:
        L1, L2, d1root, d2root = layout(sp, [{"name": "q", "argv": ["true"]},
                                             {"name": "s", "mode": "keep", "argv": SLEEP}])
        t0 = time.monotonic()
        p0 = sp.start()
        sp.wait_for(lambda: rnd(L1) >= 1, timeout=10, msg="D1 沒起來")
        t_l1 = time.monotonic() - t0
        sp.wait_for(lambda: rnd(L2) >= 1, timeout=10, msg="D2 沒起來")
        t_l2 = time.monotonic() - t0
        sp.wait_for(lambda: rnd(L2) >= 3, timeout=10, msg="L2 沒跑到第 3 回合")
        r.check("三層都起得來（L2 跑到第 3 回合）", True)
        r.measure("起 D0 到 L1 第 1 回合（秒）", round(t_l1, 2))
        r.measure("起 D0 到 L2 第 1 回合（秒）", round(t_l2, 2))
        r.check("各層 status 只列自己的 node",
                list(sp.status()["nodes"]) == ["L0"] and list(st(d1root)["nodes"]) == ["L1"]
                and list(st(d2root)["nodes"]) == ["L2"])
        r.measure("D1 status.root", st(d1root)["root"])
        r.measure("D2 status.root", st(d2root)["root"])
        r.measure("D2 status.root 長度（每層多一段任務掛載點）", len(st(d2root)["root"]))
        top = sp.status()
        r.check("D0 的 status 對下層只有一個活任務名（d1-r1），沒有 D1／D2 的回合與健康",
                top["nodes"]["L0"]["live"] == ["d1-r1"] and "L1" not in str(top))
        r.measure("回合數 L0／L1／L2（同一瞬間）", [rnd(sp.path("L0")), rnd(L1), rnd(L2)])

        # ---- pause L0：往不往下傳 ----
        sp.ctl("pause", node="L0")
        sp.wait_for(lambda: sp.status()["nodes"]["L0"]["phase"] == "paused", msg="L0 沒停")
        a = [rnd(sp.path("L0")), rnd(L1), rnd(L2)]
        time.sleep(0.6)
        b = [rnd(sp.path("L0")), rnd(L1), rnd(L2)]
        r.measure("pause L0 的 0.6 秒內各層回合增加", [y - x for x, y in zip(a, b)])
        r.check("pause L0：L0 不動，L1、L2 照跑（pause 不往下傳）", b[0] == a[0] and b[1] > a[1] and b[2] > a[2])
        sp.ctl("resume", node="L0")
        sp.wait_for(lambda: rnd(sp.path("L0")) > b[0], msg="L0 沒 resume")

        # ---- 中間層 D1 被 ctl kill（SIGTERM 路徑）----
        d1_tid = live_named(sp.path("L0"), "d1")[0]
        d1_dir = T.task_dir(sp.path("L0"), d1_tid)
        d1_root_str = st(d1root)["root"]
        d2_pid = st(d2root)["pid"]
        d2_root_old = st(d2root)["root"]
        s_tid = live_named(L2, "s")[0]
        s_pid = read_json(os.path.join(T.task_dir(L2, s_tid), "pid.json"))["pid"]
        l2_before = rnd(L2)
        tk = time.monotonic()
        pl.write(os.path.join(d1_dir, "ctl.json"), {"op": "kill", "by": "probe", "why": "nest3 中間層"})
        done = sp.wait_for(lambda: read_json(os.path.join(d1_dir, "ctl-done.json")), timeout=10, msg="kill d1 沒回條")
        t_kill = time.monotonic() - tk
        r.measure("ctl kill D1：寫 ctl.json 到回條（秒，含等下個 L0 tick）", round(t_kill, 2))
        r.measure("ctl kill D1：回條", done["result"])
        r.check("ctl kill D1：回條 ok（1 秒寬限內收完）", done["result"]["ok"], done["result"])
        r.measure("D1 結束碼（SIGTERM 收尾也是 0，I-1）", read_json(os.path.join(d1_dir, "exit.json"), {}).get("code"))
        r.check("D1 被 kill 帶走 D2 和 D2 的任務", not T.pid_alive(d2_pid) and not T.pid_alive(s_pid))
        r.measure("D1 被 kill 後，舊 D1 根底下的殘留程序", leftovers(d1_root_str))
        # keep → D0 下個 tick 起回 D1，D1 再起 D2（D-3）
        sp.wait_for(lambda: rnd(L2) > l2_before + 2, timeout=10, msg="D1 被 kill 後 L2 沒接上")
        t_back = time.monotonic() - tk
        r.measure("ctl kill D1 到 L2 回合再前進 2 回合（秒）", round(t_back, 2))
        r.check("keep 把 D1 起回來，D1 再起 D2（新 pid）", st(d2root)["pid"] != d2_pid)
        rounds2 = [z["round"] for z in read_jsonl(os.path.join(L2, ".aos", "rounds.jsonl"))]
        r.check("L2 的回合數跨過 D1 重啟沒有倒退", rounds2 == sorted(rounds2), rounds2)
        dups = sorted({x for x in rounds2 if rounds2.count(x) > 1})
        r.measure("L2 回合總結：重複的回合", dups)
        if dups:
            r.measure("L2 重複回合的總結（tick_at, tock_at, started, ended）",
                      [(z["tick_at"][-12:], z["tock_at"][-12:], z["started"], [e["tid"] for e in z["ended"]])
                       for z in read_jsonl(os.path.join(L2, ".aos", "rounds.jsonl")) if z["round"] in dups])
            r.measure("D2 log 裡那幾回合", [(e["at"][-12:], e["ev"], e.get("round"), e.get("rc"), e.get("started"))
                                           for e in read_jsonl(os.path.join(d2root, ".aosd", "log.jsonl"))
                                           if e.get("round") in dups or e.get("ev") in ("start", "stop", "stopping", "node+")])
        r.measure("L2 回合總結：跳掉的回合", [b for a, b in zip(rounds2, rounds2[1:]) if b > a + 1])
        killed = [dict(e, who=w) for w, root in (("D1", d1root), ("D2", d2root))
                  for e in read_jsonl(os.path.join(root, ".aosd", "log.jsonl"))
                  if e.get("ev") in ("tick", "tock") and isinstance(e.get("rc"), int) and e["rc"] < 0]
        r.measure("ctl kill D1 時被一起 SIGTERM 掉的 tick／tock", [(e["who"], e["ev"], e["node"], e["round"], e["rc"]) for e in killed])
        if killed:
            r.finding("kill 子 daemon 是對它的程序群組送 SIGTERM，正在跑的 tick／tock 程序也在這個群組裡，一起被殺（rc -15）："
                      "tock 被殺＝那回合沒有總結（跳號）；tick 被殺後 daemon 收尾又 tock 一次上一個已關的回合＝總結重複")
        r.measure("D2 新的 status.root 跟舊的不同（身分換了）", st(d2root)["root"] != d2_root_old)

        # ---- 中間層 D1 被 kill -9 ----
        d1_pid = st(d1root)["pid"]
        d2_pid = st(d2root)["pid"]
        d2_root_str = st(d2root)["root"]
        l2_before = rnd(L2)
        tk = time.monotonic()
        os.kill(d1_pid, signal.SIGKILL)
        sp.wait_for(lambda: st(d1root).get("pid") not in (None, d1_pid) and T.pid_alive(st(d1root)["pid"]),
                    timeout=10, msg="D1 被 kill -9 後沒被起回來")
        r.measure("kill -9 D1 到新 D1 寫出 status（秒）", round(time.monotonic() - tk, 2))
        sp.wait_for(lambda: rnd(L2) > l2_before + 3, timeout=10, msg="L2 停了")
        r.check("kill -9 D1：D2 沒死，變成沒人管的孤兒（P-04）", T.pid_alive(d2_pid) and st(d2root)["pid"] == d2_pid)
        r.check("新 D1 看 d2 還活著（keep）就不再起 D2", len(live_named(L1, "d2")) == 1)
        r.measure("孤兒 D2 的 status.root 還指向被 kill 的 D1 任務的掛載點", st(d2root)["root"] == d2_root_str)
        r.measure("此時 base 底下的 aos7-daemon 數", len(daemons_under(sp.base)))
        r.measure("回合數 L0／L1／L2（kill -9 後）", [rnd(sp.path("L0")), rnd(L1), rnd(L2)])
        l1_rounds = [z["round"] for z in read_jsonl(os.path.join(L1, ".aos", "rounds.jsonl"))]
        r.measure("L1 回合總結跳號（kill -9 那回合沒 tock）", [b for a, b in zip(l1_rounds, l1_rounds[1:]) if b != a + 1])

        # ---- 最上層 stop --kill ----
        procs_before = leftovers(sp.base)
        tk = time.monotonic()
        sp.ctl("stop", kill=True)
        rc = p0.wait(15)
        t_stop = time.monotonic() - tk
        left0 = leftovers(sp.base)
        time.sleep(1.5)
        left1 = leftovers(sp.base)
        r.measure("stop --kill 前 base 底下程序數", len(procs_before))
        r.measure("最上層 stop --kill 到 D0 退出（秒）", round(t_stop, 2))
        r.measure("D0 退出時剩下的程序", len(left0))
        r.measure("再 1.5 秒後剩下的程序", len(left1))
        r.check("D0 正常退出", rc == 0, rc)
        r.measure("stop 後孤兒 D2 還活著", T.pid_alive(d2_pid))
        r.measure("stop 後剩下的程序（comm）", comms(left1))


def stubborn_scene(r):
    with pl.Space("nest3-stub") as sp:
        L1, L2, d1root, d2root = layout(sp, [{"name": "stub", "mode": "keep", "argv": STUB},
                                             {"name": "s", "mode": "keep", "argv": SLEEP}])
        p0 = sp.start()
        sp.wait_for(lambda: rnd(L2) >= 2 and len(T.live_tasks(L2)) == 2, timeout=10, msg="頑固場 L2 沒起來")
        n_before = len(leftovers(sp.base))
        tk = time.monotonic()
        sp.ctl("stop", kill=True)
        rc = p0.wait(15)
        t_stop = time.monotonic() - tk
        left0 = leftovers(sp.base)
        time.sleep(1.5)
        left1 = leftovers(sp.base)
        r.check("頑固場：D0 還是會退出", rc == 0, rc)
        r.measure("頑固場：stop --kill 前程序數", n_before)
        r.measure("頑固場：stop --kill 到 D0 退出（秒）", round(t_stop, 2))
        r.measure("頑固場：D0 退出時剩下的程序", len(left0))
        r.measure("頑固場：再 1.5 秒後剩下的程序", len(left1))
        comm = comms(left1)
        r.measure("頑固場：剩下的是", comm)
        d1_exit = [read_json(os.path.join(d, "exit.json"), {}).get("code")
                   for d in glob.glob(os.path.join(sp.path("L0"), ".aos", "tasks", "d1-*"))]
        r.measure("頑固場：D1 結束碼（-9＝被父的寬限 SIGKILL）", d1_exit)
        if left1:
            r.finding("三層＋L2 有不理 SIGTERM 的任務：最上層 stop --kill 後留下 %d 個孤兒（%s）。D0 等 D1 1 秒就 SIGKILL，"
                      "D1 等 D2 也是 1 秒，D2 收頑固任務也要 1 秒——三個 1 秒同時到期，誰先死看運氣" % (len(left1), comm))


def p11_scene(r):
    with pl.Space("nest3-p11") as sp:
        L1, L2, d1root, d2root = layout(sp, [{"name": "q", "argv": ["true"]},
                                             {"name": "s", "mode": "keep", "argv": SLEEP}], markers=False)
        sp.start()
        sp.wait_for(lambda: os.path.isdir(os.path.join(d1root, ".aosd")), timeout=10, msg="D1 沒起來")
        time.sleep(2.0)
        log = sp.log()
        claimed = sorted({e["node"] for e in log if e.get("ev") == "node+"})
        dropped = sorted({e["node"] for e in log if e.get("ev") == "node-"})
        r.measure("P-11：D0 曾經接手的 node", claimed)
        r.measure("P-11：D0 後來放手的 node", dropped)
        r.measure("P-11：D1 最後管的 node", sorted(st(d1root).get("nodes", {})))
        r.measure("P-11：真正的 D2 根有沒有 .aosd（D2 有沒有起在對的地方）", os.path.isdir(os.path.join(d2root, ".aosd")))
        stray = os.path.join(sp.root, "L1", "d2root")
        r.measure("P-11：D0 照 L1 的 tasks.json 掛 L1/d2root，在 D0 根底下多出的資料夾", os.path.isdir(stray))
        r.measure("P-11：活著的 aos7-daemon 根（相對 base）",
                  sorted(os.path.relpath(v, sp.base) for v in daemons_under(sp.base).values()))
        s_owner = {}
        for tid in T.live_tasks(L2):
            b = read_json(os.path.join(T.task_dir(L2, tid), "birth.json"), {})
            s_owner[tid] = b.get("node")
        r.measure("P-11：L2 的活任務與 birth.json 的 node id（看是哪個 daemon 起的）", s_owner)
        r.check("P-11 場跑完沒卡死", True)


def main():
    r = pl.Result("nest3")
    main_scene(r)
    stubborn_scene(r)
    p11_scene(r)
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
