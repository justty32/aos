#!/usr/bin/env python3
# verify - 訓練迴圈的「比較前後」格（round3 § 8.5；round4 § 2.3、§ 4、§ 5.4、§ 7.1）：set.json 的驗證題各一題照「當下的」data/route.json 跑根（不強制寫手），
# 小格 $AOS_STACK/epochs/NNN/verify/<題名>/{ws,stack}；再跑 measure 題（set.json 的 measure，hints_fixed）在 epochs/NNN/measure/<題名>/；已有 score.json 的跳過。
# 收窄守門：score.json 的 style 不是 set.json scope.style＝StateBad。
# 算分寫 epochs/NNN/verify.json、追加 verify.jsonl 一行：score_mean＝驗證題所有過護欄草稿的 total 平均；dims＝照 score.json 裡有的維度走（common.gather）；
# tags／cell_hits（同 gather）；by_question＝每題分開記；measure＝{question, writer, style, 一致, dims_std}；picked_total_sum、guard_hit、bigram_overlap、
# 用量、brain（common.brain：每題幾次腦、幾 token；節點＝根 rollup 的 brain.nodes 只留每題會被叫到的（common.called），其餘 excluded）。
# 先 rollup --up train/weigh（判斷器那棵在 epoch 0 就看得到）。
# 步驟 5（§ 5.4）：上一個 epoch 的 optimize（或 selfopt）留了 epochs/NNN/params/changed.json {source, action, subtree, target?, files, created, cells?}＝這一步只改了那棵：
#   before＝上一個 epoch 的 verify.json＋params 快照裡的 <子樹>/stage.json＋那棵在上一個 epoch 驗證小格的用量，after＝這次的（common.snapshot）；
#   diff＝common.diff(before, after)（數值差、[舊,新]、{+,-}；cells＝cell_hits 的 key 集合）；changed_cells＝changed.json 的 cells，沒給＝照 files 用 cells.touched 算；
#   叫判斷器 train/weigh（小格 epochs/NNN/weigh/，題目 {A: diff, B: {}, before, after, params: {min_gain, min_loss}, epoch, subtree, action}）→ 選 A＝留、選 B＝照 changed.json 回滾（common.rollback）；
#   不論結果都寫：<子樹>/grad.json 的 steps（同 epoch 覆蓋）＋sum／三個計數；extract 那步同一筆拷給 <子樹>/<target>/grad.json（assigned_from）；
#   stage 換到 program 那步按各工具在這次驗證小格被叫的次數分攤給 <子樹>/tools/*（assigned_share，和為 1；捷徑過來的工具不算——那是別棵的）；
#   optimize/ratings.json 的 action:<動作>；weigh/ratings.json 的 judge:accept；最後 rollup --up <子樹>（＋分到梯度的工具）。
#   沒有 changed.json 而有舊的 params/optimize.json（round3 的選路）＝舊規則：action:route、delta < 0 回滾 route.json。
# 每個 epoch 寫 set.json 寫手（＋被改的那棵，有 stage.json 的）stage.json.history 一筆（同 epoch 覆蓋）：stage、tools、那棵每次的 llm_tokens／llm_calls、determinism、val、total_avg。
# 寫完根 ratings.json → common.rollup_up(".")。stdout 一行：score、Δ、每題 token 與 on_brain（第 0 個 epoch → 現在）、判斷器選了什麼。
# 結束碼：判斷器選 B（回滾了）＝stderr「train: Regressed epoch N 回滾 <子樹>/<動作> <目標>（weigh: 理由）」、退 10（收工）；舊選路 delta < 0 同樣退 10；
# epoch ≥ max_epochs＝退 10；預算到頂（開跑前看一次）＝BudgetSpent 退 2；否則 epoch.txt＋1、退 0（往 train 走）。
# 錯：stderr 一行「train: 代號 原因」、退 1——StackMissing、StateBad、SetBad、RunFailed（根退非 0；現場在小格）、WeighFailed（判斷器退非 0 或沒答案）。
import json, os, re, subprocess, sys

sys.dont_write_bytecode = True                      # 不在樹裡留 __pycache__/
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as c  # noqa: E402

OPT = os.path.join(c.HERE, "optimize", "ratings.json")
WEIGH = os.path.join(c.HERE, "weigh")


def run(sub, q):
    base = q[:-5] if q.endswith(".json") else q
    cell = os.path.join(here, sub, base)
    rc, spath = c.run_question(cell, q)
    if rc != 0:
        c.die("RunFailed", "%s %s 結束碼 %d（現場在 %s）" % ("驗證題" if sub == "verify" else "measure 題", q, rc, cell))
    s = c.load(spath, "StateBad", "score.json ")
    c.scope_check(s, sets, "%s 的 score.json" % cell)
    return base, s


