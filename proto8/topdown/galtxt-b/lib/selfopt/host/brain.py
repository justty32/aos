# brain.py - selfopt host 的 think 格（照 demo/agent-dan／writer 的 brain.py）：認領題目、第一次開 session、帶 $AOS_STACK/history.jsonl 問腦一次
# 題目（$AOS_WS＝訓練場 new/<n>.json）：{"mode": "optimize", "node": tree/ 相對路徑, "goal": 一句, "evidence": [幾行先前結果],
#   "max_calls"?: 12, "max_tokens"?: 30000, "self_test"?: "fake"|"real"|"off", "est_tokens_per_test"?: 22000, "editable"?: [白名單樣式],
#   "round"?: 第幾輪, "fake_script"?: [{"name", "arguments"}]（假腦依序叫的工具；測試用）}。
# session：$AOS_WS/selfopt/<n>/session.json（第一次 think 寫；工具從 SELFOPT_SESSION 找它、在裡面記帳）。
# 掛法（任務 b2_selfopt 第 2 項）：
#   agent 節點（資料夾有 system.txt＋fsm.json，例 writer）＝用它自己的腦：system 訊息是它自己的 system.txt 接在 host 的「優化模式」說明後面，
#     模型照它 .env 的 AOS_BRAIN_MODEL——叫起來的是「它」，只是多掛一包工具、給一句「請優化 X」。不動它的 act.py／brain.py（侵入最小）。
#   非 agent 節點（純程式，例 plan_template）＝臨時配一個腦殼：system 訊息是「優化模式」說明＋這個節點 _metainfo 的 summary 與 lifecycle，模型照 host 的 .env。
# 預算由程式擋：session.counter_tokens ≥ max_tokens＝不問腦、直接回一則收工訊息；counter_calls ≥ max_calls＝不給工具（只能交報告）。
# 沒設 AOS_BRAIN_URL＝假腦：照題目的 fake_script 依序叫工具，叫完回一段收工報告。每問一次腦（含假腦）在 $AOS_STACK/llm.jsonl 寫一行量測。
# 自己的錯一行 stderr「selfopt: 代號 原因」退 1：StackMissing、QuestionMissing／QuestionBad、NodeMissing、HistoryBad、BrainFailed、ReplyBad。
import json, os, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

sys.dont_write_bytecode = True


def die(code, reason):
    print("selfopt: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")
ws = os.path.realpath(ws)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def ls(d):
    try:
        return sorted((n for n in os.listdir(os.path.join(ws, d)) if not n.startswith(".") and n.endswith(".json")), key=lambda n: (len(n), n))
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
with open(os.path.join(stack, ".current.txt"), "w", encoding="utf-8") as f:
    f.write(name + "\n")
os.replace(os.path.join(stack, ".current.txt"), os.path.join(stack, "current.txt"))
try:
    with open(os.path.join(ws, "cur", fname), encoding="utf-8") as f:
        question = json.load(f)
    node = question["node"].strip("/")
except (ValueError, KeyError, TypeError, AttributeError) as e:
    die("QuestionBad", "%s 不是 {node, goal, …}：%s" % (fname, e))
node_dir = os.path.join(ws, "tree", node)
if not os.path.isdir(node_dir):
    die("NodeMissing", "訓練場沒有 tree/%s" % node)

session_path = os.path.join(ws, "selfopt", name, "session.json")
try:
    with open(session_path, encoding="utf-8") as f:
        session = json.load(f)
except (OSError, ValueError):
    session = {"session": name, "node": node, "goal": question.get("goal", ""), "round": question.get("round"),
               "max_calls": question.get("max_calls", 12), "max_tokens": question.get("max_tokens", 30000),
               "self_test": question.get("self_test", "fake"), "est_tokens_per_test": question.get("est_tokens_per_test", 22000),
               "counter_calls": 0, "counter_tokens": 0, "counter_tokens_brain": 0, "counter_tokens_tests": 0, "counter_notes": 0,
               "calls": [], "edits": [], "self_tests": [], "attempted_violations": [], "started_at": now_iso()}
    if question.get("editable"):
        session["editable"] = question["editable"]


def save_session():
    os.makedirs(os.path.dirname(session_path), exist_ok=True)
    tmp = session_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=1)
    os.replace(tmp, session_path)


save_session()


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def dotenv_model(d):
    for line in (read(os.path.join(d, ".env")) or "").splitlines():
        if line.startswith("AOS_BRAIN_MODEL="):
            return line.split("=", 1)[1].strip()
    return None


node_system = read(os.path.join(node_dir, "system.txt"))
is_agent = node_system is not None and os.path.isfile(os.path.join(node_dir, "fsm.json"))
try:
    meta = json.loads(read(os.path.join(node_dir, "_metainfo")) or "{}")
except ValueError:
    meta = {}
model = (dotenv_model(node_dir) if is_agent else None) or os.environ.get("AOS_BRAIN_MODEL") or "default"


