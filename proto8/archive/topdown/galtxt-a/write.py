#!/usr/bin/env python3
# write - 把 $AOS_STACK/brief.json 交給寫手 agent 跑 N 次，答案收成 $AOS_STACK/drafts/<i>.txt
# 選寫手（第三輪）：brief.writer（題目級覆寫）> data/route.json 的 by_style[brief.style] > default；值＝根底下有 _entry 的資料夾名。
# 選好先寫 $AOS_STACK/route.json {"writer", "style", "by": "question"|"by_style"|"default"}（狀態：它在就照它、不重讀表，重跑接著做不換人）。
# 每次一個新小格 $AOS_STACK/<寫手>/runs/NNN/（ws/ 放題目與 rules.json、stack/ 是寫手自己的），用 lib/agent/agent_tool.py 的 fresh_cell、run_agent。
# 題目＝brief.json 去掉 drafts、加一個 hint（第 i 個角度，照 data/hints.json 的 hints 輪著用），三份草稿才不是同一句換字；
# brief 有 hints_fixed（量確定性的題，round4 § 4.2）＝每份都用 hints[0]（同輸入同角度），hints_fixed 本身不給寫手看。
# 已經有的 drafts/<i>.txt 跳過：這格被殺掉重跑時，不重付已經寫好的草稿（P-20 接著做）。
# 錯：stderr 一行「galtxt-a write: 代號 原因」、退 1——StackMissing、StateBad（brief.json／rules.json／current.txt 缺或壞）、
#     RouteBad（route.json 壞、或選到的不是根底下有 _entry 的資料夾）、HintsBad（data/hints.json 讀不了或 hints 不是非空字串陣列）、AgentFailed／AnswerMissing（寫手退非 0 或沒答案；那一行由 agent_tool 印，現場留在小格裡）。
import json, os, shutil, sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "lib", "agent")))   # proto8/lib/agent
import agent_tool  # noqa: E402

NAME = "galtxt-a write"
HERE = os.path.dirname(os.path.realpath(__file__))


def die(code, reason):
    print("%s: %s %s" % (NAME, code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


stack = os.environ.get("AOS_STACK")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")
try:
    with open(os.path.join(stack, "brief.json"), encoding="utf-8") as f:
        brief = json.load(f)
    with open(os.path.join(stack, "current.txt"), encoding="utf-8") as f:
        name = f.read().strip()
    rules = os.path.join(stack, "rules.json")
    if not os.path.isfile(rules):
        raise FileNotFoundError(rules)
except (OSError, ValueError) as e:
    die("StateBad", "brief 還沒做好：%s" % e)
n = brief.pop("drafts", 3)
asked = brief.pop("writer", None)                  # 題目級覆寫；給寫手看的題目不帶路由
fixed = brief.pop("hints_fixed", False)
try:
    with open(os.path.join(HERE, "data", "hints.json"), encoding="utf-8") as f:
        hints = json.load(f)["hints"]
    if not (isinstance(hints, list) and hints and all(isinstance(h, str) for h in hints)):
        raise ValueError("hints 要是非空字串陣列")
except (OSError, ValueError, KeyError, TypeError) as e:
    die("HintsBad", "data/hints.json：%s" % e)


def save(path, obj):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))   # N-05
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
    os.replace(tmp, path)


route_path = os.path.join(stack, "route.json")
try:
    with open(route_path, encoding="utf-8") as f:
        route = json.load(f)
except FileNotFoundError:
    route = None
except ValueError as e:
    die("StateBad", "route.json 壞了：%s" % e)
if route is None:
    style = brief.get("style")
    try:
        with open(os.path.join(HERE, "data", "route.json"), encoding="utf-8") as f:
            table = json.load(f)
        by_style = table.get("by_style") or {}
        if not isinstance(by_style, dict):
            raise ValueError("by_style 不是物件")
    except (OSError, ValueError, AttributeError) as e:
        die("RouteBad", "data/route.json 讀不了：%s" % e)
    if asked is not None:
        route = {"writer": asked, "style": style, "by": "question"}
    elif isinstance(style, str) and style in by_style:
        route = {"writer": by_style[style], "style": style, "by": "by_style"}
    else:
        route = {"writer": table.get("default"), "style": style, "by": "default"}
writer = route.get("writer") if isinstance(route, dict) else None
if not (isinstance(writer, str) and writer and "/" not in writer and not writer.startswith(".")
        and os.path.isfile(os.path.join(HERE, writer, "_entry"))):
    die("RouteBad", "寫手 %r 不是根底下有 _entry 的資料夾（by %s）" % (writer, route.get("by") if isinstance(route, dict) else "?"))
if not os.path.exists(route_path):
    save(route_path, route)
drafts = os.path.join(stack, "drafts")
os.makedirs(drafts, exist_ok=True)

for i in range(1, n + 1):
    out = os.path.join(drafts, "%d.txt" % i)
    if os.path.exists(out):
        continue
    task = dict(brief, hint=hints[0] if fixed else hints[(i - 1) % len(hints)])
    cell = agent_tool.fresh_cell(os.path.join(stack, writer))
    os.makedirs(os.path.join(cell, "ws"))
    shutil.copyfile(rules, os.path.join(cell, "ws", "rules.json"))   # 寫手的 lint 從它自己的 $AOS_WS/rules.json 讀
    answer = agent_tool.run_agent(NAME, writer, json.dumps(task, ensure_ascii=False, indent=1) + "\n", cell,
                                  question=name)
    tmp = os.path.join(drafts, ".%d.txt" % i)     # N-05
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(answer)
    os.replace(tmp, out)