def rate_action(name, delta, accepted):
    """optimize/ratings.json 的 action:<名>（§ 5.2 第 6 點；§ 15：只有 verify 寫它）"""
    r = c.load(OPT, "StateBad", "optimize/ratings.json ")
    ar = r.get("action:" + name) or {}
    k = ar.get("counter_applied", 0) + 1
    d = delta if delta is not None else 0
    improved, regressed = d >= budget.get("min_gain", 0.25), d < 0
    sum_delta = round(ar.get("sum_delta", 0) + d, 3)
    tokens = ar.get("counter_tokens", 0) + c.usage_of(here)["counter_tokens"]
    ar = {"counter_applied": k,
          "counter_accepted": ar.get("counter_accepted", 0) + bool(accepted),
          "counter_rolled_back": ar.get("counter_rolled_back", 0) + (not accepted),
          "counter_improved": ar.get("counter_improved", 0) + improved,
          "counter_regressed": ar.get("counter_regressed", 0) + regressed,
          "counter_improved_streak": ar.get("counter_improved_streak", 0) + 1 if improved else 0,
          "sum_delta": sum_delta, "counter_tokens": tokens}
    ar["delta_avg"] = round(sum_delta / k, 3)
    ar["val"] = "good" if ar["delta_avg"] >= budget.get("min_gain", 0.25) else "ok" if ar["delta_avg"] >= 0 else "bad"
    ar["dims"] = {"命中": round(ar["counter_improved"] / k, 3), "穩定": round(1 - ar["counter_regressed"] / k, 3),
                  "收下": round(ar["counter_accepted"] / k, 3),
                  "效率": round(min(1.0, max(0.0, sum_delta / max(tokens / 100000, 1))), 3)}
    ar["rated_at"] = c.now()
    ar["rated_by"] = "train/verify.py epoch %d @ %s" % (n, st)
    r["action:" + name] = ar
    c.save(OPT, r)


def ask_weigh(q):
    """判斷器小格 epochs/NNN/weigh/{ws,stack}；已有答案（被殺重跑）就讀舊的；回 (choice, reason, by)"""
    cell = os.path.join(here, "weigh")
    ws, sk = os.path.join(cell, "ws"), os.path.join(cell, "stack")
    out = os.path.join(ws, "out", "step.json")
    if not os.path.isfile(out):
        if not os.path.isdir(ws):
            os.makedirs(os.path.join(ws, "new"))
            os.makedirs(sk, exist_ok=True)
            c.save(os.path.join(ws, "new", "step.json"), q)
        env = dict(os.environ, AOS_STACK=sk + "/")
        try:
            r = subprocess.run(["aos-exec", "--dotenv-override", "--ws", ws, WEIGH], env=env, stdout=sys.stderr)
        except OSError as e:
            c.die("WeighFailed", "aos-exec 起不來：%s" % e)
        if r.returncode != 0 or not os.path.isfile(out):
            c.die("WeighFailed", "train/weigh 結束碼 %d（現場在 %s）" % (r.returncode, cell))
    with open(out, encoding="utf-8") as f:
        text = f.read()
    m, why = re.search(r"選[:：]\s*([AB])", text), re.search(r"理由[:：]\s*(.+)", text)
    if not m:
        c.die("WeighFailed", "判斷器的答案沒有「選：A|B」（%s）" % out)
    wst = (c.load_or(os.path.join(WEIGH, "stage.json"), {}) or {}).get("stage")
    return m.group(1), why.group(1).strip() if why else "", "train/weigh epoch %d（%s）" % (n, os.environ.get("GALTXT_WEIGH_STAGE") or wst)


def grad_sum(steps):
    out, cells = {}, 0
    for s in steps:
        if not s.get("accepted"):
            continue
        share = s.get("assigned_share", 1)
        for k, x in (s.get("diff") or {}).items():
            if c._num(x):
                out[k] = round(out.get(k, 0) + x * share, 3)
        cells += len(s.get("changed_cells") or [])
    out["cells_touched"] = cells
    return out


def write_grad(rel, step):
    p = os.path.join(c.ROOT, rel, "grad.json")
    g = c.load_or(p, {}) or {}
    scope = sets.get("scope") or {}
    g["scope"] = "%s×%s・%s" % (scope.get("style"), scope.get("place"), scope.get("event"))
    g["context"] = {"tree": os.path.basename(c.ROOT), "verify": sets["verify"], "S": "data/dims.json %s" % scope.get("style")}
    steps = [s for s in g.get("steps") or [] if s.get("epoch") != step["epoch"]] + [step]
    g["steps"] = steps
    g["sum"] = grad_sum(steps)
    g["counter_steps"] = len(steps)
    g["counter_accepted"] = sum(1 for s in steps if s.get("accepted"))
    g["counter_rolled_back"] = len(steps) - g["counter_accepted"]
    c.save(p, g)


