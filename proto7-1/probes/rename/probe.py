"""rename：node 上有 keep 任務在跑時，把 node 資料夾改名、再搬到更深一層（S-14、P-15）。

node a：keep 任務 sitter（掛 b/inbox 為 mnt/b_in）；node b：keep 任務 peer（掛 a/inbox 為 mnt/a_in）。
1. 跑幾回合後 `mv a a2`（同一層改名）；2. 再 `mv a2 deep/x/a3`（深兩層）；3. 對搬過的 sitter 下 kill。
看：daemon 把它當舊 id 消失、新 id 出現；回合從哪接；舊任務還活著嗎、AOS7_NODE 指哪、收不收得到 tock；
keep 會不會起第二份；掛載的相對連結；別人掛它 inbox 的連結；kill 之後 exit.json 寫到哪。
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
        sp.wait_for(lambda: (pl.fs.read_json(sp.path("a", ".aos", "round.json")) or {}).get("open"), timeout=3, poll=0.005,
                    msg="等不到 a 回合中途")
        os.rename(sp.path("a"), sp.path("a2"))
        t_mv = time.monotonic()
        sp.wait_for(lambda: any(e.get("ev") == "node+" and e.get("node") == "a2" for e in sp.log()), timeout=5,
                    msg="daemon 沒看到 a2")
        r.measure("改名→daemon 記 node+ a2 ms", round((time.monotonic() - t_mv) * 1000))
        log = sp.log()
        r.check("log 記 node- a 與 node+ a2", any(e.get("ev") == "node-" and e.get("node") == "a" for e in log))
        a_ticks = [e["round"] for e in log if e.get("ev") == "tick" and e.get("node") == "a"]
        a_tocks = [e["round"] for e in log if e.get("ev") == "tock" and e.get("node") == "a"]
        plus = [e for e in log if e.get("ev") == "node+" and e.get("node") == "a2"][0]
        r0 = sp.round_of("a2")
        sp.wait_for(lambda: sp.round_of("a2") >= r0 + 3, timeout=5, msg="a2 沒往前跑")
        a2_ticks = [e["round"] for e in sp.log() if e.get("ev") == "tick" and e.get("node") == "a2"]
        r.check("a2 的回合接著 a 數（round.json 跟著搬）", a2_ticks and a2_ticks[0] == max(a_ticks) + 1,
                [max(a_ticks), a2_ticks[:1]])
        r.measure("a 最後 tick 回合／最後 tock 回合／a2 node+ 時讀到的回合",
                  [max(a_ticks), max(a_tocks) if a_tocks else None, plus.get("round")])
        rj = [x["round"] for x in sp.rounds("a2")]
        missing = sorted(set(range(1, max(rj) + 1)) - set(rj))
        r.measure("rounds.jsonl 缺號（搬家剛好在回合中途時，那回合沒 tock）", missing)

        r.check("舊 sitter 程序還活著", aos7_task.pid_alive(sit_pid))
        r.check("a2 認得舊 sitter 是活任務（pid.json 跟著搬）", sit in sp.live("a2"), sp.live("a2"))
        live_sitters = [t for t in sp.live("a2") if t in named("a2", "sitter")]
        r.check("keep 沒起第二份 sitter", live_sitters == [sit], live_sitters)

        def moved_seen():
            p = prog("a2", sit)
            return p.get("rel_round", 0) >= r0 + 2 and p
        p = sp.wait_for(moved_seen, timeout=5, msg="sitter 沒經相對路徑看到新的 tock")
        r.check("sitter 經「相對 cwd」的路徑照樣收到 tock", p["rel_round"] >= r0 + 2, p)
        r.check("sitter 經 $AOS7_TASK（絕對路徑）收不到搬家後的 tock", p["abs_round"] < r0, [p["abs_round"], r0])
        r.check("sitter 的 AOS7_NODE 還指向舊路徑", p.get("node_env") == old_node, p.get("node_env"))
        r.check("sitter 的 cwd 跟著資料夾搬到 a2", p.get("cwd") == sp.path("a2"), p.get("cwd"))
        r.measure("搬家後 sitter 寫 $AOS7_NODE/abs_beat.log 的失敗次數", p.get("abs_beat_err"))
        sent1 = p.get("sent", 0)
        sp.wait_for(lambda: len(os.listdir(sp.path("b/inbox"))) > b_letters0 + 2, timeout=5, msg="改名後 sitter 沒寄到 b")
        r.check("同一層改名：sitter 的相對掛載連結照樣通（寄得到 b）", True)

        pp = sp.wait_for(lambda: prog("b", peer).get("err", 0) >= 2 and prog("b", peer), timeout=5,
                         msg="peer 寄 a/inbox 沒失敗")
        link = os.path.join(sp.path("b"), ".aos", "tasks", peer, "mnt", "a_in")
        r.check("b 掛 a/inbox 的連結斷掉（連結在、目標不在）", os.path.islink(link) and not os.path.exists(link))
        r.measure("peer 寄信失敗的訊息", pp.get("last_err"))
        ghost_files = sorted(os.path.relpath(os.path.join(d, f), old_node)
                             for d, _, fs_ in os.walk(old_node) for f in fs_) if os.path.exists(old_node) else []
        r.measure("改名後舊路徑 a 被建回來的檔（mv 時正在跑的 tick／tock 照舊路徑寫）", ghost_files)
        if ghost_files:
            r.finding("mv 落在 tick／tock 程序執行中時，它們照舊路徑寫完（write_json 會 makedirs），把舊資料夾 a/.aos 建回來："
                      "%s；那回合的總結寫進鬼資料夾、新位置缺號；之後 sitter 照 AOS7_NODE 寫的檔也「成功」寫進鬼資料夾" % ghost_files)

        # ---------- 2. 搬到更深一層 a2 → deep/x/a3 ----------
        os.makedirs(sp.path("deep/x"))
        os.rename(sp.path("a2"), sp.path("deep/x/a3"))
        sp.wait_for(lambda: sp.round_of("deep/x/a3") > 0 and any(
            e.get("ev") == "tick" and e.get("node") == "deep/x/a3" for e in sp.log()), timeout=5, msg="a3 沒起來")
        r3 = sp.round_of("deep/x/a3")

        def deep_err():
            q = prog("deep/x/a3", sit)
            return q.get("send_err", 0) >= 2 and q
        q = sp.wait_for(deep_err, timeout=5, msg="深一層後 sitter 寄信沒失敗")
        mlink = os.path.join(sp.path("deep/x/a3"), ".aos", "tasks", sit, "mnt", "b_in")
        r.check("搬到不同深度：任務自己的相對掛載連結斷掉", os.path.islink(mlink) and not os.path.exists(mlink),
                os.readlink(mlink))
        r.measure("深一層後 sitter 寄信失敗的訊息", q.get("last_send_err"))
        r.check("搬到深處仍沒起第二份 sitter",
                [t for t in sp.live("deep/x/a3") if t in named("deep/x/a3", "sitter")] == [sit])

        # ---------- 3. 對搬過的舊 sitter 下 kill ----------
        pl.write(os.path.join(sp.path("deep/x/a3"), ".aos", "tasks", sit, "ctl.json"), {"op": "kill", "by": "probe"})
        sp.wait_for(lambda: sp.task_file("deep/x/a3", sit, "exit.json"), timeout=5, msg="kill 後 a3 沒有 exit.json")
        ex = sp.task_file("deep/x/a3", sit, "exit.json")
        r.check("kill 收得到搬過的任務（pid.json 的 pgid 不看路徑）", not aos7_task.pid_alive(sit_pid))
        r.measure("新位置的 exit.json（aos7-run 寫不到這裡，tock 當 lost）", ex)
        ghost = os.path.join(old_node, ".aos", "tasks", sit, "exit.json")
        sp.wait_for(lambda: os.path.exists(ghost), timeout=3, msg="舊路徑沒出現 exit.json")
        r.measure("aos7-run 把真的 exit.json 寫回舊路徑（建回 a/.aos/tasks/<tid>/）", pl.fs.read_json(ghost))
        r.check("舊路徑被建回來的不是 node（沒 timeline.json，daemon 不當它是 a）",
                not os.path.exists(os.path.join(old_node, ".aos", "timeline.json"))
                and "a" not in sp.status().get("nodes", {}))

        new = sp.wait_for(lambda: [t for t in named("deep/x/a3", "sitter") if t != sit and prog("deep/x/a3", t).get("sent", 0) >= 2],
                          timeout=5, msg="keep 沒起新 sitter")[0]
        nq = prog("deep/x/a3", new)
        r.check("新起的 sitter 環境變數指向新路徑、寄信通", nq.get("node_env") == sp.path("deep/x/a3") and nq.get("send_err") == 0, nq)

        # ---------- 4. 搬家後 restart 掛 a/inbox 的 peer ----------
        pl.write(os.path.join(sp.path("b"), ".aos", "tasks", peer, "ctl.json"), {"op": "restart", "by": "probe"})
        np_ = sp.wait_for(lambda: [t for t in named("b", "peer") if t != peer and prog("b", t).get("ok", 0) >= 2],
                          timeout=5, msg="restart 的 peer 沒寄出信")[0]
        r.check("restart 後的 peer 照舊宣告重掛 a/inbox：寄信「成功」", prog("b", np_).get("err") == 0)
        ghost_in = sp.path("a", "inbox")
        r.check("……但信進的是 tick 新建的舊路徑 a/inbox（M-2：目標不存在先建資料夾），a 真正搬去的 a3 收不到",
                os.path.isdir(ghost_in) and any(x.startswith("b-") for x in os.listdir(ghost_in))
                and not any(x.startswith("b-") and int(x[2:-5]) > r3 for x in os.listdir(sp.path("deep/x/a3/inbox"))))
        r.measure("舊路徑 a/ 底下被建回來的東西", sorted(os.listdir(sp.path("a"))))

        r.finding("搬家改名＝舊 id 消失、新 id 出現；round.json 跟著搬，回合接著數%s" % (
            "；這次搬家落在回合中途，第 %s 回合沒 tock、rounds.jsonl 缺號（P-15）" % missing if missing else
            "（這次搬家落在回合之間，沒缺號；落在回合中途時那回合不 tock、會缺號，P-15）"))
        r.finding("搬過的活任務：程序還活著、pid.json 跟著搬，所以 keep 不會起第二份、kill 收得到；"
                  "但 AOS7_TASK／AOS7_NODE 是出生時的絕對路徑，用環境變數等 tock 的任務（含 aos7_fs.wait_tock）從此收不到 tock、永遠卡住；"
                  "用相對 cwd 的路徑反而照常（cwd 跟著資料夾走）")
        r.finding("aos7-run 寫 exit.json 用的是出生時的絕對路徑：真的結束碼被寫到舊路徑（makedirs 把舊資料夾建回來），"
                  "新位置只拿到 tock 補的 lost")
        r.finding("掛載是相對符號連結：同一層改名，自己的掛載還通；搬到不同深度就斷。別人掛它 inbox 的連結一律斷，"
                  "而且掛載只增不減（M-9），連結不會自己修")
        r.finding("更糟的是 restart（或新起）的任務照舊宣告重掛舊路徑時，tick 會把不存在的目標建成資料夾（M-2），"
                  "信寄「成功」但進了沒人看的 a/inbox，寄件方看不出錯")
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
