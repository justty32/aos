"""subtimeline：任務在執行中生出子時間線（建 node 資料夾＋timeline.json＋tasks.json），再把它關掉／刪掉。

想逼出：daemon 撿新 node 的延遲、建一半的競態、刪 node 時的活任務與「建回來」（P-15）、
pause 後刪、只刪 timeline.json、同 id 重用、父 node 對巢狀子 node 的「只碰自己 node」（M-5）。
"""
import datetime
import os
import shutil
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402
from probelib import fs  # noqa: E402

MAKER = os.path.join(HERE, "maker.py")
SLEEPER = os.path.join(HERE, "sleeper.py")
JOB = {"name": "job", "mode": "each", "argv": ["true"]}
SLEEP = {"name": "sleeper", "mode": "keep", "argv": [pl.PY, SLEEPER]}


def epoch(at):
    return datetime.datetime.fromisoformat(at).timestamp()


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


class Run:
    def __init__(self, sp):
        self.sp, self.n = sp, 0

    def order(self, op, timeout=8, **kw):
        """寫一張單給 maker，等它回結果。"""
        self.n += 1
        name = "%03d-%s.json" % (self.n, op)
        fs.write_json(self.sp.path("p", "orders", name), dict(kw, op=op))
        res = self.sp.path("p", "results", name)
        return self.sp.wait_for(lambda: fs.read_json(res), timeout=timeout, msg="maker 沒回 %s" % name)

    def ev(self, kind, node):
        return [e for e in self.sp.log() if e.get("ev") == kind and e.get("node") == node]

    def wait_ev(self, kind, node, count=1, timeout=8):
        return self.sp.wait_for(lambda: len(self.ev(kind, node)) >= count and self.ev(kind, node),
                                timeout=timeout, msg="log 沒有 %s %s" % (kind, node))


def maker_writes(sp):
    """maker 任務的寫入紀錄（AOS7_AUDIT）。"""
    out = []
    for tid in sp.tasks("p"):
        if tid.startswith("maker"):
            out += fs.read_jsonl(os.path.join(pl.aos7_task.task_dir(sp.path("p"), tid), "writes.jsonl"))
    return out


def under(path, base):
    return path == base or path.startswith(base + os.sep)