def own_tool(sub, name):
    d = os.path.join(c.ROOT, sub, "tools", name)
    return os.path.isdir(d) and not os.path.islink(d)


def tool_calls(cells, sub, name):
    """這次驗證小格裡 <子樹> 每次跑叫了 <工具> 幾次：有 history.jsonl＝數 tool_calls 的名字；沒有（program 階）＝那次有 stack/<工具>/ 算 1"""
    k = 0
    for cell in cells:
        runs = os.path.join(cell, "stack", sub, "runs")
        for r in sorted(os.listdir(runs)) if os.path.isdir(runs) else []:
            h = os.path.join(runs, r, "stack", "history.jsonl")
            if os.path.isfile(h):
                with open(h, encoding="utf-8") as f:
                    for line in f:
                        try:
                            m = json.loads(line)
                        except ValueError:
                            continue
                        k += sum(1 for t in m.get("tool_calls") or [] if (t.get("function") or {}).get("name") == name)
            elif os.path.isdir(os.path.join(runs, r, "stack", name)):
                k += 1
    return k


def node_cost(cells, sub):
    return c.run_cost(cells, sub) if sub != "." and "/" not in sub else None


def step_of(change, prev):
    """§ 5.4：這一步的 before／after／diff → 判斷器 → 留或回滾 → 梯度與歸因；回寫進 verify.json 的 step"""
    sub, action, target = change["subtree"], change["action"], change.get("target")
    params = os.path.join(here, "params")
    sd = os.path.normpath(os.path.join(c.ROOT, sub))
    stage_rel = os.path.normpath(os.path.join(sub, "stage.json"))
    stage_now = c.load_or(os.path.join(sd, "stage.json"), None)
    stage_before = c.load_or(os.path.join(params, stage_rel), None) or stage_now
    before = c.snapshot(prev, stage_before, node_cost(c.epoch_cells(c.edir(st, n - 1)), sub))
    after = c.snapshot(v, stage_now, node_cost(c.epoch_cells(here), sub))
    d = c.diff(before, after)
    cc = change.get("cells")
    if not isinstance(cc, list):
        cc = sorted({i for rel in change.get("files") or []
                     for i in c.cells_touched(rel, os.path.join(params, rel) if os.path.isfile(os.path.join(params, rel)) else None,
                                              os.path.join(c.ROOT, rel))})
    q = {"A": d, "B": {}, "before": before, "after": after,
         "params": {"min_gain": budget.get("min_gain", 0.25), "min_loss": budget.get("min_loss", 0.25)},
         "epoch": n, "subtree": sub, "action": action, "target": target}
    choice, reason, by = ask_weigh(q)
    accepted = choice == "A"
    rolled = c.rollback(params, change) if not accepted else []
    step = {"epoch": n, "source": change.get("source"), "action": action, "target": target,
            "before": before, "after": after, "diff": d, "changed_cells": cc,
            "weigh": {"choice": choice, "reason": reason, "by": by}, "accepted": accepted,
            "confidence": "low" if abs(d.get("total_avg") or 0) < 0.3 else "ok", "measured_at": c.now()}
    if rolled:
        step["rolled_back"] = rolled
    write_grad(sub, step)
    tools = []                                                   # 梯度分配給工具（§ 4.3）
    if action == "extract" and isinstance(target, str) and target.startswith("tools/") and own_tool(sub, target[6:]):
        tools = [(target, 1)]
    elif action == "stage" and (stage_now or {}).get("stage") == "program":
        names = [t for t in (stage_now or {}).get("tools") or [] if own_tool(sub, t)]
        counts = {t: tool_calls(c.epoch_cells(here), sub, t) for t in names}
        total = sum(counts.values())
        shares = {t: (counts[t] / total if total else 1 / len(names)) for t in names}
        for i, t in enumerate(names):
            share = round(shares[t], 3) if i < len(names) - 1 else round(1 - sum(round(shares[x], 3) for x in names[:-1]), 3)
            tools.append(("tools/" + t, share))
    for rel, share in tools:
        tstep = {k: step[k] for k in ("epoch", "action", "target", "diff", "changed_cells", "weigh", "accepted")}
        tstep.update({"assigned_from": sub, "step_epoch": n, "assigned_share": share})
        write_grad(os.path.join(sub, rel), tstep)
    rate_action(action, v.get("delta"), accepted)
    wr = c.load_or(os.path.join(WEIGH, "ratings.json"), {}) or {}
    ja = wr.get("judge:accept") or {}
    contradicted = bool((prev or {}).get("step", {}).get("accepted")) and (v.get("delta") or 0) < 0
    ja = dict(ja, counter_judged=ja.get("counter_judged", 0) + 1,
              counter_chose_a=ja.get("counter_chose_a", 0) + (choice == "A"),
              counter_chose_b=ja.get("counter_chose_b", 0) + (choice == "B"),
              counter_contradicted=ja.get("counter_contradicted", 0) + contradicted,
              rated_at=c.now(), rated_by="train/verify.py epoch %d @ %s" % (n, st))
    wr["judge:accept"] = ja
    c.save(os.path.join(WEIGH, "ratings.json"), wr)
    return {"subtree": sub, "action": action, "target": target, "choice": choice, "reason": reason, "accepted": accepted,
            "tools": [t for t, _ in tools]}


