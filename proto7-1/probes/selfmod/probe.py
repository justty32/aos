"""selfmod：任務在執行中改自己 node 的 tasks.json／timeline.json／.aos 裡的東西。

想逼出：interval 改了何時生效、加任務、keep 任務刪掉自己（D-3）、from_round、壞 JSON 與壞型別、
兩個任務同時改 tasks.json（lost update）、改別人 argv 對跑著的有沒有影響、任務能偽造 .aos 裡哪些東西。
"""
import datetime
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402
from probelib import fs, aos7_task  # noqa: E402


def S(name):
    return os.path.join(HERE, name)


def epoch(at):
    return datetime.datetime.fromisoformat(at).timestamp()


def pid_alive(pid):
    return aos7_task.pid_alive(pid)


class Run:
    def __init__(self, sp):
        self.sp, self.n = sp, 0

    def order(self, op, **kw):
        self.n += 1
        name = "%03d-%s.json" % (self.n, op)
        fs.write_json(self.sp.path("s", "orders", name), dict(kw, op=op))
        res = self.sp.path("s", "results", name)
        return self.sp.wait_for(lambda: fs.read_json(res), timeout=8, msg="agent 沒回 %s" % name)

    def ticks(self, node="s"):
        return [e for e in self.sp.log() if e.get("ev") == "tick" and e.get("node") == node]

    def wait_rounds(self, k, node="s", timeout=8):
        target = self.sp.round_of(node) + k
        self.sp.wait_for(lambda: self.sp.round_of(node) >= target and len(self.sp.rounds(node)) and
                         self.sp.rounds(node)[-1]["round"] >= target, timeout=timeout,
                         msg="%s 沒跑到第 %d 回合" % (node, target))

    def named(self, prefix, node="s"):
        return [t for t in self.sp.tasks(node) if t.startswith(prefix + "-r")]


