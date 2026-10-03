"""hsched 的控制 kernel（keep 任務，node `ctl`）：確定性根 kernel＋驗證器＋執行層，每個控制回合（ctl 的 tock）跑一次。

被測策略在 `ctl/cfg.json` 的 `strategy`：
  A     確定性 stride 啟發（sim.pick_jobs，預設政策）
  Adon  A 加依賴捐贈（對照用：確定性規則自己就能拿到的那一份）
  Atuned A 從頭到尾固定用 cfg 的 `tuned` 政策（對照用：人手調好一次的靜態規則，不花 LLM）
  B     固定 8 回合發放窗口（sim.frame_pick）
  C     LLM 直接挑下一份有界工作：有空位就發挑選請求、空位留著等；PICK_WAIT 回合內收到合格的就派，
        否則（壞、晚、越權、舊 epoch、要 pause 自己、沒回）在那一回合由 A 保底派
  D     LLM 每 20 個控制回合或重大事件提出一段期間的政策（報告 §10 格式）；kernel 每回合照**目前有效**的政策
        確定性執行，從不等 LLM；提案不合格就沿用有效政策或預設 A
kernel 從不 pause 任何 node（控制線不在被測策略的 pause 範圍；提案要 pause ctl 一律拒絕）。

掛載：P → P/work、Q → Q/work（派工與結果）、Pspawn → P/.aos/spawn（擴 worker）。自己 node 底下：
  pub/envelope.json、pub/tickets/<票>.json（閘門讀）、pub/provider.json（probe 寫，worker 讀）
  requests/<rev>.json → agent；answers/<rev>.txt＋.meta.json ← agent
  kernel/state.json（每回合持久化；重起接著做、epoch +1）、kernel/decisions.jsonl、kernel/validation.jsonl、
  kernel/final.json（跑完或收到 stop.json 時寫）
"""
import copy
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "lib"))
sys.path.insert(0, HERE)
import aos7_fs as fs  # noqa: E402
import sim  # noqa: E402

E = fs.task_env()
NODE = E["node"]
M = os.path.join(E["task"], "mnt")
KD = os.path.join(NODE, "kernel")
PUB = os.path.join(NODE, "pub")
RQ = os.path.join(NODE, "requests")
AN = os.path.join(NODE, "answers")
for d in (KD, os.path.join(PUB, "tickets"), RQ, AN):
    os.makedirs(d, exist_ok=True)
SP = os.path.join(KD, "state.json")
cfg = fs.read_json(os.path.join(NODE, "cfg.json"), {}) or {}
STRAT = cfg.get("strategy", "A")
END = cfg.get("end", sim.END)
trace = fs.read_json(os.path.join(NODE, "trace.json"))
JOBS = trace["jobs"]
JB = {j["id"]: j for j in JOBS}
MAJOR = {"urgent", "scale", "latency", "freeze"}

st = fs.read_json(SP)
restarted = isinstance(st, dict)
if not restarted:
    st = {"epoch_n": 0, "last_round": 0, "rev": 0, "jobs": {j["id"]: {"state": "queued", "tries": 0} for j in JOBS},
          "workers": {p: {} for p in sim.PROJECTS}, "sst": {}, "fst": {}, "pol": None, "pol_src": None,
          "pol_until": None, "pending": None, "answered": [], "applied": [], "frozen": [], "env_n": 1,
          "takeovers": 0, "restarts": 0}
st["epoch_n"] += 1
if restarted:
    st["restarts"] += 1
EPOCH = "c-%d" % st["epoch_n"]


def log(name, obj):
    fs.append_jsonl(os.path.join(KD, name), dict(obj, at=fs.now()))


def envelope():
    return {"envelope_id": "env-%d" % st["env_n"], "epoch": EPOCH, "global_max_inflight": sim.GLOBAL_CAP,
            "projects": {p: {"weight": sim.WEIGHTS[p], "tokens": sim.BUDGET[p], "max_inflight": sim.PROJECT_CAP,
                             "frozen": p in st["frozen"]} for p in sim.PROJECTS}}


