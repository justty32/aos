"""hsched：報告 2026-10-03-other-os-borrow §10、§14 實驗三「階層 scheduler 的慢策略、快執行」。

一個控制 node（ctl：確定性根 kernel＋驗證器＋執行層，keep 任務 kernel.py；C／D 另有 agent.py）、
帳本／閘門 node（bank：gate.py，四組共用）、兩個專案（P、Q：各三個合作式 mock worker，P 中途擴成 10 個）。
同一份可重播 trace（sim.build_trace），四組策略：A stride、B 固定八回合窗口、C LLM 直接挑工作、D LLM 提政策＋kernel 執行；
另跑 Adon（A＋依賴捐贈）、Atuned（A 固定用離線 D 那份政策）當對照。指標以控制回合計。

    python3 probe.py                       # 離線協議驗證（run_all 用）：C／D 用預錄回答，含晚三回合、壞 JSON、超父額、
                                           # 舊 epoch、要求 pause 自己；D 中途 kill kernel。不打 LLM，約 30 秒
    python3 probe.py --real deepseek-chat[,claude-haiku-4.5] [--groups D:deepseek-chat,C:deepseek-chat,...]
                     [--reps 3] [--cap 300] [--no-det] [--tag x-]
                                           # 真模型比較：只打 LiteLLM 127.0.0.1:4000；回合 1 秒、每次 ≤120 秒；
                                           # 呼叫上限跨多次執行累計（runs/calls.json）；同批預設也跑 A／Adon／Atuned／B；紀錄存 runs/
"""
import json
import os
import signal
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import probelib as pl  # noqa: E402
import llmop  # noqa: E402
import sim  # noqa: E402

PY = pl.PY
fs = pl.fs
WMOUNTS = {"bank": "bank/io", "clk": "ctl/.aos", "pub": "ctl/pub"}

# 離線預錄：D 的政策請求依序 0..；C 的挑選請求依序 0..
GOOD_CHOICE = {"group_policy": "stride_inspired", "interactive_max_wait_rounds": 3, "dependency_donation": True,
               "max_calls_inflight": 3, "background_max_inflight": 3}
D_SCRIPT = {"choice": GOOD_CHOICE, "default": {"delay": 1},
            "0": {"raw": "{\"schema\": \"aos.agent-policy-proposal.v1\", \"choice\": {"},          # 壞 JSON
            "2": {"delay": 1, "override": {"choice": {"max_calls_inflight": 6}}},                 # 超父額
            "3": {"late": 3},                                                                     # 晚三回合
            "4": {"delay": 1, "override": {"validity": {"epoch": "c-0"}}},                        # 舊 epoch
            "5": {"delay": 1, "override": {"pause": ["ctl"]}}}                                    # 要求 pause 自己
D_EXPECT = {0: "bad_json", 2: "over_parent", 3: "late", 4: "stale_epoch", 5: "pause_self"}
C_SCRIPT = {"default": {"delay": 0},
            "1": {"raw": "jobs: Q-int-00 please"},
            "3": {"delay": 0, "override": {"jobs": "@all"}},
            "5": {"late": 3},
            "7": {"delay": 0, "override": {"epoch": "c-0"}},
            "9": {"delay": 0, "override": {"pause": ["ctl"]}}}
C_EXPECT = {1: "bad_json", 3: "over_parent", 5: "late", 7: "stale_epoch", 9: "pause_self"}


