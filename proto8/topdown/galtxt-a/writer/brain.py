# brain.py - think 格（抄 agent-dan）：認領題目、把 tools/*/tool.json 組成 tools、帶 $AOS_STACK/history.jsonl 問腦，回覆一行接進 history
# 沒設 AOS_BRAIN_URL＝假腦（模板填槽：先叫 lint、再交稿）；有設就問 OpenAI 相容的 {url}/chat/completions。失敗時 history 不接任何東西、退 1（P-20）。
# 假腦技能表（第三輪，round3 § 6）：WEAK 裡的（模型標籤, 風格）＝這個假寫手寫這種風格會寫砸——女角那句句尾加 NG 標記「～～」（lint 扣 Tier 1）。
# 模型標籤從 AOS_BRAIN_MODEL 來（各寫手 .env）：含 sol＝"sol"，其餘＝""。表是劇本、不是品質證據；測試要換時設 GALTXT_FAKE_WEAK（「標籤:風格」逗號分隔，只有假腦讀）。
# 傲嬌另有一套模板（挖空、整場）；文靜／書卷的模板一字不動。
# GALTXT_FAKE_JITTER=1（第四輪，round4 § 10 測試 7；只有假腦讀）：第 n 個小格（$AOS_STACK 上一層的 runs/NNN）的草稿在最後一字前多 n 個「…」，
# 讓「同輸入同角度」的幾份字面不同，驗「一致」的公式。
# 跟範本不同的兩處：fake() 改寫；問真腦時把 API 回的 usage 多記一行到 $AOS_STACK/usage.jsonl（給實測對照用，OpenAI 的欄位名照留）。
import datetime, json, os, sys, urllib.error, urllib.request


def die(code, reason):
    print("writer: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")


def ls(d):
    try:
        return sorted(n for n in os.listdir(os.path.join(ws, d)) if not n.startswith("."))   # . 開頭＝別人寫到一半的暫存檔（N-05），不撿
    except FileNotFoundError:
        return []


# 認領題目：cur/ 有上次認領沒做完的先接著做，沒有就把 new/ 第一題搬到 cur/
names = ls("cur")
if not names:
    names = ls("new")
    if not names:
        die("QuestionMissing", "new/ 是空的")
    os.makedirs(os.path.join(ws, "cur"), exist_ok=True)
    os.replace(os.path.join(ws, "new", names[0]), os.path.join(ws, "cur", names[0]))
name = names[0]
tmp = os.path.join(stack, ".current.txt")       # N-05：先寫 . 開頭的暫存檔再改名
with open(tmp, "w", encoding="utf-8") as f:
    f.write(name + "\n")
os.replace(tmp, os.path.join(stack, "current.txt"))
with open(os.path.join(ws, "cur", name), encoding="utf-8") as f:
    question = f.read()

# 對話：一行一則 OpenAI message（C-46），只附加
history_path = os.path.join(stack, "history.jsonl")
history = []
try:
    with open(history_path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.strip():
                try:
                    history.append(json.loads(line))
                except ValueError as e:
                    die("HistoryBad", "history.jsonl 第 %d 行不是 JSON：%s" % (n, e))
except FileNotFoundError:
    pass


def append(message):
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")
    history.append(message)


# 最後一則不是 user／tool（空的、或上一題已答完）才接題目；腦失敗後重跑時不會重複接
if not history or history[-1].get("role") not in ("user", "tool"):
    append({"role": "user", "content": question})

# tools：工具名＝資料夾名，說明來自 tool.json 的 description／parameters（其他 key 忽略；讀不懂的 tool.json 當作沒有）
tools = []
for tool in (sorted(os.listdir("tools")) if os.path.isdir("tools") else []):
    try:
        with open(os.path.join("tools", tool, "tool.json"), encoding="utf-8") as f:
            spec = json.load(f)
    except (OSError, ValueError):
        continue
    if not isinstance(spec, dict):
        continue
    function = {"name": tool}
    function.update({k: spec[k] for k in ("description", "parameters") if k in spec})
    tools.append({"type": "function", "function": function})

system = []
if os.path.exists("system.txt"):
    with open("system.txt", encoding="utf-8") as f:
        system = [{"role": "system", "content": f.read()}]   # 每次從檔讀，不存進 history

# 假腦的固定片語（確定性、不用亂數）：hint 不同就換開頭與旁白，三份草稿字面不同
OPEN = {"借景": "春天的光正好呢……既然這樣，", "動作": "嗯……既然這樣，", "留白": "……既然這樣，"}
SCENE_OPEN = {"借景": "（{place}。{detail}。）", "動作": "（{place}深處，兩人的手同時搭上同一本書。）", "留白": "（{place}。門鈴響過之後，只剩翻頁的聲音。）"}
SCENE_CLOSE = {"借景": "（百葉窗的光斜斜落在書背上。）", "動作": "（{heroine}把書輕輕推了過去。）", "留白": "（店裡又安靜下來。）"}
TSUN_OPEN = {"借景": "……哼，", "動作": "哼，", "留白": "……"}
WEAK = {("", "傲嬌")}
if os.environ.get("GALTXT_FAKE_WEAK") is not None:
    WEAK = {tuple(x.split(":", 1)) for x in os.environ["GALTXT_FAKE_WEAK"].split(",") if ":" in x}
TAG = "sol" if "sol" in (os.environ.get("AOS_BRAIN_MODEL") or "") else ""


def weak(text, style):
    """技能表裡有（這個模型, 這種風格）＝在最後一句女角台詞的句尾加「～～」"""
    if (TAG, style) not in WEAK:
        return text
    lines = text.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].endswith("」") and not lines[i].startswith("主角："):
            lines[i] = lines[i][:-1] + "～～」"
            break
    return "\n".join(lines)


