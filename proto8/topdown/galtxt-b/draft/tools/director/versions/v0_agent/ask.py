# ask.py - director 的單發腦函數（round3 收攏：原 loop→fsm idle→think→act 縮成這一支，grow_level 4）：
#   認領題目 new/<n>.json → 渲染成一則 user 訊息、帶 $AOS_STACK/history.jsonl 問腦一次、回覆接進 history → 寫答案 out/<n>.txt、題目 cur/→done/。
#   同一個小格再叫＝history 最後一則是 assistant，接新的 user 再問（續聊）。失敗（BrainFailed、ReplyBad…）＝退 1、不寫答案；重跑＝整個再問一次（interrupt safe）。
# 前半照原 brain.py 原樣搬（下面幾行是它原來的頭註解），後半照原 act.py（「act 那段」以下）。
# 原 brain.py：brain.py - think 格：認領題目（new/<n>.json＝稿紙＋plan_lint 的理由）、渲染成一則 user 訊息、帶 $AOS_STACK/history.jsonl 問腦，回覆（beat 表 JSON）一行接進 history
# 原 brain.py：照 judge/tools/critic/brain.py 複製（沒有工具），只改 render（送場景、人物一句、beat 文法、必提關鍵詞；第 2 次只送理由＝續聊）與 fake（照稿紙拼一張合文法的表）。
# 原 brain.py：測試用開關 GALTXT_FAKE_BAD_PLAN=n：假腦前 n 次故意回缺 B0 的表，讓 plan_lint 打回（n≥2＝draft 停在 PlanBad 等人）。
# 原 brain.py：每問一次腦（含假腦）在 $AOS_STACK/llm.jsonl 寫一行量測（record）。
import json, os, shutil, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone


def die(code, reason):
    print("director: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")


def ls(d):
    try:
        return sorted((n for n in os.listdir(os.path.join(ws, d)) if not n.startswith(".") and n.endswith(".json")),
                      key=lambda n: (len(n), n))
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
    """稿紙 → 一則 user 訊息。第 1 次送場景與 beat 文法；之後只送 plan_lint 的理由（稿紙已在 history 裡）。"""
    b, attempt, feedback = q["brief"], q.get("attempt", 1), q.get("feedback") or []
    if attempt > 1 and feedback:
        out = ["第 %d 次。上一張 beat 表沒過文法校驗，理由：" % attempt]
        out += ["- %s" % v.get("reason", "") for v in feedback]
        out.append("請照原來的稿紙重出整張表（只輸出 JSON）。")
        return "\n".join(out)
    s, t = b["scene"], b.get("beats") or {}
    out = ["【任務】幫這段 galgame 台詞排節拍：出一張 beat 表（%d～%d 拍）。" % (t.get("min_beats", 5), t.get("max_beats", 10)),
           "【場景】%s・%s・%s。%s" % (s.get("season", ""), s.get("time", ""), s.get("place", ""), s.get("summary", "")),
           "【事件】%s" % s.get("event", ""), "【意圖】%s" % s.get("intent", ""),
           "【在場】" + "；".join("%s（%s）：%s" % (c["display"], "、".join(c["type"]), c["voice"].get("tone", "")) for c in b["cast"]),
           "【地點】%s：%s" % (b["place"]["display"], "；".join(b["place"].get("canon", [])[:4])),
           "【必須提到（每組擇一，分到某一拍的 must）】%s" % "；".join("／".join(g) if isinstance(g, list) else g for g in b.get("must_mention", [])),
           "【beat 清單】"]
    out += ["- %s %s（%s）：%s" % (x["beat"], x["name"], "必要" if x.get("required") else "可省", x["content"]) for x in t.get("beats", [])]
    out += ["【文法】%s" % t.get("grammar", ""), "【約束】" + "；".join(t.get("constraints", [])),
            "【輸出】只輸出一份 JSON：{\"beats\": [{\"beat\": \"B0\", \"who\": \"旁白\", \"do\": \"這一拍做什麼（一句）\", \"must\": []}, ...]}；"
            "who 只能是 %s 或「旁白」；連著同一個 beat 名可以有好幾拍（例 B3 兩人各一拍）。" % "、".join(c["display"] for c in b["cast"])]
    return "\n".join(out)


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

