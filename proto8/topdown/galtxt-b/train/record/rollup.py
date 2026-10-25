#!/usr/bin/env python3
# rollup.py - 子樹彙總（round6 §7-1、使用者「樹中有樹、不要壓平成一張表」）：由下往上把每個節點的子樹彙總進它自己的 _metainfo.rollup。純程式。
# 誰算：train/record（每輪 record 的第 3b 步，寫訓練場的 tree/ 複本）；也可單獨跑：python3 rollup.py <樹根> [--write] [--out 檔]
#   沒 --write＝只印樹狀圖（repo 的樹用這個：P-15 定義資料夾不被寫）。
# 何時更新：每輪 record 後（梯度之前，所以 rollup 的變化也進 gradient）。
# 子樹被別處重用（捷徑，例 writer/tools/lint → lib/lint）：在目標的位置算一次、捷徑那頭照抄目標的 rollup（帶著走，不重算）；父節點照樣把它算進合計。
# 每節點寫進 rollup 的 key（其他 key，例 measured、counter_rows，原樣保留）：
#   llm_tokens {val＝自己＋子樹, self, source}：self 只算「自己有腦殼」的節點（資料夾裡有 brain.py 或 ask.py）——有 record 量到的 rollup.measured.llm_tokens 用量到的
#     （source measured），沒有用宣告的 llm_tokens.val（declared）；其餘節點 self 0（根、draft 的 uses_llm 是因為底下有腦，不重算）。
#   uses_llm：自己有腦殼或子樹有。 stage：自己的 lifecycle.stage；沒宣告的＝子樹沒腦就 pure、有腦就 null。
#   stage_min：子樹裡最不固化的那階（agent < tools < script < pure）——整棵子樹 pure＝tokens 0、不問腦。
#   deterministic_score：自己量過（rollup.measured.deterministic_score，score 那個）用量的；子樹沒腦＝1.0；否則有腦的子節點取最小（有一個不知道就 null）。
#   hard_cases {counter_open, counter_resolved}：自己的＋子樹的。 counter_nodes：子樹節點數（含自己）。 links：捷徑子節點（→ 目標）。
import json, os, sys

STAGES = ["agent", "tools", "script", "pure"]
SKIP = ("versions", "__pycache__")
TOP_SKIP = ("plan", "train", "human")           # 跟 train/init 一樣：訓練迴圈、規劃、人評不屬於台詞樹
KEYS = ("llm_tokens", "uses_llm", "stage", "stage_min", "deterministic_score", "hard_cases", "counter_nodes", "links")


