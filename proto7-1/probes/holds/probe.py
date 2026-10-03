"""holds：多個控制者 pause 同一條線，各自只想解自己的（D-12），用現有單一 paused 狀態湊。

兩個世界跑同一份劇本（同一個 daemon，各自的 ctrl node 回合當時鐘）：
  naive/   預算 kernel、凍結 kernel、人都直接寫 daemon 控制檔 pause／resume
  holds/   預算、凍結、人只寫自己的 hold 檔（`holds/ctrl/holds/<owner>.json`）；arbiter 合成單一 pause／resume，
           只解自己停的（從 daemon log.jsonl 看最後一筆是誰下的）

劇本（ctrl 的回合）：人 10～22 要停；凍結 15～35；預算視 line 用量自己停放；
28：不走協定的舊腳本直接寫 resume（rogue）；31：對 line 的工作下 task kill（pause 中要等多久，D-13）；
40～45：維運用 CLI 直接 pause／resume（不走 holds 的外部 pause，arbiter 不該把它解掉）。
量：每個控制者「要停」期間 line 還跑了幾回合（扣掉 GRACE 秒的生效延遲），是誰的 resume 放掉的。
"""
import datetime
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import probelib as pl  # noqa: E402

PY = pl.PY
C = os.path.join(HERE, "ctrlr.py")
WORLDS = ("naive", "holds")
GRACE = 0.35          # 要停之後這麼多秒內還開的回合不算（ctrl 回合 0.1＋line 收完本回合 0.1＋餘裕）
END = 52


def ts(iso):
    return datetime.datetime.fromisoformat(iso).timestamp()


