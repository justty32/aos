#!/usr/bin/env python3
# verify - 訓練迴圈的「比較前後」格（round3 § 8.5；round4 § 2.3、§ 4.2、§ 7.1）：set.json 的驗證題各一題照「當下的」data/route.json 跑根（不強制寫手），
# 小格 $AOS_STACK/epochs/NNN/verify/<題名>/{ws,stack}；再跑 measure 題（set.json 的 measure，hints_fixed）在 epochs/NNN/measure/<題名>/；已有 score.json 的跳過。
# 收窄守門：score.json 的 style 不是 set.json scope.style＝StateBad。
# 算分寫 epochs/NNN/verify.json、追加 verify.jsonl 一行：score_mean＝驗證題所有過護欄草稿的 total 平均；dims＝照 score.json 裡有的維度走（common.gather）；
# by_question＝每題分開記（score_mean、dims、picked_total、bench；判讀時 Q16 與 held-out 分列）；measure＝{question, writer, style, 一致, dims_std（三份各維度的標準差，只記）}；
# 另記 picked_total_sum、guard_hit、bigram_overlap、用量（驗證＋measure）、brain（common.brain：每題幾次腦、幾 token；每個節點在哪階＝根 rollup 的 brain.nodes）。
# 寫完根 ratings.json → common.rollup_up(".")（根的 rollup.json 重算）。
# 根 ratings.json 的 "style:<scope.style>" 整格覆蓋（val 門檻同 rate.py；determinism＝measure 的一致；cost＝每題平均）；檔頂層 scope。
# 跟上一個 epoch 比 score_mean：上一個 epoch 的 optimize 有改 route（epochs/NNN/params/optimize.json 的 changed）才記一筆給優化函數的評級
# （train/optimize/ratings.json 的 action:route，§ 15：只有這支寫它）。stdout 一行：score、Δ、每題 token 與 on_brain（第 0 個 epoch → 現在）。
# 結束碼：跌了（< 0）＝把 epochs/NNN/params/route.json（optimize 改之前那份）拷回 data/route.json、stderr「train: Regressed …」、退 10（收工）；
# epoch ≥ max_epochs＝退 10；預算到頂（開跑前看一次）＝BudgetSpent 退 2；否則 epoch.txt＋1、退 0（往 train 走）。
# 錯：stderr 一行「train: 代號 原因」、退 1——StackMissing、StateBad、SetBad、RunFailed（根退非 0；現場在小格）。
import json, os, sys

sys.dont_write_bytecode = True                      # 不在樹裡留 __pycache__/
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as c  # noqa: E402

OPT = os.path.join(c.HERE, "optimize", "ratings.json")


def val_of(avg, k):
    if k < 3:
        return "none"
    return "good" if avg >= 4.0 else "ok" if avg >= 3.0 else "bad"