def jload(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def children(d, top):
    out = []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return out
    for n in names:
        p = os.path.join(d, n)
        if n.startswith(".") or n in SKIP or (top and n in TOP_SKIP) or not os.path.isdir(p):
            continue
        if os.path.isfile(os.path.join(p, "_metainfo")):
            out.append((n, p, os.path.islink(p)))
    return out


def own(d, meta):
    """自己那一層：(self tokens, source, 有沒有腦殼, 自己的 stage 或 None, 自己量的 det)。"""
    brain = any(os.path.isfile(os.path.join(d, f)) for f in ("brain.py", "ask.py"))
    roll = meta.get("rollup") if isinstance(meta.get("rollup"), dict) else {}
    measured = roll.get("measured") if isinstance(roll.get("measured"), dict) else {}
    tok, src = 0, None
    if brain:
        if num(measured.get("llm_tokens")) is not None:
            tok, src = measured["llm_tokens"], "measured"
        else:
            decl = meta.get("llm_tokens")
            tok, src = (num(decl.get("val")) if isinstance(decl, dict) else num(decl)) or 0, "declared"
    det = measured.get("deterministic_score")
    det = num(det.get("score")) if isinstance(det, dict) else num(det)
    stage = (meta.get("lifecycle") or {}).get("stage") if isinstance(meta.get("lifecycle"), dict) else None
    return tok, src, brain, stage, det


def compute(d, top, cache, write, lines, depth, label):
    real = os.path.realpath(d)
    meta = jload(os.path.join(d, "_metainfo"))
    meta = meta if isinstance(meta, dict) else {}
    if real in cache:                            # 捷徑那頭：照抄目標的；目標本人（先因捷徑算過）：照原位置印出它那段
        r, sub = cache[real]
        if os.path.islink(d):
            lines.append((depth, label + "  → 捷徑（rollup 照抄目標）", r))
        else:
            lines.extend((depth + k, lab, x) for k, lab, x in sub)
        return r
    tok, src, brain, stage, det = own(d, meta)
    hc = meta.get("hard_cases") if isinstance(meta.get("hard_cases"), dict) else {}
    kids, links, sub_lines = [], [], []
    for n, p, is_link in children(d, top):
        if is_link:
            links.append("%s → %s" % (n, os.readlink(p)))
            tgt = os.path.realpath(p)
            if tgt not in cache:                 # 目標在樹裡別處、還沒算到：先在目標位置算（不印在這裡，輪到目標本人時再印）
                compute(tgt, False, cache, write, [], depth + 1, os.path.basename(tgt))
        kids.append(compute(p, False, cache, write, sub_lines, depth + 1, n))
    uses = brain or any(k["uses_llm"] for k in kids)
    if stage is None:
        stage = None if uses else "pure"
    mins = [k["stage_min"] for k in kids if k.get("stage_min")] + ([stage] if stage else ["agent"] if brain else [])
    stage_min = min(mins, key=STAGES.index) if mins else ("pure" if not uses else None)
    if det is None:
        if not uses:
            det = 1.0
        else:
            ds = [k["deterministic_score"] for k in kids if k["uses_llm"]]
            det = min(ds) if ds and all(x is not None for x in ds) and not brain else None
    r = {"llm_tokens": {"val": round(tok + sum(k["llm_tokens"]["val"] for k in kids), 1), "self": tok, "source": src},
         "uses_llm": uses, "stage": stage, "stage_min": stage_min, "deterministic_score": det,
         "hard_cases": {"counter_open": int(hc.get("counter_open") or 0) + sum(k["hard_cases"]["counter_open"] for k in kids),
                        "counter_resolved": int(hc.get("counter_resolved") or 0) + sum(k["hard_cases"]["counter_resolved"] for k in kids)},
         "counter_nodes": 1 + sum(k["counter_nodes"] for k in kids), "links": links}
    mine = [(depth, label, r)] + sub_lines
    cache[real] = (r, [(k - depth, lab, x) for k, lab, x in mine])
    lines.extend(mine)
    if write:
        roll = dict(meta.get("rollup") or {}) if isinstance(meta.get("rollup"), dict) else {}
        new = dict(roll, **r)
        if new != meta.get("rollup"):
            meta["rollup"] = new
            path = os.path.join(d, "_metainfo")
            tmp = os.path.join(os.path.dirname(path), "._metainfo")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=1)
                f.write("\n")
            os.replace(tmp, path)
    return r


def rollup(tree, write=False):
    """回 {"counter_nodes", "lines": [(深度, 名字, rollup)], "root": 根的 rollup}；write＝寫回各 _metainfo.rollup。"""
    lines, cache = [], {}
    r = compute(tree, True, cache, write, lines, 0, ".")
    return {"counter_nodes": r["counter_nodes"], "lines": lines, "root": r}


def render(lines):
    out = []
    for depth, label, r in lines:
        tok = r["llm_tokens"]
        det = r["deterministic_score"]
        hc = r["hard_cases"]
        out.append("%s%s  [%s／min %s]  tokens %s（自己 %s%s）  det %s%s  nodes %d" % (
            "  " * depth, label, r["stage"] or "—", r["stage_min"] or "—", tok["val"], tok["self"],
            "，%s" % tok["source"] if tok["source"] else "", "—" if det is None else det,
            "  難例 %d 開／%d 解" % (hc["counter_open"], hc["counter_resolved"]) if hc["counter_open"] or hc["counter_resolved"] else "",
            r["counter_nodes"]))
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args or not os.path.isfile(os.path.join(args[0], "_metainfo")):
        print("rollup: TreeMissing 用法：rollup.py <樹根（有 _metainfo）> [--write] [--out=檔]", file=sys.stderr)
        sys.exit(1)
    got = rollup(args[0], write="--write" in sys.argv)
    text = render(got["lines"])
    out = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--out=")), None)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
    sys.stdout.write(text)