def main():
    r = pl.Result("holds")
    with pl.Space("holds") as sp:
        for w in WORLDS:
            sp.node(w + "/line", [{"name": "burn", "mode": "keep", "argv": [PY, C, "burn", w]}], interval_ms=100)
            m = {"aosd": ".aosd", "line": w + "/line"}
            items = [{"name": x, "mode": "keep", "argv": [PY, C, x, w], "mounts": m} for x in ("budget", "freeze")]
            if w == "holds":
                items.append({"name": "arbiter", "mode": "keep", "argv": [PY, C, "arbiter", w], "mounts": m})
            sp.node(w + "/ctrl", items, interval_ms=100)
        sp.start()

        ev = {w: [] for w in WORLDS}      # 探針自己扮的角色：(t, who, on)
        done = {w: set() for w in WORLDS}
        kill_at = {}

        def human(w, on, rnd):
            t = time.time()
            if w == "naive":
                sp.ctl("pause" if on else "resume", node=w + "/line", by="human")
            else:
                p = sp.path(w + "/ctrl", "holds", "human.json")
                if on:
                    pl.write(p, {"owner": "human", "node": w + "/line", "kind": "pause_timeline", "why": "人要維護"})
                else:
                    os.remove(p)
            pl.fs.append_jsonl(sp.path(w + "/ctrl", "intents.jsonl"), {"who": "human", "on": on, "t": t, "round": rnd})

        def script(w, rnd):
            def once(key, fn):
                if key not in done[w]:
                    done[w].add(key)
                    fn()
            if rnd >= 10:
                once("h+", lambda: human(w, True, rnd))
            if rnd >= 22:
                once("h-", lambda: human(w, False, rnd))
            if rnd >= 28:
                once("rogue", lambda: (sp.ctl("resume", node=w + "/line", by="old-script"),
                                       ev[w].append((time.time(), "rogue", None))))
            if rnd >= 31:
                def k():
                    live = sp.live(w + "/line")
                    if live:
                        pl.write(os.path.join(pl.aos7_task.task_dir(sp.path(w + "/line"), live[0]), "ctl.json"),
                                 {"op": "kill", "by": "probe", "why": "pause 中要收掉這個任務"})
                        kill_at[w] = (time.time(), rnd, live[0])
                once("kill", k)
            if rnd >= 40:
                once("ops+", lambda: (sp.ctl("pause", node=w + "/line", by="ops-cli"),
                                      pl.fs.append_jsonl(sp.path(w + "/ctrl", "intents.jsonl"),
                                                         {"who": "ops", "on": True, "t": time.time(), "round": rnd})))
            if rnd >= 45:
                once("ops-", lambda: (sp.ctl("resume", node=w + "/line", by="ops-cli"),
                                      pl.fs.append_jsonl(sp.path(w + "/ctrl", "intents.jsonl"),
                                                         {"who": "ops", "on": False, "t": time.time(), "round": rnd})))

        while min(sp.round_of(w + "/ctrl") for w in WORLDS) < END:
            for w in WORLDS:
                script(w, sp.round_of(w + "/ctrl"))
            time.sleep(0.01)
        for w in WORLDS:
            sp.ctl("pause", node=w + "/ctrl")
        time.sleep(0.3)

        log = sp.log()
        for w in WORLDS:
            line = w + "/line"
            intents = pl.fs.read_jsonl(sp.path(w + "/ctrl", "intents.jsonl"))
            spans = {}            # who -> [(on_t, off_t)]
            open_ = {}
            for x in sorted(intents, key=lambda x: x["t"]):
                if x["on"]:
                    open_[x["who"]] = x["t"]
                elif x["who"] in open_:
                    spans.setdefault(x["who"], []).append((open_.pop(x["who"]), x["t"]))
            for who, t0 in open_.items():
                spans.setdefault(who, []).append((t0, None))
            ticks = [ts(x["tick_at"]) for x in sp.rounds(line)]
            resumes = [(ts(x["at"]), x.get("by")) for x in log if x.get("ev") == "ctl" and x.get("node") == line
                       and x.get("op") == "resume" and x.get("ok")]
            leaked = {}
            released_by = {}
            for who, ss in spans.items():
                n = 0
                for a, b in ss:
                    for t in ticks:
                        if t >= a + GRACE and (b is None or t < b):
                            n += 1
                            rel = [by for rt, by in resumes if a <= rt <= t]
                            if rel:
                                released_by[rel[-1]] = released_by.get(rel[-1], 0) + 1
                leaked[who] = n
            r.measure("%s：每個控制者要停期間 line 還開了幾回合（扣 %.2f 秒生效延遲）" % (w, GRACE), leaked)
            r.measure("%s：放掉別人 hold 的 resume 是誰下的（回合數）" % w, released_by)
            r.measure("%s：要停的區間數" % w, {k: len(v) for k, v in spans.items()})
            pauses = sum(1 for x in log if x.get("ev") == "ctl" and x.get("node") == line and x.get("op") == "pause")
            r.measure("%s：寫給 daemon 的 pause／resume 控制檔數" % w, {"pause": pauses, "resume": len(resumes)})
            if w in kill_at:
                t0, rnd, tid = kill_at[w]
                cd = sp.task_file(line, tid, "ctl-done.json")
                done_t = os.path.getmtime(os.path.join(pl.aos7_task.task_dir(sp.path(line), tid), "ctl-done.json")) if cd else None
                r.measure("%s：pause 中下的 task kill 等了幾秒才執行（D-13）" % w,
                          None if done_t is None else round(done_t - t0, 2))
            spans_[w] = (leaked, released_by)

        nl, nrel = spans_["naive"]
        hl, hrel = spans_["holds"]
        alog = pl.fs.read_jsonl(sp.path("holds/ctrl", "arbiter.jsonl"))
        r.check("naive：至少一次某個控制者的 resume 放掉了別人還要停的線（單一 paused 位元）",
                any(by not in ("old-script",) for by in nrel), nrel)
        r.check("holds：arbiter 的 resume 都是在沒有任何 hold 時下的",
                all(not x["holds"] for x in alog if x["op"] == "resume"), [x for x in alog if x["op"] == "resume"][:3])
        fix = [x for x in alog if x.get("fix_external_resume")]
        r.check("holds：不走協定的 resume（old-script）被 arbiter 重新 pause", bool(fix), fix[:1])
        r.check("holds：只有 old-script 的 resume 放掉過 hold", set(hrel) <= {"old-script"}, hrel)
        ops = [ts(x["at"]) for x in log if x.get("ev") == "ctl" and x.get("node") == "holds/line" and x.get("by") == "ops-cli"]
        bad = [x for x in alog if x["op"] == "resume" and len(ops) == 2 and ops[0] < x["t"] < ops[1]]
        r.check("holds：ops-cli 直接下的 pause 被當成外部 hold，arbiter 沒去 resume 它（兩筆 ops-cli 之間沒有 arbiter 的 resume）",
                len(ops) == 2 and not bad, {"ops": len(ops), "bad": bad[:2]})
        r.measure("naive／holds：被放掉的回合合計", [sum(nl.values()), sum(hl.values())])
        span = ts(log[-1]["at"]) - ts(log[0]["at"]) if len(log) > 1 else 0
        r.measure("daemon log.jsonl 每秒幾行（4 條線）→ arbiter 看的尾端 400 行約涵蓋幾秒",
                  [round(len(log) / span, 1), round(400 / (len(log) / span), 1)] if span else None)
        r.finding("daemon 只有一個 paused 位元：誰的 resume 都會放掉所有人的 pause；holds 要靠一個常駐 arbiter "
                  "把 hold 檔合成單一 pause，arbiter 認『這個 pause 是不是我下的』只能翻 log.jsonl 尾端的 by（D-12）")
        r.finding("不走協定的 resume 仍會讓線多跑一兩回合才被 arbiter 補 pause；daemon 不知道 hold，擋不住")
        r.finding("pause 中的 task kill 要等所有 hold 放開（下一個 tick／tock）才執行（D-13：缺維護回合）")
    return r.done()


spans_ = {}

if __name__ == "__main__":
    pl.run_main(main)