def reconcile():
    """重起：已發的票是事實來源。狀態還寫著 queued、但票已發（上一代死在發票之後、存狀態之前）就照票認領。"""
    for f in os.listdir(os.path.join(PUB, "tickets")):
        tk = fs.read_json(os.path.join(PUB, "tickets", f))
        if not isinstance(tk, dict):
            continue
        s = st["jobs"].get(tk["job"])
        if s and s["state"] == "queued" and tk["tries"] >= s["tries"] and \
                not os.path.exists(os.path.join(M, tk["project"], tk["worker"], "results", tk["job"] + ".json")):
            s.update(state="dispatched", ticket=tk["ticket"], worker=tk["worker"], dispatch=tk["round"], src=tk["by"])
            st["workers"][tk["project"]][tk["worker"]] = tk["job"]
            log("decisions.jsonl", {"round": st["last_round"], "src": "reconcile", "dispatched": [tk["job"]]})


def collect(r):
    for p in sim.PROJECTS:
        base = os.path.join(M, p)
        try:
            names = sorted(os.listdir(base))
        except OSError:
            names = []
        for w in names:
            if w not in st["workers"][p] and os.path.exists(os.path.join(base, w, "alive.json")):
                st["workers"][p][w] = None
        for w, jid in st["workers"][p].items():
            if not jid:
                continue
            res = fs.read_json(os.path.join(base, w, "results", jid + ".json"))
            if not isinstance(res, dict):
                continue
            s = st["jobs"][jid]
            st["workers"][p][w] = None
            if res.get("ok"):
                s.update(state="done", start=res["start"], done=res["done"], seen=r)
            elif res.get("reason") == "budget":
                s.update(state="dropped", why=res.get("why"), seen=r)
            else:
                s.update(state="queued", tries=s["tries"] + 1, last_reject=res.get("why"))


def apply_events(r):
    fired = []
    for i, ev in enumerate(trace["events"]):
        if i in st["applied"] or ev["round"] > r:
            continue
        st["applied"].append(i)
        fired.append(ev)
        if ev["kind"] == "scale":
            have = len(st["workers"][ev["project"]])
            batch = [{"name": "w%d" % k, "mode": "keep", "argv": cfg["worker_argv"] + ["w%d" % k],
                      "mounts": cfg["worker_mounts"]} for k in range(have + 1, ev["workers"] + 1)]
            fs.write_json(os.path.join(M, ev["project"] + "spawn", "scale-%s.json" % EPOCH), {"batch": batch})
        elif ev["kind"] == "freeze":
            st["frozen"] = sorted(set(st["frozen"]) | {ev["project"]})
            st["env_n"] += 1
    for i in st["applied"]:
        ev = trace["events"][i]
        if ev["kind"] == "freeze" and r > ev["until"] and ev["project"] in st["frozen"]:
            st["frozen"].remove(ev["project"])
            st["env_n"] += 1
            fired.append({"round": r, "kind": "unfreeze", "project": ev["project"]})
    return fired


def capview(pol):
    inflight = {p: 0 for p in sim.PROJECTS}
    committed = {p: 0 for p in sim.PROJECTS}
    bg = 0
    for jid, s in st["jobs"].items():
        j = JB[jid]
        if s["state"] in ("dispatched", "done"):
            committed[j["project"]] += j["tokens"]
        if s["state"] == "dispatched":
            inflight[j["project"]] += 1
            if j["cls"] != "interactive":
                bg += 1
    held = set()
    if pol and st["pol_until"] and pol.get("pause"):
        held = set(pol["pause"])
    return {"inflight": inflight, "bg_inflight": bg,
            "free_workers": {p: sum(1 for v in st["workers"][p].values() if not v) for p in sim.PROJECTS},
            "budget": {p: sim.BUDGET[p] - committed[p] for p in sim.PROJECTS},
            "frozen": set(st["frozen"]), "held": held}