def tsun(b, hint, lead, heroine, calls, called, must):
    """傲嬌的模板：先否認、再讓步、補一句遮掩（corpus/固化/01 § 1）"""
    if b.get("mode") == "fill":
        deny = must[0][0] if must and hint != "留白" else "也沒有"
        give = must[1][0] if len(must) > 1 else "也不是不能"
        return "%s：「%s%s那樣啦。不過……%s接受，真是的。」" % (b.get("speaker") or heroine["name"], TSUN_OPEN[hint], deny, give)
    place = (b.get("place") or {}).get("name", "")
    details = (b.get("place") or {}).get("details") or [""]
    samples = [s for s in b.get("samples", []) if s.startswith(heroine["name"] + "：")]
    lines = [SCENE_OPEN[hint].format(place=place, detail=details[min(1, len(details) - 1)]),
             "%s：「喂，%s。這個幫我拿一下。」" % (heroine["name"], calls),
             "%s：「又來了？%s，這次的理由是什麼？」" % (lead["name"], called or "妳"),
             "%s：「你手比較長。……哼，別、別誤會了。」" % heroine["name"],
             samples[0] if samples else "%s：「才不是特地等你的。」" % heroine["name"],
             "%s：「好好好，我拿就是了。」" % lead["name"],
             "%s：「……真是的，隨便你啦。」" % heroine["name"],
             SCENE_CLOSE[hint].format(heroine=heroine["name"])]
    lo, hi = b.get("min_lines", 5), b.get("max_lines", 10)
    return "\n".join(lines[:max(lo, min(hi, len(lines)))])


def jitter(text):
    if os.environ.get("GALTXT_FAKE_JITTER") != "1" or not text:
        return text
    try:
        n = int(os.path.basename(os.path.dirname(stack.rstrip("/"))))
    except ValueError:
        return text
    return text[:-1] + "…" * n + text[-1]


def draft():
    """compose() 的結果過一次假腦技能表（風格＝brief 的 style）"""
    try:
        style = json.loads(question).get("style")
    except (ValueError, AttributeError):
        style = None
    return jitter(weak(compose(), style))


