#!/usr/bin/env python3
# rate - 訓練迴圈的「記成果」格（round3 § 2、§ 8.3、§ 14）：收 $AOS_STACK/epochs/*/runs/*/ws/out/*/score.json（只收訓練題；驗證題在 verify/、不算），
# 每個（寫手, 風格）算一格評級，整格覆蓋寫進 <寫手>/ratings.json 的 "style:<風格>"（這次沒跑到的風格留舊格）。
# 一格：{val, score_avg, score_min, counter_samples, counter_runs, dims, rated_at, rated_by}；樣本＝過了 Tier 0 的草稿（每份一筆）。
# val 門檻寫死：counter_samples < 3＝none；score_avg ≥ 4.0＝good、≥ 3.0＝ok、其餘 bad。
# dims（0～1）：語域、語意＝過護欄那幾份的平均；護欄＝過護欄份數 ÷ 全部份數；多樣性＝各題 score.json 整題多樣性的平均。只平均、不重算（評分節點在 pick）。
# human/samples.json 不在時順手挑人評樣本（§ 16.2，≤ 6 筆；在就不動，要重挑刪掉它）。印一行摘要到 stdout。
# 錯：stderr 一行「train: 代號 原因」、退 1——StackMissing、StateBad（score.json 壞、寫手資料夾不在）。
import os, sys

sys.dont_write_bytecode = True                      # 不在樹裡留 __pycache__/
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as c  # noqa: E402

MAX_SAMPLES = 6
RANK = {"good": 3, "ok": 2, "bad": 1, "none": 0}


def val_of(avg, k):
    if k < 3:
        return "none"
    return "good" if avg >= 4.0 else "ok" if avg >= 3.0 else "bad"


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


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
n = c.epoch(st)
epochs = os.path.join(st, "epochs")
runs = []
for e in sorted(os.listdir(epochs)) if os.path.isdir(epochs) else []:
    runs += scores(os.path.join(epochs, e, "runs"))

cells = {}
for cell, s in runs:
    one = cells.setdefault((s.get("writer"), s.get("style")), {"totals": [], "域": [], "意": [], "欄": [], "樣": [], "runs": 0})
    one["runs"] += 1
    one["樣"].append((s.get("dims") or {}).get("多樣性"))
    for d in s["drafts"]:
        one["欄"].append(d["dims"]["護欄"])
        if not d["tier0"]:
            one["totals"].append(d["total"])
            one["域"].append(d["dims"]["語域"])
            one["意"].append(d["dims"]["語意"])

at, by = c.now(), "train/rate.py epoch %d @ %s" % (n, st)
summary = {}
for w in sorted({w for w, _ in cells}, key=str):
    if not isinstance(w, str) or not os.path.isfile(os.path.join(c.ROOT, w, "_entry")):
        c.die("StateBad", "score.json 的 writer %r 不是根底下的寫手資料夾" % (w,))
    path = os.path.join(c.ROOT, w, "ratings.json")
    r = c.load(path, "StateBad", "%s/ratings.json " % w)
    for (w2, style), one in sorted(cells.items(), key=lambda kv: str(kv[0])):
        if w2 != w:
            continue
        k = len(one["totals"])
        avg = round(sum(one["totals"]) / k, 3) if k else None
        r["style:%s" % style] = {"val": val_of(avg, k), "score_avg": avg, "score_min": min(one["totals"]) if k else None,
                                 "counter_samples": k, "counter_runs": one["runs"],
                                 "dims": {"語域": mean(one["域"]), "語意": mean(one["意"]), "多樣性": mean(one["樣"]), "護欄": mean(one["欄"])},
                                 "rated_at": at, "rated_by": by}
        summary.setdefault(w, []).append("%s:%s" % (style, r["style:%s" % style]["val"]))
    c.save(path, r)


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
            disagree = abs((d["dims"]["語域"] or 0) - (d["dims"]["語意"] or 0))
            tie = totals.count(d["total"]) > 1
            edge = 3 <= d["total"] <= 4
            why = "disagree" if disagree >= 0.3 else "tie" if tie else "threshold" if edge else "cover"
            scene = {"cast": [x.get("name") for x in brief.get("cast", [])], "place": (brief.get("place") or {}).get("name"),
                     "event": brief.get("event") or brief.get("setting"), "style": s.get("style"), "intent": brief.get("intent")}
            if brief.get("mode") == "fill":
                scene["context"] = brief.get("context", [])
            rows.append({"score": round(disagree + 0.5 * tie + 0.5 * edge + 0.3 * (len(lines) == 1), 3),
                         "cell": (s.get("writer"), s.get("style")), "text": "\n".join(lines),
                         "sample": {"id": "a-%s-%s-%d" % (s["name"].lower(), s.get("writer"), d["n"]), "team": "a", "round": n,
                                    "scene": scene, "lines": lines, "produced_by": s.get("writer"),
                                    "auto_scores": {"val": val_of(d["total"], 3), "total": d["total"], "tier1": d["tier1"],
                                                    "tier2": d["tier2"], "dims": dims, "reason": d.get("reason")},
                                    "brain": "real" if os.environ.get("AOS_BRAIN_URL") else "fake",
                                    "why_picked": why}})
    rows.sort(key=lambda r: (-r["score"], r["sample"]["id"]))
    chosen, seen, per = [], set(), {}
    for first in (True, False):                                  # 先每個（寫手, 風格）格一筆，再照分數補到 6 筆、每格 ≤ 2
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