def build(sp, strategy, agent, interval_ms, end):
    trace = sim.build_trace()
    ctl_tasks = [{"name": "kernel", "mode": "keep", "argv": [PY, os.path.join(HERE, "kernel.py")],
                  "mounts": {"P": "P/work", "Q": "Q/work", "Pspawn": "P/.aos/spawn"}}]
    if strategy in ("C", "D"):
        ctl_tasks.append({"name": "agent", "mode": "keep", "argv": [PY, os.path.join(HERE, "agent.py")]})
    sp.node("ctl", ctl_tasks, interval_ms=interval_ms,
            files={"trace.json": trace, "pub/provider.json": trace["provider"],
                   "cfg.json": {"strategy": strategy, "end": end, "agent": agent, "tuned": GOOD_CHOICE,
                                "worker_argv": [PY, os.path.join(HERE, "worker.py")], "worker_mounts": WMOUNTS}})
    sp.node("bank", [{"name": "gate", "mode": "keep", "argv": [PY, os.path.join(HERE, "gate.py")],
                      "mounts": {"pub": "ctl/pub", "clk": "ctl/.aos"}}], interval_ms=200)
    for p in sim.PROJECTS:
        sp.node(p, [{"name": "w%d" % k, "mode": "keep", "argv": [PY, os.path.join(HERE, "worker.py"), "w%d" % k],
                     "mounts": WMOUNTS} for k in (1, 2, 3)], interval_ms=200)
    pl.write(os.path.join(sp.root, ".aosd", "paused.json"), {"paused": ["ctl"]})   # 等 worker、閘門都起來才開始數回合
    return trace


def kill_task(sp, node, name):
    tid = sp.wait_for(lambda: [t for t in sp.live(node)
                               if (sp.task_file(node, t, "birth.json") or {}).get("name") == name], msg="沒有活的 " + name)[0]
    pid = sp.wait_for(lambda: sp.task_file(node, tid, "pid.json"), msg="沒有 pid.json")
    os.killpg(pid["pgid"], signal.SIGKILL)
    sp.wait_for(lambda: sp.task_file(node, tid, "exit.json"), msg="%s 沒寫 exit.json" % tid)
    return tid


def run_one(strategy, agent=None, interval_ms=60, end=sim.END, kill_kernel_at=None, wall_cap=None, extra=None):
    """開一個空間跑一次 trace，回 (分析, 原始紀錄)。extra(sp)：跑完、收掉之前做的額外動作（回 dict 併進分析）。"""
    with pl.Space("hsched") as sp:
        trace = build(sp, strategy, agent, interval_ms, end)
        sp.start()
        sp.wait_for(lambda: all(os.path.exists(sp.path(p, "work", "w%d" % k, "alive.json"))
                                for p in sim.PROJECTS for k in (1, 2, 3)) and sp.live("bank"),
                    timeout=20, msg="worker／閘門沒起來")
        time.sleep(0.1)
        sp.ctl("resume", "ctl")
        t0 = time.monotonic()
        info = {}
        if kill_kernel_at:
            sp.wait_for(lambda: sp.round_of("ctl") >= kill_kernel_at, timeout=60, msg="ctl 沒到 kill 回合")
            info["killed_at"] = sp.round_of("ctl")
            kill_task(sp, "ctl", "kernel")
        fin = sp.path("ctl", "kernel", "final.json")
        limit = wall_cap or (end * interval_ms / 1000.0 * 10 + 60)   # 離線：機器忙時回合會變慢，給寬
        while not os.path.exists(fin):
            if time.monotonic() - t0 > limit and not os.path.exists(sp.path("ctl", "stop.json")):
                pl.write(sp.path("ctl", "stop.json"), {"why": "wall cap %.0f s" % limit})
            if time.monotonic() - t0 > limit + 30:
                raise pl.ProbeTimeout("kernel 沒寫 final.json")
            time.sleep(0.1)
        info["wall_s"] = round(time.monotonic() - t0, 1)
        time.sleep(0.05)
        if extra:
            info.update(extra(sp))
        raw = collect(sp)
        raw["info"] = info
        a = analyze(trace, raw, strategy, end)
        return a, raw