def compose():
    """固化階梯第 3 級：模板＋槽填充，用 brief 裡的東西組一份台詞。挖空模式第 3 個角度（留白）刻意漏掉第一組必要關鍵詞。"""
    try:
        b = json.loads(question)
    except ValueError:
        return "（題目不是 JSON）"
    hint = b.get("hint") if b.get("hint") in OPEN else "借景"
    cast = b.get("cast") or []
    lead = next((c for c in cast if c.get("name") == "主角"), {"name": "主角"})
    heroine = next((c for c in cast if c is not lead), {"name": b.get("speaker") or "她"})
    calls = heroine.get("calls_lead") or "你"
    called = heroine.get("called_by_lead") or ""
    must = b.get("must") or []
    if heroine.get("type") == "傲嬌":
        return tsun(b, hint, lead, heroine, calls, called, must)
    if b.get("mode") == "fill":
        book = "《%s》" % must[0][0] if must and hint != "留白" else "書"
        give = must[1][0] if len(must) > 1 else "讓給"
        return "%s：「%s這本%s就%s%s吧。我下次再來呢。」" % (b.get("speaker") or heroine["name"], OPEN[hint], book, give, calls)
    place = (b.get("place") or {}).get("name", "")
    details = (b.get("place") or {}).get("details") or [""]
    samples = [s for s in b.get("samples", []) if s.startswith(heroine["name"] + "：")]
    lines = [SCENE_OPEN[hint].format(place=place, detail=details[min(1, len(details) - 1)]),
             "%s：「啊，抱歉，妳先請。」" % lead["name"],
             "%s：「不，是我沒注意到……咦，%s？」" % (heroine["name"], calls),
             "%s：「%s？原來妳也會來這裡。」" % (lead["name"], called or "是妳"),
             samples[0] if samples else "%s：「嗯，因為這裡很安靜呢。」" % heroine["name"],
             "%s：「只是突然想重溫。剛好是春天。」" % lead["name"],
             "%s：「既然這樣，這本就讓給%s吧。我下次再來呢。」" % (heroine["name"], calls),
             SCENE_CLOSE[hint].format(heroine=heroine["name"])]
    lo, hi = b.get("min_lines", 5), b.get("max_lines", 10)
    return "\n".join(lines[:max(lo, min(hi, len(lines)))])


def fake():
    last = history[-1]
    if last.get("role") == "user" and any(t["function"]["name"] == "lint" for t in tools):
        return {"role": "assistant", "content": None,
                "tool_calls": [{"id": "call_fake_1", "type": "function",
                                "function": {"name": "lint", "arguments": json.dumps({"text": draft()}, ensure_ascii=False)}}]}
    return {"role": "assistant", "content": draft()}


def ask(url):
    body = {"model": os.environ.get("AOS_BRAIN_MODEL") or "default", "messages": system + history}
    if tools:
        body["tools"] = tools
    headers = {"Content-Type": "application/json"}
    if os.environ.get("AOS_BRAIN_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["AOS_BRAIN_KEY"]
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions",
                                 json.dumps(body, ensure_ascii=False).encode("utf-8"), headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read()[:200].decode("utf-8", "replace")
        die("BrainFailed", ("HTTP %d：%s" % (e.code, detail)).replace("\n", " "))
    except (urllib.error.URLError, OSError) as e:     # 連不上、逾時（TimeoutError 是 OSError）
        die("BrainFailed", ("%s 連不上或逾時：%s" % (url, getattr(e, "reason", e))).replace("\n", " "))
    try:
        message = json.loads(raw)["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        die("ReplyBad", ("回覆不是 OpenAI 的形狀（%s: %s）" % (type(e).__name__, e)).replace("\n", " "))
    report, usage = os.environ.get("AOS_KERNEL_REPORT"), json.loads(raw).get("usage")
    if report and isinstance(usage, dict):           # 經 LLM kernel 跑時把 API 回的 usage 交給它（P-23 註；不寫＝kernel 只算次數）
        tmp = os.path.join(os.path.dirname(report), "." + os.path.basename(report))   # N-05：先寫暫存再改名
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(usage, f)
        os.replace(tmp, report)
    if isinstance(usage, dict):                      # 實測用：每次回覆一行，OpenAI usage 原名照留
        at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        with open(os.path.join(stack, "usage.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(dict({"recorded_at": at}, **usage), ensure_ascii=False) + "\n")
    if not isinstance(message, dict):
        die("ReplyBad", "choices[0].message 不是物件")
    out = {"role": message.get("role") or "assistant", "content": message.get("content")}
    calls = message.get("tool_calls")
    if calls:
        if not isinstance(calls, list) or not all(isinstance(c, dict) for c in calls):
            die("ReplyBad", "tool_calls 不是物件的陣列")
        out["tool_calls"] = [{k: c[k] for k in ("id", "type", "function") if k in c} for c in calls]
    return out                                       # 只留 role、content、tool_calls（模型想的內容不收，P-23）


url = os.environ.get("AOS_BRAIN_URL")
append(fake() if not url else ask(url))
