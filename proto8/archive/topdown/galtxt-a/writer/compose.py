#!/usr/bin/env python3
# compose - 寫手的 program 階（round4 § 2.1：stage.json 的 stage 是 program 時 _entry 跑這支，不跑 aos-loop；腦 0 次）
# 對外介面跟 agent 階一樣：認領 $AOS_WS/new/ 第一題（cur/ 有就先接著做）→ 答案寫 $AOS_WS/out/<題名>、題目搬 done/。
# 怎麼寫：照 data/templates.json 的槽（brief.detail 在 by_detail 就用它、缺的槽退回 generic）填一份，固定順序叫三個工具——
#   tools/beat（deny、yield、cover 三槽 → 一句）→ tools/voice（口癖、句尾、稱呼、說話者 → 一行對白）→ tools/lint（自檢）。
#   挑第幾個候選＝這份的 hint 在 data/hints.json（hints 或 options 任一組）的位置；同 hint 同題永遠同一份（確定性）。
#   fill：只寫說話者那一行；deny／yield 優先挑含 must 第 1／2 組詞的候選。scene：開場旁白、主角、女角（beat→voice）、洩底旁白、主角、收尾旁白。
# 接不住（round4 § 6）：brief 有 detail 而 by_detail 沒有＝TemplateMissing，用 generic 照樣產出；lint 沒過（用了 by_detail 的話先退回 generic 再試一次）仍沒過＝LintFailed，答案照交。
#   兩種都追加一行到 writer/hard.jsonl（{at, question, brief_key {mode, detail}, why, output}；同 question 同 why 已有就不再記）——寫在樹裡，給 distill 當資料。
#   brief 沒有 detail（例 Q16）＝本來就只用 generic，不算難例。
# 程式階只寫 out/、done/ 與 hard.jsonl：不寫 history.jsonl／usage.jsonl／trace.jsonl（沒有腦、沒有 loop）；工具的 stack 照 act.py 給 $AOS_STACK/<工具名>/。
# 步驟 3b（round4-data.md § 3）：模板的槽候選是格（tpl.<路徑>；data/templates.distilled.json 的 tpld.<路徑> 接在同槽人寫的後面），pick() 回 (字面, 格 id)；
#   {prop}＝這題小動作的道具字面（$AOS_WS/rules.json 的 scene＋brief.detail → scene.<場>.detail.<detail>.prop）；口癖 tics 從 rules.contrast.card 的 tic.* 格拿（沒有才退回切 catchphrase）。
#   hard.jsonl 每行多 cells（TemplateMissing＝缺的那格 scene.<場>.detail.<detail>；LintFailed＝這次用到的模板格）、cells_hit（lint 的 hits 攤平）、tpl（用到的模板格 id）。
# 錯：stderr 一行「writer: 代號 原因」、退 1——StackMissing、QuestionMissing（new/ 是空的）、TemplatesBad（data/templates.json、hints.json 讀不了或缺 generic 槽）、ToolFailed（工具退非 0 或起不來）。
import datetime, fcntl, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.realpath(__file__))
DATA = os.path.join(HERE, "..", "data")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.dont_write_bytecode = True                   # 樹裡不留 __pycache__
import cells  # noqa: E402
HARD = os.path.join(HERE, "hard.jsonl")
SLOTS = ("open", "lead", "deny", "yield", "cover", "reveal", "lead2", "close")