def history(sub, step):
    """<子樹>/stage.json.history 這個 epoch 一筆（同 epoch 覆蓋）；回滾後寫在拷回來的那份上（記的是這次實際跑的 stage）"""
    p = os.path.join(c.ROOT, sub, "stage.json")
    s = c.load_or(p, None)
    if not isinstance(s, dict):
        return
    ran = (step or {}).get("ran_stage", {}).get(sub) or s
    cost = node_cost(c.epoch_cells(here), sub) or {}
    e = {"epoch": n, "stage": ran.get("stage"), "tools": ran.get("tools"),
         "llm_tokens": cost.get("llm_tokens"), "llm_calls": cost.get("llm_calls"),
         "determinism": (v.get("measure") or {}).get("一致"), "val": c.val_of(v["score_mean"], v["counter_samples"]),
         "total_avg": v["score_mean"]}
    if step and step.get("subtree") == sub:
        e.update({"action": step["action"], "accepted": step["accepted"]})
    s["history"] = [h for h in s.get("history") or [] if h.get("epoch") != n] + [e]
    c.save(p, s)


st = c.stack()
sets, budget = c.settings()
n = c.epoch(st)
here = c.edir(st, n)
vpath = os.path.join(here, "verify.json")
c.mark_started(st)

if not os.path.exists(vpath):
    c.check_budget(st, budget)
    route = c.load(os.path.join(c.ROOT, "data", "route.json"), "StateBad", "data/route.json ")
    got, picked, guard, overlap, by, per_q = [], 0, 0, [], {}, {}
    for q in sets["verify"]:
        base, s = run("verify", q)
        got.append(s)
        by[base] = s.get("writer")
        g1 = c.gather([s])
        p = next((d["total"] for d in s["drafts"] if d["n"] == s["picked"]), 0)
        picked += p
        per_q[base] = {"score_mean": c.mean(g1["totals"]), "dims": g1["dims"], "picked_total": p}
        if s.get("bench"):
            guard += 1 if s["bench"].get("guard_hit") else 0
            overlap.append(s["bench"].get("bigram_overlap"))
            per_q[base]["bench"] = s["bench"]
    g = c.gather(got)
    m = None
    if sets.get("measure"):
        mbase, ms = run("measure", sets["measure"])
        names = sorted({k for d in ms["drafts"] for k in d["dims"]})
        m = {"question": mbase, "writer": ms.get("writer"), "style": ms.get("style"), "一致": (ms.get("dims") or {}).get("一致"),
             "dims_std": {k: (round(sd, 3) if sd is not None else None)
                          for k in names for sd in [c.std([d["dims"].get(k) for d in ms["drafts"]])]}}
    usage = c.usage_of(here)
    questions = len(sets["verify"]) + (1 if m else 0)
    if os.path.isfile(os.path.join(WEIGH, "_metainfo")):
        c.rollup_up(os.path.relpath(WEIGH, c.ROOT))              # 判斷器那棵（train/weigh → train → 根），epoch 0 就攤平得到
    change = c.load_or(os.path.join(here, "params", "changed.json"), None) if n > 0 else None
    if isinstance(change, dict) and isinstance(change.get("subtree"), str) and os.path.isfile(os.path.join(c.ROOT, change["subtree"], "_metainfo")):
        c.rollup_up(change["subtree"])                           # 被改那棵的新階先彙上去，brain.nodes 才是這次實際跑的
    v = {"epoch": n, "score_mean": c.mean(g["totals"]), "counter_samples": len(g["totals"]), "dims": g["dims"],
         "tags": g["tags"], "cell_hits": g["cell_hits"],
         "by_question": per_q, "measure": m,
         "picked_total_sum": picked, "guard_hit": guard, "bigram_overlap": c.mean(overlap),
         "writers": by, "route_by_style": route.get("by_style", {}),
         "usage": usage, "brain": c.brain(usage, questions, sets), "verified_at": c.now()}
    prev = c.load_or(os.path.join(c.edir(st, n - 1), "verify.json"), None) if n > 0 else None
    if prev is not None and prev.get("score_mean") is not None and v["score_mean"] is not None:
        v["delta"] = round(v["score_mean"] - prev["score_mean"], 3)
    if isinstance(change, dict):
        ran = c.load_or(os.path.join(c.ROOT, change["subtree"], "stage.json"), None)   # 這次實際跑的階（回滾前）
        v["step"] = step_of(change, prev)
        if isinstance(ran, dict):
            v["step"]["ran_stage"] = {change["subtree"]: {"stage": ran.get("stage"), "tools": ran.get("tools")}}
    elif v.get("delta") is not None and c.load_or(os.path.join(here, "params", "optimize.json"), {}).get("changed"):
        rate_action("route", v["delta"], v["delta"] >= 0)       # round3 的選路（沒改＝平手留原值不算一次，§ 15.3 壞法 a）
        v["optimize_rated"] = True
    for w in sorted(set(sets["writers"]) | ({v["step"]["subtree"]} if v.get("step") else set())):
        history(w, v.get("step"))
    if v.get("step"):
        for sub in [v["step"]["subtree"]] + [os.path.join(v["step"]["subtree"], t) for t in v["step"]["tools"]]:
            c.rollup_up(sub)
    c.save(vpath, v)
    # 根的評級（整棵樹對外的那格）
    style = (sets.get("scope") or {}).get("style") or (got[0].get("style") if got else None)
    rp = os.path.join(c.ROOT, "ratings.json")
    root = c.load(rp, "StateBad", "根的 ratings.json ")
    root["scope"] = sets.get("scope")
    k = len(g["totals"])
    root["style:%s" % style] = {"val": c.val_of(v["score_mean"], k), "score_avg": v["score_mean"], "score_min": min(g["totals"]) if k else None,
                                "counter_samples": k, "dims": g["dims"], "determinism": (m or {}).get("一致"),
                                "cost": {"llm_calls": v["brain"]["llm_calls_per_question"], "llm_tokens": v["brain"]["llm_tokens_per_question"]},
                                "brain": v["brain"], "rated_at": c.now(), "rated_by": "train/verify.py epoch %d @ %s" % (n, st)}
    c.save(rp, root)
    c.rollup_up(".")
    with open(os.path.join(st, "verify.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({k: v.get(k) for k in ("epoch", "score_mean", "delta", "dims", "verified_at")}, ensure_ascii=False) + "\n")
    first = c.load_or(os.path.join(c.edir(st, 0), "verify.json"), {}).get("brain") or v["brain"]
    s5 = v.get("step")
    print("train: epoch %d verify score_mean %s%s tokens/題 %s → %s on_brain %s → %s determinism %s%s" % (
        n, v["score_mean"], " delta %+.3f" % v["delta"] if "delta" in v else "",
        first["llm_tokens_per_question"], v["brain"]["llm_tokens_per_question"],
        first["counter_on_brain"], v["brain"]["counter_on_brain"], (m or {}).get("一致"),
        " weigh %s（%s）%s/%s" % (s5["choice"], s5["reason"], s5["subtree"], s5["action"]) if s5 else ""))

v = c.load(vpath)
s5 = v.get("step")
if s5 and not s5.get("accepted"):
    print("train: Regressed epoch %d 回滾 %s/%s %s（weigh: %s）" % (
        n, s5["subtree"], s5["action"], os.path.basename(s5.get("target") or ""), s5.get("reason")), file=sys.stderr)
    sys.exit(10)
if not s5 and v.get("delta") is not None and v["delta"] < 0:
    before = os.path.join(here, "params", "route.json")
    if os.path.isfile(before):
        c.copy(before, os.path.join(c.ROOT, "data", "route.json"))
    print("train: Regressed epoch %d 回滾到 %d（delta %+.3f）" % (n, n - 1, v["delta"]), file=sys.stderr)
    sys.exit(10)
if n >= budget.get("max_epochs", 2):
    sys.exit(10)
tmp = os.path.join(st, ".epoch.txt")
with open(tmp, "w", encoding="utf-8") as f:
    f.write("%d\n" % (n + 1))
os.replace(tmp, os.path.join(st, "epoch.txt"))
