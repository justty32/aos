#!/usr/bin/env python3
# brief - 認領一題（cur/ 有就接著做，沒有就把 new/ 第一題搬到 cur/），從 data/ 組出 $AOS_STACK/brief.json（給寫手看）與 rules.json（給 lint 用）
# 題目是 JSON：{"mode": "scene", place, cast, event, season, time, intent, rank, min_lines, max_lines, drafts} 或 {"mode": "fill", "bench": "Q01", drafts}。
# 挖空模式從 data/bench/<編號>.json 拿前後文與護欄關鍵詞，不拿 answer（正解只有 pick 讀）。
# 換了一題（current.txt 記的不是這題）時，先清掉上一題留在 stack 的 drafts/、checks.json、judge.json、route.json——不然 write、judge 會把舊的當成已做好。
# brief.json 多兩個 key 給 write 選寫手（第三輪）：style＝風格（挖空：說話者的人物卡 type；場景：第一個不是主角的卡司的 type），
# writer＝題目 JSON 有寫就照抄（題目級覆寫，write 那邊驗資料夾在不在）。
# 第四輪（round4 § 1.3、§ 4.2）：brief.json 多 detail（題目的小動作開關，沒有＝不帶）、hints_fixed（題目有才帶；write 照它讓每份同一角度、pick 照它算「一致」）；
# rules.json 多 switches（data/lint_switches.json 原樣）與 contrast（主角以外那位女角的風格在 styles.json 有 deny 表才有：
# {who, names（display＋short）, deny, yield, cover, reveal, ooc}，lint 拿來量反差、洩底、OocMark；沒有＝null）。
# 步驟 3b（round4-data.md § 3）：設定拆成有 id 的格（data/cast/yuzu.json、style/tsun.json、place/classroom.json、scene/closeup.json），
# 表裡那一項是 {"$ref"}——這裡解一層（cells.py），照舊組成 brief.json（給腦的字面、格式不變；格 id 不進 brief.json，省腦 token）。
# 場景條件：題目（或評測題）寫 scene（scene.closeup 或 closeup）就從那格補 place、cast、season、time、intent、rank（題目自己有寫的優先）；
# 場景題沒寫 event＝用 occasion＋detail 的 before／say／do 照固定句型渲染（有寫＝人的覆寫、照抄）；detail 不在 scene.detail＝DetailMissing（題目壞）。
# 挖空題 bench 有 scene 而沒有 setting／speaker_note＝setting 從 scene.setting＋mood、speaker_note 從說話者的 trait／bio＋scene.backstory＋bench.blank_note 渲染。
# rules.json（給 lint，腦看不到）多兩樣——contrast.cells：{deny|yield|cover|reveal|ooc|markers|calls: {字面: 格 id}, ng_marks: 格 id}（lint 回 hits 用）；
# 頂層 scene（場景格 id）與 cells_used（這題用到的格 id，排序）；沒用到任何格的題（晴子、Q01）rules.json 一字不變。
# 錯：stderr 一行「galtxt-a brief: 代號 原因」、退 1（QuestionMissing、TaskBad、CastMissing、PlaceMissing、BenchMissing、SceneMissing、DetailMissing、StackMissing）。
import json, os, shutil, sys

HERE = os.path.dirname(os.path.realpath(__file__))
DATA = os.path.join(HERE, "data")
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True                   # 樹裡不留 __pycache__（每個資料夾都要有 _metainfo）
import cells  # noqa: E402


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
    src = {k: bench.get(k) for k in ("place", "cast", "season", "time", "intent", "rank", "speaker", "scene")   # 不拿 answer
           if k in bench}
else:
    src = dict(task)
used = set()                                     # 這題用到的格 id（進 rules.json 的 cells_used）
scene_id, scene = src.get("scene"), None
if scene_id is not None:
    if not isinstance(scene_id, str) or not scene_id:
        die("TaskBad", "scene 要是場景格 id（例 scene.closeup）")
    scene_id = scene_id if scene_id.startswith("scene.") else "scene." + scene_id
    try:
        scene = cells.resolve(scene_id)[2]
        place_card = cells.resolve(scene["place"])[2]
    except (cells.CellMissing, cells.RefBad, KeyError, TypeError, OSError, ValueError) as e:
        die("SceneMissing", "場景格解不到：%s（%s）" % (scene_id, e))
    fill_in = {"place": place_card.get("name"), "cast": scene.get("cast"), "rank": scene.get("rank"),
               "season": (scene.get("when") or {}).get("season"), "time": (scene.get("when") or {}).get("time"),
               "intent": cells.text(scene["intent"]) if "intent" in scene else None}
    for k, v in fill_in.items():
        if src.get(k) is None and v is not None:
            src[k] = v
    used.update(i for i in ("%s.intent" % scene_id,) if "intent" in scene)
