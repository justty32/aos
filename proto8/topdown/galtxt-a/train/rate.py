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
# 人評樣本（round4 § 8.1）：配對優先、追加到 human/samples.json（≤ 6 筆；已有的不動，只補空著的槽；要重挑刪掉它）。印一行摘要到 stdout。
# 錯：stderr 一行「train: 代號 原因」、退 1——StackMissing、StateBad（score.json 壞、寫手資料夾不在、style 出了收窄範圍）、SetBad。
import os, sys

sys.dont_write_bytecode = True                      # 不在樹裡留 __pycache__/
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as c  # noqa: E402



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


# 人評樣本（round4 § 8.1；步驟 7）：全部在收窄範圍（scope_check 過的才是候選）；配對優先、追加不覆蓋（已在 samples.json 的那幾筆一字不動，只補還空著的槽）。
# 槽（順位＝表的順序，合起來最多 6 筆）：
#   pair-stage × 驗證題（set.json verify：Q16、cls-lights）× {agent, program}——同一題固化前（最早一個寫手 agent 階的驗證 epoch）vs 固化後（最早一個 program 階的），pick 挑中的那份；
#   disagree × 1——驗證小格（各 epoch）＋這個 epoch 訓練題的過護欄草稿裡 |反差 − 像柚葉| 最大、≥ 0.33 的（場景題只收 ≤ 8 行）；
#   hard × 1——這個 epoch 訓練題裡 hard.jsonl 有 TemplateMissing、還沒蒸餾（不是 held-out）的那題，pick 挑中的降級產出。
# 槽的產出還沒出現（program 階要 epoch 3 之後）＝這次先空著、之後的 rate 補；所以第一個 epoch 後是 3 筆（兩個 agent 半邊＋disagree），寫手到 program 之後補到 6。
# 每筆照網頁契約（round3 § 16.1：id、team、round、scene{cast, place, event, style, intent, context}、lines、produced_by、auto_scores、brain、why_picked），
# scene 多 epoch（產出那份的 epoch）、stage（寫手那時的階）、pair_id（同題配對共用；不是配對＝null）；頂層多 question、picked_at_epoch（哪一次 rate 補進來的）。
# id＝a4-<題>-<階>-e<epoch>-<份>（a4＝甲隊第四輪，不跟第三輪 a-q01-writer-* 那批撞）。
SLOTS = 6
DISAGREE_MIN = 0.33


def stages_of(w):
    """寫手 stage.json.history → ({epoch: 那次驗證實際跑的階}, {epoch: 那次判完後留下的階＝下一個 epoch 訓練題用的})"""
    hist = (c.load_or(os.path.join(c.ROOT, w, "stage.json"), {}) or {}).get("history") or []
    ran, kept, cur = {}, {}, None
    for h in sorted((h for h in hist if isinstance(h, dict) and isinstance(h.get("epoch"), int)), key=lambda h: h["epoch"]):
        ran[h["epoch"]] = h.get("stage")
        if h.get("accepted") is not False or cur is None:
            cur = h.get("stage")
        kept[h["epoch"]] = cur
    return ran, kept


def draft_of(cell, s, k=None):
    """score.json 的第 k 份（預設 pick 挑中的）→ (草稿, 行)；沒過護欄、檔讀不到＝None"""
    k = s.get("picked") if k is None else k
    d = next((d for d in s.get("drafts") or [] if d.get("n") == k), None)
    if not d or d.get("tier0"):
        return None
    try:
        with open(os.path.join(cell, "stack", "drafts", "%d.txt" % k), encoding="utf-8") as f:
            lines = [l.strip() for l in f.read().splitlines() if l.strip()]
    except OSError:
        return None
    return (d, lines) if lines else None


def sample_of(cell, s, d, lines, epoch, stage, why, pair):
    brief = c.load_or(os.path.join(cell, "stack", "brief.json"), {}) or {}
    q = s.get("name") or "?"
    scene = {"cast": [x.get("name") for x in brief.get("cast") or [] if isinstance(x, dict)], "place": (brief.get("place") or {}).get("name"),
             "event": brief.get("event") or brief.get("setting"), "style": s.get("style"), "intent": brief.get("intent")}
    if brief.get("mode") == "fill":
        scene["context"] = brief.get("context", [])
    scene.update(epoch=epoch, stage=stage, pair_id=pair)
    return {"id": "a4-%s-%s-e%d-%d" % (q.lower(), stage or "na", epoch, d["n"]), "team": "a", "round": 4, "question": q,
            "scene": scene, "lines": lines, "produced_by": s.get("writer"),
            "auto_scores": {"val": val_of(d["total"], 3), "total": d["total"], "tier1": d.get("tier1"), "tier2": d.get("tier2"),
                            "dims": dict(d.get("dims") or {}, 多樣性=(s.get("dims") or {}).get("多樣性")), "reason": d.get("reason")},
            "brain": "real" if os.environ.get("AOS_BRAIN_URL") else "fake", "why_picked": why, "picked_at_epoch": n}