def collect(sp):
    d = lambda *x: sp.path("ctl", *x)  # noqa: E731
    answers = {}
    for f in sorted(os.listdir(d("answers"))) if os.path.isdir(d("answers")) else []:
        if f.endswith(".meta.json"):
            rev = int(f.split(".")[0])
            try:
                raw = open(d("answers", "%06d.txt" % rev), encoding="utf-8").read()
            except OSError:
                raw = None
            answers[rev] = {"meta": fs.read_json(d("answers", f)), "raw": raw}
    reqs = {}
    for f in sorted(os.listdir(d("requests"))) if os.path.isdir(d("requests")) else []:
        if f.endswith(".json"):
            reqs[int(f[:-5])] = fs.read_json(d("requests", f))
    tickets = {}
    for f in os.listdir(d("pub", "tickets")):
        tk = fs.read_json(d("pub", "tickets", f))
        if isinstance(tk, dict):
            tickets[tk["ticket"]] = tk
    return {"final": fs.read_json(d("kernel", "final.json")), "decisions": fs.read_jsonl(d("kernel", "decisions.jsonl")),
            "validation": fs.read_jsonl(d("kernel", "validation.jsonl")), "answers": answers, "requests": reqs,
            "tickets": tickets, "gate": fs.read_jsonl(sp.path("bank", "ledger", "events.jsonl")),
            "daemon_log": [x for x in sp.log() if x.get("ev") == "ctl"], "paused": fs.read_json(
                os.path.join(sp.root, ".aosd", "paused.json")),
            "ctl_rounds": [x.get("round") for x in sp.rounds("ctl")],
            "p_workers": sorted(x for x in os.listdir(sp.path("P", "work"))
                                if os.path.exists(sp.path("P", "work", x, "alive.json")))}


def gate_audit(trace, raw):
    """獨立重算閘門帳：在途、額度、凍結、票的來源。回 (違規清單, 量)。"""
    jb = {j["id"]: j for j in trace["jobs"]}
    bad, inflight, held, spent, res = [], {p: 0 for p in sim.PROJECTS}, {}, {p: 0 for p in sim.PROJECTS}, \
        {p: 0 for p in sim.PROJECTS}
    rejected = {v["revision"] for v in raw["validation"] if not v["ok"]}
    granted_jobs, max_p_after = set(), 0
    freeze = [(e["project"], e["round"], e["until"]) for e in trace["events"] if e["kind"] == "freeze"]
    scale_r = next(e["round"] for e in trace["events"] if e["kind"] == "scale")
    inflight_at_freeze, freeze_settled = [], []
    for ev in raw["gate"]:
        if ev["kind"] == "grant":
            p = ev["project"]
            tk = raw["tickets"].get(ev["ticket"])
            if not tk:
                bad.append("grant %s 沒有對應的票" % ev["ticket"])
                continue
            if ev["job"] in granted_jobs:
                bad.append("%s 拿到第二次 grant" % ev["job"])
            granted_jobs.add(ev["job"])
            by = tk.get("by") or ""
            if ":" in by and int(by.split(":")[1]) in rejected:
                bad.append("%s 的票來自被拒的提案／挑選 %s" % (ev["job"], by))
            if ev["round"] > tk["round"] + sim.TICKET_TTL:
                bad.append("%s 用過期票開工" % ev["job"])
            for fp, a, b in freeze:
                if p == fp and a <= ev["round"] <= b:
                    bad.append("%s 在凍結期（%d）拿到 grant" % (ev["job"], ev["round"]))
            inflight[p] += 1
            res[p] += ev["tokens"]
            held[ev["ticket"]] = (p, ev["tokens"], ev["round"])
            if inflight[p] > sim.PROJECT_CAP or sum(inflight.values()) > sim.GLOBAL_CAP:
                bad.append("在途超限：%s" % inflight)
            if spent[p] + res[p] > sim.BUDGET[p]:
                bad.append("%s 超出額度" % p)
            if p == "P" and ev["round"] >= scale_r:
                max_p_after = max(max_p_after, inflight[p])
        elif ev["kind"] == "settle":
            p, t, g = held.pop(ev["ticket"])
            inflight[p] -= 1
            res[p] -= t
            spent[p] += ev["used"]
            for fp, a, b in freeze:
                if p == fp and g < a <= ev["round"]:
                    freeze_settled.append({"ticket": ev["ticket"], "reserved": t, "used": ev["used"]})
    for fp, a, b in freeze:
        inflight_at_freeze = [x for x in freeze_settled]
    return bad, {"spent": spent, "max_P_inflight_after_scale": max_p_after,
                 "freeze_inflight_settled": inflight_at_freeze, "still_held": len(held)}