def die(code, reason):
    print("writer: %s %s" % (code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")


def ls(d):
    try:
        return sorted(n for n in os.listdir(os.path.join(ws, d)) if not n.startswith("."))   # N-05：. 開頭是暫存檔
    except FileNotFoundError:
        return []


names = ls("cur")
if not names:
    names = ls("new")
    if not names:
        die("QuestionMissing", "new/ 是空的")
    os.makedirs(os.path.join(ws, "cur"), exist_ok=True)
    os.replace(os.path.join(ws, "new", names[0]), os.path.join(ws, "cur", names[0]))
name = names[0]
with open(os.path.join(ws, "cur", name), encoding="utf-8") as f:
    raw = f.read()
try:
    b = json.loads(raw)
    if not isinstance(b, dict):
        raise ValueError("不是物件")
except ValueError:
    b = {}                                       # 題目壞了也照交一份（通用句）；lint 會擋下



def as_cells(slots, prefix):
    """{槽: {序號: 格}} → {槽: [(格 id, 格)]}（照序號；退役的不算）"""
    return {k: [("%s.%s.%s" % (prefix, k, n), v) for n, v in cells.kids(xs) if cells.is_cell(v)]
            for k, xs in (slots or {}).items() if k not in cells.SKIP}


try:
    with open(os.path.join(DATA, "templates.json"), encoding="utf-8") as f:
        table = json.load(f)
    generic = as_cells(table["generic"], "tpl.generic")
    if not all(generic.get(k) for k in SLOTS):
        raise ValueError("generic 缺槽（要 %s，各至少一格）" % "、".join(SLOTS))
    by_detail = {d: as_cells(s, "tpl.by_detail." + d) for d, s in (table.get("by_detail") or {}).items()}
    try:
        with open(os.path.join(DATA, "templates.distilled.json"), encoding="utf-8") as f:
            distilled = json.load(f).get("by_detail") or {}
    except FileNotFoundError:
        distilled = {}
    for d, s in distilled.items():                # distill 追加的：接在同槽人寫的後面
        for k, xs in as_cells(s, "tpld.by_detail." + d).items():
            by_detail.setdefault(d, {}).setdefault(k, []).extend(xs)
    with open(os.path.join(DATA, "hints.json"), encoding="utf-8") as f:
        hints = json.load(f)
    orders = [hints.get("hints") or []] + list(hints.get("options") or [])
except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
    die("TemplatesBad", e)

hint = b.get("hint")
idx = next((o.index(hint) for o in orders if isinstance(o, list) and hint in o), 0)
cast = b.get("cast") if isinstance(b.get("cast"), list) else []
lead = next((c for c in cast if isinstance(c, dict) and c.get("name") == "主角"), {"name": "主角"})
heroine = next((c for c in cast if isinstance(c, dict) and c is not lead), {"name": b.get("speaker") or "她"})
must = b.get("must") if isinstance(b.get("must"), list) else []
fill = b.get("mode") == "fill"
detail = b.get("detail")
qname = b.get("name") or (name[:-5] if name.endswith(".json") else name)
try:
    with open(os.path.join(ws, "rules.json"), encoding="utf-8") as f:
        rules = json.load(f)
    rules = rules if isinstance(rules, dict) else {}
except (OSError, ValueError):
    rules = {}
contrast = rules.get("contrast") if isinstance(rules.get("contrast"), dict) else {}
scene_id = rules.get("scene") if isinstance(rules.get("scene"), str) else None
detail_cell = "%s.detail.%s" % (scene_id, detail) if scene_id and isinstance(detail, str) and detail else None


def cell_text(cid, default):
    try:
        return cells.text(cells.resolve(cid)[2])
    except (cells.CellMissing, cells.RefBad, OSError, ValueError, KeyError, TypeError):
        return default


prop = ""
if detail_cell:
    try:
        prop = cell_text(cells.resolve(detail_cell)[2]["prop"], "")
    except (cells.CellMissing, cells.RefBad, OSError, ValueError, KeyError, TypeError):
        prop = ""
fmt = {"place": (b.get("place") or {}).get("name", "教室") if isinstance(b.get("place"), dict) else "教室",
       "heroine": heroine.get("name", "她"), "called": heroine.get("called_by_lead") or heroine.get("name", "妳"), "prop": prop}
used = []                                        # 這一版用到的模板格 id


def tool(tname, args):
    """aos-exec tools/<名>，arguments 從 stdin 進、stdout 是結果（同 act.py）；工具的 stderr 不吞（降級訊息人看得到）"""
    env = dict(os.environ, AOS_STACK=os.path.join(stack, tname) + "/", AOS_WS=ws)
    try:
        r = subprocess.run(["aos-exec", os.path.join(HERE, "tools", tname)], input=json.dumps(args, ensure_ascii=False),
                           stdout=subprocess.PIPE, text=True, env=env)
    except OSError as e:
        die("ToolFailed", "%s 起不來：%s" % (tname, e))
    if r.returncode != 0:
        die("ToolFailed", "%s 結束碼 %d：%s" % (tname, r.returncode, r.stdout.strip()[:200]))
    return r.stdout.strip()


def pick(slots, k, group=None):
    """slots[k] 的第 idx 個候選格 → 字面（記下格 id）；給了 group（must 的一組詞）先只看含那組詞的候選"""
    xs = slots.get(k) or generic[k]
    if group:
        xs = [x for x in xs if any(w in x[1]["text"] for w in group)] or xs
    cid, c = xs[idx % len(xs)]
    used.append(cid)
    return c["text"].format(**fmt)


def tics_of():
    """她的口癖：rules.contrast.card 的 tic.* 格（一源）；沒有才切 brief 的 catchphrase 字串"""
    try:
        got = [cells.text(cells.resolve(i)[2]) for i in cells.expand(contrast["card"] + ".tic.*")]
        if got:
            return got
    except (cells.CellMissing, cells.RefBad, OSError, ValueError, KeyError, TypeError):
        pass
    return [t for t in (heroine.get("catchphrase") or "").split("／") if t]


def write(slots):
    del used[:]
    tics = tics_of()
    args = {"deny": pick(slots, "deny", must[0] if fill and must else None),
            "yield": pick(slots, "yield", must[1] if fill and len(must) > 1 else None),
            "cover": pick(slots, "cover")}
    said = tool("voice", {"text": tool("beat", args), "who": b.get("speaker") or heroine.get("name", "她"),
                          "calls": heroine.get("calls_lead") or "你", **({"tics": tics} if tics else {})})
    if fill:
        return said
    lines = [pick(slots, "open"), pick(slots, "lead"), said, pick(slots, "reveal"), pick(slots, "lead2"), pick(slots, "close")]
    lo, hi = b.get("min_lines", 5), b.get("max_lines", 10)
    return "\n".join(lines[:max(lo, min(hi, len(lines)))])


def lint(text):
    """→ (過了沒, hits 攤平成排序的格 id)"""
    try:
        got = json.loads(tool("lint", {"text": text}))
        return got.get("pass") is True, sorted({i for xs in (got.get("hits") or {}).values() for i in xs})
    except (ValueError, AttributeError, TypeError):
        return False, []


def hard(why, output, cells_):
    """追加一行到 writer/hard.jsonl；同 question 同 why 已有就不記（鎖住再查再寫：三份草稿可能同時跑）"""
    row = {"at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
           "question": qname, "brief_key": {"mode": b.get("mode"), "detail": detail}, "why": why, "output": output,
           "cells": cells_, "cells_hit": hit, "tpl": list(used)}
    with open(HARD, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        for l in f:
            try:
                old = json.loads(l)
            except ValueError:
                continue
            if isinstance(old, dict) and (old.get("question"), old.get("why")) == (qname, why):
                return
        f.seek(0, os.SEEK_END)
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


slots = {}
if isinstance(detail, str) and detail:
    if isinstance(by_detail.get(detail), dict):
        slots = by_detail[detail]
text = write(slots)
ok, hit = lint(text)
if not ok and slots:                             # 專屬句沒過：退回 generic 再試一次
    slots = {}
    text = write(slots)
    ok, hit = lint(text)
if isinstance(detail, str) and detail and not isinstance(by_detail.get(detail), dict):
    hard("TemplateMissing", text, [detail_cell] if detail_cell else [])
if not ok:
    hard("LintFailed", text, list(used))

os.makedirs(os.path.join(ws, "out"), exist_ok=True)
os.makedirs(os.path.join(ws, "done"), exist_ok=True)
tmp = os.path.join(ws, "out", "." + name)        # N-05
with open(tmp, "w", encoding="utf-8") as f:
    f.write(text + "\n")
os.replace(tmp, os.path.join(ws, "out", name))
shutil.move(os.path.join(ws, "cur", name), os.path.join(ws, "done", name))
