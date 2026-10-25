# brain.py - think 格：認領題目（new/<n>.json＝稿紙＋打回理由）、渲染成一則 user 訊息、帶 $AOS_STACK/history.jsonl 問腦，回覆一行接進 history
# 照 demo/agent-dan/brain.py 改：題目是 JSON 不是純文字（render 那段）、假腦寫的是一段台詞（fake 那段）。其餘相同：
# 沒設 AOS_BRAIN_URL＝假腦；有設就問 OpenAI 相容的 {url}/chat/completions。失敗時 history 不接任何東西、退 1（P-20）。
# 測試用開關 GALTXT_FAKE_BAD_FIRST=1：假腦第 1 稿故意寫壞（叫錯名字、感嘆號、漏關鍵詞），讓 check 打回、第 2 稿才寫好——為了把重寫那條路跑一遍。
# 第 2 輪：題目多帶 plan（director 出的 beat 表，照表寫）；tools/lint（捷徑 → lib/lint）讓腦交稿前自檢——工具那段第 1 輪就留著，這裡不用改。
# 測試用開關 GALTXT_FAKE_LINT=1：假腦每稿先回一次 tool_calls 叫 lint、看到 tool 結果再交稿——把自檢那條路跑一遍。
# 每問一次腦（含假腦）在 $AOS_STACK/llm.jsonl 寫一行量測（record）。
import json, os, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone


def die(code, reason):
    print("writer: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")


def ls(d):
    try:
        return sorted((n for n in os.listdir(os.path.join(ws, d)) if not n.startswith(".") and n.endswith(".json")),
                      key=lambda n: (len(n), n))   # 1.json、2.json … 照數字序
    except FileNotFoundError:
        return []


names = ls("cur")
if not names:
    names = ls("new")
    if not names:
        die("QuestionMissing", "new/ 是空的")
    os.makedirs(os.path.join(ws, "cur"), exist_ok=True)
    os.replace(os.path.join(ws, "new", names[0]), os.path.join(ws, "cur", names[0]))
fname = names[0]
name = fname[:-len(".json")]
tmp = os.path.join(stack, ".current.txt")
with open(tmp, "w", encoding="utf-8") as f:
    f.write(name + "\n")
os.replace(tmp, os.path.join(stack, "current.txt"))
try:
    with open(os.path.join(ws, "cur", fname), encoding="utf-8") as f:
        question = json.load(f)
except ValueError as e:
    die("QuestionBad", "%s 不是 JSON：%s" % (fname, e))


def render(q):
    """稿紙 → 一則 user 訊息。第 1 稿送整份稿紙；第 2 稿起只送打回理由（稿紙已在 history 裡）。"""
    b, attempt, feedback = q["brief"], q.get("attempt", 1), q.get("feedback") or []
    if attempt > 1 and feedback:
        lines = ["第 %d 稿。上一稿被確定性檢核打回，理由：" % attempt]
        lines += ["- 第 %s 行「%s」：%s" % (v.get("line") or "-", (v.get("text") or "")[:30], v["reason"]) for v in feedback]
        lines.append("請照原來的稿紙重寫整段（格式同前，只輸出稿子本體）。")
        return "\n".join(lines)
    s = b["scene"]
    out = ["【任務】寫一小段 galgame 台詞：%d～%d 句台詞，可加少量旁白（最多 %d 行）。第 %d 稿。" % (
               b["lines"]["min"], b["lines"]["max"], b["lines"].get("narration_max", 4), attempt),
           "【你的題目檔】cur/%s.json（自檢時 lint 的 brief_path 寫 cur/%s.json#/brief）" % (name, name),
           "【場景】%s・%s・%s。%s" % (s.get("season", ""), s.get("time", ""), s.get("place", ""), s.get("summary", "")),
           "【事件】%s" % s.get("event", ""), "【意圖／風格】%s" % s.get("intent", ""), "【在場】"]
    for c in b["cast"]:
        v = c["voice"]
        out.append("- %s（%s）：%s" % (c["display"], "、".join(c["type"]), c["profile"]))
        out.append("  語氣：%s；句型：%s；小動作：%s" % (v.get("tone", ""), "、".join(v.get("patterns", [])), "、".join(v.get("habits", []))))
        if v.get("endings"):
            out.append("  句尾：%s；口頭禪（最多 %d 次）：%s" % ("、".join(v["endings"]), c["budget"].get("catchphrase_max", 1), "、".join(c.get("catchphrases", []))))
        out.append("  不可：%s" % "；".join(v.get("ng", [])))
        out.append("  叫%s：%s（階 %d）" % (c["address"]["other"], "／".join(c["address"]["allowed"]), c["address"]["level"]))
    p = b["place"]
    out += ["【地點硬設定・%s】%s" % (p["display"], "；".join(p["canon"])),
            "【可用道具】%s" % "、".join(p.get("hooks", [])),
            "【感官】%s" % "；".join("%s：%s" % (k, v) for k, v in p.get("senses", {}).items()),
            "【必須提到（每組擇一）】%s" % "；".join("／".join(g) if isinstance(g, list) else g for g in b.get("must_mention", [])),
            "【加分】%s" % "、".join(b.get("nice_to_mention", [])),
            "【開場（照用）】%s" % b.get("opener", ""), "【收尾（照用或改寫）】%s" % b.get("closer", ""),
            "【總則】" + "；".join(b.get("style_rules", []))]
    for x in b.get("samples") or []:                # 語料錨：別題的前後文，學語氣與節奏，不抄
        out += ["【語感參考（別的場景，不要照抄）】", x.get("text", "")]
    plan = q.get("plan") or {}
    if plan.get("beats"):
        out.append("【節拍表】照這張表寫，每拍一到兩句；who 是旁白的拍寫成（旁白）；must 裡的詞要在那一拍寫到：")
        for k, x in enumerate(plan["beats"], 1):
            out.append("%d. %s %s：%s%s" % (k, x.get("beat", ""), x.get("who", ""), x.get("do", ""),
                                            "（帶到：%s）" % "、".join(x["must"]) if x.get("must") else ""))
    return "\n".join(out)