def analyze(trace, raw, strategy, end):
    fin = raw["final"] or {}
    st = fin.get("jobs", {})
    last = fin.get("round", end)
    iw, bw, qual, n_done = [], [], 0, 0
    per = {}
    for j in trace["jobs"]:
        s = st.get(j["id"], {})
        if j["arrival"] > last:
            continue
        if s.get("state") == "done":
            n_done += 1
            w = s["start"] - j["arrival"]
            if s["done"] - j["arrival"] <= j["deadline"]:
                qual += 1
        else:
            w = last - j["arrival"]          # 沒開工：等到結束（設限）
        (iw if j["cls"] == "interactive" else bw).append(w)
        per[j["id"]] = w
    bad, gm = gate_audit(trace, raw)
    sched_tok = sum((a["meta"] or {}).get("tokens", 0) for a in raw["answers"].values())
    sched_calls = sum((a["meta"] or {}).get("calls", 0) for a in raw["answers"].values())
    worker_tok = sum(gm["spent"].values())
    cost = worker_tok + sched_tok
    ctl_pauses = [x for x in raw["daemon_log"] if x.get("op") in ("pause", "stop") and x.get("node") in (sim.CTL, None)
                  and x.get("by") != "probe"]
    val = raw["validation"]
    return {"strategy": strategy, "last_round": last, "done": n_done, "qualified": qual,
            "int_p50": sim.pctl(iw, 50), "int_p95": sim.pctl(iw, 95), "bg_max_wait": max(bw or [0]),
            "urgent_A_wait": per.get("Q-urgent-A"), "violations": len(bad) + len(ctl_pauses),
            "violation_list": (bad + ["控制線被 pause：%s" % x for x in ctl_pauses])[:5],
            "takeovers": fin.get("takeovers"), "rejected": sum(1 for v in val if not v["ok"] and v["reason"] != "timeout"),
            "timeouts": sum(1 for v in val if v["reason"] == "timeout"), "accepted": sum(1 for v in val if v["ok"]),
            "sched_tokens": sched_tok, "sched_calls": sched_calls, "worker_tokens": worker_tok, "cost": cost,
            "qual_per_10k": round(qual / cost * 10000, 3) if cost else None,
            "restarts": fin.get("restarts"), "max_P_inflight_after_scale": gm["max_P_inflight_after_scale"],
            "P_workers": len(raw["p_workers"]), "freeze_inflight_settled": gm["freeze_inflight_settled"],
            "kernel_skipped_rounds": sum(len(x.get("skipped", [])) for x in raw["decisions"] if x.get("src") == "skip"),
            "kernel_ms_max": max([x.get("ms", 0) for x in raw["decisions"]] or [0]),
            "frame_miss": sum(sum(m["unused"].values()) for m in (fin.get("fst") or {}).get("miss", [])),
            "frame_late": (fin.get("fst") or {}).get("late")}


def idx_rev(raw, kind):
    revs = sorted(k for k, v in raw["requests"].items() if (v or {}).get("kind") == kind)
    return {i: r for i, r in enumerate(revs)}