for k, t in (("place", str), ("cast", list), ("rank", int)):
    if not isinstance(src.get(k), t):
        die("TaskBad", "缺 %s 或型別不對" % k)
if mode == "scene":
    if not isinstance(src.get("event"), str) and not (scene and isinstance(task.get("detail"), str)):
        die("TaskBad", "場景模式缺 event（或 scene＋detail）")
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


def deref(obj, code, what):
    """表裡的 {"$ref": "cast/yuzu.json"} 解一層，回 (內容, 格 id 前綴 或 None)"""
    if not (isinstance(obj, dict) and "$ref" in obj):
        return obj, None
    try:
        got = cells.load_ref(obj)
    except (cells.RefBad, OSError, ValueError) as e:
        die(code, "%s的 $ref 解不了：%s" % (what, e))
    rel = obj["$ref"][:-5] if obj["$ref"].endswith(".json") else obj["$ref"]
    return got, rel.replace("/", ".")


def tab(c, cid, key):
    """拆格的卡的一張表 → [(格 id, 格)]（照 id 序、跳過退役的）"""
    return [("%s.%s.%s" % (cid, key, k), v) for k, v in cells.kids(c.get(key))]


def render_card(c, cid):
    """拆格的人物卡渲染回舊卡的形狀（brief 給腦的字面一字不變）；另回 {類: {字面: 格 id}} 給 lint 的 hits"""
    if cid is None:
        return c, {}
    out = {k: c[k] for k in ("name", "display", "short", "type") if k in c}
    out["voice"] = [v["text"] for _, v in tab(c, cid, "trait")]
    tics = tab(c, cid, "tic")
    out["catchphrase"] = "／".join(v["text"] for _, v in tics)
    groups = {}
    for _, v in tab(c, cid, "gesture"):
        groups.setdefault(v.get("habit", v["text"]), []).append(v["text"])
    out["habits"] = ["、".join(g) for g in groups.values()]
    out["markers"] = [cells.marker(v) for _, v in tics]
    out["never"] = [v["text"] for _, v in tab(c, cid, "ng")]
    for key in ("calls_lead", "called_by_lead"):
        if key in c:
            out[key] = {r.lstrip("r"): [v["text"] for _, v in cells.kids(t)] for r, t in cells.kids(c[key])}
    calls = {cells.text(v): "%s.calls_lead.r%s.%s" % (cid, rank, k) for k, v in cells.kids((c.get("calls_lead") or {}).get("r" + rank))}
    ids = {"markers": {cells.marker(v): i for i, v in tics}, "calls": calls,
           "reveal": {cells.marker(v): i for i, v in tab(c, cid, "gesture") if v.get("reveal")}}
    used.update(i for k in ("trait", "tic", "gesture", "ng") for i, _ in tab(c, cid, k))
    used.update(calls.values())
    out["_cid"] = cid
    return out, ids


def render_style(s, sid):
    """拆格的風格表渲染回舊的陣列（每格取 marker）；另回 {類: {字面: 格 id}}"""
    if sid is None:
        return s, {}
    out, ids = dict(s), {}
    for key in ("deny", "yield", "cover", "reveal", "ooc", "ending", "ng"):
        rows = tab(s, sid, key)
        out[key] = [cells.marker(v) for _, v in rows]
        ids[key] = {cells.marker(v): i for i, v in rows}
    out["endings"] = out.pop("ending")
    return out, ids


place, pid = deref(load(os.path.join(DATA, "places.json"), "TaskBad", "地點表").get(src["place"]), "PlaceMissing", "地點卡")
if not isinstance(place, dict):
    die("PlaceMissing", "找不到地點卡：%s" % src["place"])
if pid is not None:
    facts = tab(place, pid, "fact")
    states = tab(scene, scene_id, "state") if scene else []
    place = {"name": place["name"], "details": [v["text"] for _, v in facts + states]}
    used.update(i for i, _ in facts + states)
cast = load(os.path.join(DATA, "cast.json"), "TaskBad", "人物表")
cards, card_ids = [], {}
for who in src["cast"]:
    if not isinstance(who, str) or "/" in who or who.startswith("."):
        die("TaskBad", "cast 裡要是人名字串")
    if not isinstance(cast.get(who), dict):
        die("CastMissing", "找不到人物卡：%s" % who)
    one, ids = render_card(*deref(cast[who], "CastMissing", "人物卡 %s " % who))
    cards.append(one)
    card_ids[one["display"]] = ids
lead = next((c for c in cards if c.get("display") == "主角"), None)
if mode == "fill":
    hero = next((c for c in cards if c.get("display") == src.get("speaker")), None)
else:
    hero = next((c for c in cards if c is not lead), None)
