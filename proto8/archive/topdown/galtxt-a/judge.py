#!/usr/bin/env python3
# judge - 過了護欄（checks.json 的 pass）的草稿逐份交給評審 agent（grader/）打三項 0～3 的分（承接、像柚葉、文筆；round4 § 1.3），收成 $AOS_STACK/judge.json
# 每份一個新小格 $AOS_STACK/judge/runs/NNN/（lib/agent/agent_tool.py 的 fresh_cell、run_agent）；judge.json 裡已有的那份不重評（重跑接著做）。
# 題目＝場景條件（或挖空題的前後文與評分要點的紅線）＋這份草稿；不含正解（brief.json 本來就沒有）。
# 答案要有「承接：N」（N 是 0～3；沒有＝ReplyBad 停——出口保證；重跑會開新小格、不帶上次的回答）；「像柚葉：N」「文筆：N」缺行＝那項 null（不停）；「理由：…」可缺。
# judge.json 一份一格：{tier2: 承接（舊 Tier 2 改名，文靜這種沒評分結構的風格照舊算 Tier 1＋Tier 2）, scores: {承接, 像柚葉, 文筆}, reason}。
# 沒有任何草稿過護欄時什麼都不評、judge.json 是空表、退 0。
# 步驟 3b（round4-data.md § 3）：rubric 的人物描述不寫在 grader/system.txt（那裡只留評分尺度）——風格在 data/dims.json 的 profiles、
# 評審量的維度有 cells 時，從那些格（例 像柚葉 → cast.yuzu.trait.*、bio.*）渲染一行「人物設定：<名>（<型>）——<格字面、…>」進題目；改卡一字、rubric 跟著變。
# 錯：stderr 一行「galtxt-a judge: 代號 原因」、退 1——StackMissing、StateBad、ReplyBad、AgentFailed／AnswerMissing（由 agent_tool 印）。
import json, os, re, sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "lib", "agent")))   # proto8/lib/agent
import agent_tool  # noqa: E402
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True                   # 樹裡不留 __pycache__
import cells  # noqa: E402

NAME = "galtxt-a judge"
ITEMS = ("承接", "像柚葉", "文筆")
SCORES = {k: re.compile(r"^\s*%s\s*[:：]\s*([0-3])\s*$" % k, re.M) for k in ITEMS}
REASON = re.compile(r"^\s*理由\s*[:：]\s*(.+?)\s*$", re.M)


def die(code, reason):
    print("%s: %s %s" % (NAME, code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


def save(path, obj):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))   # N-05
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
    os.replace(tmp, path)


stack = os.environ.get("AOS_STACK")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")
try:
    with open(os.path.join(stack, "checks.json"), encoding="utf-8") as f:
        checks = json.load(f)
    with open(os.path.join(stack, "brief.json"), encoding="utf-8") as f:
        brief = json.load(f)
    with open(os.path.join(stack, "current.txt"), encoding="utf-8") as f:
        name = f.read().strip()
except (OSError, ValueError) as e:
    die("StateBad", "check 還沒做好：%s" % e)
path = os.path.join(stack, "judge.json")
try:
    with open(path, encoding="utf-8") as f:
        done = json.load(f)
except FileNotFoundError:
    done = {}
except ValueError as e:
    die("StateBad", "judge.json 壞了：%s" % e)
if os.environ.get("GALTXT_JUDGE") == "off":       # optkit opt_try（round4-selfopt.md § 1）：不叫評審、省腦；pick 照「沒評」算（評審的維度 null）
    save(path, done)
    sys.exit(0)


def persona():
    """評審量的維度（by grader）在 dims.json 有 cells＝渲染「人物設定」行；格解不到＝StateBad"""
    try:
        with open(os.path.join(HERE, "data", "dims.json"), encoding="utf-8") as f:
            profile = json.load(f)["profiles"].get(brief.get("style")) or {}
        out = []
        for dim, spec in profile.items():
            ids = [i for p in spec.get("cells") or [] for i in cells.expand(p)] if spec.get("by") == "grader" else []
            if not ids:
                continue
            who = cells.resolve(".".join(ids[0].split(".")[:2]))[2]
            out.append("人物設定：%s（%s）——%s" % (who.get("display"), who.get("type"), "、".join(cells.text(cells.resolve(i)[2]) for i in ids)))
        return out
    except (OSError, ValueError, KeyError, TypeError, AttributeError, cells.CellMissing, cells.RefBad) as e:
        die("StateBad", "data/dims.json 的 cells 解不了：%s" % e)


def task(draft):
    b = brief
    head = ["地點：%s（%s）" % (b["place"]["name"], "、".join(b["place"].get("details", [])[:3])),
            "季節與時間：%s %s；基調：%s；稱謂階：%s" % (b.get("season"), b.get("time"), b.get("intent"), b.get("rank")),
            "角色：" + "；".join("%s（%s）" % (c["name"], c.get("type")) for c in b.get("cast", []))] + persona()
    if b["mode"] == "fill":
        head += ["題型：挖空，只評空格那一行（說話者 %s）" % b.get("speaker"), "說話者設定：%s" % b.get("speaker_note"),
                 "前後文：", *b.get("context", [])]
    else:
        head += ["題型：整場（%d～%d 行）" % (b["min_lines"], b["max_lines"]), "事件：%s" % b.get("event")]
    return "\n".join(head + ["", "草稿：", draft.rstrip("\n"), ""])


for n in sorted(checks, key=int):
    if not checks[n].get("pass") or n in done:
        continue
    with open(os.path.join(stack, "drafts", n + ".txt"), encoding="utf-8") as f:
        draft = f.read()
    cell = agent_tool.fresh_cell(os.path.join(stack, "judge"))
    reply = agent_tool.run_agent(NAME, "grader", task(draft), cell, question=name[:-5] + ".txt" if name.endswith(".json") else name + ".txt")
    got = {k: (int(m.group(1)) if m else None) for k, m in ((k, SCORES[k].search(reply)) for k in ITEMS)}
    if got["承接"] is None:
        die("ReplyBad", "第 %s 份的評審回覆沒有「承接：0～3」（現場在 %s）" % (n, cell))
    r = REASON.search(reply)
    done[n] = {"tier2": got["承接"], "scores": got, "reason": r.group(1) if r else ""}
    save(path, done)                              # 一份一存：被殺掉重跑時已評的不重評
save(path, done)
