#!/usr/bin/env python3
# pick - 合分、挑一份交卷：總分＝Tier 1＋Tier 2（0～5），Tier 0 不過＝0；嚴格比大小、平手編號小的贏（同樣的候選永遠挑同一個）
# 寫 $AOS_WS/out/<題名>/answer.txt 與 score.json（先寫 . 開頭暫存資料夾再改名，N-05），題目 cur/ → done/。
# 全部沒過 Tier 0 時照樣挑違規最少的那份、score.json 標 pass: false、退 0（預料到的正常結果，N-43）。
# 挖空模式再讀 data/bench/<編號>.json 的 answer：記字元二元組重疊率（只記錄、不計分）與護欄關鍵詞有沒有全中。
# 結構分（第三輪，round3 § 14；只記錄、不改挑法）：score.json 多 writer、style（從 $AOS_STACK/route.json），每份草稿多 dims
# {語域: tier1/2, 語意: tier2/3（沒評＝null）, 護欄: 過 Tier 0＝1.0 否則 0.0}，整題多 dims {多樣性: 1 − 各份兩兩字元二元組重疊率的平均}。
# 第四輪（round4 § 1.3、§ 1.4）：照 data/dims.json 走——風格（route.json 的 style）在 profiles 裡＝每份 dims 是表上的維度（by tools/lint 取 lint 的 dims、
# by grader 取評審那項 ÷ 3；modes 不含這題的 mode＝null）＋護欄，total＝5 × Σ(weight×值)/Σweight（null 不進分母），Tier 0 沒過＝0；
# 不在 profiles＝舊公式（Tier 1＋Tier 2、dims 語域／語意／護欄，一字不變）。整題 dims 照 question_dims：多樣性；一致＝1 − 多樣性，只在 brief 有 hints_fixed 時算。
# 錯：stderr 一行「galtxt-a pick: 代號 原因」、退 1——StackMissing、StateBad（checks.json、drafts/、current.txt、route.json 缺或壞）。
import json, os, shutil, sys

DATA = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")