def protocol_checks(r, tag, raw, kind, expect):
    """預錄的壞回答全被拒、理由對；被拒那份不產生任何效果；保底在下一次決策就接手。"""
    ir = idx_rev(raw, kind)
    vbyrev = {}
    for v in raw["validation"]:
        vbyrev.setdefault(v["revision"], []).append(v)
    got = {i: [v["reason"] for v in vbyrev.get(ir.get(i), [])] for i in expect}
    r.check("%s：預錄的 %s 全被拒、理由對" % (tag, "／".join(expect.values())),
            all(expect[i] in got[i] and not any(v["ok"] for v in vbyrev.get(ir.get(i), [])) for i in expect), got)
    rejected = {v["revision"] for v in raw["validation"] if not v["ok"]}
    srcs = {d.get("src") for d in raw["decisions"]}
    tk_bad = [t for t in raw["tickets"].values() if ":" in (t.get("by") or "") and int(t["by"].split(":")[1]) in rejected]
    r.check("%s：被拒的提案／挑選沒有任何效果（沒當過來源、沒發過票）" % tag,
            not tk_bad and not any(("%s:%d" % ("policy" if kind == "policy" else "pick", x)) in srcs for x in rejected),
            tk_bad[:3])
    rounds = {}
    for d in raw["decisions"]:
        rounds.setdefault(d["round"], []).append(d)
    late = []
    last = (raw["final"] or {}).get("round", 0)
    if kind == "pick":
        for i, rev in ir.items():
            req = raw["requests"][rev]
            if req["respond_by"] + 1 > last:      # trace 結束時還在等的，不算
                continue
            ok = any(v["ok"] for v in vbyrev.get(rev, []))
            if ok:
                continue
            tk = [d["round"] for d in raw["decisions"] if any(x.endswith(":%d" % rev) for x in d.get("takeover", []))]
            if not tk or tk[0] > req["respond_by"] + 1:
                late.append((i, rev, tk[:1], req["respond_by"]))
    else:
        for i in expect:
            rev = ir.get(i)
            rej = [v["round"] for v in vbyrev.get(rev, []) if not v["ok"]]
            if not rej or not [d for d in rounds.get(rej[0], []) if d.get("src") not in (None, "start", "skip")]:
                late.append((i, rev, rej))
    r.check("%s：被拒或沒回之後，保底在下一次控制決策就接手（C：期限後一回合內代派；D：同一回合照有效政策或預設派）"
            % tag, not late, late[:3])


def check_offline_validator(r):
    """純函式：六種壞提案、五種壞挑選直接丟驗證器（不經 daemon）。"""
    req = {"revision": 7, "round": 40, "respond_by": 48, "epoch": "c-1"}
    good = {"schema": "aos.agent-policy-proposal.v1", "proposal_id": "x", "input_revision": 7, "envelope_id": "env-1",
            "validity": {"clock_node": "ctl", "epoch": "c-1", "until_round": 70}, "choice": dict(GOOD_CHOICE),
            "pause": []}

    def v(o, now=41, raw=None):
        return sim.validate_proposal(raw if raw is not None else json.dumps(o), req, now, "c-1", "env-1")[1]
    cases = {"ok": v(good), "bad_json": v(None, raw="{\"schema\": "),
             "late": v(good, now=51), "over_parent": v(dict(good, choice={"max_calls_inflight": 4})),
             "stale_epoch": v(dict(good, validity=dict(good["validity"], epoch="c-0"))),
             "pause_self": v(dict(good, pause=["ctl"])),
             "stale_envelope": v(dict(good, envelope_id="env-0")),
             "out_of_range": v(dict(good, validity=dict(good["validity"], until_round=200)))}
    r.check("驗證器（純函式）：提案的合格／壞 JSON／晚三回合／超父額／舊 epoch／pause 自己／舊 envelope／期限過長各得其理由",
            all(k == got for k, got in cases.items()), cases)
    preq = {"revision": 3, "round": 10, "respond_by": 12, "epoch": "c-1"}
    ready = [{"id": "a", "project": "P", "cls": "interactive", "tokens": 100, "waited": 0},
             {"id": "b", "project": "P", "cls": "background", "tokens": 100, "waited": 0}]
    cap = {"inflight": {"P": 2, "Q": 0}, "bg_inflight": 0, "free_workers": {"P": 3, "Q": 3},
           "budget": {"P": 1000, "Q": 1000}, "frozen": set()}
    gp = {"schema": "aos.pick.v1", "input_revision": 3, "epoch": "c-1", "jobs": ["a"]}

    def vp(o, now=11, raw=None):
        return sim.validate_pick(raw if raw is not None else json.dumps(o), preq, now, "c-1", ready, cap)[1]
    pc = {"ok": vp(gp), "bad_json": vp(None, raw="a,b"), "late": vp(gp, now=15),
          "over_parent": vp(dict(gp, jobs=["a", "b"])), "stale_epoch": vp(dict(gp, epoch="c-0")),
          "pause_self": vp(dict(gp, pause=["ctl"])), "not_ready": vp(dict(gp, jobs=["zz"]))}
    r.check("驗證器（純函式）：挑選的合格／壞 JSON／晚三回合／超父額／舊 epoch／pause 自己／不可派各得其理由",
            all(k == got for k, got in pc.items()), pc)