# 對話：一行一則 OpenAI message（C-46），只附加；同一個小格裡第 2 稿接著第 1 稿聊
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


if not history or history[-1].get("role") not in ("user", "tool"):
    append({"role": "user", "content": render(question)})

tools = []                                       # 第 1 輪 writer 沒有工具；留著這段，之後掛 tools/<名>/tool.json 就能用（P-41）
for tool in (sorted(os.listdir("tools")) if os.path.isdir("tools") else []):
    try:
        with open(os.path.join("tools", tool, "tool.json"), encoding="utf-8") as f:
            spec = json.load(f)
    except (OSError, ValueError):
        continue
    if isinstance(spec, dict):
        function = {"name": tool}
        function.update({k: spec[k] for k in ("description", "parameters") if k in spec})
        tools.append({"type": "function", "function": function})

system = []
if os.path.exists("system.txt"):
    with open("system.txt", encoding="utf-8") as f:
        system = [{"role": "system", "content": f.read()}]


def fake():
    """假腦：照稿紙拼一段一定過得了 check 的稿（開場、關鍵詞、合階的叫法、收尾）；GALTXT_FAKE_BAD_FIRST=1 時第 1 稿故意寫壞。"""
    b, attempt = question["brief"], question.get("attempt", 1)
    hero = next(c for c in b["cast"] if c["role"] == "hero")
    her = next(c for c in b["cast"] if c["role"] != "hero")
    musts = [(g[0] if isinstance(g, list) else g) for g in b.get("must_mention", [])]
    nice = (b.get("nice_to_mention") or [""])[0]
    s = b["scene"]
    title = "【%s%s・%s】" % (s.get("season", ""), s.get("time", ""), s.get("place", ""))
    she_calls_him = her["address"]["allowed"][0].split("（")[0]    # 她的卡上 allowed＝「她叫主角」的叫法
    he_calls_her = hero["address"]["allowed"][0].split("（")[0]    # 主角的卡上 allowed＝「主角叫她」的叫法
    if os.environ.get("GALTXT_FAKE_LINT") == "1" and history[-1].get("role") == "user":   # 先自檢一次，看到 tool 結果再交
        good = fake_draft(b, s, title, hero, her, musts, nice, she_calls_him, he_calls_her)
        args = {"text": good["content"], "brief_path": "cur/%s.json#/brief" % name}
        return {"role": "assistant", "content": None,
                "tool_calls": [{"id": "fake_lint_%d" % attempt, "type": "function",
                                "function": {"name": "lint", "arguments": json.dumps(args, ensure_ascii=False)}}]}
    if os.environ.get("GALTXT_FAKE_BAD_FIRST") == "1" and attempt == 1:
        return {"role": "assistant", "content": "\n".join([
            title, "（假腦故意寫壞的第 1 稿：叫錯名字、感嘆號、沒提關鍵詞。）",
            "%s：「%s！你怎麼也在這！」" % (hero["display"], her["given"]),
            "%s：「%s！好巧！」" % (her["display"], hero["given"]),
            "%s：「心跳漏了一拍。」" % hero["display"],
            "%s：「……嗯。」" % her["display"],
            "%s：「走吧。」" % hero["display"]])}
    return fake_draft(b, s, title, hero, her, musts, nice, she_calls_him, he_calls_her)


