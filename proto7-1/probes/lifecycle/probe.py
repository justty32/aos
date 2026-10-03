"""lifecycle（D-3 延伸）：失敗重試、自我 restart、「別再起我」、crash loop。

想讓基礎設施露出：tasks.json 沒有 retry／停用欄位時，誰來數、怎麼表達「別再起我」；
自己寫自己的 ctl.json 何時生效；一起來就死的 keep 任務 50 回合後留下多少東西、有沒有退避；
rounds.jsonl 的 ended／exit.json 夠不夠 kernel 判斷「失敗」。
"""
import collections
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import probelib as pl  # noqa: E402

LT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lt.py")
N, M, FAILS = 3, 5, 2          # 失敗後 N 回合重試、最多 M 次、前 FAILS 次會失敗
GENS = 3                       # phoenix 自己 restart 幾次
CRASH_ROUNDS = 50


def argv(*a):
    return [pl.PY, LT] + [str(x) for x in a]


def jl(sp, nid, name):
    return pl.fs.read_jsonl(sp.path(nid, name + ".jsonl"))


def names_of(sp, nid):
    out = collections.defaultdict(list)
    for t in sp.tasks(nid):
        out[(sp.task_file(nid, t, "birth.json") or {}).get("name")].append(t)
    return out


def du(path, flag="-sb"):
    try:
        return int(subprocess.run(["du", flag, path], capture_output=True, text=True).stdout.split()[0])
    except (ValueError, IndexError):
        return None


