# brain.py - think 格（抄 agent-dan）：認領題目、把 tools.json 登記的工具（aos-tools ls --json）組成 tools、帶 $AOS_STACK/history.jsonl 問腦，回覆一行接進 history
# 沒設 AOS_BRAIN_URL＝假腦（模板填槽：先叫 lint、再交稿）；有設就問 OpenAI 相容的 {url}/chat/completions。失敗時 history 不接任何東西、退 1（P-20）。
# 假腦技能表（第三輪，round3 § 6）：WEAK 裡的（模型標籤, 風格）＝這個假寫手寫這種風格會寫砸——女角那句句尾加 NG 標記「～～」（lint 扣 Tier 1）。
# 模型標籤從 AOS_BRAIN_MODEL 來（各寫手 .env）：含 sol＝"sol"，其餘＝""。表是劇本、不是品質證據；測試要換時設 GALTXT_FAKE_WEAK（「標籤:風格」逗號分隔，只有假腦讀）。
# 傲嬌另有一套模板（挖空、整場）；文靜／書卷的模板一字不動。
# GALTXT_FAKE_JITTER=1（第四輪，round4 § 10 測試 7；只有假腦讀）：第 n 個小格（$AOS_STACK 上一層的 runs/NNN）的草稿在最後一字前多「…」＋第 n 個天干，
# 讓「同輸入同角度」的幾份字面不同，驗「一致」的公式。（原本是 n 個「…」：「一致」量的是二元組「集合」，n ≥ 2 多出來的「……」本來就有、三份集合一樣 → 量不出差；步驟 3 改。）
# 第四輪步驟 3（round4 § 2.1、§ 2.2）：只列 stage.json 的 tools 裡的工具（沒有 stage.json＝全部）；假腦在 semi 階看得到 beat 時先叫 beat 一次。
# 第四輪步驟 6b（隊長裁定：假腦 agent 階預設就有抽樣差）：腦自己決定的環節（開場旁白、收尾旁白、挖空句的口氣）照「第幾次抽」挑說法（$AOS_STACK 上一層 runs/NNN 的 NNN；
# 第 n 次抽＝KEYS[(n−1) mod 3]），不照 hint——平常每份的 hint 剛好也是第 n 個角度，字面跟以前一字不差；同輸入同角度（hints_fixed 的 measure 題）三份才不一樣，
# 像真腦每次抽樣不同。GALTXT_FAKE_JITTER=0＝關（照 hint，同輸入同輸出）；=1＝再加上舊的句尾記號（測試 7、14 用）。
# 看得到 open／close 工具（selfopt 抽出來的）時先叫它、用它回的那行當開場／收尾旁白——那個環節交給工具＝不再隨抽樣變（確定性就是這樣升的）。
# 下面的 compose() 是寫手 program 階 compose.py 的第一版（compose.py 已照 data/templates.json 另寫；這裡留給 agent／semi 階的假腦用）。
# 跟範本不同的兩處：fake() 改寫；問真腦時把 API 回的 usage 多記一行到 $AOS_STACK/usage.jsonl（給實測對照用，OpenAI 的欄位名照留）。
import datetime, json, os, subprocess, sys, urllib.error, urllib.request


