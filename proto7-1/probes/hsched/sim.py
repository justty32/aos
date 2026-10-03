"""hsched 共用的純函式：trace、確定性派工規則（A／B／D 的執行層、C 的保底）、提案／挑選驗證器。

kernel.py、agent.py、probe.py 都 import 這份；不碰檔案、不碰時間，同樣輸入同樣輸出（可重播）。
時間單位一律是**控制回合**（node ctl 的回合數）。
"""
import json
import math

END = 100                 # trace 跑到第幾個控制回合
GLOBAL_CAP = 4            # 根：全域同時在途呼叫
PROJECT_CAP = 3           # 根給每專案的 envelope：同時在途上限
WEIGHTS = {"P": 1, "Q": 1}
BUDGET = {"P": 45000, "Q": 40000}
DEADLINE = {"interactive": 8, "retrieval": 30, "background": 60}
TICKET_TTL = 3            # 派工票幾回合內沒被 grant 就作廢（不追發過期 grant）
FRAME = 8                 # B：固定發放窗口長度
FRAME_QUOTA = 6           # B：每專案每窗口可開工幾件
FRAME_DELAY = {49: 3}     # B：這個窗口故意晚 3 回合才發（記 miss，不補發）
PICK_WAIT = 2             # C：挑選要在 2 回合內回來
POLICY_WAIT = 8           # D：政策提案要在 8 回合內回來
POLICY_EVERY = 20         # D：每 20 個控制回合問一次
MAX_VALID = 40            # D：一份政策最多管 40 回合
PROJECTS = ("P", "Q")
CTL = "ctl"

DEFAULT_POLICY = {"group_policy": "stride_inspired", "interactive_max_wait_rounds": None,
                  "dependency_donation": False, "max_calls_inflight": PROJECT_CAP,
                  "background_max_inflight": GLOBAL_CAP}
CHOICE_RANGE = {"group_policy": ("stride_inspired", "interactive_first"),
                "interactive_max_wait_rounds": (1, 20), "max_calls_inflight": (1, PROJECT_CAP),
                "background_max_inflight": (1, GLOBAL_CAP)}


def build_trace():
    """同一份可重播 trace。回 {"jobs": [...], "events": [...], "provider": {...}}。"""
    jobs = []

    def add(jid, p, cls, tokens, lat, arrival, deps=()):
        jobs.append({"id": jid, "project": p, "cls": cls, "tokens": tokens, "lat": lat, "arrival": arrival,
                     "deps": list(deps), "deadline": DEADLINE[cls]})

    for i in range(6):                                   # 昂貴背景：一開始就堆
        add("P-bg-%02d" % i, "P", "background", 2500, 8, 1)
    for i in range(4):
        add("Q-bg-%02d" % i, "Q", "background", 3000, 8, 1)
    for i in range(3):                                   # 檢索 B 前面先塞三件背景
        add("Q-bg-%02d" % (4 + i), "Q", "background", 3000, 8, 26)
    add("Q-retr-B", "Q", "retrieval", 600, 2, 28)        # 低優先檢索 B
    add("Q-urgent-A", "Q", "interactive", 300, 1, 30, deps=["Q-retr-B"])   # 急件 A 等 B
    for i in range(10):                                  # P 擴成 10 個 worker 同時湧進的背景
        add("P-fan-%02d" % i, "P", "background", 2000, 6, 40)
    for i in range(4):
        add("Q-bg-%02d" % (7 + i), "Q", "background", 3000, 8, 60)
    for k, r in enumerate(range(3, 96, 5)):              # 便宜互動
        add("P-int-%02d" % k, "P", "interactive", 200, 1, r)
    for k, r in enumerate(range(2, 99, 4)):
        add("Q-int-%02d" % k, "Q", "interactive", 150, 1, r)
    events = [
        {"round": 30, "kind": "urgent", "job": "Q-urgent-A", "note": "急件 Q-urgent-A 到了，它等 Q-retr-B"},
        {"round": 40, "kind": "scale", "project": "P", "workers": 10, "note": "P 的 worker 從 3 增為 10"},
        {"round": 50, "kind": "latency", "factor": 3, "until": 69, "note": "外部延遲變 3 倍（50～69 回合開工的）"},
        {"round": 82, "kind": "freeze", "project": "P", "until": 86, "note": "根禁止 P 發新 grant（82～86）"},
    ]
    jobs.sort(key=lambda j: (j["arrival"], j["id"]))
    return {"jobs": jobs, "events": events,
            "provider": {"spikes": [{"from": 50, "to": 69, "factor": 3}]}}