def fake_draft(b, s, title, hero, her, musts, nice, she_calls_him, he_calls_her):
    lines = [title, b.get("opener", ""), "（假腦寫的稿：照稿紙拼的，不是真的創作。）",
             "%s：「啊，抱歉，妳先請。」" % hero["display"],
             "%s：「不……是我沒注意到。咦，%s？」" % (her["display"], she_calls_him),
             "%s：「%s？原來妳也會來這家店。」" % (hero["display"], he_calls_her),
             "%s：「嗯，因為這裡很安靜。你也在找%s嗎？」" % (her["display"], musts[0] if musts else "書"),
             "%s：「只是順路。剛好是%s。」" % (hero["display"], s.get("season", "今天")),
             "%s：「……這本，就%s%s吧。我下次再來，等爺爺蓋好%s的新書進來。」" % (her["display"], musts[1] if len(musts) > 1 else "讓給", she_calls_him, nice or "章"),
             "%s：「這怎麼好意思。」" % hero["display"],
             "%s：「沒什麼。……這句，很好。」" % her["display"],
             b.get("closer", "")]
    return {"role": "assistant", "content": "\n".join(l for l in lines if l)}


def record(asked_at, model, elapsed_ms, usage):
    """量測（round2 §4）：每問一次腦在自己的 stack 寫一行 llm.jsonl——實測寫 stack，絕不回寫 _metainfo（M7）。
    計數照 C-54 用 counter_*；API 回的 usage 原物件照原名放旁邊（外部欄位名照原名）。假腦也寫一行（model fake、計數全 0），形狀才一致。"""
    usage = usage if isinstance(usage, dict) else {}
    num = lambda k: usage.get(k) if isinstance(usage.get(k), int) else 0
    line = {"asked_at": asked_at, "model": model, "elapsed_ms": elapsed_ms,
            "counter_tokens_prompt": num("prompt_tokens"), "counter_tokens_completion": num("completion_tokens"),
            "counter_tokens": num("total_tokens") or num("prompt_tokens") + num("completion_tokens"), "usage": usage}
    with open(os.path.join(stack, "llm.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def ask(url):
    body = {"model": os.environ.get("AOS_BRAIN_MODEL") or "default", "messages": system + history}
    if tools:
        body["tools"] = tools
    headers = {"Content-Type": "application/json"}
    if os.environ.get("AOS_BRAIN_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["AOS_BRAIN_KEY"]
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions",
                                 json.dumps(body, ensure_ascii=False).encode("utf-8"), headers)
    asked_at, t0 = now_iso(), time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=170) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        die("BrainFailed", ("HTTP %d：%s" % (e.code, e.read()[:200].decode("utf-8", "replace"))).replace("\n", " "))
    except (urllib.error.URLError, OSError) as e:
        die("BrainFailed", ("%s 連不上或逾時：%s" % (url, getattr(e, "reason", e))).replace("\n", " "))
    try:
        reply = json.loads(raw)
        message = reply["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        die("ReplyBad", ("回覆不是 OpenAI 的形狀（%s: %s）" % (type(e).__name__, e)).replace("\n", " "))
    report, usage = os.environ.get("AOS_KERNEL_REPORT"), reply.get("usage")
    record(asked_at, reply.get("model") or body["model"], int((time.monotonic() - t0) * 1000), usage)
    if report and isinstance(usage, dict):           # 經 LLM kernel 跑時把 usage 交給它（P-23 註）
        tmp = os.path.join(os.path.dirname(report), "." + os.path.basename(report))
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(usage, f)
        os.replace(tmp, report)
    if not isinstance(message, dict):
        die("ReplyBad", "choices[0].message 不是物件")
    out = {"role": message.get("role") or "assistant", "content": message.get("content")}
    calls = message.get("tool_calls")
    if calls:
        if not isinstance(calls, list) or not all(isinstance(c, dict) for c in calls):
            die("ReplyBad", "tool_calls 不是物件的陣列")
        out["tool_calls"] = [{k: c[k] for k in ("id", "type", "function") if k in c} for c in calls]
    return out


url = os.environ.get("AOS_BRAIN_URL")
if url:
    append(ask(url))
else:
    record(now_iso(), "fake", 0, {})
    append(fake())