def die(code, reason):
    print("writer: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


def registered():
    """tools.json 登記的工具（aos-tools ls --json，cwd＝agent 資料夾；沒有 tools.json＝沒有工具），照名字排。
    aos-tools 起不來、退非 0（例：登記了但壞掉的工具）＝自己這層的錯：停、人修好再跑（P-20）；aos-tools 的 stderr 不吞，它自己說哪個工具壞。"""
    try:
        r = subprocess.run(["aos-tools", "ls", "--json"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)
    except OSError as e:
        die("ToolsBad", "aos-tools 起不來：%s" % e)
    if r.returncode != 0:
        die("ToolsBad", "aos-tools ls 退 %d" % r.returncode)
    return json.loads(r.stdout)


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

# 固化到哪階（round4 § 2.2）：有 stage.json＝腦只看得到 stage.tools 裡的工具；沒有（例：writer-sol）＝tools.json 登記的全部（原本的行為）。
# GALTXT_STAGE 蓋過 stage（同 _entry）；這支只會在 agent／semi 階跑到。
STAGE, ALLOWED = None, None
try:
    with open("stage.json", encoding="utf-8") as f:
        _st = json.load(f)
    STAGE, ALLOWED = _st.get("stage"), set(_st.get("tools") or [])
except FileNotFoundError:
    pass
except (OSError, ValueError, AttributeError, TypeError) as e:
    die("StateBad", "stage.json 讀不了：%s" % e)
STAGE = os.environ.get("GALTXT_STAGE") or STAGE
# optkit 自我優化模式（round4-selfopt.md § 2）：GALTXT_OPT=1（只有 optkit/run 設）＝多看得到 opt_*（tools.json 登記的 tools/opt_*，optkit 的捷徑）、system 換讀 system.opt.txt、
# 沒真腦時照 optkit/fake_opt.py 的劇本叫工具。平常（沒設）一字不變：opt_* 不在 stage.tools 裡＝看不到。
OPT = os.environ.get("GALTXT_OPT") == "1"
REGISTERED = registered()
if OPT and ALLOWED is not None:
    ALLOWED |= {t["name"] for t in REGISTERED if t["name"].startswith("opt_")}

# tools：工具清單來自 tools.json（aos-tools ls --json；10-28 aos-tools 起，沒有 tools.json＝沒有工具），說明取工具定義的 description／parameters（其他 key 忽略）
tools = []
for t in REGISTERED:
    if ALLOWED is not None and t["name"] not in ALLOWED:
        continue
    function = {"name": t["name"]}
    function.update({k: t["tooldef"][k] for k in ("description", "parameters") if k in t["tooldef"]})
    tools.append({"type": "function", "function": function})

system = []
SYSTEM = "system.opt.txt" if OPT else "system.txt"
if os.path.exists(SYSTEM):
    with open(SYSTEM, encoding="utf-8") as f:
        system = [{"role": "system", "content": f.read()}]   # 每次從檔讀，不存進 history

# 假腦的固定片語（確定性、不用亂數）：hint 不同就換開頭與旁白，三份草稿字面不同
OPEN = {"借景": "春天的光正好呢……既然這樣，", "動作": "嗯……既然這樣，", "留白": "……既然這樣，"}
SCENE_OPEN = {"借景": "（{place}。{detail}。）", "動作": "（{place}深處，兩人的手同時搭上同一本書。）", "留白": "（{place}。門鈴響過之後，只剩翻頁的聲音。）"}
SCENE_CLOSE = {"借景": "（百葉窗的光斜斜落在書背上。）", "動作": "（{heroine}把書輕輕推了過去。）", "留白": "（店裡又安靜下來。）"}
TSUN_OPEN = {"借景": "……哼，", "動作": "哼，", "留白": "……"}
KEYS = ["借景", "動作", "留白"]
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
        return "%s：「%s%s那樣啦。不過……%s接受，真是的。」" % (b.get("speaker") or heroine["name"], say(TSUN_OPEN, hint), deny, give)
    place = (b.get("place") or {}).get("name", "")
    details = (b.get("place") or {}).get("details") or [""]
    samples = [s for s in b.get("samples", []) if s.startswith(heroine["name"] + "：")]
    lines = [used("open") or say(SCENE_OPEN, hint).format(place=place, detail=details[min(1, len(details) - 1)]),
             "%s：「喂，%s。這個幫我拿一下。」" % (heroine["name"], calls),
             "%s：「又來了？%s，這次的理由是什麼？」" % (lead["name"], called or "妳"),
             "%s：「你手比較長。……哼，別、別誤會了。」" % heroine["name"],
             samples[0] if samples else "%s：「才不是特地等你的。」" % heroine["name"],
             "%s：「好好好，我拿就是了。」" % lead["name"],
             "%s：「……真是的，隨便你啦。」" % heroine["name"],
             used("close") or say(SCENE_CLOSE, hint).format(heroine=heroine["name"])]
    lo, hi = b.get("min_lines", 5), b.get("max_lines", 10)
    return "\n".join(lines[:max(lo, min(hi, len(lines)))])


def draw():
    """第幾次抽：$AOS_STACK 上一層 runs/NNN 的 NNN；拿不到＝None"""
    try:
        return int(os.path.basename(os.path.dirname(stack.rstrip("/"))))
    except ValueError:
        return None


def say(table, hint):
    """腦自己決定的環節挑哪個說法：預設照第幾次抽（KEYS[(n−1) mod 3]），GALTXT_FAKE_JITTER=0 或拿不到 n＝照 hint"""
    n = draw()
    if os.environ.get("GALTXT_FAKE_JITTER") == "0" or n is None:
        return table[hint]
    return table[KEYS[(n - 1) % len(KEYS)]]


def used(name):
    """這題裡叫過的工具 name 回的第一行（沒叫過、或回的是錯誤行＝None）：腦把那個環節交給工具，用它的輸出"""
    since = max((i for i, m in enumerate(history) if m.get("role") == "user"), default=0)
    ids = {c.get("id") for m in history[since:] for c in m.get("tool_calls") or [] if (c.get("function") or {}).get("name") == name}
    for m in history[since:]:
        if m.get("role") == "tool" and m.get("tool_call_id") in ids:
            line = (m.get("content") or "").strip().split("\n")[0].strip()
            return line if line and not line.startswith(name + ":") else None
    return None


def jitter(text):
    if os.environ.get("GALTXT_FAKE_JITTER") != "1" or not text:
        return text
    n = draw()
    if n is None:
        return text
    return text[:-1] + "…" + "甲乙丙丁戊己庚辛壬癸"[(n - 1) % 10] + text[-1]


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
        return "%s：「%s這本%s就%s%s吧。我下次再來呢。」" % (b.get("speaker") or heroine["name"], say(OPEN, hint), book, give, calls)
    place = (b.get("place") or {}).get("name", "")
    details = (b.get("place") or {}).get("details") or [""]
    samples = [s for s in b.get("samples", []) if s.startswith(heroine["name"] + "：")]
    lines = [say(SCENE_OPEN, hint).format(place=place, detail=details[min(1, len(details) - 1)]),
             "%s：「啊，抱歉，妳先請。」" % lead["name"],
             "%s：「不，是我沒注意到……咦，%s？」" % (heroine["name"], calls),
             "%s：「%s？原來妳也會來這裡。」" % (lead["name"], called or "是妳"),
             samples[0] if samples else "%s：「嗯，因為這裡很安靜呢。」" % heroine["name"],
             "%s：「只是突然想重溫。剛好是春天。」" % lead["name"],
             "%s：「既然這樣，這本就讓給%s吧。我下次再來呢。」" % (heroine["name"], calls),
             say(SCENE_CLOSE, hint).format(heroine=heroine["name"])]
    lo, hi = b.get("min_lines", 5), b.get("max_lines", 10)
    return "\n".join(lines[:max(lo, min(hi, len(lines)))])


def fake():
    """假腦的順序：整場題看得到 open／close（selfopt 抽的）＝先各叫一次、用它回的那行；semi 階而且看得到 beat＝先叫 beat 一次（三槽取自題目的 must，沒有就用通用的；回的句子不拿來用——只示範「腦叫工具」）；
    看得到 lint 而這題還沒叫過＝叫 lint；都叫過＝交稿。"""
    names = {t["function"]["name"] for t in tools}
    since = max((i for i, m in enumerate(history) if m.get("role") == "user"), default=0)
    called = {c["function"]["name"] for m in history[since:] for c in m.get("tool_calls") or []}

    def call(n, args):
        return {"role": "assistant", "content": None,
                "tool_calls": [{"id": "call_fake_%d" % (len(called) + 1), "type": "function",
                                "function": {"name": n, "arguments": json.dumps(args, ensure_ascii=False)}}]}
    if history[-1].get("role") in ("user", "tool"):
        try:
            b = json.loads(question)
        except ValueError:
            b = {}
        if b.get("mode") == "scene":                         # selfopt 抽出來的旁白工具：看得到就交給它（任何階；工具在 stage.tools 才看得到）
            for t in ("open", "close"):
                if t in names and t not in called:
                    heroine = next((c.get("name") for c in b.get("cast") or [] if c.get("name") != "主角"), "她")
                    return call(t, {"hint": b.get("hint"), "heroine": heroine, "place": (b.get("place") or {}).get("name", "")})
        if STAGE == "semi" and "beat" in names and "beat" not in called:
            try:
                must = json.loads(question).get("must") or []
            except (ValueError, AttributeError):
                must = []
            return call("beat", {"deny": must[0][0] if must else "才沒有",
                                 "yield": must[1][0] if len(must) > 1 else "也不是不能接受", "cover": "真是的"})
        if "lint" in names and "lint" not in called:
            return call("lint", {"text": draft()})
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
if OPT and not url:
    sys.dont_write_bytecode = True
    sys.path.insert(0, os.environ.get("OPTKIT_HOME") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "optkit"))
    import fake_opt  # noqa: E402
    append(fake_opt.step(history, tools))
else:
    append(fake() if not url else ask(url))
