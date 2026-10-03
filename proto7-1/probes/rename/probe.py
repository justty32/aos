"""rename：node 上有 keep 任務在跑時，把 node 資料夾改名、再搬到更深一層（S-14、P-15）。

node a：keep 任務 sitter（掛 b/inbox 為 mnt/b_in）；node b：keep 任務 peer（掛 a/inbox 為 mnt/a_in）。
1. 跑幾回合後 `mv a a2`（同一層改名）；2. 再 `mv a2 deep/x/a3`（深兩層）；3. restart 掛 a/inbox 的 peer。
看（使用者 10-03 Q4 選 (a) 之後）：舊 id 上的活任務被 daemon kill、結束碼寫到新位置；新位置由 keep 重起、環境變數與掛載正確；
回合接著數；別人掛它 inbox 的連結。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import probelib as pl  # noqa: E402
import aos7_task  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def src(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def main():
    r = pl.Result("rename")
    with pl.Space("rename") as sp:
        sp.node("a", [{"name": "sitter", "mode": "keep", "argv": [pl.PY, "sitter.py"], "mounts": {"b_in": "b/inbox"}}],
                interval_ms=100, files={"sitter.py": src("sitter.py")})
        sp.node("b", [{"name": "peer", "mode": "keep", "argv": [pl.PY, "peer.py"], "mounts": {"a_in": "a/inbox"}}],
                interval_ms=100, files={"peer.py": src("peer.py")})
        sp.start()

        def named(nid, name):
            return [t for t in sp.tasks(nid) if (sp.task_file(nid, t, "birth.json") or {}).get("name") == name]

        def prog(nid, tid):
            return sp.task_file(nid, tid, "progress.json") or {}

        sp.wait_for(lambda: named("a", "sitter") and prog("a", named("a", "sitter")[0]).get("rel_round", 0) >= 3
                    and named("b", "peer") and prog("b", named("b", "peer")[0]).get("ok", 0) >= 2,
                    timeout=10, msg="搬家前沒跑起來")
        sit = named("a", "sitter")[0]
        peer = named("b", "peer")[0]
        sit_pid = sp.task_file("a", sit, "pid.json")["pid"]
        b_letters0 = len(os.listdir(sp.path("b/inbox")))
        old_node = sp.path("a")

        # ---------- 1. 同一層改名 a → a2（挑回合中途：round.json open） ----------
        # 使用者 10-03 Q4 選 (a)：node 消失（含搬家）＝daemon kill 上面的活任務，新位置由 keep 重起
        sp.wait_for(lambda: (pl.fs.read_json(sp.path("a", ".aos", "round.json")) or {}).get("open"), timeout=3, poll=0.005,
                    msg="等不到 a 回合中途")
        os.rename(sp.path("a"), sp.path("a2"))
        t_mv = time.monotonic()
        sp.wait_for(lambda: any(e.get("ev") == "node+" and e.get("node") == "a2" for e in sp.log()), timeout=5,
                    msg="daemon 沒看到 a2")
        r.measure("改名→daemon 記 node+ a2 ms", round((time.monotonic() - t_mv) * 1000))
        log = sp.log()
        r.check("log 記 node- a 與 node+ a2", any(e.get("ev") == "node-" and e.get("node") == "a" for e in log))
        a_ticks = [e["round"] for e in log if e.get("ev") == "tick" and e.get("node") == "a" and e.get("round")]
        r0 = sp.round_of("a2")
        sp.wait_for(lambda: sp.round_of("a2") >= r0 + 3, timeout=5, msg="a2 沒往前跑")
        a2_ticks = [e["round"] for e in sp.log() if e.get("ev") == "tick" and e.get("node") == "a2" and e.get("round")]
        r.check("a2 的回合接著 a 數（round.json 跟著搬）", a2_ticks and a2_ticks[0] == max(a_ticks) + 1,
                [max(a_ticks), a2_ticks[:1]])
        rj = [x["round"] for x in sp.rounds("a2")]
        missing = sorted(set(range(1, max(rj) + 1)) - set(rj))
        r.measure("rounds.jsonl 缺號（搬家剛好在回合中途時，那回合沒 tock）", missing)

        r.check("修補後：舊 sitter 被 daemon 收掉", sp.wait_for(lambda: not aos7_task.pid_alive(sit_pid), timeout=5,
                                                          msg="舊 sitter 還活著"))
        r.check("修補後：log 有 node-gone-kill a", any(e.get("ev") == "node-gone-kill" and e.get("node") == "a" for e in sp.log()))
        ex = sp.wait_for(lambda: sp.task_file("a2", sit, "exit.json"), timeout=5, msg="a2 沒有舊 sitter 的 exit.json")
        r.check("修補後：舊 sitter 的結束碼寫到新位置（-15，不是 lost）", ex.get("code") == -15 and not ex.get("lost"), ex)
        new = sp.wait_for(lambda: [t for t in sp.live("a2") if t in named("a2", "sitter") and t != sit], timeout=5,
                          msg="keep 沒在 a2 起新 sitter")
        p = sp.wait_for(lambda: prog("a2", new[0]).get("abs_round", 0) >= 1 and prog("a2", new[0]), timeout=5,
                        msg="新 sitter 收不到 tock")
        r.check("新 sitter 的 AOS7_NODE 是新路徑、經 $AOS7_TASK 收得到 tock",
                p.get("node_env") == sp.path("a2") and p.get("abs_round", 0) >= 1, p)
        r.check("同時只有一個活的 sitter", len([t for t in sp.live("a2") if t in named("a2", "sitter")]) == 1)

        pp = sp.wait_for(lambda: prog("b", peer).get("err", 0) >= 2 and prog("b", peer), timeout=5,
                         msg="peer 寄 a/inbox 沒失敗")
        link = os.path.join(sp.path("b"), ".aos", "tasks", peer, "mnt", "a_in")
        r.check("b 掛 a/inbox 的連結斷掉（連結在、目標不在）", os.path.islink(link) and not os.path.exists(link))
        r.measure("peer 寄信失敗的訊息", pp.get("last_err"))
        time.sleep(0.2)
        ghost_files = sorted(os.path.relpath(os.path.join(d, f), old_node)
                             for d, _, fs_ in os.walk(old_node) for f in fs_) if os.path.exists(old_node) else []
        r.check("修補後：舊路徑 a 沒被 tick／tock／aos7-run 建回來", not ghost_files, ghost_files)

        # ---------- 2. 搬到更深一層 a2 → deep/x/a3 ----------
        sit2 = new[0]
        sit2_pid = sp.wait_for(lambda: sp.task_file("a2", sit2, "pid.json"))["pid"]
        os.makedirs(sp.path("deep/x"))
        os.rename(sp.path("a2"), sp.path("deep/x/a3"))
        sp.wait_for(lambda: sp.round_of("deep/x/a3") > 0 and any(
            e.get("ev") == "tick" and e.get("node") == "deep/x/a3" for e in sp.log()), timeout=5, msg="a3 沒起來")
        r.check("搬深一層：上一個 sitter 也被收掉", sp.wait_for(lambda: not aos7_task.pid_alive(sit2_pid), timeout=5,
                                                     msg="sitter 還活著"))
        new3 = sp.wait_for(lambda: [t for t in sp.live("deep/x/a3") if t in named("deep/x/a3", "sitter") and t != sit2
                                    and prog("deep/x/a3", t).get("sent", 0) >= 2], timeout=5, msg="a3 的新 sitter 沒寄出信")
        nq = prog("deep/x/a3", new3[0])
        r.check("a3 的新 sitter 掛載照新位置建、寄信通", nq.get("node_env") == sp.path("deep/x/a3") and nq.get("send_err") == 0, nq)
        r3 = sp.round_of("deep/x/a3")

        # ---------- 3. 搬家後 restart 掛 a/inbox 的 peer ----------
        pl.write(os.path.join(sp.path("b"), ".aos", "tasks", peer, "ctl.json"), {"op": "restart", "by": "probe"})
        np_ = sp.wait_for(lambda: [t for t in named("b", "peer") if t != peer and prog("b", t).get("ok", 0) >= 2],
                          timeout=5, msg="restart 的 peer 沒寄出信")[0]
        r.check("restart 後的 peer 照舊宣告重掛 a/inbox：寄信「成功」", prog("b", np_).get("err") == 0)
        ghost_in = sp.path("a", "inbox")
        r.check("……但信進的是 tick 新建的舊路徑 a/inbox（M-2：目標不存在先建資料夾），a 真正搬去的 a3 收不到",
                os.path.isdir(ghost_in) and any(x.startswith("b-") for x in os.listdir(ghost_in))
                and not any(x.startswith("b-") and int(x[2:-5]) > r3 for x in os.listdir(sp.path("deep/x/a3/inbox"))))

        r.finding("〔10-03 Q4 (a) 之後〕搬家改名＝舊 id 消失、新 id 出現：舊 id 上的活任務被 daemon kill（結束碼經 fd 寫到新位置），"
                  "新位置由 keep 重起，環境變數與掛載都照新路徑；round.json 跟著搬，回合接著數%s" % (
                      "；這次搬家落在回合中途，第 %s 回合沒 tock（P-15）" % missing if missing else ""))
        r.finding("別人掛它 inbox 的連結一律斷，掛載只增不減（M-9），連結不會自己修；"
                  "restart（或新起）的任務照舊宣告重掛舊路徑時，tick 會把不存在的目標建成資料夾（M-2），"
                  "信寄「成功」但進了沒人看的 a/inbox，寄件方看不出錯（N-48）")
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
