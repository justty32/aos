# shared.py - agent-gus 各格共用的小函式：報錯、讀寫 history、認領題目、組 tools、問腦（C-50「程式可以擠在一坨，共用一些 lib」）
# 各格的身體是 plan.py、fork.py、brain.py、act.py；這支不是格，只被它們 import。
import json, os, subprocess, sys, urllib.error, urllib.request

NAME = "agent-gus"


def die(code, reason):
    print("%s: %s %s" % (NAME, code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


STACK, WS = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not STACK:
    die("StackMissing", "沒設定 AOS_STACK")
HISTORY = os.path.join(STACK, "history.jsonl")
STEPS = os.path.join(STACK, "steps.json")          # 這題的規劃與各步結論（fork 格的帳）


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        die("ArgumentsBad", "%s 不是整數：%r" % (name, os.environ.get(name)))


def ls(d):
    try:
        return sorted(n for n in os.listdir(os.path.join(WS, d)) if not n.startswith("."))
    except FileNotFoundError:
        return []


def write_atomic(path, text):                       # N-05：先寫 . 開頭的暫存檔再改名
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def claim():
    """認領題目（同 dan）：cur/ 有沒做完的先接著做，沒有就把 new/ 第一題搬到 cur/；回 (題名, 題目)。"""
    names = ls("cur")
    if not names:
        names = ls("new")
        if not names:
            die("QuestionMissing", "new/ 是空的")
        os.makedirs(os.path.join(WS, "cur"), exist_ok=True)
        os.replace(os.path.join(WS, "new", names[0]), os.path.join(WS, "cur", names[0]))
    name = names[0]
    write_atomic(os.path.join(STACK, "current.txt"), name + "\n")
    with open(os.path.join(WS, "cur", name), encoding="utf-8") as f:
        return name, f.read()


def read_history():
    out = []
    try:
        with open(HISTORY, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except ValueError as e:
                        die("HistoryBad", "history.jsonl 第 %d 行不是 JSON：%s" % (n, e))
    except FileNotFoundError:
        pass
    return out


def append_history(*messages):
    """一次寫完幾則（一個 write），只附加。"""
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in messages))


def tools_spec():
    """工具名＝資料夾名，說明來自 tool.json（同 dan）。"""
    tools = []
    for tool in (sorted(os.listdir("tools")) if os.path.isdir("tools") else []):
        spec = None
        try:
            spec = read_json(os.path.join("tools", tool, "tool.json"))
        except (OSError, ValueError):
            pass
        if not isinstance(spec, dict):
            continue
        function = {"name": tool}
        function.update({k: spec[k] for k in ("description", "parameters") if k in spec})
        tools.append({"type": "function", "function": function})
    return tools


def system():
    if os.path.exists("system.txt"):
        with open("system.txt", encoding="utf-8") as f:
            return [{"role": "system", "content": f.read()}]
    return []


def ask(cell, messages, tools=None):
    """問 OpenAI 相容的 {AOS_BRAIN_URL}/chat/completions，回 message（只留 role、content、tool_calls）。
    回覆的 usage 記一行到 $AOS_STACK/usage.jsonl（看得到每一層花了多少 token）。"""
    url = os.environ["AOS_BRAIN_URL"]
    body = {"model": os.environ.get("AOS_BRAIN_MODEL") or "default", "messages": messages}
    if tools:
        body["tools"] = tools
    headers = {"Content-Type": "application/json"}
    if os.environ.get("AOS_BRAIN_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["AOS_BRAIN_KEY"]
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions",
                                 json.dumps(body, ensure_ascii=False).encode("utf-8"), headers)
    try:
        with urllib.request.urlopen(req, timeout=110) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        die("BrainFailed", "HTTP %d：%s" % (e.code, e.read()[:200].decode("utf-8", "replace")))
    except (urllib.error.URLError, OSError) as e:
        die("BrainFailed", "%s 連不上或逾時：%s" % (url, getattr(e, "reason", e)))
    try:
        reply = json.loads(raw)
        message = reply["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        die("ReplyBad", "回覆不是 OpenAI 的形狀（%s: %s）" % (type(e).__name__, e))
    if not isinstance(message, dict):
        die("ReplyBad", "choices[0].message 不是物件")
    with open(os.path.join(STACK, "usage.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"cell": cell, "usage": reply.get("usage"),
                            "counter_sent_chars": len(json.dumps(messages, ensure_ascii=False))}, ensure_ascii=False) + "\n")
    out = {"role": message.get("role") or "assistant", "content": message.get("content")}
    calls = message.get("tool_calls")
    if calls:
        if not isinstance(calls, list) or not all(isinstance(c, dict) for c in calls):
            die("ReplyBad", "tool_calls 不是物件的陣列")
        out["tool_calls"] = [{k: c[k] for k in ("id", "type", "function") if k in c} for c in calls]
    return out


# ---- 小念頭：fork.py（一次多個）與 thought.py（別的程式叫一個）共用 ----

def task_text(goal, context="", needs=(), max_chars=1500):
    """給小念頭的題目：背景摘要＋前面幾步的結論（[(id, goal, conclusion)]）＋這一步的目標＋規矩（只回結論）。"""
    lines = ["（你是一個小念頭：母體把一件事拆成幾步，你負責其中一步。你看不到母體的對話。）", ""]
    if context:
        lines += ["背景：" + context, ""]
    if needs:
        lines.append("前面幾步的結論：")
        lines += ["- %s（%s）：%s" % n for n in needs]
        lines.append("")
    lines += ["你的目標：" + goal, "",
              "做完只回結論：直接寫結果與要點（數字、判斷），不寫過程，%d 字以內。" % max_chars]
    return "\n".join(lines) + "\n"


def launch(cell, qname, task, depth, budget):
    """在小格 cell/ 開 ws/、stack/，題目放 ws/new/<qname>.txt（小格已存在＝重跑，不重放題目），
    背景起「同一隻 agent」（aos-exec --ws cell/ws .，cwd 是本資料夾），自成一個行程群組；回 Popen。"""
    ws = os.path.join(cell, "ws")
    fresh = not os.path.isdir(ws)
    for d in ("new", "out"):
        os.makedirs(os.path.join(ws, d), exist_ok=True)
    os.makedirs(os.path.join(cell, "stack"), exist_ok=True)
    if fresh:
        write_atomic(os.path.join(ws, "new", qname + ".txt"), task)
    env = dict(os.environ, AOS_STACK=os.path.join(cell, "stack") + "/", AOS_WS=ws,
               THOUGHT_DEPTH=str(depth), THOUGHT_BUDGET=budget)
    with open(os.path.join(cell, "log.txt"), "a", encoding="utf-8") as log:
        return subprocess.Popen(["aos-exec", "--ws", ws, "."], cwd=os.getcwd(), env=env, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=log, start_new_session=True)


def conclusion(cell, qname, code, max_chars):
    """小念頭結束後：回 (結論, None) 或 (None, 失敗原因)。結論＝它 out/ 裡那一段答案，超過 max_chars 截斷。"""
    if code != 0:
        return None, "結束碼 %d（現場在 %s，log.txt）" % (code, cell)
    path = os.path.join(cell, "ws", "out", qname + ".txt")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read().strip()
    except FileNotFoundError:
        return None, "跑完沒有答案（%s）" % path
    if len(text) > max_chars:
        text = text[:max_chars] + "…（截斷；全文在 %s）" % path
    return text, None
