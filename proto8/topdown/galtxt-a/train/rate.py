#!/usr/bin/env python3
# rate - 訓練迴圈的「記成果」格（round3 § 2、§ 8.3、§ 14；round4 § 3.2、§ 7.1）：收 $AOS_STACK/epochs/*/runs/*/ws/out/*/score.json（只收訓練題；驗證題在 verify/、不算），
# 每個（寫手, 風格）算一格評級，整格覆蓋寫進 <寫手>/ratings.json 的 "style:<風格>"（這次沒跑到的風格留舊格）；檔頂層 scope＝set.json 的 scope。
# 收窄守門：score.json 的 style 不是 set.json scope.style＝StateBad（round4 § 1.2）。
# 一格：{val, score_avg, score_min, counter_samples, counter_runs, dims, determinism, cost, tags, cell_hits, rated_at, rated_by}；樣本＝過了 Tier 0 的草稿（每份一筆）。
# val 門檻寫死：counter_samples < 3＝none；score_avg ≥ 4.0＝good、≥ 3.0＝ok、其餘 bad。
# dims（0～1）照 score.json 裡有的走（pick 照 data/dims.json 算的，不寫死維度名）：每個維度＝過護欄那幾份的平均；護欄＝過護欄份數 ÷ 全部份數；整題維度（多樣性）＝各題平均。
# determinism＝這個 epoch 的 verify 量的 measure 題（epochs/NNN/verify.json 的 measure.一致，只給跑 measure 的那個寫手）；沒量＝null。
# cost＝寫手每跑一次（一個小格）平均的 {llm_calls, llm_tokens, time_ms}（common.run_cost）；tags＝評審理由標籤計數（非數值梯度的來源）；cell_hits＝{格 id: 次數}（lint 命中哪一格，步驟 3b，「哪一格在起作用」）。
# 評審：grader/ratings.json 的 "role:grader" 整格覆蓋：{cost, dims: {分辨力＝同題幾份承接、像柚葉的標準差平均 ÷ 0.5（0～3 分的標準差上限 1.5）}, counter_samples, rated_at, rated_by}。
# 寫完評級 → common.rollup_up（寫手、grader 各沿自己往上重算 rollup.json 到根，round4 § 3.3）。
# human/samples.json 不在時順手挑人評樣本（§ 16.2，≤ 6 筆；在就不動，要重挑刪掉它）。印一行摘要到 stdout。
# 錯：stderr 一行「train: 代號 原因」、退 1——StackMissing、StateBad（score.json 壞、寫手資料夾不在、style 出了收窄範圍）、SetBad。
import os, sys

sys.dont_write_bytecode = True                      # 不在樹裡留 __pycache__/
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as c  # noqa: E402

MAX_SAMPLES = 6


def val_of(avg, k):
    if k < 3:
        return "none"
    return "good" if avg >= 4.0 else "ok" if avg >= 3.0 else "bad"


def scores(d):
    """d/*/ws/out/*/score.json → [(小格, score)]"""
    out = []
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        o = os.path.join(d, name, "ws", "out")
        for q in sorted(os.listdir(o)) if os.path.isdir(o) else []:
            p = os.path.join(o, q, "score.json")
            if os.path.isfile(p):
                out.append((os.path.join(d, name), c.load(p, "StateBad", "score.json ")))
    return out


st = c.stack()
sets, _ = c.settings()
n = c.epoch(st)
epochs = os.path.join(st, "epochs")
runs = []
for e in sorted(os.listdir(epochs)) if os.path.isdir(epochs) else []:
    runs += scores(os.path.join(epochs, e, "runs"))
for cell, s in runs:
    c.scope_check(s, sets, "%s 的 score.json" % cell)

cells = {}
for cell, s in runs:
    cells.setdefault((s.get("writer"), s.get("style")), []).append((cell, s))
measure = (c.load_or(os.path.join(c.edir(st, n), "verify.json"), {}) or {}).get("measure") or {}

at, by = c.now(), "train/rate.py epoch %d @ %s" % (n, st)
summary = {}
for w in sorted({w for w, _ in cells}, key=str):
    if not isinstance(w, str) or not os.path.isfile(os.path.join(c.ROOT, w, "_entry")):
        c.die("StateBad", "score.json 的 writer %r 不是根底下的寫手資料夾" % (w,))
    path = os.path.join(c.ROOT, w, "ratings.json")
    r = c.load(path, "StateBad", "%s/ratings.json " % w)
    r["scope"] = sets.get("scope")
    for (w2, style), got in sorted(cells.items(), key=lambda kv: str(kv[0])):
        if w2 != w:
            continue
        g = c.gather([s for _, s in got])
        k = len(g["totals"])
        avg = round(sum(g["totals"]) / k, 3) if k else None
        r["style:%s" % style] = {"val": val_of(avg, k), "score_avg": avg, "score_min": min(g["totals"]) if k else None,
                                 "counter_samples": k, "counter_runs": len(got), "dims": g["dims"],
                                 "determinism": measure.get("一致") if measure.get("writer") == w and measure.get("style") == style else None,
                                 "cost": c.run_cost([cl for cl, _ in got], w), "tags": g["tags"], "cell_hits": g["cell_hits"],
                                 "rated_at": at, "rated_by": by}
        summary.setdefault(w, []).append("%s:%s" % (style, r["style:%s" % style]["val"]))
    c.save(path, r)
    c.rollup_up(w)