def active_policy():
    return dict(sim.DEFAULT_POLICY, **(st["pol"] or {}).get("choice", {})) if st["pol"] else dict(sim.DEFAULT_POLICY)


def dispatch(r, ids, src):
    for jid in ids:
        j = JB[jid]
        s = st["jobs"][jid]
        w = sorted((k for k, v in st["workers"][j["project"]].items() if not v), key=lambda x: int(x[1:]))[0]
        t = "t-%s-%s-%d" % (jid, EPOCH, s["tries"])
        fs.write_json(os.path.join(PUB, "tickets", t + ".json"),
                      {"ticket": t, "job": jid, "project": j["project"], "tokens": j["tokens"], "worker": w,
                       "round": r, "by": src, "epoch": EPOCH, "tries": s["tries"]})
        fs.write_json(os.path.join(M, j["project"], w, "assign", jid + ".json"),
                      {"job": jid, "ticket": t, "tokens": j["tokens"], "lat": j["lat"], "round": r})
        st["workers"][j["project"]][w] = jid
        s.update(state="dispatched", ticket=t, worker=w, src=src)
        s.setdefault("dispatch", r)
        s["last_dispatch"] = r


def waits_done(r, lo):
    out = {"interactive": [], "background": []}
    for jid, s in st["jobs"].items():
        j = JB[jid]
        if s["state"] == "done" and s.get("start", -1) >= lo:
            out["interactive" if j["cls"] == "interactive" else "background"].append(s["start"] - j["arrival"])
    return out


def policy_input(r, view, cap, fired):
    q = {}
    for p in sim.PROJECTS:
        mine = [j for j in view if j["project"] == p]
        blocked = [jid for jid, s in st["jobs"].items() if JB[jid]["project"] == p and s["state"] == "queued"
                   and JB[jid]["arrival"] <= r and JB[jid]["deps"] and
                   not all(st["jobs"][d]["state"] == "done" for d in JB[jid]["deps"])]
        q[p] = {"ready_interactive": sum(1 for j in mine if j["cls"] == "interactive"),
                "ready_background": sum(1 for j in mine if j["cls"] != "interactive"),
                "oldest_wait": max([j["waited"] for j in mine] or [0]),
                "blocked_by_deps": [{"job": b, "waits_on": JB[b]["deps"], "cls": JB[b]["cls"]} for b in blocked]}
    w = waits_done(r, r - 20)
    return {"queues": q, "inflight": cap["inflight"], "background_inflight": cap["bg_inflight"],
            "workers": {p: len(st["workers"][p]) for p in sim.PROJECTS}, "budget_left": cap["budget"],
            "frozen": sorted(cap["frozen"]),
            "last_20_rounds": {"interactive_waits": sorted(w["interactive"]), "background_waits": sorted(w["background"])},
            "events_so_far": [ev.get("note", ev["kind"]) for ev in
                              [trace["events"][i] for i in st["applied"]]],
            "events_this_round": [ev.get("note", ev["kind"]) for ev in fired],
            "current_policy": {"source": st["pol_src"] or "default", "until_round": st["pol_until"],
                               "choice": active_policy()}}


def new_request(r, kind, payload):
    st["rev"] += 1
    wait = sim.PICK_WAIT if kind == "pick" else sim.POLICY_WAIT
    req = {"revision": st["rev"], "kind": kind, "round": r, "respond_by": r + wait, "epoch": EPOCH,
           "envelope_id": "env-%d" % st["env_n"], "input": payload}
    fs.write_json(os.path.join(RQ, "%06d.json" % st["rev"]), req)
    st["pending"] = {k: req[k] for k in ("revision", "kind", "round", "respond_by", "epoch")}
    return req


def answers():
    """還沒處理過的回答（meta 先寫好的才算到了）。回 [(rev, raw, meta, req)]。"""
    out = []
    for f in sorted(os.listdir(AN)):
        if not f.endswith(".meta.json"):
            continue
        rev = int(f.split(".")[0])
        if rev in st["answered"]:
            continue
        meta = fs.read_json(os.path.join(AN, f), {}) or {}
        try:
            with open(os.path.join(AN, "%06d.txt" % rev), encoding="utf-8") as fh:
                raw = fh.read()
        except OSError:
            raw = ""
        req = fs.read_json(os.path.join(RQ, "%06d.json" % rev), {}) or {}
        out.append((rev, raw, meta, req))
    return out