def latency(job_lat, start_round, provider):
    f = 1
    for s in provider.get("spikes", []):
        if s["from"] <= start_round <= s["to"]:
            f = s["factor"]
    return job_lat * f


# ---------------- 執行層：一回合派哪些工作 ----------------

def ready_view(jobs, st, r, donation):
    """可派的工作清單（已到、依賴都完成、還沒派）。donation：被擋的互動工作把自己的等級與等待借給擋它的依賴。
    回 [{"id","project","cls"（有效）,"tokens","arrival","waited","donated_from"?}]，已排序（互動先、再到達先）。"""
    out = {}
    for j in jobs:
        s = st[j["id"]]
        if j["arrival"] > r or s["state"] != "queued":
            continue
        if all(st[d]["state"] == "done" for d in j["deps"]):
            out[j["id"]] = {"id": j["id"], "project": j["project"], "cls": j["cls"], "tokens": j["tokens"],
                            "arrival": j["arrival"], "waited": r - j["arrival"]}
    if donation:
        for j in jobs:
            s = st[j["id"]]
            if j["arrival"] > r or s["state"] != "queued" or j["cls"] != "interactive" or j["id"] in out:
                continue
            for d in j["deps"]:
                if d in out:
                    out[d] = dict(out[d], cls="interactive", waited=max(out[d]["waited"], r - j["arrival"]),
                                  donated_from=j["id"])
    rank = {"interactive": 0, "retrieval": 1, "background": 1}
    return sorted(out.values(), key=lambda x: (rank[x["cls"]], x["arrival"], x["id"]))


def pick_jobs(ready, cap, pol, sst):
    """確定性派工（stride 啟發）。cap＝{"inflight":{p:n},"bg_inflight":n,"free_workers":{p:n},"budget":{p:n},
    "frozen":set,"held":set}；pol＝政策參數；sst＝stride 狀態 {"pass":{p:float}}（就地更新）。回派出的 id 清單。"""
    inflight = dict(cap["inflight"])
    bg = cap["bg_inflight"]
    fw = dict(cap["free_workers"])
    budget = dict(cap["budget"])
    blocked = set(cap.get("frozen", ())) | set(cap.get("held", ()))
    pcap = min(PROJECT_CAP, pol.get("max_calls_inflight") or PROJECT_CAP)
    bgcap = min(GLOBAL_CAP, pol.get("background_max_inflight") or GLOBAL_CAP)
    W = pol.get("interactive_max_wait_rounds")
    left = list(ready)
    out = []
    passes = sst.setdefault("pass", {p: 0.0 for p in PROJECTS})
    while sum(inflight.values()) < GLOBAL_CAP:
        cands = {}
        for j in left:
            p = j["project"]
            if p in cands or p in blocked or inflight[p] >= pcap or fw[p] <= 0 or budget[p] < j["tokens"]:
                continue
            if j["cls"] != "interactive" and bg >= bgcap:
                continue
            cands[p] = j
        if not cands:
            break
        active = [passes[p] for p in cands]
        lo = min(active)
        for p in cands:                      # 閒置後回來的專案不能拿舊的低 pass 一口氣補回
            passes[p] = max(passes[p], lo - 3000)
        pick = None
        if W is not None:
            urgent = [j for j in cands.values() if j["cls"] == "interactive" and j["waited"] >= W]
            if urgent:
                pick = min(urgent, key=lambda j: (-j["waited"], j["arrival"], j["id"]))
        if pick is None and pol.get("group_policy") == "interactive_first":
            inter = [j for j in cands.values() if j["cls"] == "interactive"]
            if inter:
                pick = min(inter, key=lambda j: (j["arrival"], j["id"]))
        if pick is None:
            p = min(cands, key=lambda p: (passes[p], p))
            pick = cands[p]
        p = pick["project"]
        passes[p] += pick["tokens"] / WEIGHTS[p]
        inflight[p] += 1
        fw[p] -= 1
        budget[p] -= pick["tokens"]
        if pick["cls"] != "interactive":
            bg += 1
        out.append(pick["id"])
        left = [j for j in left if j["id"] != pick["id"]]
    return out