system = []
if os.path.exists("system.txt"):
    with open("system.txt", encoding="utf-8") as f:
        system = [{"role": "system", "content": f.read()}]


def fake():
    """假腦：照稿紙拼一張合文法的表（B0 B1 B2 B3×2 B4 B5 B6 B7），必提各組的第一個詞分到 B1／B4；GALTXT_FAKE_BAD_PLAN=n 時前 n 次缺 B0。"""
    b, attempt = question["brief"], question.get("attempt", 1)
    hero = next(c["display"] for c in b["cast"] if c["role"] == "hero")
    her = next(c["display"] for c in b["cast"] if c["role"] != "hero")
    musts = [(g[0] if isinstance(g, list) else g) for g in b.get("must_mention", [])]
    beats = [{"beat": "B0", "who": "旁白", "do": "門鈴＋舊紙的味道，建立涼、靜、舊", "must": []},
             {"beat": "B1", "who": "旁白", "do": "兩人同時伸手拿同一本書", "must": musts[:1]},
             {"beat": "B2", "who": hero, "do": "先讓：妳先請", "must": []},
             {"beat": "B3", "who": her, "do": "為什麼來這裡：因為安靜", "must": []},
             {"beat": "B3", "who": hero, "do": "只是順路", "must": []},
             {"beat": "B4", "who": her, "do": "把書讓出去、說下次再來", "must": musts[1:]},
             {"beat": "B5", "who": her, "do": "表面：沒什麼；洩底：手指沿書背滑一遍", "must": []},
             {"beat": "B6", "who": "旁白", "do": "爺爺蓋梅花章", "must": []},
             {"beat": "B7", "who": "旁白", "do": "光退回去，定格", "must": []}]
    if attempt <= int(os.environ.get("GALTXT_FAKE_BAD_PLAN") or 0):
        beats = beats[1:]                        # 故意缺 B0
    return {"role": "assistant", "content": json.dumps({"beats": beats}, ensure_ascii=False)}


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
    headers = {"Content-Type": "application/json"}
    if os.environ.get("AOS_BRAIN_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["AOS_BRAIN_KEY"]
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions",
                                 json.dumps(body, ensure_ascii=False).encode("utf-8"), headers)
    asked_at, t0 = now_iso(), time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=110) as r:
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
    if report and isinstance(usage, dict):
        tmp = os.path.join(os.path.dirname(report), "." + os.path.basename(report))
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(usage, f)
        os.replace(tmp, report)
    if not isinstance(message, dict):
        die("ReplyBad", "choices[0].message 不是物件")
    return {"role": message.get("role") or "assistant", "content": message.get("content")}


url = os.environ.get("AOS_BRAIN_URL")
if url:
    append(ask(url))
else:
    record(now_iso(), "fake", 0, {})
    append(fake())


# ── act 那段（原 act.py）：把腦的最後一則回覆（content）寫成答案 out/<n>.txt、題目 cur/→done/
said = next((m for m in reversed(history) if isinstance(m, dict) and m.get("role") == "assistant"), None)
if said is None:
    die("HistoryBad", "history.jsonl 裡沒有 assistant 的訊息")
if said.get("tool_calls"):
    die("ReplyBad", "director 不該叫工具，腦卻回了 tool_calls")
content = said.get("content") or ""
if not content.endswith("\n"):
    content += "\n"
os.makedirs(os.path.join(ws, "out"), exist_ok=True)
os.makedirs(os.path.join(ws, "done"), exist_ok=True)
tmp = os.path.join(ws, "out", "." + name + ".txt")
with open(tmp, "w", encoding="utf-8") as f:
    f.write(content)
os.replace(tmp, os.path.join(ws, "out", name + ".txt"))
shutil.move(os.path.join(ws, "cur", fname), os.path.join(ws, "done", fname))