def die(code, reason):
    print("galtxt-a pick: %s %s" % (code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


def bigrams(s):
    s = "".join(ch for ch in s if ch.strip())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def quote(line):
    """「角色：「台詞」」只取引號裡；不是那個形狀就整行。"""
    head, sep, rest = line.partition("：「")
    return rest[:-1] if sep and rest.endswith("」") else line


stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")
try:
    with open(os.path.join(stack, "checks.json"), encoding="utf-8") as f:
        checks = json.load(f)
    with open(os.path.join(stack, "brief.json"), encoding="utf-8") as f:
        brief = json.load(f)
    with open(os.path.join(stack, "current.txt"), encoding="utf-8") as f:
        name = f.read().strip()
    with open(os.path.join(stack, "route.json"), encoding="utf-8") as f:
        route = json.load(f)
    if not isinstance(route, dict):
        raise ValueError("route.json 不是物件")
    texts = {}
    for n in checks:
        with open(os.path.join(stack, "drafts", n + ".txt"), encoding="utf-8") as f:
            texts[n] = f.read()
except (OSError, ValueError) as e:
    die("StateBad", "前面的格還沒做好：%s" % e)
if not checks:
    die("StateBad", "checks.json 是空的")
try:
    with open(os.path.join(stack, "judge.json"), encoding="utf-8") as f:
        judged = json.load(f)
except FileNotFoundError:
    judged = {}
except ValueError as e:
    die("StateBad", "judge.json 壞了：%s" % e)

try:
    with open(os.path.join(DATA, "dims.json"), encoding="utf-8") as f:
        table = json.load(f)
    profile = (table.get("profiles") or {}).get(route.get("style"))
    question_dims = table.get("question_dims") or {}
except (OSError, ValueError, AttributeError) as e:
    die("StateBad", "data/dims.json 讀不了：%s" % e)


def measured(dim, spec, lint, grade):
    """一個維度的值：by tools/lint＝lint 的 dims；by grader＝評審那項 ÷ 3；這題的 mode 不在 modes＝null"""
    if "modes" in spec and brief.get("mode") not in spec["modes"]:
        return None
    v = {"tools/lint": lint, "grader": grade}.get(spec.get("by"), {}).get(dim)
    return round(v, 3) if isinstance(v, (int, float)) else None


rows = []
for n in sorted(checks, key=int):
    c = checks[n]
    j = judged.get(n, {}) if c.get("pass") else {}
    t2 = j.get("tier2")
    row = {"n": int(n), "tier0": [x["code"] for x in c.get("tier0", [])], "tier1": c.get("tier1"),
           "tier1_notes": c.get("tier1_notes", []), "tier2": t2,
           "reason": j.get("reason") if c.get("pass") else None,
           "total": (c.get("tier1") or 0) + (t2 or 0) if c.get("pass") else 0}
    if profile:
        grade = {k: v / 3 for k, v in (j.get("scores") or {"承接": t2}).items() if isinstance(v, int)}
        row["dims"] = {}
        for dim, spec in profile.items():
            row["dims"][dim] = measured(dim, spec, c.get("dims") or {}, grade)
        row["dims"]["護欄"] = 1.0 if c.get("pass") else 0.0
        got = [(spec.get("weight", 1), row["dims"][k]) for k, spec in profile.items() if row["dims"][k] is not None]
        row["total"] = round(5 * sum(w * v for w, v in got) / sum(w for w, _ in got), 3) if c.get("pass") and got else 0
    else:
        row["dims"] = {"語域": round((c.get("tier1") or 0) / 2, 3),
                       "語意": round(t2 / 3, 3) if t2 is not None else None,
                       "護欄": 1.0 if c.get("pass") else 0.0}
    if c.get("bonus"):
        row["bonus"] = c["bonus"]
    rows.append(row)
passed = [r for r in rows if not r["tier0"]]
if passed:
    best = passed[0]
    for r in passed[1:]:
        if r["total"] > best["total"]:           # 嚴格比大小：平手留編號小的
            best = r
else:
    best = rows[0]
    for r in rows[1:]:
        if len(r["tier0"]) < len(best["tier0"]):
            best = r
answer = texts[str(best["n"])]
base = brief.get("name") or (name[:-5] if name.endswith(".json") else name)
grams = [bigrams(texts[str(r["n"])]) for r in rows]
pairs = [len(a & b) / len(a | b) if a | b else 1.0 for i, a in enumerate(grams) for b in grams[i + 1:]]
score = {"mode": brief.get("mode"), "name": base, "writer": route.get("writer"), "style": route.get("style"),
         "picked": best["n"], "pass": bool(passed), "drafts": rows,
         "dims": {}}
diversity = round(1 - sum(pairs) / len(pairs), 3) if pairs else None
formulas = {"多樣性": diversity, "一致": round(1 - diversity, 3) if diversity is not None else None}   # 一致＝同輸入同角度幾份有多像（round4 § 4.2）
for qname, spec in question_dims.items():
    if not (spec.get("only") and not brief.get(spec["only"])):
        score["dims"][qname] = formulas.get(qname)

if brief.get("mode") == "fill":
    task_bench = brief.get("bench")
    if task_bench:
        try:
            with open(os.path.join(DATA, "bench", task_bench + ".json"), encoding="utf-8") as f:
                bench = json.load(f)
        except (OSError, ValueError) as e:
            die("StateBad", "評測題讀不到：%s" % e)
        a, b = bigrams(quote(answer.strip())), bigrams(quote(bench["answer"]))
        score["bench"] = {"id": task_bench,
                          "bigram_overlap": round(len(a & b) / len(a | b), 3) if a | b else 0.0,
                          "guard_hit": all(any(w in answer for w in g) for g in bench["guard"]["must"]),
                          "bonus_hit": [w for w in bench["guard"].get("bonus", []) if w in answer]}

out = os.path.join(ws, "out", base)
tmp = os.path.join(ws, "out", "." + base)
shutil.rmtree(tmp, ignore_errors=True)
os.makedirs(tmp)
with open(os.path.join(tmp, "answer.txt"), "w", encoding="utf-8") as f:
    f.write(answer if answer.endswith("\n") else answer + "\n")
with open(os.path.join(tmp, "score.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps(score, ensure_ascii=False, indent=1) + "\n")
shutil.rmtree(out, ignore_errors=True)            # 重跑同一題：蓋掉上次的答案
os.replace(tmp, out)
os.makedirs(os.path.join(ws, "done"), exist_ok=True)
if os.path.exists(os.path.join(ws, "cur", name)):
    shutil.move(os.path.join(ws, "cur", name), os.path.join(ws, "done", name))