def slot_of(x):
    sc = x.get("scene") or {}
    if x.get("why_picked") == "pair-stage":
        return ("pair-stage", sc.get("pair_id"), sc.get("stage"))
    return (x.get("why_picked"),)


def pick_samples(have):
    w = (sets.get("writers") or ["writer"])[0]
    ran, kept = stages_of(w)
    taken = {slot_of(x) for x in have}
    texts = {(x.get("question"), "\n".join(x.get("lines") or [])) for x in have}   # 同題同字面不重複（不同題同字面照收：模板沒管小動作，正是要人看的）
    out = []

    def add(slot, cell, s, d, lines, epoch, stage, why, pair=None):
        t = (s.get("name"), "\n".join(lines))
        if slot in taken or t in texts or len(have) + len(out) >= SLOTS:
            return False
        taken.add(slot)
        texts.add(t)
        out.append(sample_of(cell, s, d, lines, epoch, stage, why, pair))
        return True

    ver = []                                                    # [(epoch, 小格, score)]：各 epoch 的驗證小格（在範圍內的）
    for e in sorted(os.listdir(epochs)) if os.path.isdir(epochs) else []:
        if e.isdigit():
            ver += [(int(e), cl, s) for cl, s in scores(os.path.join(epochs, e, "verify"))
                    if s.get("style") == (sets.get("scope") or {}).get("style") and s.get("writer") == w]
    for q in sets.get("verify") or []:                          # 1、2：同題 agent vs program
        name = q[:-5] if q.endswith(".json") else q
        pair = "a4-%s" % name.lower()
        for stage in ("agent", "program"):
            for e, cl, s in ver:
                if s.get("name") == name and ran.get(e) == stage:
                    got = draft_of(cl, s)
                    if got and add(("pair-stage", pair, stage), cl, s, got[0], got[1], e, stage, "pair-stage", pair):
                        break
    cands = [(e, cl, s, ran.get(e)) for e, cl, s in ver]       # 3：純程式說好、評審說不好（或反過來）
    cands += [(n, cl, s, kept.get(n - 1)) for cl, s in scores(os.path.join(c.edir(st, n), "runs")) if s.get("writer") == w]
    rows = []
    for e, cl, s, stage in cands:
        for d in s.get("drafts") or []:
            prog, judge = (d.get("dims") or {}).get("反差"), (d.get("dims") or {}).get("像柚葉")
            if d.get("tier0") or prog is None or judge is None or abs(prog - judge) < DISAGREE_MIN:
                continue
            got = draft_of(cl, s, d.get("n"))
            if got and (len(got[1]) <= 8 or s.get("mode") == "fill"):
                rows.append((-round(abs(prog - judge), 3), e, s.get("name") or "", d["n"], cl, s, got, stage))
    for _, e, _, _, cl, s, got, stage in sorted(rows, key=lambda r: r[:4]):
        if add(("disagree",), cl, s, got[0], got[1], e, stage, "disagree"):
            break
    held = c.heldout_details(sets)                               # 4：難例那題蒸餾前的降級產出
    open_q = {r.get("question") for r in c.hard_rows(w) or [] if r.get("why") == "TemplateMissing" and r.get("resolved_epoch") is None
              and ((r.get("brief_key") or {}).get("detail") not in held)}
    for cl, s in scores(os.path.join(c.edir(st, n), "runs")):
        if s.get("writer") == w and s.get("name") in open_q:
            got = draft_of(cl, s)
            if got and add(("hard",), cl, s, got[0], got[1], n, kept.get(n - 1) or "program", "hard"):
                break
    return out


human = os.path.join(c.ROOT, "human", "samples.json")
have = c.load_or(human, [])
new = pick_samples(have) if isinstance(have, list) else []      # 壞的（不是陣列）不碰：人評樣本只追加、不覆蓋
if new:
    c.save(human, have + new)
u = c.load_or(os.path.join(c.edir(st, n), "usage.json"), {})
print("train: epoch %d rated %s tokens %s" % (n, " ".join("%s{%s}" % (w, " ".join(v)) for w, v in summary.items()),
                                             u.get("counter_tokens", "?")))