def forge(sp):
    """閘門是最後一道：直接丟三個假請求。"""
    def req(rid, obj):
        pl.write(sp.path("bank", "io", "requests", rid + ".json"), dict(obj, request_id=rid))
        return sp.wait_for(lambda: fs.read_json(sp.path("bank", "io", "receipts", rid + ".json")), msg="閘門沒回")
    used = next(e for e in fs.read_jsonl(sp.path("bank", "ledger", "events.jsonl")) if e["kind"] == "grant")
    out = {"no_ticket": req("forge-1", {"op": "grant", "ticket": "t-fake", "project": "P", "job": "P-bg-00",
                                        "tokens": 1, "worker": "w1"}).get("reason"),
           "replay": req("forge-2", {"op": "grant", "ticket": used["ticket"], "project": used["project"],
                                     "job": used["job"], "tokens": used["tokens"], "worker": used["worker"]}).get("reason"),
           "mismatch": req("forge-3", {"op": "grant", "ticket": used["ticket"], "project": used["project"],
                                       "job": used["job"], "tokens": 1, "worker": used["worker"]}).get("reason")}
    return {"forge": out}


FMT = ("strategy", "done", "qualified", "int_p50", "int_p95", "bg_max_wait", "urgent_A_wait", "violations",
       "takeovers", "rejected", "timeouts", "accepted", "sched_calls", "sched_tokens", "cost", "qual_per_10k")


def table(rows):
    lines = [" | ".join(FMT)]
    for a in rows:
        lines.append(" | ".join(str(a.get(k)) for k in FMT))
    return "\n".join(lines)