def vlog(r, kind, rev, ok, reason, why, arrived, req, pid=None):
    log("validation.jsonl", {"round": r, "kind": kind, "revision": rev, "ok": ok, "reason": reason, "why": why,
                             "arrived": arrived, "respond_by": req.get("respond_by"), "asked": req.get("round"),
                             "id": pid})


def step(r):
    t0 = time.monotonic()
    collect(r)
    fired = apply_events(r)
    env = envelope()
    fs.write_json(os.path.join(PUB, "envelope.json"), env)
    fs.write_json(os.path.join(PUB, "clock.json"), {"round": r, "epoch": EPOCH})
    rec = {"round": r, "epoch": EPOCH, "dispatched": [], "src": None}
    if STRAT == "B":
        view = sim.ready_view(JOBS, st["jobs"], r, False)
        ids = sim.frame_pick(view, capview(None), st["fst"], r)
        dispatch(r, ids, "frame")
        rec.update(dispatched=ids, src="frame")
    elif STRAT in ("A", "Adon", "Atuned"):
        pol = dict(sim.DEFAULT_POLICY, dependency_donation=(STRAT == "Adon"))
        if STRAT == "Atuned":
            pol.update(cfg.get("tuned") or {})
        view = sim.ready_view(JOBS, st["jobs"], r, pol["dependency_donation"])
        ids = sim.pick_jobs(view, capview(None), pol, st["sst"])
        dispatch(r, ids, "stride")
        rec.update(dispatched=ids, src="stride")
    elif STRAT == "C":
        step_c(r, rec)
    elif STRAT == "D":
        step_d(r, rec, fired)
    rec["ms"] = round((time.monotonic() - t0) * 1000, 1)
    if fired:
        rec["events"] = [ev["kind"] for ev in fired]
    log("decisions.jsonl", rec)


def fallback(r, rec, why):
    view = sim.ready_view(JOBS, st["jobs"], r, False)
    ids = sim.pick_jobs(view, capview(None), sim.DEFAULT_POLICY, st["sst"])
    dispatch(r, ids, "fallback")
    rec["dispatched"] += ids
    rec.setdefault("takeover", []).append(why)
    st["takeovers"] += 1


def step_c(r, rec):
    rec["src"] = "pick"
    for rev, raw, meta, req in answers():
        st["answered"].append(rev)
        arrived = r                 # 以 kernel 看到的回合為準（不信回答自報）
        pend = st["pending"] and st["pending"]["revision"] == rev
        view = sim.ready_view(JOBS, st["jobs"], r, False)
        cap = capview(None)
        ok, reason, why, o = sim.validate_pick(raw, req, r, EPOCH, view, cap, arrived=arrived)
        if ok and not pend:
            ok, reason, why = False, "late", "這份請求已經由保底接手（期限第 %s 回合）" % req.get("respond_by")
        vlog(r, "pick", rev, ok, reason, why, arrived, req)
        if pend:
            st["pending"] = None
            if ok:
                dispatch(r, o["jobs"], "pick:%d" % rev)
                rec["dispatched"] += o["jobs"]
            else:
                fallback(r, rec, "rejected:%s:%d" % (reason, rev))
    p = st["pending"]
    if p and r > p["respond_by"]:
        vlog(r, "pick", p["revision"], False, "timeout", "期限內沒回", None, p)
        st["pending"] = None
        fallback(r, rec, "timeout:%d" % p["revision"])
    if not st["pending"]:
        view = sim.ready_view(JOBS, st["jobs"], r, False)
        cap = capview(None)
        if sim.pick_jobs(view, cap, sim.DEFAULT_POLICY, copy.deepcopy(st["sst"])):
            free = {p: min(sim.PROJECT_CAP - cap["inflight"][p], cap["free_workers"][p]) for p in sim.PROJECTS}
            new_request(r, "pick", {
                "free_slots": {"global": sim.GLOBAL_CAP - sum(cap["inflight"].values()), **free},
                "inflight": cap["inflight"], "budget_left": cap["budget"], "frozen": sorted(cap["frozen"]),
                "ready": [{k: j[k] for k in ("id", "project", "cls", "tokens", "waited")} for j in view[:25]],
                "ready_total": len(view)})
            rec["held"] = st["rev"]
    else:
        rec["held"] = st["pending"]["revision"]