def main():
    r = pl.Result("selfmod")
    with pl.Space("selfmod") as sp:
        PY = pl.PY
        sp.node("s", [
            {"name": "agent", "mode": "keep", "argv": [PY, S("agent.py")]},
            {"name": "pulse", "mode": "each", "argv": ["true"]},
            {"name": "late", "mode": "each", "argv": ["true"]},
            {"name": "sleepy", "mode": "keep", "argv": [PY, S("sleepy.py"), "v1"]},
            {"name": "quitter", "mode": "keep", "argv": [PY, S("quitter.py")]},
            {"name": "bouncer", "mode": "keep", "argv": [PY, S("bouncer.py")]},
        ], interval_ms=100)
        sp.node("r", [], interval_ms=100)
        sp.start(env={"AOS7_AUDIT": "1"})
        run = Run(sp)
        sp.wait_for(lambda: sp.round_of("s") >= 2)

        # ---- A. keep 任務刪掉自己（D-3）----
        sp.wait_for(lambda: fs.read_json(sp.path("s", "bouncer.count"), 0) >= 2, timeout=6, msg="bouncer 沒被起回來")
        run.wait_rounds(4)
        qn = fs.read_json(sp.path("s", "quitter.count"), 0)
        names = [t.get("name") for t in fs.read_json(sp.path("s", ".aos", "tasks.json"))["tasks"]]
        r.check("keep 任務先把自己從 tasks.json 拿掉再 kill 自己：只起過一次", qn == 1 and "quitter" not in names, qn)
        q1 = run.named("quitter")
        r.check("quitter 是被自己的 ctl kill 收掉的（code -15）",
                q1 and (sp.task_file("s", q1[0], "exit.json") or {}).get("code") == -15, q1)
        r.check("只 kill 自己、不改 tasks.json 的 bouncer 被起回來（D-3）",
                fs.read_json(sp.path("s", "bouncer.count"), 0) >= 2)

        # ---- B. 改別的任務的 argv：跑著的不受影響；restart 用舊 argv，kill 才用新的 ----
        sl0 = [t for t in sp.live("s") if t.startswith("sleepy")]
        run.order("set_field", name="sleepy", key="argv", value=[PY, S("sleepy.py"), "v2"])
        run.wait_rounds(3)
        r.check("改了 tasks.json 的 argv，跑著的 sleepy 還是原本那個",
                [t for t in sp.live("s") if t.startswith("sleepy")] == sl0, sl0)
        run.order("task_ctl", tid=sl0[0], ctl="restart")
        sp.wait_for(lambda: [t for t in sp.live("s") if t.startswith("sleepy") and t not in sl0], msg="restart 沒起新的")
        sl1 = [t for t in sp.live("s") if t.startswith("sleepy") and t not in sl0]
        sp.wait_for(lambda: fs.read_json(sp.path("s", "ver", sl1[0])))
        v_restart = fs.read_json(sp.path("s", "ver", sl1[0]))
        r.measure("改了 argv 之後 restart：新實例跑的版本", v_restart)
        run.order("task_ctl", tid=sl1[0], ctl="kill")
        sp.wait_for(lambda: [t for t in sp.live("s") if t.startswith("sleepy") and t not in sl0 + sl1],
                    msg="kill 後沒被 keep 起回來")
        sl2 = [t for t in sp.live("s") if t.startswith("sleepy") and t not in sl0 + sl1]
        sp.wait_for(lambda: fs.read_json(sp.path("s", "ver", sl2[0])))
        v_kill = fs.read_json(sp.path("s", "ver", sl2[0]))
        r.measure("改了 argv 之後 kill（keep 起回來）：新實例跑的版本", v_kill)
        if v_restart == "v1" and v_kill == "v2":
            r.finding("改任務表的 argv 不會影響跑著的任務；restart 抄 birth.json 的舊 argv（永遠是舊版），"
                      "反而 kill 讓 keep 照 tasks.json 起回來才換到新版。要「照新定義重起」沒有直接的 op。")

        # ---- C. 偽造別的任務的 exit.json ----
        pj = sp.task_file("s", sl2[0], "pid.json")
        run.order("forge_exit", tid=sl2[0])
        sp.wait_for(lambda: [t for t in sp.live("s") if t.startswith("sleepy") and t not in sl0 + sl1 + sl2],
                    msg="偽造 exit 後沒起新的")
        forged_alive = pid_alive(pj["pid"])
        r.measure("偽造 exit.json 後：被『結束』的 sleepy 程序其實還活著", forged_alive)
        ended = [e for x in sp.rounds("s") for e in x.get("ended", []) if e["tid"] == sl2[0]]
        r.measure("tock 記下的結束（偽造的）", ended)
        if forged_alive:
            r.finding("任務寫同 node 別的任務的 exit.json，tock 就當它結束、keep 又起一個：同名程序同時兩個在跑，"
                      "舊的變成沒人管的孤兒（kill 看到 exit.json 就當成功，不送訊號）。寫入紀錄記這筆是 ok。")
            try:
                os.killpg(pj["pgid"], signal.SIGTERM)
            except OSError:
                pass

        # ---- D. 偽造回合數 ----
        run.order("forge_round", round=1000)
        sp.wait_for(lambda: sp.round_of("s") > 1000)
        r.measure("任務把 round.json 改成 1000 後下一回合", sp.round_of("s"))
        r.finding("任務能改自己 node 的 round.json，回合數直接跳號（tick 照它 +1）；回合數是 S-08 的時間，任何任務都能撥鐘。")

        # ---- E. 改 from_round ----
        rw = sp.round_of("s")
        run.order("set_field", name="late", key="from_round", value=rw + 6)
        rw2 = sp.round_of("s")                            # 寫完時的回合（機器忙時可能比 rw 晚）
        run.wait_rounds(max(2, rw + 8 - rw2))
        late_rounds = sorted(x["round"] for x in sp.rounds("s") if any(t.startswith("late-r") for t in x.get("started", [])))
        gap = [n for n in range(rw2 + 1, rw + 6) if n in late_rounds]
        r.check("from_round 改到未來：中間的回合不起 late、到了又起",
                not gap and any(n >= rw + 6 for n in late_rounds), {"改的回合": rw, "起 late 的回合": [n for n in late_rounds if n > rw - 2]})

        # ---- F. 加一個 each 任務 ----
        res = run.order("add_task", item={"name": "added", "mode": "each", "argv": ["true"]})
        rnd_at = sp.round_of("s")
        sp.wait_for(lambda: run.named("added"), msg="加的任務沒起")
        first = run.named("added")[0]
        b = sp.task_file("s", first, "birth.json")
        r.check("執行中加的 each 任務被起了", bool(first))
        r.measure("加任務 → 第一次被起：[寫完時回合, 起的回合, 延遲_ms]",
                  [rnd_at, b["round"], round((epoch(b["at"]) - res["t1"]) * 1000)])

        # ---- G. 不原子地寫 tasks.json（寫一半停 400 ms）----
        sly = [t for t in sp.live("s") if t.startswith("sleepy")]
        n_tick = len(run.ticks())
        res = run.order("half_write", gap_ms=400)
        run.wait_rounds(2)
        during = [e for e in run.ticks()[n_tick:] if epoch(e["at"]) < res["t1"]]
        miss = [e["round"] for e in during if not any(t.startswith("pulse-r") for t in e.get("started", []))]
        r.measure("tasks.json 寫一半的 400 ms：tick 數、沒起 pulse 的回合數", [len(during), len(miss)])
        r.check("tasks.json 壞掉時 tick 不出錯（rc 0）、回合照走", all(e.get("rc") == 0 for e in during) and during)
        r.check("壞掉期間 keep 的 sleepy 沒被重起", [t for t in sp.live("s") if t.startswith("sleepy")] == sly)
        r.check("寫完之後 pulse 又起了", any(t.startswith("pulse-r") for t in run.ticks()[-1].get("started", [])))
        if miss:
            r.finding("tasks.json 壞掉（寫一半／JSON 錯）時 tick 當成空表、默默不起 each 任務（%d 回合），"
                      "round.json／rounds.jsonl／log 都沒記「任務表讀不懂」；任務自己用 open('w') 寫就會碰上。" % len(miss))

        # ---- H. 壞型別：from_round 寫成字串 ----
        n_tick = len(run.ticks())
        run.order("set_field", name="pulse", key="from_round", value="5")
        run.wait_rounds(3)
        bad = run.ticks()[n_tick + 1:]
        r.measure("from_round 是字串時 tick 的 rc", sorted({e.get("rc") for e in bad}))
        err = sp.status().get("nodes", {}).get("s", {}).get("last_error") or {}
        r.measure("status 的 last_error（末段）", (err.get("err") or "")[-80:])
        r.measure("那幾回合起的任務", [e.get("started") for e in bad][:3])
        run.order("set_field", name="pulse", key="from_round", value=1)
        run.wait_rounds(2)
        r.check("改回數字後 tick 恢復、pulse 又起", run.ticks()[-1].get("rc") == 0 and
                any(t.startswith("pulse-r") for t in run.ticks()[-1].get("started", [])))
        if any(e.get("rc") for e in bad):
            r.finding("tasks.json 一項的型別錯（from_round 是字串）讓整個 tick 丟例外：這回合後面所有任務都不起"
                      "（同 node 的 keep 掛了也不補），只有 status 的 last_error 看得到；壞 JSON 卻是默默當空表——兩種壞法處理不一致。")

        # ---- I. keep 任務沒寫 name ----
        run.order("add_task", item={"mode": "keep", "argv": ["sleep", "30"]})
        run.wait_rounds(5)
        noname = [t for t in sp.live("s") if t.startswith("task-r")]
        r.measure("沒寫 name 的 keep 任務 5 回合後的活實例數", len(noname))
        run.order("remove_task", name=None)
        for t in noname:
            run.order("task_ctl", tid=t, ctl="kill")
        if len(noname) > 1:
            r.finding("keep 項沒寫 name 時每回合都起一個：birth.json 的 name 補成 \"task\"，"
                      "但 keep 判斷拿 tasks.json 的 None 去比，永遠比不到（bug）。")

        # ---- J. 兩個任務同時改 tasks.json（lost update）----
        for lock in (False, True):
            fs.write_json(sp.path("r", ".aos", "tasks.json"), {"tasks": []})
            tag = "L" if lock else "N"
            for who in ("a", "b"):
                fs.write_json(sp.path("r", ".aos", "spawn", "%s%s.json" % (tag, who)),
                              {"name": "racer-" + tag + who,
                               "argv": [PY, S("racer.py"), tag + who, "100"] + (["--lock"] if lock else [])})
            sp.wait_for(lambda: len([t for t in sp.tasks("r") if t.startswith("racer-" + tag)]) == 2
                        and not [t for t in sp.live("r") if t.startswith("racer-" + tag)], timeout=15,
                        msg="racer 沒跑完")
            got = len([t for t in fs.read_json(sp.path("r", ".aos", "tasks.json"))["tasks"]
                       if t.get("name", "").startswith("r-" + tag)])
            r.measure("兩個任務各讀改寫 tasks.json 100 次，留下的項數（%s）" % ("用 flock" if lock else "不加鎖"), got)
            if lock:
                r.check("兩個任務用自己約定的 flock 改 tasks.json：200 項都在", got == 200, got)
            elif got < 200:
                r.finding("tasks.json 沒有鎖或版本號：兩個任務同時讀改寫，200 次只留下 %d 項（lost update）。"
                          "這次自己約定 flock `.aos/tasks.lock` 就 200/200，但 tick、kernel、人不會遵守這個約定。" % got)

        # ---- K. 改 interval：變慢、再變快 ----
        res = run.order("set_interval", ms=1500)
        sp.wait_for(lambda: [e for e in run.ticks() if epoch(e["at"]) > res["t1"]], msg="改慢後沒 tick")
        t_first = [epoch(e["at"]) for e in run.ticks() if epoch(e["at"]) > res["t1"]][0]
        sp.wait_for(lambda: [e for e in run.ticks() if epoch(e["at"]) > t_first], timeout=5)
        t_second = [epoch(e["at"]) for e in run.ticks() if epoch(e["at"]) > t_first][0]
        r.measure("改成 1500 ms：寫完到下一個 tick_ms、再下一個 tick 的間隔_ms",
                  [round((t_first - res["t1"]) * 1000), round((t_second - t_first) * 1000)])
        time.sleep(0.2)                                   # 現在在一個 1500 ms 回合的中間
        res = run.order("set_interval", ms=50)
        sp.wait_for(lambda: [e for e in run.ticks() if epoch(e["at"]) > res["t1"]], timeout=5)
        t_next = [epoch(e["at"]) for e in run.ticks() if epoch(e["at"]) > res["t1"]][0]
        delay = round((t_next - res["t1"]) * 1000)
        r.measure("1500 ms 回合中途改成 50 ms：寫完到下一個 tick_ms", delay)
        r.check("改快在一個舊 interval 內生效（< 3 秒）", delay < 3000, delay)
        if delay > 500:
            r.finding("interval 每回合開頭才讀：改快要等目前這回合的舊 interval 跑完（量到 %d ms），"
                      "沒有「立刻重讀」的 ctl（rescan 只重掃 node，不打斷等待）。" % delay)

        # ---- L. timeline.json 的 interval_ms 寫成字串：時間線 thread 掛掉 ----
        run.order("set_interval", ms=100)
        run.wait_rounds(2)
        run.order("write_timeline_raw", text='{"interval_ms": "fast"}')
        time.sleep(0.6)
        errs = [e for e in sp.log() if e.get("ev") == "error" and e.get("node") == "s"]
        st = sp.status().get("nodes", {}).get("s", {})
        r.measure("interval_ms 寫成字串後：log error、status phase", [e.get("msg") for e in errs][:1] + [st.get("phase")])
        rr = sp.round_of("s")
        run.order("set_interval", ms=100)
        time.sleep(0.6)
        r.measure("改回正常 interval 0.6 秒後回合有沒有前進", sp.round_of("s") > rr)
        if errs and sp.round_of("s") == rr:
            r.finding("timeline.json 的 interval_ms 不是數字（\"fast\"、null）會讓那條時間線的 thread 丟例外死掉，"
                      "status 停在 phase stopped，改回正確也不會復活；只能讓 node 消失再出現（或重開 daemon）。"
                      "agent 還活著但再也收不到 tock。")
        # 修補後（10-03）：interval 寫壞用預設、記 last_error，改回來就照新的跑；不必再「拿掉 timeline.json 再寫回」
        # （那樣現在等於 node 消失，daemon 會 kill 上面的任務，連這個 agent 一起；使用者 10-03 Q4 選 (a)）
        r.check("修補後：interval 寫壞時間線不死，改回正常後回合前進", sp.wait_for(lambda: sp.round_of("s") > rr, timeout=5))
        r.check("修補後：status 的 last_error 記了 timeline 的錯",
                any((e.get("last_error") or {}).get("prog") == "timeline" for e in [sp.status().get("nodes", {}).get("s", {})]))

        # ---- 寫入紀錄：任務改自己 .aos 的東西都算 ok ----
        ag = run.named("agent")
        w = fs.read_jsonl(os.path.join(aos7_task.task_dir(sp.path("s"), ag[0]), "writes.jsonl")) if ag else []
        aos = os.path.realpath(sp.path("s", ".aos"))
        touched = sorted({os.path.relpath(x["path"], aos).split(".tmp.")[0] for x in w if x["path"].startswith(aos + os.sep)})
        r.measure("agent 寫過自己 node 的 .aos/ 裡這些檔（全部記 ok）",
                  [t for t in touched if not t.startswith("tasks/") or t.endswith(("exit.json", "ctl.json"))][:8])
        r.check("寫入紀錄把這些都記成 ok（沒擋也沒標）",
                w and all(x["ok"] for x in w if x["path"].startswith(aos + os.sep)))
        r.finding("「只碰自己 node」把 .aos/ 也算自己的：任務能改 round.json（撥鐘）、別的任務的 exit.json（假結束）、"
                  "timeline.json（弄死時間線），寫入紀錄全記 ok。tasks.json／timeline.json 該給任務改，"
                  "round.json、rounds.jsonl、tasks/<別人>/ 的 exit.json／pid.json 照 spec 只有 tick／tock／aos7-run 寫。")

        r.check("daemon 還活著", sp.procs[0][1].poll() is None)
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