def frame_pick(ready, cap, fst, r):
    """B：固定 8 回合發放窗口。fst＝{"frame_start","left":{p:n},"miss":[...]}（就地更新）。窗口一開就給每專案
    FRAME_QUOTA 件；用不完的到期作廢（記 miss），不補發；FRAME_DELAY 的窗口晚幾回合才發。"""
    start = ((r - 1) // FRAME) * FRAME + 1
    if fst.get("frame_start") != start:
        if fst.get("frame_start") is not None:
            fst.setdefault("miss", []).append({"frame": fst["frame_start"], "unused": dict(fst["left"])})
        fst["frame_start"] = start
        fst["left"] = {p: 0 for p in PROJECTS}
        fst["issued"] = False
    if not fst["issued"] and r >= start + FRAME_DELAY.get(start, 0):
        fst["left"] = {p: FRAME_QUOTA for p in PROJECTS}
        fst["issued"] = True
        if FRAME_DELAY.get(start):
            fst.setdefault("late", []).append({"frame": start, "issued_at": r, "lost_rounds": r - start})
    inflight = dict(cap["inflight"])
    fw = dict(cap["free_workers"])
    budget = dict(cap["budget"])
    blocked = set(cap.get("frozen", ()))
    out = []
    turn = fst.get("turn", 0)
    while sum(inflight.values()) < GLOBAL_CAP:
        got = None
        for k in range(len(PROJECTS)):
            p = PROJECTS[(turn + k) % len(PROJECTS)]
            if p in blocked or fst["left"][p] <= 0 or inflight[p] >= PROJECT_CAP or fw[p] <= 0:
                continue
            for j in ready:
                if j["project"] == p and j["id"] not in out and budget[p] >= j["tokens"]:
                    got = j
                    break
            if got:
                turn = (turn + k + 1) % len(PROJECTS)
                break
        if not got:
            break
        p = got["project"]
        fst["left"][p] -= 1
        inflight[p] += 1
        fw[p] -= 1
        budget[p] -= got["tokens"]
        out.append(got["id"])
    fst["turn"] = turn
    return out


# ---------------- 驗證器：提案（D）與挑選（C） ----------------

def parse(raw):
    """LLM 常把 JSON 包在 ``` 裡：只剝這一層，其他照嚴格 JSON。"""
    t = (raw or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    try:
        o = json.loads(t)
    except ValueError:
        return None
    return o if isinstance(o, dict) else None


def _pause_check(o):
    pz = o.get("pause", [])
    if not isinstance(pz, list) or not all(isinstance(x, str) for x in pz):
        return "schema", "pause 要是字串陣列"
    if CTL in pz or "." in pz:
        return "pause_self", "要求 pause 控制 node 自己（%s）：控制線不在被測策略的 pause 範圍" % pz
    bad = [x for x in pz if x not in PROJECTS]
    if bad:
        return "out_of_scope", "pause 只能是 %s，不能是 %s" % (list(PROJECTS), bad)
    return None


def validate_proposal(raw, req, now, epoch, envelope_id, arrived=None):
    """D 的提案。req＝kernel 發出的請求（revision、respond_by、epoch）。回 (ok, reason, why, proposal)。"""
    arrived = now if arrived is None else arrived
    o = parse(raw)
    if o is None:
        return False, "bad_json", "不是 JSON 物件", None
    if o.get("schema") != "aos.agent-policy-proposal.v1" or not isinstance(o.get("choice"), dict) \
            or not isinstance(o.get("validity"), dict):
        return False, "schema", "schema／choice／validity 不合", o
    if o.get("input_revision") != req["revision"]:
        return False, "schema", "input_revision %r 不是這份請求的 %r" % (o.get("input_revision"), req["revision"]), o
    v = o["validity"]
    if v.get("epoch") != epoch or req.get("epoch") != epoch:
        return False, "stale_epoch", "epoch %r 不是現在的 %r" % (v.get("epoch"), epoch), o
    if arrived > req["respond_by"]:
        return False, "late", "第 %d 回合才到，期限是第 %d 回合" % (arrived, req["respond_by"]), o
    if o.get("envelope_id") != envelope_id:
        return False, "stale_envelope", "envelope %r 不是現在的 %r" % (o.get("envelope_id"), envelope_id), o
    if v.get("clock_node") != CTL:
        return False, "schema", "clock_node 要是 %r" % CTL, o
    u = v.get("until_round")
    if not isinstance(u, int) or isinstance(u, bool) or u <= now or u > now + MAX_VALID:
        return False, "out_of_range", "until_round %r 要在 (%d, %d]" % (u, now, now + MAX_VALID), o
    c = o["choice"]
    for k in c:
        if k not in DEFAULT_POLICY:
            return False, "schema", "不認得的 choice 欄位 %r" % k, o
    if "group_policy" in c and c["group_policy"] not in CHOICE_RANGE["group_policy"]:
        return False, "out_of_range", "group_policy %r" % c["group_policy"], o
    if "dependency_donation" in c and not isinstance(c["dependency_donation"], bool):
        return False, "schema", "dependency_donation 要是 bool", o
    for k in ("interactive_max_wait_rounds", "max_calls_inflight", "background_max_inflight"):
        if k in c and c[k] is not None:
            x = c[k]
            if not isinstance(x, int) or isinstance(x, bool) or x < 1:
                return False, "out_of_range", "%s=%r 要是正整數" % (k, x), o
            hi = CHOICE_RANGE[k][1]
            if x > hi:
                return False, "over_parent", "%s=%d 超過父 envelope 的 %d" % (k, x, hi), o
    pc = _pause_check(o)
    if pc:
        return False, pc[0], pc[1], o
    return True, "ok", "", o


def validate_pick(raw, req, now, epoch, ready, cap, arrived=None):
    """C 的挑選。ready＝現在可派的（ready_view 的結果）；cap 同 pick_jobs。回 (ok, reason, why, pick)。"""
    arrived = now if arrived is None else arrived
    o = parse(raw)
    if o is None:
        return False, "bad_json", "不是 JSON 物件", None
    if o.get("schema") != "aos.pick.v1" or not isinstance(o.get("jobs"), list):
        return False, "schema", "schema／jobs 不合", o
    if o.get("input_revision") != req["revision"]:
        return False, "schema", "input_revision %r 不是這份請求的 %r" % (o.get("input_revision"), req["revision"]), o
    if o.get("epoch") != epoch or req.get("epoch") != epoch:
        return False, "stale_epoch", "epoch %r 不是現在的 %r" % (o.get("epoch"), epoch), o
    if arrived > req["respond_by"]:
        return False, "late", "第 %d 回合才到，期限是第 %d 回合" % (arrived, req["respond_by"]), o
    pc = _pause_check(o)
    if pc:
        return False, pc[0], pc[1], o
    ids = o["jobs"]
    if not ids or len(set(ids)) != len(ids) or not all(isinstance(x, str) for x in ids):
        return False, "schema", "jobs 要是不重複、非空的 id 陣列", o
    rd = {j["id"]: j for j in ready}
    miss = [x for x in ids if x not in rd]
    if miss:
        return False, "not_ready", "%s 現在不可派" % miss, o
    inflight = dict(cap["inflight"])
    budget = dict(cap["budget"])
    fw = dict(cap["free_workers"])
    for x in ids:
        p = rd[x]["project"]
        inflight[p] += 1
        fw[p] -= 1
        budget[p] -= rd[x]["tokens"]
        if p in cap.get("frozen", ()):
            return False, "over_parent", "%s 被根凍結" % p, o
        if inflight[p] > PROJECT_CAP or sum(inflight.values()) > GLOBAL_CAP or fw[p] < 0 or budget[p] < 0:
            return False, "over_parent", "挑了 %d 件，超過父額（%s 在途 %d／%d、全域 %d／%d、剩額 %d）" % (
                len(ids), p, inflight[p], PROJECT_CAP, sum(inflight.values()), GLOBAL_CAP, budget[p]), o
    return True, "ok", "", o


def pctl(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    k = max(0, min(len(s) - 1, math.ceil(q / 100.0 * len(s)) - 1))   # nearest-rank
    return s[k]