# 評審：分辨力＝同一題幾份草稿評審給的分拉得多開（全給同分＝0）；只看評審量的維度（每份 dims 裡 by grader 的那幾個：承接、像柚葉）
spread = []
for _, s in runs:
    for dim in ("承接", "像柚葉"):
        sd = c.std([d["dims"].get(dim) for d in s["drafts"] if not d["tier0"]])
        if sd is not None:
            spread.append(sd / 0.5)
gpath = os.path.join(c.ROOT, "grader", "ratings.json")
if runs:
    gr = c.load(gpath, "StateBad", "grader/ratings.json ")
    gr["scope"] = sets.get("scope")
    gr["role:grader"] = {"cost": c.run_cost([cl for cl, _ in runs], "judge"), "dims": {"分辨力": c.mean(spread)},
                         "counter_samples": len(spread), "rated_at": at, "rated_by": by}
    c.save(gpath, gr)
    c.rollup_up("grader")


# 人評樣本（§ 16.2，主動學習）：候選＝這個 epoch 的訓練題＋上一次驗證的所有過護欄草稿
def pick_samples():
    cands = scores(os.path.join(c.edir(st, n), "runs")) + scores(os.path.join(c.edir(st, n - 1), "verify"))
    rows = []
    for cell, s in cands:
        brief = c.load_or(os.path.join(cell, "stack", "brief.json"), {})
        totals = [d["total"] for d in s["drafts"] if not d["tier0"]]
        for d in s["drafts"]:
            if d["tier0"]:
                continue
            try:
                with open(os.path.join(cell, "stack", "drafts", "%d.txt" % d["n"]), encoding="utf-8") as f:
                    lines = [l.strip() for l in f.read().splitlines() if l.strip()]
            except OSError:
                continue
            if len(lines) > 8:                                       # 短：場景題只收 ≤ 8 行
                continue
            dims = dict(d["dims"], 多樣性=(s.get("dims") or {}).get("多樣性"))
            prog = d["dims"].get("反差", d["dims"].get("語域"))           # 純程式量的 vs 評審量的（round4 § 8.1 順位 3 的雛形）
            brain = d["dims"].get("像柚葉", d["dims"].get("語意"))
            disagree = abs((prog or 0) - (brain or 0))
            tie = totals.count(d["total"]) > 1
            edge = 3 <= d["total"] <= 4
            why = "disagree" if disagree >= 0.3 else "tie" if tie else "threshold" if edge else "cover"
            scene = {"cast": [x.get("name") for x in brief.get("cast", [])], "place": (brief.get("place") or {}).get("name"),
                     "event": brief.get("event") or brief.get("setting"), "style": s.get("style"), "intent": brief.get("intent")}
            if brief.get("mode") == "fill":
                scene["context"] = brief.get("context", [])
            rows.append({"score": round(disagree + 0.5 * tie + 0.5 * edge + 0.3 * (len(lines) == 1), 3),
                         "cell": (s.get("writer"), s.get("style"), s.get("name")), "text": "\n".join(lines),
                         "sample": {"id": "a-%s-%s-%d" % (s["name"].lower(), s.get("writer"), d["n"]), "team": "a", "round": n,
                                    "scene": scene, "lines": lines, "produced_by": s.get("writer"),
                                    "auto_scores": {"val": val_of(d["total"], 3), "total": d["total"], "tier1": d["tier1"],
                                                    "tier2": d["tier2"], "dims": dims, "reason": d.get("reason")},
                                    "brain": "real" if os.environ.get("AOS_BRAIN_URL") else "fake",
                                    "why_picked": why}})
    rows.sort(key=lambda r: (-r["score"], r["sample"]["id"]))
    chosen, seen, per = [], set(), {}
    for first in (True, False):                                  # 先每個（寫手, 風格, 題）格一筆，再照分數補到 6 筆、每格 ≤ 2
        for r in rows:
            if len(chosen) >= MAX_SAMPLES or r["text"] in seen or per.get(r["cell"], 0) >= (1 if first else 2):
                continue
            if first and r["cell"] in per:
                continue
            chosen.append(r)
            seen.add(r["text"])
            per[r["cell"]] = per.get(r["cell"], 0) + 1
    ids = set()
    out = []
    for r in chosen:
        s = r["sample"]
        if s["id"] in ids:
            s["id"] += "-e%d" % n
        ids.add(s["id"])
        out.append(s)
    return out


human = os.path.join(c.ROOT, "human", "samples.json")
if not os.path.exists(human):
    c.save(human, pick_samples())
u = c.load_or(os.path.join(c.edir(st, n), "usage.json"), {})
print("train: epoch %d rated %s tokens %s" % (n, " ".join("%s{%s}" % (w, " ".join(v)) for w, v in summary.items()),
                                             u.get("counter_tokens", "?")))