task_style = hero.get("type") if hero else None


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
    style = render_style(*deref(styles["types"].get(c.get("type"), {}), "TaskBad", "語域表"))[0]
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
if task.get("detail") is not None:
    if not isinstance(task["detail"], str):
        die("TaskBad", "detail 要是字串（小動作開關，例 ribbon）")
    brief["detail"] = task["detail"]
if task.get("hints_fixed"):
    brief["hints_fixed"] = True
must, bonus = [], []
detail_id = None
if scene and isinstance(task.get("detail"), str):
    detail_id = "%s.detail.%s" % (scene_id, task["detail"])
    d = (scene.get("detail") or {}).get(task["detail"])
    if not isinstance(d, dict):
        die("DetailMissing", "%s 沒有這個小動作：%s" % (scene_id, task["detail"]))
    used.add(detail_id)
if mode == "fill":
    setting, note = bench.get("setting"), bench.get("speaker_note")
    if scene and setting is None and "setting" in scene:
        moods = tab(scene, scene_id, "mood")
        setting = cells.text(scene["setting"]) + "氛圍：" + "、".join(v["text"] for _, v in moods) + "。"
        used.update(["%s.setting" % scene_id] + [i for i, _ in moods])
    if scene and note is None and hero is not None and hero.get("_cid"):
        raw = cells.resolve(hero["_cid"])[2]
        bio, back = tab(raw, hero["_cid"], "bio"), tab(scene, scene_id, "backstory")
        note = "%s——%s（%s）。%s" % (hero["display"], "、".join(hero["voice"]), "；".join(
            x for x in ("、".join(v["text"] for _, v in bio), "、".join(v["text"] for _, v in back)) if x), bench.get("blank_note", ""))
        used.update(i for i, _ in bio + back)
    must = cells.must_groups(bench["guard"]["must"])
    brief.update(bench=task["bench"], speaker=bench["speaker"], setting=setting, speaker_note=note,
                 context=bench["context"], must=must)
    bonus = bench["guard"].get("bonus", [])
else:
    if isinstance(src.get("event"), str):
        brief["event"] = src["event"]
    else:                                        # 渲染：「<occasion>：<before><她的短名><say>，<do>」
        brief["event"] = "%s：%s%s%s，%s" % (cells.text(scene["occasion"]), d.get("before", ""),
                                            (hero or {}).get("short") or (hero or {}).get("display", ""), d["say"], d["do"])
        used.add("%s.occasion" % scene_id)
    brief["must"] = []

rules = {"mode": mode, **lines, "speakers": [c["display"] for c in cards],
         "speaker": brief.get("speaker"),
         "forbidden": [w for k in ("A", "B", "C") for w in forbidden[k]],
         "setting": forbidden["D"],
         "address": addr_rules, "markers": markers, "ng_marks": styles["ng_marks"],
         "must": must, "bonus": bonus, "max_line_chars": 60}
switches = load(os.path.join(DATA, "lint_switches.json"), "TaskBad", "lint 開關表")
rules["switches"] = {k: v for k, v in switches.items() if k != "source"}
hero_style, style_ids = render_style(*deref(styles["types"].get(task_style, {}), "TaskBad", "語域表")) if hero else ({}, {})
rules["contrast"] = None
if hero_style.get("deny"):
    rules["contrast"] = {"who": hero["display"], "names": [n for n in (hero["display"], hero.get("short")) if n],
                         **{k: hero_style.get(k, []) for k in ("deny", "yield", "cover", "reveal", "ooc")}}
    hids = card_ids.get(hero["display"]) or {}
    if style_ids or hids:                        # 有拆格：洩底字＝她自己的小動作（reveal 的）＋這型的通用洩底字；字面 → 格 id
        rules["contrast"]["reveal"] = list(hids.get("reveal", {})) + [w for w in hero_style.get("reveal", []) if w not in hids.get("reveal", {})]
        table = {k: dict(style_ids.get(k, {})) for k in ("deny", "yield", "cover", "ooc")}
        table["reveal"] = dict(hids.get("reveal", {}), **style_ids.get("reveal", {}))
        table["markers"], table["calls"] = hids.get("markers", {}), hids.get("calls", {})
        rules["contrast"]["cells"] = dict(table, ng_marks="styles.ng_marks")
        if hero.get("_cid"):
            rules["contrast"]["card"] = hero["_cid"]      # 她的人物卡格 id（compose 從 <card>.tic.* 拿口癖）
        used.update(i for k in ("deny", "yield", "cover", "reveal", "ooc", "ng") for i in style_ids.get(k, {}).values())
if scene_id:
    rules["scene"] = scene_id
if used:
    rules["cells_used"] = sorted(used)

write_atomic(os.path.join(stack, "brief.json"), dump(brief))
write_atomic(os.path.join(stack, "rules.json"), dump(rules))