def main():
    r = pl.Result("subtimeline")
    with pl.Space("subtimeline") as sp:
        sp.node("p", [{"name": "maker", "mode": "keep", "argv": [pl.PY, MAKER], "mounts": {"q": "q"}}],
                interval_ms=100)
        sp.start(env={"AOS7_AUDIT": "1"})
        run = Run(sp)
        root = sp.root
        sp.wait_for(lambda: any(t.startswith("maker") for t in sp.live("p")), msg="maker 沒起來")

        # ---- 1. 子時間線建在自己 node 底下（先 tasks.json、後 timeline.json）----
        res = run.order("create", target={"via": "own", "path": "sub/a"}, order="tasks_first",
                        interval_ms=50, tasks=[JOB, SLEEP])
        plus = run.wait_ev("node+", "p/sub/a")[0]
        tick1 = run.wait_ev("tick", "p/sub/a")[0]
        r.check("自己 node 底下建的子時間線被 daemon 撿到", plus and tick1)
        r.measure("建好 timeline.json → node+ 延遲_ms", round((epoch(plus["at"]) - res["t_timeline"]) * 1000))
        r.measure("建好 timeline.json → 第一個 tick 結束_ms", round((epoch(tick1["at"]) - res["t_timeline"]) * 1000))
        r.check("先寫 tasks.json 再寫 timeline.json：第一回合就起了任務",
                any(t.startswith("job-r1") for t in tick1.get("started", [])), tick1.get("started"))
        rescans = [e for e in sp.log() if e.get("ev") == "ctl"]
        r.measure("撿到新 node 用到的 rescan ctl 數", len(rescans))

        # ---- 2. 建一半：timeline.json 先寫、隔 400 ms 才寫 tasks.json ----
        run.order("create", target={"via": "own", "path": "sub/b"}, order="timeline_first", gap_ms=400,
                  interval_ms=50, tasks=[JOB])
        sp.wait_for(lambda: any(x.get("started") for x in sp.rounds("p/sub/b")), msg="sub/b 一直沒起任務")
        empty = 0
        for x in sp.rounds("p/sub/b"):
            if x.get("started"):
                break
            empty += 1
        r.measure("timeline.json 先寫、tasks.json 晚 400 ms：沒起任務的空回合數", empty)
        if empty:
            r.finding("建 node 的兩個檔不是一次到位：timeline.json 一出現 daemon 就開回合，tasks.json 還沒寫的那段是空回合"
                      "（%d 回合）。沒有「node 準備好了」的訊號；要避開只能約定先寫 tasks.json、最後寫 timeline.json。" % empty)

        # ---- 3. 建在自己 node 外：經過掛載（q）與不經過（z，直接寫）----
        run.order("create", target={"via": "mount", "path": "q/c"}, order="tasks_first", interval_ms=100, tasks=[JOB])
        run.order("create", target={"via": "raw", "path": "z/d"}, order="tasks_first", interval_ms=100, tasks=[JOB])
        run.wait_ev("tick", "q/c")
        run.wait_ev("tick", "z/d")
        w = maker_writes(sp)
        rq = os.path.realpath(os.path.join(root, "q", "c"))
        rz = os.path.realpath(os.path.join(root, "z", "d"))
        r.check("經過掛載建的 node（q/c）寫入紀錄全 ok",
                [x for x in w if under(x["path"], rq)] and all(x["ok"] for x in w if under(x["path"], rq)))
        r.check("不經掛載直接建的 node（z/d）寫入紀錄是 ok:false",
                [x for x in w if under(x["path"], rz)] and not any(x["ok"] for x in w if under(x["path"], rz)))
        r.finding("在自己 node 外生子時間線，經掛載與直接寫 daemon 都照樣撿（z/d 也跑起來了）；寫入紀錄只記不擋。")
        sa = os.path.realpath(sp.path("p", "sub", "a"))
        sb = os.path.realpath(sp.path("p", "sub", "b"))
        bad_a = [x for x in w if under(x["path"], sa) and not x["ok"]]
        bad_b = [x for x in w if under(x["path"], sb) and not x["ok"]]
        r.measure("建 sub/a（先 tasks 後 timeline）被記 ok:false 的寫入數", len(bad_a))
        r.measure("建 sub/b（先 timeline 後 tasks）被記 ok:false 的寫入數", len(bad_b))
        if not bad_a and bad_b:
            r.finding("父在自己 node 裡生子 node：寫入紀錄判不判違規看寫的順序——timeline.json 寫下去之前都算父自己的 node，"
                      "之後同一個資料夾就變成「巢狀別人的 node」（M-5）。先 tasks 後 timeline 全 ok，反過來 tasks.json 被記違規。")

        # ---- 4. 父看子的結果：直接讀子的 rounds.jsonl ----
        pk = run.order("peek", target={"via": "own", "path": "sub/a"})
        r.check("父直接讀得到子時間線的 round.json／rounds.jsonl",
                pk["ok"] and pk["round"].get("round", 0) >= 1 and pk["last"], pk.get("round"))

        # ---- 5. 父改子的 tasks.json：直接改 vs 加掛後經過掛載改（M-5）----
        tk = os.path.join(sa, ".aos", "tasks.json")
        n0 = len(maker_writes(sp))
        run.order("edit_tasks", target={"via": "own", "path": "sub/a"}, add=dict(JOB, name="edit1"))
        direct = [x for x in maker_writes(sp)[n0:] if x["path"].startswith(tk)]
        m = run.order("mount", path="p/sub/a")
        n1 = len(maker_writes(sp))
        run.order("edit_tasks", target={"via": "mount", "path": "p/sub/a"}, add=dict(JOB, name="edit2"))
        viam = [x for x in maker_writes(sp)[n1:] if x["path"].startswith(tk)]
        r.check("執行中加掛自己 node 裡的子 node 給了", m.get("status") == "mounted", m)
        r.check("父直接改巢狀子 node 的 tasks.json 被記 ok:false（M-5）", direct and not any(x["ok"] for x in direct))
        r.check("經過掛載改同一個檔是 ok", viam and all(x["ok"] for x in viam))
        r.finding("父要管自己 node 裡的子時間線，得先加掛自己 node 裡的路徑（要等一個 tick）；直接寫只被記違規、照樣生效。")

        # ---- 6. 直接 rm -rf（子上有活的 sleeper）----
        sl = [t for t in sp.live("p/sub/a") if t.startswith("sleeper")]
        sp.wait_for(lambda: sp.task_file("p/sub/a", sl[0], "pid.json"), msg="sleeper 沒 pid.json")
        pidj = sp.task_file("p/sub/a", sl[0], "pid.json")
        last_round = sp.round_of("p/sub/a")
        r.measure("父直接寫進子 tasks.json 的 edit1 照樣在子時間線起了",
                  any(t.startswith("edit1") for t in sp.tasks("p/sub/a")))
        run.order("rmtree", target={"via": "own", "path": "sub/a"})
        run.wait_ev("node-", "p/sub/a")
        time.sleep(0.4)
        st = sp.status()
        r.check("rm -rf 後 status 不再列出 p/sub/a", "p/sub/a" not in st.get("nodes", {}))
        # 使用者 10-03 Q4 選 (a)：node 消失，daemon 就 kill 它上面的活任務（pid.json 跟著被刪也收得到）
        r.check("修補後：rm -rf 後子上的 sleeper 被 daemon 收掉（不留孤兒）",
                sp.wait_for(lambda: not pid_alive(pidj["pid"]), timeout=5, msg="sleeper 沒被收"))
        # reaper 收乾淨之後才寫 log：剛看到 pid 死時可能還沒寫，等一下
        r.check("修補後：log 有 node-gone-kill", bool(sp.wait_for(lambda: run.ev("node-gone-kill", "p/sub/a"), timeout=3,
                                                                   msg="沒有 node-gone-kill")))
        time.sleep(0.3)
        ghost = []
        for d, _, files in os.walk(sa):
            ghost += [os.path.relpath(os.path.join(d, f), sa) for f in files]
        r.measure("rm -rf 後被建回來的檔（tick／tock／aos7-run 不再建；剩下的是任務被收掉前自己 makedirs 寫的）", sorted(ghost)[:6])
        ex = os.path.join(sa, ".aos", "tasks", sl[0], "exit.json")
        r.check("修補後：aos7-run 沒把 exit.json 建回已刪的 node", not os.path.exists(ex))
        if ghost or os.path.exists(ex):
            r.finding("刪掉的 node 會被「建回來」成空殼（不是 node，沒 timeline.json）：活任務照常 makedirs 寫心跳，"
                      "aos7-run 結束時 write_json 也會 makedirs 寫 exit.json（P-15 只防了 tock）。")
        # 同名重用
        shutil.rmtree(sa, ignore_errors=True)
        before = len(run.ev("node+", "p/sub/a"))
        run.order("create", target={"via": "own", "path": "sub/a"}, order="tasks_first", interval_ms=50, tasks=[JOB])
        run.wait_ev("node+", "p/sub/a", count=before + 1)
        sp.wait_for(lambda: sp.rounds("p/sub/a"), msg="重建的 sub/a 沒回合")
        r.measure("刪前回合 → 重建同名後第一回合", [last_round, sp.rounds("p/sub/a")[0]["round"]])
        r.finding("同 id 重用：rm -rf 後重建從第 1 回合重數（round.json 跟著資料夾走）；daemon 沒有記 node 的歷史，"
                  "log 裡兩段 node+ 的 round 1 是不同的東西，看 log 分不出來。")

        # ---- 7. 先 pause 再刪，再建同名 ----
        run.order("create", target={"via": "own", "path": "sub/f"}, order="tasks_first", interval_ms=50, tasks=[JOB])
        run.wait_ev("tick", "p/sub/f")
        sp.ctl("pause", "p/sub/f")
        sp.wait_for(lambda: sp.status().get("nodes", {}).get("p/sub/f", {}).get("phase") == "paused")
        n2 = len(maker_writes(sp))
        run.order("rmtree", target={"via": "own", "path": "sub/f"})
        rw = maker_writes(sp)[n2:]
        okn, badn = sum(1 for x in rw if x["ok"]), sum(1 for x in rw if not x["ok"])
        r.measure("父 rm -rf 沒掛載的巢狀子 node：寫入紀錄 [ok 筆數, ok:false 筆數]", [okn, badn])
        if okn:
            r.finding("寫入紀錄對「刪掉巢狀子 node」判得不一致：timeline.json 刪掉之前的 remove 記 ok:false，之後的"
                      "（含 rmtree 子資料夾本身）記 ok——改子 node 的一個檔算違規，整個刪掉大半算合規。")
        run.wait_ev("node-", "p/sub/f")
        paused = fs.read_json(os.path.join(root, ".aosd", "paused.json"), {}).get("paused", [])
        r.measure("刪掉後 paused.json 還留著 p/sub/f", "p/sub/f" in paused)
        run.order("create", target={"via": "own", "path": "sub/f"}, order="tasks_first", interval_ms=50, tasks=[JOB])
        run.wait_ev("node+", "p/sub/f", count=2)
        time.sleep(0.6)
        rf = sp.round_of("p/sub/f")
        r.measure("重建同名 sub/f 後 0.6 秒的回合數（pause 被繼承就是 0）", rf)
        if rf == 0 and "p/sub/f" in paused:
            r.finding("pause 綁在 node id 上、存在 paused.json，node 刪掉也不清：日後同名重建的 node 一出生就是 paused，"
                      "status 有 paused: true 但 log 沒說為什麼。")
        sp.ctl("resume", "p/sub/f")
        r.check("resume 後重建的 sub/f 開始跑", sp.wait_for(lambda: sp.round_of("p/sub/f") >= 1, msg="resume 後沒跑"))

        # ---- 8. 只刪 timeline.json（資料夾與活任務留著），再寫回 ----
        run.order("create", target={"via": "own", "path": "sub/g"}, order="tasks_first", interval_ms=50,
                  tasks=[JOB, SLEEP])
        sp.wait_for(lambda: sp.round_of("p/sub/g") >= 3)
        run.order("rm_timeline", target={"via": "own", "path": "sub/g"})
        run.wait_ev("node-", "p/sub/g")
        time.sleep(0.3)
        rg = sp.round_of("p/sub/g")
        old_sl = [t for t in sp.tasks("p/sub/g") if t.startswith("sleeper")]
        r.check("修補後：只刪 timeline.json 也算 node 消失，sleeper 被收掉（Q4）",
                sp.wait_for(lambda: not [t for t in sp.live("p/sub/g") if t.startswith("sleeper")], timeout=5,
                            msg="sleeper 沒被收"))
        ex_g = sp.task_file("p/sub/g", old_sl[0], "exit.json") if old_sl else None
        r.check("……資料夾還在，所以 aos7-run 照常寫 exit.json（被訊號收掉）", ex_g and ex_g.get("code") == -15, ex_g)
        run.order("write_timeline", target={"via": "own", "path": "sub/g"}, interval_ms=50)
        run.wait_ev("node+", "p/sub/g", count=2)
        sp.wait_for(lambda: sp.round_of("p/sub/g") > rg)
        plus2 = run.ev("node+", "p/sub/g")[-1]
        r.check("寫回 timeline.json：回合數接著數", plus2.get("round") == rg, [rg, plus2.get("round")])
        sp.wait_for(lambda: [t for t in sp.live("p/sub/g") if t.startswith("sleeper") and t not in old_sl],
                    msg="寫回後沒起新 sleeper")
        r.check("寫回後 keep 起新的 sleeper（舊的已死）",
                len([t for t in sp.live("p/sub/g") if t.startswith("sleeper")]) == 1)
        r.finding("〔10-03 Q4 (a) 之後〕只刪 timeline.json＝node 消失：上面的活任務被 kill，寫回後 keep 重起、回合接著數。"
                  "想「暫停但保留任務」要用 pause。")

        # ---- 9. P-15：快時間線（5 ms）被 rm -rf，資料夾會不會被 tick／tock 建回來 ----
        ghosts, contents = 0, []
        for i in range(8):
            gone_before = len(run.ev("node-", "h"))
            sp.node("h", [JOB], interval_ms=5)
            sp.wait_for(lambda: sp.round_of("h") >= 3 + i % 3, timeout=5)
            shutil.rmtree(sp.path("h"), ignore_errors=True)
            run.wait_ev("node-", "h", count=gone_before + 1)
            time.sleep(0.25)
            if os.path.exists(sp.path("h")):
                ghosts += 1
                found = []
                for d, _, files in os.walk(sp.path("h")):
                    found += [os.path.relpath(os.path.join(d, f), sp.path("h")) for f in files]
                contents.append(sorted(found)[:6])
                shutil.rmtree(sp.path("h"), ignore_errors=True)
        r.measure("5 ms 時間線 rm -rf 8 次：資料夾被建回來的次數", ghosts)
        if contents:
            r.measure("被建回來的內容（前幾個檔）", contents[:3])
            r.finding("P-15 只在 tock 前看 gone；rm -rf 落在 tick／tock／aos7-run 執行中時，"
                      "它們的 write_json／append_jsonl 會 makedirs 把 .aos 建回來（%d/8 次）。" % ghosts)
        errs = [e for e in sp.log() if e.get("ev") == "error"]
        r.measure("log 裡的 error（時間線 thread 掛掉）", len(errs))

        r.check("daemon 還活著", sp.procs[0][1].poll() is None)
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
