#!/usr/bin/env python3
# brief - 認領一題（cur/ 有就接著做，沒有就把 new/ 第一題搬到 cur/），從 data/ 組出 $AOS_STACK/brief.json（給寫手看）與 rules.json（給 lint 用）
# 題目是 JSON：{"mode": "scene", place, cast, event, season, time, intent, rank, min_lines, max_lines, drafts} 或 {"mode": "fill", "bench": "Q01", drafts}。
# 挖空模式從 data/bench/<編號>.json 拿前後文與護欄關鍵詞，不拿 answer（正解只有 pick 讀）。
# 換了一題（current.txt 記的不是這題）時，先清掉上一題留在 stack 的 drafts/、checks.json、judge.json、route.json——不然 write、judge 會把舊的當成已做好。
# brief.json 多兩個 key 給 write 選寫手（第三輪）：style＝風格（挖空：說話者的人物卡 type；場景：第一個不是主角的卡司的 type），
# writer＝題目 JSON 有寫就照抄（題目級覆寫，write 那邊驗資料夾在不在）。
# 錯：stderr 一行「galtxt-a brief: 代號 原因」、退 1（QuestionMissing、TaskBad、CastMissing、PlaceMissing、BenchMissing、StackMissing）。
import json, os, shutil, sys

DATA = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")


def die(code, reason):
    print("galtxt-a brief: %s %s" % (code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


def write_atomic(path, text):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))   # N-05：先寫 . 開頭的暫存檔再改名
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def load(path, code, what):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        die(code, "找不到%s：%s" % (what, path))
    except ValueError as e:
        die("TaskBad", "%s 不是 JSON：%s（%s）" % (what, path, e))


stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")


def ls(d):
    try:
        return sorted(n for n in os.listdir(os.path.join(ws, d)) if not n.startswith("."))   # . 開頭＝別人寫到一半的暫存檔（N-05），不撿
    except FileNotFoundError:
        return []


# 1. 認領
names = ls("cur")
if not names:
    names = ls("new")
    if not names:
        die("QuestionMissing", "new/ 與 cur/ 都是空的")
    os.makedirs(os.path.join(ws, "cur"), exist_ok=True)
    os.replace(os.path.join(ws, "new", names[0]), os.path.join(ws, "cur", names[0]))
name = names[0]
current = os.path.join(stack, "current.txt")
try:
    with open(current, encoding="utf-8") as f:
        before = f.read().strip()
except FileNotFoundError:
    before = None
if before is not None and before != name:          # 換題：上一題的半成品不留在桌上
    shutil.rmtree(os.path.join(stack, "drafts"), ignore_errors=True)
    for n in ("checks.json", "judge.json", "route.json"):
        try:
            os.remove(os.path.join(stack, n))
        except FileNotFoundError:
            pass
write_atomic(current, name + "\n")

# 2. 題目
try:
    with open(os.path.join(ws, "cur", name), encoding="utf-8") as f:
        task = json.load(f)
except ValueError as e:
    die("TaskBad", "%s 不是 JSON：%s" % (name, e))
if not isinstance(task, dict) or task.get("mode") not in ("scene", "fill"):
    die("TaskBad", "%s 要是物件、mode 是 scene 或 fill" % name)
mode = task["mode"]
drafts = task.get("drafts", 3)
if "writer" in task and not isinstance(task["writer"], str):
    die("TaskBad", "writer 要是字串（根底下的寫手資料夾名）")
if not isinstance(drafts, int) or isinstance(drafts, bool) or not 1 <= drafts <= 9:
    die("TaskBad", "drafts 要是 1～9 的整數")

bench = None
if mode == "fill":
    if not isinstance(task.get("bench"), str) or "/" in task["bench"] or task["bench"].startswith("."):
        die("TaskBad", "挖空模式要有 bench（評測題編號，例 Q01）")
    bench = load(os.path.join(DATA, "bench", task["bench"] + ".json"), "BenchMissing", "評測題")
    src = {k: bench.get(k) for k in ("place", "cast", "season", "time", "intent", "rank", "speaker")}   # 不拿 answer
else:
    src = task
for k, t in (("place", str), ("cast", list), ("rank", int)):
    if not isinstance(src.get(k), t):
        die("TaskBad", "缺 %s 或型別不對" % k)
if mode == "scene":
    if not isinstance(src.get("event"), str):
        die("TaskBad", "場景模式缺 event")
    lines = {"min_lines": src.get("min_lines", 5), "max_lines": src.get("max_lines", 10)}
    if not (isinstance(lines["min_lines"], int) and isinstance(lines["max_lines"], int)
            and 1 <= lines["min_lines"] <= lines["max_lines"]):
        die("TaskBad", "min_lines、max_lines 要是整數、1 ≤ min_lines ≤ max_lines")
