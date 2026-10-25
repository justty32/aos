#!/usr/bin/env python3
# verify - 訓練迴圈的「比較前後」格（round3 § 8.5）：set.json 的驗證題各一題照「當下的」data/route.json 跑根（不強制寫手），
# 小格 $AOS_STACK/epochs/NNN/verify/<題名>/{ws,stack}（已有 score.json 的跳過）；算分寫 epochs/NNN/verify.json、追加 verify.jsonl 一行。
# score_mean＝所有驗證題所有過護欄草稿的 total 平均；dims＝四個維度在驗證題上的平均；另記 picked_total_sum、guard_hit、bigram_overlap、用量（只記不比）。
# 跟上一個 epoch 比 score_mean：上一個 epoch 的 optimize 有改 route（epochs/NNN/params/optimize.json 的 changed）才記一筆給優化函數的評級
# （train/optimize/ratings.json 的 action:route，§ 15：只有這支寫它）。
# 結束碼：跌了（< 0）＝把 epochs/NNN/params/route.json（optimize 改之前那份）拷回 data/route.json、stderr「train: Regressed …」、退 10（收工）；
# epoch ≥ max_epochs＝退 10；預算到頂（開跑前看一次）＝BudgetSpent 退 2；否則 epoch.txt＋1、退 0（往 train 走）。
# 錯：stderr 一行「train: 代號 原因」、退 1——StackMissing、StateBad、SetBad、RunFailed（根退非 0；現場在小格）。
import json, os, sys

sys.dont_write_bytecode = True                      # 不在樹裡留 __pycache__/
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as c  # noqa: E402

OPT = os.path.join(c.HERE, "optimize", "ratings.json")


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


st = c.stack()
sets, budget = c.settings()
n = c.epoch(st)
here = c.edir(st, n)
vpath = os.path.join(here, "verify.json")
c.mark_started(st)

if not os.path.exists(vpath):
    c.check_budget(st, budget)
    route = c.load(os.path.join(c.ROOT, "data", "route.json"), "StateBad", "data/route.json ")
    totals, dims, picked, guard, overlap, by = [], {"語域": [], "語意": [], "護欄": [], "多樣性": []}, 0, 0, [], {}
    for q in sets["verify"]:
        base = q[:-5] if q.endswith(".json") else q
        cell = os.path.join(here, "verify", base)
        rc, spath = c.run_question(cell, q)
        if rc != 0:
            c.die("RunFailed", "驗證題 %s 結束碼 %d（現場在 %s）" % (q, rc, cell))
        s = c.load(spath, "StateBad", "score.json ")
        by[base] = s.get("writer")
        for d in s["drafts"]:
            dims["護欄"].append(d["dims"]["護欄"])
            if not d["tier0"]:
                totals.append(d["total"])
                dims["語域"].append(d["dims"]["語域"])
                dims["語意"].append(d["dims"]["語意"])
        dims["多樣性"].append(s.get("dims", {}).get("多樣性"))
        picked += next((d["total"] for d in s["drafts"] if d["n"] == s["picked"]), 0)
        if s.get("bench"):
            guard += 1 if s["bench"].get("guard_hit") else 0
            overlap.append(s["bench"].get("bigram_overlap"))
    v = {"epoch": n, "score_mean": mean(totals), "counter_samples": len(totals),
         "dims": {k: mean(xs) for k, xs in dims.items()},
         "picked_total_sum": picked, "guard_hit": guard, "bigram_overlap": mean(overlap),
         "writers": by, "route_by_style": route.get("by_style", {}),
         "usage": c.usage_of(os.path.join(here, "verify")), "verified_at": c.now()}
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
    with open(os.path.join(st, "verify.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({k: v.get(k) for k in ("epoch", "score_mean", "delta", "dims", "verified_at")}, ensure_ascii=False) + "\n")
    print("train: epoch %d verify score_mean %s%s" % (n, v["score_mean"], " delta %+.3f" % v["delta"] if "delta" in v else ""))

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