def offline():
    r = pl.Result("hsched")
    check_offline_validator(r)
    res = {}
    jobs = [("A", dict(extra=forge)), ("Adon", {}), ("Atuned", {}), ("B", {}),
            ("C", dict(agent={"mode": "script", "script": {"pick": C_SCRIPT}})),
            ("D", dict(agent={"mode": "script", "script": {"policy": D_SCRIPT}}, kill_kernel_at=55))]
    errs = []

    def go(name, kw):
        try:
            res[name] = run_one(name, **kw)
        except Exception as e:   # noqa: BLE001  探針：記下來，讓 check 失敗
            errs.append("%s: %r" % (name, e))
    ths = [threading.Thread(target=go, args=x) for x in jobs]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    r.check("六組都跑完 trace（%d 個控制回合）" % sim.END, not errs and all(
        (res[n][0]["last_round"] or 0) >= sim.END for n, _ in jobs), errs or {n: res[n][0]["last_round"] for n in res})
    if errs:
        return r.done()
    A = {n: res[n][0] for n, _ in jobs}
    for n, a in A.items():
        r.check("%s：超額／越權生效 0 次（閘門帳獨立重算：在途、額度、凍結期、票來源；控制線沒被 pause）" % n,
                a["violations"] == 0, a["violation_list"])
        r.check("%s：P 擴到 10 個 worker 後，P 在途仍 ≤ 根給的 %d（根額度不因多開子 worker 增加）" % (n, sim.PROJECT_CAP),
                a["P_workers"] == 10 and 0 < a["max_P_inflight_after_scale"] <= sim.PROJECT_CAP,
                (a["P_workers"], a["max_P_inflight_after_scale"]))
        r.check("%s：禁止 P 發新 grant 時，在途的 P 工作照保留額結算（沒有被放掉）" % n,
                all(x["used"] == x["reserved"] for x in a["freeze_inflight_settled"]), a["freeze_inflight_settled"])
    fz = sum(len(a["freeze_inflight_settled"]) for a in A.values())
    r.check("凍結期間各組至少有一件跨凍結的在途工作（上一條不是空驗）", fz > 0, fz)
    r.check("閘門最後一道：沒票、重用票、票上欄位不符的 grant 全拒",
            res["A"][1]["info"].get("forge") == {"no_ticket": "no_ticket", "replay": "replay", "mismatch": "mismatch"},
            res["A"][1]["info"].get("forge"))
    protocol_checks(r, "C", res["C"][1], "pick", C_EXPECT)
    protocol_checks(r, "D", res["D"][1], "policy", D_EXPECT)
    d = res["D"][1]
    kr = d["info"].get("killed_at")
    starts = [x for x in d["decisions"] if x.get("src") == "start"]
    after = [x["round"] for x in d["decisions"] if x.get("epoch") == "c-2" and x.get("src") not in ("start", "skip")]
    r.check("D：kill kernel 後 keep 重起、讀回持久狀態接著做（epoch c-1→c-2，3 回合內恢復派工決策）",
            A["D"]["restarts"] == 1 and len(starts) == 2 and after and after[0] - kr <= 3, (kr, after[:1]))
    r.check("D：控制線回合連續（kernel 死掉期間 ctl 照常 tick-tock）",
            d["ctl_rounds"] == list(range(1, len(d["ctl_rounds"]) + 1)), d["ctl_rounds"][-3:])
    r.check("B：固定窗口晚發 3 回合，記下 miss、不補發", A["B"]["frame_late"] and A["B"]["frame_late"][0]["lost_rounds"] == 3,
            A["B"]["frame_late"])
    for n in A:
        r.measure(n, {k: A[n][k] for k in FMT[1:] + ("kernel_skipped_rounds", "kernel_ms_max")})
    r.measure("離線指標（C／D 是預錄回答，只驗協議，不代表 LLM 品質）", "\n" + table(A.values()))
    r.finding("離線版只驗協議：預錄的壞回答全被拒、保底接手、閘門帳 0 違規；D／A 的指標差來自預錄政策（我寫的），不能拿來判 LLM")
    return r.done()


# ---------------- 真模型 ----------------

def proxy_up():
    try:
        with urllib.request.urlopen(llmop.URL + "/models", timeout=5) as f:
            return [m["id"] for m in json.loads(f.read())["data"]]
    except (OSError, ValueError, KeyError):
        return None


