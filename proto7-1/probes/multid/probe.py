"""multid：一個 kernel（在 daemon A 裡）管三個不同空間根的 daemon（S-21 路二、S-18、S-14）。

- B：根放在 A 的根底下（`sub_b`，先建 `.aosd/`，A 掃描跳過）→ kernel 用掛載 `sub_b/.aosd` 碰得到。
- C：根在 A 外面 → 掛載 `../c/.aosd` 被拒、符號連結 `link_c` 也被拒（realpath 跑出根）；只能在設定裡寫絕對路徑硬寫。
- 量：ctl 回條延遲、跨 daemon 的 node id、A 的 ctl 寫 `sub_b/x` 會怎樣、kill -9 B／C 後 kernel 多久看出來
  （status.at 停、pid 不在、daemon.lock 鎖得到）、死的時候寫的 ctl、kernel 用 spawn 把 daemon 起回來。
"""
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402
from aos7_fs import read_json, read_jsonl  # noqa: E402

SLEEP = ["sleep", "1000"]


def main():
    r = pl.Result("multid")
    with pl.Space("multid") as sp:
        A = sp.root
        B = os.path.join(A, "sub_b")
        os.makedirs(os.path.join(B, ".aosd"))           # P-11：先建，A 才不會把 sub_b/x 當自己的 node
        C = sp.new_root("c")
        os.symlink(C, os.path.join(A, "link_c"))
        kdir = sp.path("k", "kern")

        def events(**match):
            return [e for e in read_jsonl(os.path.join(kdir, "events.jsonl"))
                    if all(e.get(k) == v for k, v in match.items())]

        def view():
            return read_json(os.path.join(kdir, "view.json"), {}) or {}

        cmd_n = [0]

        def cmd(daemon, **body):
            cmd_n[0] += 1
            fn = "%03d.json" % cmd_n[0]
            pl.write(os.path.join(kdir, "cmd", fn), {"op": "ctl", "daemon": daemon, "body": body})
            return fn

        def receipt(fn, timeout=5.0):
            return sp.wait_for(lambda: (events(ev="receipt", cmd=fn) or [None])[0], timeout=timeout,
                               msg="kernel 沒拿到 %s 的回條" % fn)

        # ---- 佈置 ----
        sp.node("x", [{"name": "q", "argv": ["true"]}, {"name": "s", "mode": "keep", "argv": SLEEP}],
                interval_ms=100, root=B)
        sp.node("y", [{"name": "q", "argv": ["true"]}], interval_ms=100, root=C)
        sp.node("a1", [{"name": "q", "argv": ["true"]}], interval_ms=100)
        sp.node("k", [{"name": "kern", "mode": "keep", "argv": [pl.PY, os.path.join(HERE, "kern.py")],
                       "mounts": {"a": ".aosd", "b": "sub_b/.aosd", "clink": "link_c/.aosd", "cdd": "../c/.aosd"}}],
                interval_ms=100,
                files={"kern/kernel.json": {
                    "poll": 0.05, "stale_s": 0.5,
                    "daemons": {
                        "a": {"space": ".aosd"},
                        "b": {"space": "sub_b/.aosd",
                              "restart": {"name": "bd", "argv": ["aos7-daemon", "$AOS7_TASK/mnt/broot"],
                                          "mounts": {"broot": "sub_b"}}},
                        "c": {"abs": os.path.join(C, ".aosd"),
                              "restart": {"name": "cd", "argv": ["aos7-daemon", C]}},
                        "c_link": {"space": "link_c/.aosd"},
                    }}})
        pa = sp.start(env={"AOS7_AUDIT": "1"})
        pb = sp.start(root=B)
        pc = sp.start(root=C)
        sp.wait_for(lambda: all((view().get("daemons", {}).get(n) or {}).get("sig") == {"stale": False, "pid_dead": False}
                                for n in ("a", "b", "c")), timeout=10, msg="kernel 沒看到三個 daemon 都活著")
        r.check("A 的 status 不含 B 的 node（含 .aosd 的子資料夾跳過）", list(sp.status()["nodes"]) == ["a1", "k"],
                list(sp.status()["nodes"]))

        # ---- 掛載：巢狀可以，外面的不行 ----
        birth = sp.task_file("k", "kern-r1", "birth.json")
        m = birth["mounts"]
        r.check("巢狀的 B：掛載 sub_b/.aosd 成功", "at" in m.get("b", {}))
        r.check("A 外面的 C：`../c/.aosd` 宣告被拒", any("error" in v and "../c" in v["error"] for v in m.values()),
                {k: v.get("error") for k, v in m.items() if "error" in v})
        r.check("A 外面的 C：經符號連結 link_c 也被拒（realpath 跑出根）", "error" in m.get("clink", {}))
        sp.wait_for(lambda: events(ev="mount", daemon="c_link", result="pending"), msg="kernel 沒寫加掛請求")
        sp.wait_for(lambda: [e for e in events(ev="mount", daemon="c_link") if str(e["result"]).startswith("refused")],
                    msg="執行中加掛 link_c 沒被拒")
        r.check("執行中加掛 link_c/.aosd 也被拒", True)

        # ---- 跨 daemon 的 ctl ----
        f1 = cmd("b", op="pause", node="x")
        rc1 = receipt(f1)
        r.check("經掛載寫 B 的 ctl：回條 ok", rc1["result"]["ok"], rc1["result"])
        r.measure("ctl 回條延遲（kernel 寫 → 看到 ctl-done，秒）B", rc1["latency"])
        sp.wait_for(lambda: sp.status(root=B)["nodes"]["x"]["paused"], msg="B 的 x 沒 pause")
        f2 = cmd("c", op="pause", node="y")
        rc2 = receipt(f2)
        r.check("用絕對路徑硬寫 A 外面的 C：回條 ok（沒有東西擋）", rc2["result"]["ok"])
        r.measure("ctl 回條延遲 C（秒）", rc2["latency"])
        # 寫入紀錄看得到哪些
        writes = pl.fs.read_jsonl(os.path.join(sp.path("k", ".aos", "tasks", "kern-r1"), "writes.jsonl"))
        wc = [w for w in writes if w["path"].startswith(C)]
        wb = [w for w in writes if w["path"].startswith(B)]
        r.check("寫 B 的 ctl 有寫入紀錄且 ok", wb and all(w["ok"] for w in wb), len(wb))
        r.measure("寫 C（空間外）的寫入紀錄筆數", len(wc))
        if not wc:
            r.finding("kernel 用絕對路徑寫空間外的 daemon C，寫入紀錄一筆都沒有（audit 只記空間根底下），等於完全看不見")

        # A 的 ctl 寫 sub_b/x：A 不管這個 node，卻回 ok
        rx = sp.round_of("x", root=B)
        sp.ctl("resume", node="x", root=B)
        sp.wait_for(lambda: sp.round_of("x", root=B) > rx + 1, msg="B 的 x 沒 resume")
        f3 = cmd("a", op="pause", node="sub_b/x")
        rc3 = receipt(f3)
        rx = sp.round_of("x", root=B)
        time.sleep(0.5)
        rx2 = sp.round_of("x", root=B)
        r.measure("對 A 寫 pause sub_b/x：回條", rc3["result"])
        r.measure("之後 0.5 秒 B 的 x 回合增加", rx2 - rx)
        if rc3["result"]["ok"] and rx2 > rx:
            r.finding("對 A 寫 pause sub_b/x（同一個資料夾在 A 空間裡的路徑）回條 ok，但 B 的 x 照跑："
                      "沒有跨 daemon 的 node id，錯送的控制拿到成功回條")
        sp.ctl("resume", node="sub_b/x")
        sp.ctl("resume", node="y", root=C)

        # ---- B 卡住（SIGSTOP）：at 停了但沒死 ----
        t_stop = time.time()
        os.kill(pb.pid, signal.SIGSTOP)
        try:
            e = sp.wait_for(lambda: [e for e in events(ev="signal", daemon="b", sig="stale", value=True)
                                     if e["t"] >= t_stop], timeout=5, msg="kernel 沒看到 B 停更")[0]
            r.measure("SIGSTOP B → kernel 看到 stale（秒）", round(e["t"] - t_stop, 3))
            time.sleep(0.3)
            sig_b = view()["daemons"]["b"]["sig"]
            r.measure("B 卡住時 kernel 的訊號", sig_b)
            r.check("B 卡住：status 停更但 pid 在、鎖拿不到（只看 at 會誤判成死掉）",
                    sig_b.get("stale") and not sig_b.get("pid_dead") and sig_b.get("lock_free") is False, sig_b)
        finally:
            os.kill(pb.pid, signal.SIGCONT)
        sp.wait_for(lambda: not view()["daemons"]["b"]["sig"]["stale"], msg="B SIGCONT 後沒恢復")
        r.check("B 卡住期間 kernel 沒有去重起它", not events(ev="restart_spawned"))

        # ---- kill -9 B、C ----
        x_tasks_before = sp.live("x", root=B)
        s_pid = (sp.task_file("x", [t for t in x_tasks_before if t.startswith("s-")][0], "pid.json", root=B) or {})["pid"]
        rx_before = sp.round_of("x", root=B)
        ry_before = sp.round_of("y", root=C)
        t_kill = time.time()
        os.kill(pb.pid, signal.SIGKILL)
        os.kill(pc.pid, signal.SIGKILL)
        pb.wait()
        pc.wait()
        f4 = cmd("b", op="pause", node="x")          # 死的時候寫的 ctl
        for n in ("b", "c"):
            for sig in ("stale", "pid_dead", "lock_free"):
                e = sp.wait_for(lambda: [e for e in events(ev="signal", daemon=n, sig=sig, value=True) if e["t"] >= t_kill],
                                timeout=5, msg="kernel 沒看到 %s 的 %s" % (n, sig))[0]
                r.measure("kill -9 %s → kernel 看到 %s（秒）" % (n, sig), round(e["t"] - t_kill, 3))
        st_dead = sp.status(root=B)
        r.check("B 死了 status.json 還寫著舊 pid、stopping false（沒人更新）",
                st_dead["pid"] == pb.pid and st_dead["stopping"] is False)
        r.check("B 死了，它的 keep 任務 s 還活著（孤兒，P-04）", pl.aos7_task.pid_alive(s_pid))
        # kernel 用 spawn 把 B、C 起回來（變成 A 的任務：路二起不了 daemon，只能借路一）
        back = {}
        for n in ("b", "c"):
            back[n] = sp.wait_for(lambda: [e for e in events(ev="back", daemon=n) if e["t"] >= t_kill],
                                  timeout=8, msg="%s 沒被起回來" % n)[0]
            r.measure("%s：kill -9 到 kernel 看到它回來（秒）" % n, round(back[n]["t"] - t_kill, 3))
        r.check("kernel 寫自己 node 的 spawn，B、C 被 A 的 tick 起回來", True)
        r.measure("B 回來後 status.root（變成 A 任務的掛載點路徑）", back["b"]["root"])
        r.check("B 回來後 status.root 跟原本的根不同字串（身分跟著起的方式變）", back["b"]["root"] != B)
        rc4 = receipt(f4, timeout=5)
        r.measure("B 死的時候寫的 ctl：回條延遲（秒，含死掉的時間）", rc4["latency"])
        r.check("B 死的時候寫的 ctl 留在 ctl/，重開後才執行", rc4["result"]["ok"])
        sp.ctl("resume", node="x", root=B)
        sp.wait_for(lambda: sp.round_of("x", root=B) > rx_before + 2 and sp.round_of("y", root=C) > ry_before + 2,
                    msg="B、C 重開後回合沒接上")
        rounds_x = [z["round"] for z in sp.rounds("x", root=B)]
        r.check("B 重開後 x 的回合數接著數（P-08）", rounds_x == sorted(rounds_x))
        gap = [b for a, b in zip(rounds_x, rounds_x[1:]) if b != a + 1]
        r.measure("x 的回合總結有跳號（crash 那回合沒 tock）", gap)
        s_live = [t for t in sp.live("x", root=B) if t.startswith("s-")]
        r.check("重開的 B 把孤兒 s 當活任務接回（keep 不重起）", len(s_live) == 1 and
                sp.task_file("x", s_live[0], "pid.json", root=B)["pid"] == s_pid, s_live)
        r.measure("kernel 事件數", len(events()))
        r.finding("路二只能寫控制檔，『起 daemon』沒有控制檔可寫；kernel 只能寫自己 node 的 spawn 讓 tick 起"
                  "（＝路一），起回來的 daemon 變成 A 的任務，status.root 變成任務掛載點路徑")
        r.finding("沒有 daemon 存活的檔案證明：status.json 不會說自己死了；kernel 得自己比 at（要跟牆鐘比）、"
                  "或用 pid（不是檔案介面）、或試 flock daemon.lock（會跟正要起來的 daemon 搶鎖）")
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