else:
    lines = {"min_lines": 1, "max_lines": 1}
rank = str(src["rank"])

# 3. 卡片
address = load(os.path.join(DATA, "address.json"), "TaskBad", "稱謂階表")
forbidden = load(os.path.join(DATA, "forbidden.json"), "TaskBad", "禁語表")
styles = load(os.path.join(DATA, "styles.json"), "TaskBad", "語域表")
if rank not in address["ranks"]:
    die("TaskBad", "rank %s 不在稱謂階表裡（0～5）" % rank)
place = load(os.path.join(DATA, "places.json"), "TaskBad", "地點表").get(src["place"])
if not isinstance(place, dict):
    die("PlaceMissing", "找不到地點卡：%s" % src["place"])
cast = load(os.path.join(DATA, "cast.json"), "TaskBad", "人物表")
cards = []
for who in src["cast"]:
    if not isinstance(who, str) or "/" in who or who.startswith("."):
        die("TaskBad", "cast 裡要是人名字串")
    if not isinstance(cast.get(who), dict):
        die("CastMissing", "找不到人物卡：%s" % who)
    cards.append(cast[who])
lead = next((c for c in cards if c.get("display") == "主角"), None)
if mode == "fill":
    task_style = next((c.get("type") for c in cards if c.get("display") == src.get("speaker")), None)
else:
    task_style = next((c.get("type") for c in cards if c is not lead), None)


def higher(table):
    """比本場階更高的那幾階的字面（越階＝穿幫；退階可以，corpus 02）。"""
    return [w for r, ws_ in sorted(table.items()) if int(r) > int(rank) for w in ws_]


brief_cast, addr_rules, markers = [], {}, {}
for c in cards:
    one = {"name": c["display"], "type": c.get("type"), "voice": c.get("voice", []), "likes": c.get("likes", [])}
    if c.get("catchphrase"):
        one["catchphrase"] = c["catchphrase"]
    if c.get("habits"):
        one["habits"] = c["habits"]
    style = styles["types"].get(c.get("type"), {})
    if style.get("ng") or c.get("never"):
        one["never"] = c.get("never") or style.get("ng")
    if "calls_lead" in c:
        ok = c["calls_lead"].get(rank, [])
        one["calls_lead"] = ok[0] if ok else None
        addr_rules[c["display"]] = {"ok": ok, "bad": higher(c["calls_lead"])}
        if lead is not None and "called_by_lead" in c:
            ok2 = c["called_by_lead"].get(rank, [])
            prev = addr_rules.setdefault(lead["display"], {"ok": [], "bad": []})
            prev["ok"] += [w for w in ok2 if w not in prev["ok"]]
            prev["bad"] += [w for w in higher(c["called_by_lead"]) if w not in prev["bad"] and w not in ok2]
            one["called_by_lead"] = ok2[0] if ok2 else None
    if c.get("markers"):
        markers[c["display"]] = c["markers"]
    brief_cast.append(one)

samples = []
sample_table = load(os.path.join(DATA, "samples.json"), "TaskBad", "範例句表")
for c in cards:
    if c["name"] in sample_table:
        samples += sample_table[c["name"]]["lines"]

reg = address["ranks"][rank]["register"]
base = name[:-5] if name.endswith(".json") else name
brief = {"mode": mode, "name": base,
         "place": {"name": place["name"], "details": place.get("details", [])},
         "cast": brief_cast,
         "season": src.get("season"), "time": src.get("time"), "intent": src.get("intent"),
         "rank": int(rank), "register": {"name": reg, "how": address["registers"].get(reg)},
         **lines, "drafts": drafts, "samples": samples, "style": task_style}
if "writer" in task:
    brief["writer"] = task["writer"]
must, bonus = [], []
if mode == "fill":
    brief.update(bench=task["bench"], speaker=bench["speaker"], setting=bench.get("setting"), speaker_note=bench.get("speaker_note"),
                 context=bench["context"], must=bench["guard"]["must"])
    must, bonus = bench["guard"]["must"], bench["guard"].get("bonus", [])
else:
    brief["event"] = src["event"]
    brief["must"] = []

rules = {"mode": mode, **lines, "speakers": [c["display"] for c in cards],
         "speaker": brief.get("speaker"),
         "forbidden": [w for k in ("A", "B", "C") for w in forbidden[k]],
         "setting": forbidden["D"],
         "address": addr_rules, "markers": markers, "ng_marks": styles["ng_marks"],
         "must": must, "bonus": bonus, "max_line_chars": 60}

write_atomic(os.path.join(stack, "brief.json"), dump(brief))
write_atomic(os.path.join(stack, "rules.json"), dump(rules))