def real(groups_spec, reps, cap, det=True, tag=""):
    """groups_spec＝[(組, 模型)]，例如 [("D","deepseek-chat"),("C","deepseek-chat")]；det＝同批也跑 A／Adon／Atuned／B。
    呼叫上限跨多次執行累計：runs/calls.json 記已用的，加上這次預留的不超過 cap。"""
    ids = proxy_up()
    if ids is None:
        print("LiteLLM 代理 127.0.0.1:4000 不在：跳過真模型")
        return 0
    for _, m in groups_spec:
        llmop.check_model(m)
        if m not in ids:
            raise SystemExit("代理上沒有 %s" % m)
    out_dir = os.path.join(HERE, "runs")
    os.makedirs(out_dir, exist_ok=True)
    ledger_p = os.path.join(out_dir, "calls.json")
    led = fs.read_json(ledger_p, {"used": 0, "tokens": 0, "log": []}) or {"used": 0, "tokens": 0, "log": []}
    left = cap - led["used"]
    per_call = {"C": 50, "D": 12}
    rows = []
    for rep in range(1, reps + 1):
        groups = [("A", None), ("Adon", None), ("Atuned", None), ("B", None)] if det else []
        plan = []
        for g, m in groups + list(groups_spec):
            if m is None:
                plan.append((g, m, 0))
            elif left >= per_call[g]:
                left -= per_call[g]
                plan.append((g, m, per_call[g]))
            else:
                print("rep %d：%s/%s 跳過（呼叫上限剩 %d）" % (rep, g, m, left))
        res = {}

        def go(g, m, mc):
            agent = {"mode": "real", "model": m, "max_calls": mc} if m else None
            try:
                res[(g, m)] = run_one(g, agent=agent, interval_ms=1000, wall_cap=112)
            except Exception as e:  # noqa: BLE001
                res[(g, m)] = ({"strategy": g, "error": repr(e)}, {})
        ths = [threading.Thread(target=go, args=x) for x in plan]
        for t in ths:
            t.start()
        for t in ths:
            t.join()
        for g, m, mc in plan:
            a, raw = res[(g, m)]
            used = a.get("sched_calls", 0) or 0
            left += mc - used                      # 沒用完的還回去
            led["used"] += used
            led["tokens"] += a.get("sched_tokens", 0) or 0
            if m:
                led["log"].append({"tag": tag, "rep": rep, "group": g, "model": m, "calls": used,
                                   "tokens": a.get("sched_tokens", 0)})
            a.update(rep=rep, model=m or "-", wall_s=(raw.get("info") or {}).get("wall_s"))
            rows.append(a)
            keep = {"metrics": a,
                    "validation": raw.get("validation"),
                    "answers": {k: {"meta": v["meta"], "raw": (v["raw"] or "")[:1500]} for k, v in
                                (raw.get("answers") or {}).items()},
                    "decision_srcs": [[x["round"], x.get("src"), x.get("takeover")] for x in raw.get("decisions", [])
                                      if x.get("takeover") or (x.get("src") or "").startswith(("pick", "policy"))]}
            with open(os.path.join(out_dir, "%srep%d-%s-%s.json" % (tag, rep, g, (m or "det").replace(".", "_"))),
                      "w", encoding="utf-8") as f:
                json.dump(keep, f, ensure_ascii=False, separators=(",", ":"))
        fs.write_json(ledger_p, led)
        print("rep %d 完：累計呼叫 %d" % (rep, led["used"]), flush=True)
    sp = os.path.join(out_dir, "summary.json")
    summ = fs.read_json(sp, {"rows": []}) or {"rows": []}
    summ["rows"] += [dict({k: x.get(k) for k in ("rep", "model", "wall_s") + FMT + ("violation_list", "last_round",
                                                                                     "error")}, tag=tag) for x in rows]
    summ["calls_used"], summ["tokens_used"], summ["cap"] = led["used"], led["tokens"], cap
    fs.write_json(sp, summ)
    print(table(rows))
    print("真模型呼叫累計 %d（上限 %d）" % (led["used"], cap))
    return 0


def main():
    argv = sys.argv[1:]
    if "--real" in argv:
        val = lambda k, d: argv[argv.index(k) + 1] if k in argv else d  # noqa: E731
        models = val("--real", "").split(",")
        groups = [tuple(x.split(":", 1)) for x in val("--groups", "").split(",") if x] or \
            [(g, m) for m in models for g in ("D", "C")]
        return real(groups, int(val("--reps", "3")), min(int(val("--cap", "300")), 300),
                    det="--no-det" not in argv, tag=val("--tag", ""))
    return offline()


if __name__ == "__main__":
    pl.run_main(main)