def run(sub, q):
    base = q[:-5] if q.endswith(".json") else q
    cell = os.path.join(here, sub, base)
    rc, spath = c.run_question(cell, q)
    if rc != 0:
        c.die("RunFailed", "%s %s 結束碼 %d（現場在 %s）" % ("驗證題" if sub == "verify" else "measure 題", q, rc, cell))
    s = c.load(spath, "StateBad", "score.json ")
    c.scope_check(s, sets, "%s 的 score.json" % cell)
    return base, s


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
    v = {"epoch": n, "score_mean": c.mean(g["totals"]), "counter_samples": len(g["totals"]), "dims": g["dims"],
         "by_question": per_q, "measure": m,
         "picked_total_sum": picked, "guard_hit": guard, "bigram_overlap": c.mean(overlap),
         "writers": by, "route_by_style": route.get("by_style", {}),
         "usage": usage, "brain": c.brain(usage, questions), "verified_at": c.now()}
    prev = c.load_or(os.path.join(c.edir(st, n - 1), "verify.json"), None) if n > 0 else None
    if prev is not None and prev.get("score_mean") is not None and v["score_mean"] is not None:
        v["delta"] = round(v["score_mean"] - prev["score_mean"], 3)
        opt = c.load_or(os.path.join(here, "params", "optimize.json"), {})
        if opt.get("changed"):                                   # 沒改（平手留原值）不算一次（§ 15.3 壞法 a）
            r = c.load(OPT, "StateBad", "optimize/ratings.json ")
            ar = r.get("action:route") or {}
            k = ar.get("counter_applied", 0)
            improved, regressed = v["delta"] >= budget.get("min_gain", 0.25), v["delta"] < 0
            sum_delta = round(ar.get("sum_delta", 0) + v["delta"], 3)
            tokens = ar.get("counter_tokens", 0) + c.usage_of(here)["counter_tokens"]
            ar = {"counter_applied": k + 1,
                    "counter_improved": ar.get("counter_improved", 0) + improved,
                    "counter_regressed": ar.get("counter_regressed", 0) + regressed,
                    "counter_improved_streak": ar.get("counter_improved_streak", 0) + 1 if improved else 0,
                    "sum_delta": sum_delta, "counter_tokens": tokens}
            ar["delta_avg"] = round(sum_delta / ar["counter_applied"], 3)
            ar["val"] = "good" if ar["delta_avg"] >= budget.get("min_gain", 0.25) else "ok" if ar["delta_avg"] >= 0 else "bad"
            ar["dims"] = {"命中": round(ar["counter_improved"] / ar["counter_applied"], 3),
                            "穩定": round(1 - ar["counter_regressed"] / ar["counter_applied"], 3),
                            "效率": round(min(1.0, max(0.0, sum_delta / max(tokens / 100000, 1))), 3)}
            ar["rated_at"] = c.now()
            ar["rated_by"] = "train/verify.py epoch %d @ %s" % (n, st)
            r["action:route"] = {k2: ar[k2] for k2 in ("val", "delta_avg", "counter_applied", "counter_improved", "counter_regressed",
                                                        "counter_improved_streak", "sum_delta", "counter_tokens", "dims", "rated_at", "rated_by")}
            c.save(OPT, r)
            v["optimize_rated"] = True
    c.save(vpath, v)
    # 根的評級（整棵樹對外的那格）
    style = (sets.get("scope") or {}).get("style") or (got[0].get("style") if got else None)
    rp = os.path.join(c.ROOT, "ratings.json")
    root = c.load(rp, "StateBad", "根的 ratings.json ")
    root["scope"] = sets.get("scope")
    k = len(g["totals"])
    root["style:%s" % style] = {"val": val_of(v["score_mean"], k), "score_avg": v["score_mean"], "score_min": min(g["totals"]) if k else None,
                                "counter_samples": k, "dims": g["dims"], "determinism": (m or {}).get("一致"),
                                "cost": {"llm_calls": v["brain"]["llm_calls_per_question"], "llm_tokens": v["brain"]["llm_tokens_per_question"]},
                                "brain": v["brain"], "rated_at": c.now(), "rated_by": "train/verify.py epoch %d @ %s" % (n, st)}
    c.save(rp, root)
    c.rollup_up(".")
    with open(os.path.join(st, "verify.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({k: v.get(k) for k in ("epoch", "score_mean", "delta", "dims", "verified_at")}, ensure_ascii=False) + "\n")
    first = c.load_or(os.path.join(c.edir(st, 0), "verify.json"), {}).get("brain") or v["brain"]
    print("train: epoch %d verify score_mean %s%s tokens/題 %s → %s on_brain %s → %s determinism %s" % (
        n, v["score_mean"], " delta %+.3f" % v["delta"] if "delta" in v else "",
        first["llm_tokens_per_question"], v["brain"]["llm_tokens_per_question"],
        first["counter_on_brain"], v["brain"]["counter_on_brain"], (m or {}).get("一致")))

v = c.load(vpath)
if v.get("delta") is not None and v["delta"] < 0:
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