def render(q):
    lc = meta.get("lifecycle") or {}
    out = ["【優化模式】請優化你自己。你是 tree/%s（%s，lifecycle stage：%s）。" % (
               node, "agent：平常用的就是上面那份 system 說明" if is_agent else "平常是純程式、不問腦；這次臨時配你這個腦來替它想", lc.get("stage")),
           "【目標】%s" % q.get("goal", "")]
    if q.get("evidence"):
        out.append("【先前結果（證據）】")
        out += ["- %s" % e for e in q["evidence"]]
    out.append("【預算】工具最多叫 %d 次；腦 token 最多 %d（含 run_self_test 真腦跑樹）；run_self_test：%s。" % (
        session["max_calls"], session["max_tokens"],
        {"real": "可用真腦（每次約 %d token）" % session["est_tokens_per_test"], "fake": "只准假腦（不花 token，只驗流程）", "off": "不准跑"}.get(session["self_test"], session["self_test"])))
    out.append("【做法】先 read_self、read_runs 看自己與證據；決定改什麼（也可以決定不改）；用 edit_self／extract_tool 改；預算允許就 run_self_test；收工前叫 note；最後回一段文字報告。")
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

tools = []
if session.get("counter_calls", 0) < session["max_calls"]:
    for tool in sorted(os.listdir("tools")) if os.path.isdir("tools") else []:
        try:
            with open(os.path.join("tools", tool, "_tooldef.json"), encoding="utf-8") as f:
                spec = json.load(f)
        except (OSError, ValueError):
            continue
        function = {"name": tool}
        function.update({k: spec[k] for k in ("description", "parameters") if k in spec})
        tools.append({"type": "function", "function": function})

head = read("system.txt") or ""
if is_agent:
    system_text = head + "\n\n【你平常工作時的說明（你自己的 system.txt，也是你可以改的檔）】\n" + node_system
else:
    system_text = head + "\n\n【你替它想的節點】tree/%s\n%s\nlifecycle：%s" % (
        node, meta.get("summary", ""), json.dumps(meta.get("lifecycle") or {}, ensure_ascii=False))
system = [{"role": "system", "content": system_text}]


def record(asked_at, mdl, elapsed_ms, usage):
    usage = usage if isinstance(usage, dict) else {}
    num = lambda k: usage.get(k) if isinstance(usage.get(k), int) else 0
    total = num("total_tokens") or num("prompt_tokens") + num("completion_tokens")
    line = {"asked_at": asked_at, "model": mdl, "elapsed_ms": elapsed_ms, "counter_tokens_prompt": num("prompt_tokens"),
            "counter_tokens_completion": num("completion_tokens"), "counter_tokens": total, "usage": usage}
    with open(os.path.join(stack, "llm.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    session["counter_tokens"] = session.get("counter_tokens", 0) + total
    session["counter_tokens_brain"] = session.get("counter_tokens_brain", 0) + total
    save_session()


def fake():
    """假腦：照 fake_script 依序叫工具（一次一個），叫完（或沒給工具）回收工報告。"""
    script = question.get("fake_script") or [{"name": "read_self", "arguments": {}}, {"name": "note", "arguments": {"why": "假腦：只看了自己，沒改"}}]
    done = sum(1 for m in history if m.get("role") == "assistant" and m.get("tool_calls"))
    if tools and done < len(script):
        step = script[done]
        return {"role": "assistant", "content": None,
                "tool_calls": [{"id": "fake_%d" % (done + 1), "type": "function",
                                "function": {"name": step["name"], "arguments": json.dumps(step.get("arguments") or {}, ensure_ascii=False)}}]}
    return {"role": "assistant", "content": "假腦收工：照 fake_script 叫了 %d 次工具。" % done}


def ask(url):
    body = {"model": model, "messages": system + history}
    if tools:
        body["tools"] = tools
    headers = {"Content-Type": "application/json"}
    if os.environ.get("AOS_BRAIN_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["AOS_BRAIN_KEY"]
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions", json.dumps(body, ensure_ascii=False).encode("utf-8"), headers)
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
    record(asked_at, reply.get("model") or model, int((time.monotonic() - t0) * 1000), reply.get("usage"))
    if not isinstance(message, dict):
        die("ReplyBad", "choices[0].message 不是物件")
    out = {"role": message.get("role") or "assistant", "content": message.get("content")}
    calls = message.get("tool_calls")
    if calls:
        if not isinstance(calls, list) or not all(isinstance(c, dict) for c in calls):
            die("ReplyBad", "tool_calls 不是物件的陣列")
        out["tool_calls"] = [{k: c[k] for k in ("id", "type", "function") if k in c} for c in calls]
    return out


if session.get("counter_tokens", 0) >= session["max_tokens"]:
    append({"role": "assistant", "content": "（host：腦 token 預算用完（%d ≥ %d），不再問腦，直接收工。）" % (
        session["counter_tokens"], session["max_tokens"])})
    sys.exit(0)
url = os.environ.get("AOS_BRAIN_URL")
if url:
    append(ask(url))
else:
    record(now_iso(), "fake", 0, {})
    append(fake())