def step_d(r, rec, fired):
    for rev, raw, meta, req in answers():
        st["answered"].append(rev)
        arrived = r
        pend = st["pending"] and st["pending"]["revision"] == rev
        ok, reason, why, o = sim.validate_proposal(raw, req, r, EPOCH, "env-%d" % st["env_n"], arrived=arrived)
        vlog(r, "policy", rev, ok, reason, why, arrived, req, pid=(o or {}).get("proposal_id"))
        if pend:
            st["pending"] = None
        if ok:
            st["pol"], st["pol_src"], st["pol_until"] = o, "policy:%d" % rev, o["validity"]["until_round"]
        elif not st["pol"]:
            rec.setdefault("takeover", []).append("rejected:%s:%d" % (reason, rev))
            st["takeovers"] += 1
    p = st["pending"]
    if p and r > p["respond_by"]:
        vlog(r, "policy", p["revision"], False, "timeout", "期限內沒回", None, p)
        st["pending"] = None
        if not st["pol"]:
            rec.setdefault("takeover", []).append("timeout:%d" % p["revision"])
            st["takeovers"] += 1
    if st["pol"] and r > st["pol_until"]:
        rec.setdefault("takeover", []).append("expired:%s" % st["pol_src"])
        st["takeovers"] += 1
        st["pol"], st["pol_src"], st["pol_until"] = None, None, None
    pol = active_policy()
    view = sim.ready_view(JOBS, st["jobs"], r, pol["dependency_donation"])
    cap = capview(st["pol"])
    major = [ev for ev in fired if ev["kind"] in MAJOR]
    if r == 1 or r % sim.POLICY_EVERY == 0 or major:
        if st["pending"]:
            rec["coalesced"] = st["pending"]["revision"]
        else:
            new_request(r, "policy", policy_input(r, view, cap, fired))
            rec["asked"] = st["rev"]
    ids = sim.pick_jobs(view, cap, pol, st["sst"])
    src = st["pol_src"] or "default"
    dispatch(r, ids, src)
    rec.update(dispatched=ids, src=src)


def finalize(r, why):
    fs.write_json(os.path.join(KD, "final.json"), {"round": r, "why": why, "epoch": EPOCH, "jobs": st["jobs"],
                                                   "takeovers": st["takeovers"], "restarts": st["restarts"],
                                                   "fst": st["fst"], "workers": st["workers"]})


if restarted:
    reconcile()
log("decisions.jsonl", {"round": st["last_round"], "src": "start", "epoch": EPOCH, "restarted": restarted,
                        "dispatched": []})
fs.write_json(SP, st)
TOCK = os.path.join(E["task"], "tock.json")
done = os.path.exists(os.path.join(KD, "final.json"))
while True:
    t = fs.read_json(TOCK, {}) or {}
    r = t.get("round", 0)
    if not done and r > st["last_round"]:
        if r > st["last_round"] + 1 and st["last_round"]:
            log("decisions.jsonl", {"round": r, "src": "skip", "skipped": list(range(st["last_round"] + 1, r)),
                                    "dispatched": []})
        st["last_round"] = r
        step(r)
        fs.write_json(SP, st)
        stop = os.path.exists(os.path.join(NODE, "stop.json"))
        if r >= END or stop:
            finalize(r, "stop" if stop and r < END else "end")
            done = True
    time.sleep(0.003)
