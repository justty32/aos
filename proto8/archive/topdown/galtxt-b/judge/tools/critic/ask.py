# ask.py - critic 的單發腦函數（round3 收攏：原 loop→fsm idle→think→act 縮成這一支，grow_level 4）：
#   認領題目 new/<n>.json → 渲染成一則 user 訊息、帶 $AOS_STACK/history.jsonl 問腦一次、回覆接進 history → 寫答案 out/<n>.txt、題目 cur/→done/。
#   同一個小格再叫＝history 最後一則是 assistant，接新的 user 再問（續聊）。失敗（BrainFailed、ReplyBad…）＝退 1、不寫答案；重跑＝整個再問一次（interrupt safe）。
# 前半照原 brain.py 原樣搬（下面幾行是它原來的頭註解），後半照原 act.py（「act 那段」以下）。
# 原 brain.py：brain.py - think 格：認領題目（new/<n>.json＝稿子＋場景＋benchmark）、渲染成一則 user 訊息、問腦一次，回覆一行接進 history
# 原 brain.py：照 demo/agent-dan/brain.py 改：題目是 JSON（render）、假腦回一份固定的 JSON 分數（fake）。其餘相同。
import json, os, shutil, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone


def die(code, reason):
    print("critic: %s %s" % (code, reason), file=sys.stderr)
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
    s = q.get("scene") or {}
    out = ["【場景】%s・%s・%s。%s" % (s.get("season", ""), s.get("time", ""), s.get("place", ""), s.get("summary", "")),
           "【事件】%s　【意圖】%s　【稱謂階】%s" % (s.get("event", ""), s.get("intent", ""), s.get("relation_level", "")),
           "【女角風格】%s" % q.get("style", ""), "【在場】"]
    for c in q.get("cast_notes") or []:
        out.append("- %s（%s）：語氣 %s；不可：%s；叫對方：%s" % (
            c["name"], "、".join(c.get("type") or []), c.get("tone", ""), "；".join(c.get("ng") or []), "／".join(c.get("address_allowed") or [])))
    out += ["【總則】" + "；".join(q.get("style_rules") or []), "", "【稿子】", q.get("draft", ""), ""]
    b = q.get("benchmark")
    if b:
        out += ["【benchmark %s・%s（%s）】" % (b.get("id", ""), b.get("title", ""), b.get("difficulty", "")),
                "context：%s" % b.get("context", ""), "說話者設定：%s" % b.get("speaker_note", ""),
                "挖空對白：", b.get("dialogue", ""), "正解：%s" % b.get("answer", ""),
                "評分要點：(a) %s (b) %s (c) %s" % tuple((b.get("points") or {}).get(k, "") for k in "abc")]
    else:
        out.append("【沒有 benchmark】只照場景與總則打分。")
    out.append("請只輸出 JSON：{\"semantic\": 0-3, \"register\": 0-2, \"dims\": {\"承接\": 0-1, \"含蓄\": 0-1, \"角色味\": 0-1, \"反差\": 0-1, \"文筆\": 0-1},\"reasons\": [...]}")
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
    """假腦：不讀稿，給中間分（dims 也固定）；理由寫明是假的，免得有人拿它當真。
    測試開關 GALTXT_FAKE_CRITIC_DIMS：no＝不給 dims（拆不出來那條路）、bad＝dims 給壞的值（不是數字）。"""
    dims = {"no": None, "bad": {"承接": "高", "含蓄": True}}.get(os.environ.get("GALTXT_FAKE_CRITIC_DIMS"),
                                                             {"承接": 0.7, "含蓄": 0.6, "角色味": 0.7, "反差": 0.5, "文筆": 0.8})
    verdict = {"semantic": 2, "register": 2, "reasons": ["假腦：沒有真的讀稿，固定給 semantic 2、register 2、dims 固定值"]}
    if dims is not None:
        verdict["dims"] = dims
    return {"role": "assistant", "content": json.dumps(verdict, ensure_ascii=False)}


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
    die("ReplyBad", "critic 不該叫工具，腦卻回了 tool_calls")
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