def main():
    r = pl.Result("lifecycle")
    with pl.Space("lifecycle") as sp:
        sp.node("retry_self", [{"name": "flaky", "mode": "keep", "argv": argv("flaky_self", N, M, FAILS)}])
        job_argv = argv("job", FAILS)
        sp.node("retry_sup", [{"name": "sup", "mode": "keep", "argv": argv("sup", N, M, json.dumps(job_argv))}],
                files={".aos/spawn/a-job-1.json": {"name": "job", "argv": job_argv}})
        sp.node("phoenix", [{"name": "phoenix", "mode": "keep", "argv": argv("phoenix", GENS)}])
        sp.node("quit", [
            {"name": "rc0", "mode": "keep", "argv": argv("quit_rc0")},
            {"name": "marker", "mode": "keep", "argv": argv("quit_marker")},
            {"name": "edit1", "mode": "keep", "argv": argv("quit_edit", 3, 0.03)},
            {"name": "edit2", "mode": "keep", "argv": argv("quit_edit", 3, 0.03)},
            {"name": "selfkill", "mode": "keep", "argv": argv("quit_selfkill")},
        ])
        sp.node("crash", [{"name": "die", "mode": "keep", "argv": argv("die", 3)},
                          {"name": "nobin", "mode": "keep", "argv": ["/nonexistent/aos7probe-prog"]}], interval_ms=50)
        sp.start()

        def ready():
            ph = [e for e in jl(sp, "phoenix", "phoenix") if e["ev"] == "start"]
            fs_ = [e for e in jl(sp, "retry_self", "flaky_self") if e["ev"] in ("ok", "give-up")]
            jobs = [e for e in jl(sp, "retry_sup", "job")]
            return (len(sp.rounds("crash")) >= CRASH_ROUNDS and len(ph) > GENS and fs_
                    and any(e["n"] > FAILS for e in jobs) and len(sp.rounds("quit")) >= 15
                    and len(sp.rounds("retry_self")) >= 15)
        sp.wait_for(ready, timeout=28, msg="各情境都跑完")
        nodes = ("retry_self", "retry_sup", "phoenix", "quit", "crash")
        for nid in nodes:
            sp.ctl("pause", node=nid)
        sp.wait_for(lambda: all(sp.status().get("nodes", {}).get(n, {}).get("phase") == "paused" for n in nodes),
                    timeout=10)
        time.sleep(0.2)

        # ---------- (a) 失敗重試 ----------
        ev = jl(sp, "retry_self", "flaky_self")
        fails = [e for e in ev if e["ev"] == "fail"]
        oks = [e for e in ev if e["ev"] == "ok"]
        skips = [e for e in ev if e["ev"] == "done-skip"]
        rs = sp.rounds("retry_self")
        r.check("(a) keep＋自己數：失敗 %d 次後成功" % FAILS, len(fails) == FAILS and len(oks) == 1, [e["ev"] for e in ev[:6]])
        seq = [e["logical"] for e in fails + oks]
        r.measure("(a) 自己數：每次嘗試的回合", seq)
        r.measure("(a) 自己數：嘗試間隔（要 %d）" % N, [b - a for a, b in zip(seq, seq[1:])])
        r.measure("(a) 自己數：等重試時活著空等的 tock 數", [e["waited_tocks"] for e in fails + oks])
        done_round = oks[0]["logical"] if oks else None
        r.measure("(a) 自己數：成功後被 keep 再起、看到 done 立刻退出的次數（到暫停時）",
                  "%d 次／成功後 %d 回合" % (len(skips), rs[-1]["round"] - (done_round or 0)))
        r.measure("(a) 自己數：flaky 任務資料夾數", len(names_of(sp, "retry_self")["flaky"]))
        ended_codes = collections.Counter(e["code"] for x in rs for e in x["ended"])
        r.measure("(a) rounds.jsonl ended 的 code 分佈", dict(ended_codes))

        st = sp.task_file("retry_sup", names_of(sp, "retry_sup")["sup"][0], "sup.json") or {}
        jobs = names_of(sp, "retry_sup")["job"]
        job_birth = sorted((sp.task_file("retry_sup", t, "birth.json") or {}).get("round") for t in jobs)
        fail_seen = [e["seen_round"] for e in st.get("events", []) if e["ev"] == "job-fail"]
        r.check("(a) 小 kernel 寫 spawn：job 跑了 %d 次、最後成功" % (FAILS + 1),
                len(jobs) == FAILS + 1 and any(e["ev"] == "job-ok" for e in st.get("events", [])),
                {"jobs": jobs, "events": st.get("events")})
        r.measure("(a) 小 kernel：job 起的回合", job_birth)
        r.measure("(a) 小 kernel：tock 看到失敗的回合 → 下一次起的回合",
                  list(zip(fail_seen, job_birth[1:])))
        rsup = sp.rounds("retry_sup")
        codes = [(e["tid"], e["code"]) for x in rsup for e in x["ended"]]
        r.check("(a) rounds.jsonl 的 ended 看得到 job 的 code（1＝失敗、0＝成功）",
                [c for t, c in codes if t.startswith("job-")] == [1] * FAILS + [0], codes)
        ex = sp.task_file("retry_sup", jobs[0], "exit.json") or {}
        r.measure("(a) 失敗 job 的 exit.json", ex)

        # ---------- (b) 自我 restart ----------
        pev = jl(sp, "phoenix", "phoenix")
        starts = [e for e in pev if e["ev"] == "start"]
        ctlw = [e for e in pev if e["ev"] == "ctl-written"]
        terms = [e for e in pev if e["ev"] == "term"]
        r.check("(b) 自我 restart：gen 0..%d 都起來、新任務的 restart_of 接到前一個" % GENS,
                [e["gen"] for e in starts[:GENS + 1]] == list(range(GENS + 1))
                and all(starts[i + 1]["restart_of"] == starts[i]["tid"] for i in range(GENS)),
                [(e["gen"], e["tid"], e["restart_of"]) for e in starts])
        rph = sp.rounds("phoenix")
        r.check("(b) 同時活著的 phoenix 從不超過 1 個（restart 的 spawn 與 keep 不會雙開）",
                all(sum(1 for t in x["alive"] if t.startswith("phoenix-")) <= 1 for x in rph))
        delays = []
        for i, c in enumerate(ctlw[:GENS]):
            nxt = starts[i + 1]["birth_round"] if i + 1 < len(starts) else None
            delays.append({"寫 ctl 時剛收到的 tock": c["tock"], "下一代 birth round": nxt})
        r.measure("(b) 寫 ctl.json → 下一代起來", delays)
        r.measure("(b) 被 restart 的舊任務在 ended 的 code（有接 SIGTERM 乾淨退出）",
                  [(e["tid"], e["code"]) for x in rph for e in x["ended"]])
        r.measure("(b) rounds.jsonl 的 ctl 紀錄", [c for x in rph for c in x["ctl"]])

        # ---------- (c) 別再起我 ----------
        qn = names_of(sp, "quit")
        rq = sp.rounds("quit")
        tj = pl.fs.read_json(sp.path("quit", ".aos", "tasks.json"), {})
        left = [i["name"] for i in tj.get("tasks", [])]
        r.measure("(c) quit 回合數", len(rq))
        r.measure("(c) 各做法的任務資料夾數", {k: len(v) for k, v in qn.items()})
        qev = jl(sp, "quit", "quit")
        r.measure("(c) marker：看到標記立刻退出的次數", sum(1 for e in qev if e["ev"] == "start-skip"))
        r.measure("(c) tasks.json 最後剩下", left)
        edited = [e["name"] for e in qev if e["ev"] == "edited"]
        r.check("(c) edit1／edit2 都把自己從 tasks.json 拿掉了（最後都不在表上）",
                set(edited) == {"edit1", "edit2"} and not ({"edit1", "edit2"} & set(left)), {"edited": edited, "left": left})
        relaunch = {n: len(qn[n]) - 1 for n in ("edit1", "edit2")}
        r.measure("(c) edit：改 tasks.json 的次數（>1＝修改被別人蓋掉、被起回來後又改一次）",
                  dict(collections.Counter(edited)))
        r.measure("(c) edit 任務改完後又被起的次數", relaunch)
        if any(relaunch.values()):
            r.finding("兩個任務同一個 tock 讀—改—寫 tasks.json（中間隔 30 ms）：%s 的修改被蓋掉，被起回來、又改一次才停" %
                      [n for n, v in relaunch.items() if v])
        r.check("(c) rc=0 退出擋不住 keep：rc0 幾乎每回合被起一次", len(qn["rc0"]) >= len(rq) - 3, len(qn["rc0"]))
        r.check("(c) 自己寫 ctl kill（D-3）擋不住 keep：selfkill 被起不只一次", len(qn["selfkill"]) >= 2, len(qn["selfkill"]))
        sk_codes = [e["code"] for x in rq for e in x["ended"] if e["tid"].startswith("selfkill-")]
        r.measure("(c) selfkill 被 kill 的 code", collections.Counter(sk_codes))
        r.finding("「別再起我」只有改 tasks.json 有效；rc=0、標記檔、ctl kill 都擋不住 keep（%d 回合各留 %d／%d／%d 個資料夾）" %
                  (len(rq), len(qn["rc0"]), len(qn["marker"]), len(qn["selfkill"])))

        # ---------- (d) crash loop ----------
        rc_ = sp.rounds("crash")
        cn = names_of(sp, "crash")
        per_round = collections.Counter()
        for x in rc_:
            for t in x["started"]:
                per_round[t.rsplit("-r", 1)[0]] += 1
        r.check("(d) crash loop：die 每回合都被起（沒有退避）", len(cn["die"]) >= len(rc_) - 2,
                {"die": len(cn["die"]), "rounds": len(rc_)})
        r.measure("(d) crash 回合數／die 資料夾／nobin 資料夾", [len(rc_), len(cn["die"]), len(cn["nobin"])])
        r.measure("(d) crash node .aos/tasks 內容 bytes／實際佔磁碟 KiB",
                  [du(sp.path("crash", ".aos", "tasks")), du(sp.path("crash", ".aos", "tasks"), "-sk")])
        r.measure("(d) crash rounds.jsonl bytes", os.path.getsize(sp.path("crash", ".aos", "rounds.jsonl")))
        cc = collections.Counter((e["tid"].rsplit("-r", 1)[0], e["code"]) for x in rc_ for e in x["ended"])
        r.measure("(d) ended (name, code) 分佈", {"%s:%s" % k: v for k, v in cc.items()})
        nb = sp.task_file("crash", cn["nobin"][0], "exit.json") or {}
        r.check("(d) 找不到程式：exit.json code 127 帶 error", nb.get("code") == 127 and "error" in nb, nb)
        same_round = sum(1 for x in rc_ for e in x["ended"]
                         if e["tid"].startswith("die-") and e["tid"] in x["started"])
        r.measure("(d) die 起來、同一回合 tock 就記 ended 的比例", "%d/%d" % (same_round, len(cn["die"])))
        early = [e.get("early") for e in sp.log() if e.get("ev") == "tock" and e.get("node") == "crash"]
        r.measure("(d) crash node 提前 tock 比例（起的都死了 → 提前）", "%d/%d" % (early.count(True), len(early)))
        r.finding("keep＋自己數做得到重試，但成功後 keep 仍每回合起一個、看到 done 就退出（%d 個空殼）；"
                  "等重試時程序要活著空等 tock" % len(skips))
        r.finding("rounds.jsonl 的 ended 只有 tid／code，沒有 name；kernel 判斷失敗要拆 tid 或讀 birth.json，"
                  "而且被 ctl kill（-15，或接 SIGTERM 後 0）和自己掛掉分不出來，要回頭對 ctl 欄")
        r.finding("crash loop 沒有退避：%d 回合 die、nobin 各 %d／%d 個資料夾，每回合 ended 兩筆失敗，沒有任何地方累計『連續失敗幾次』" %
                  (len(rc_), len(cn["die"]), len(cn["nobin"])))
    return r.done()


if __name__ == "__main__":
    pl.run_main(main)
