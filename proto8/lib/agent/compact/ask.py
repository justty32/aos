# ask.py - compact 格問腦與讀回覆：經 endpoint 格（aos-exec <endpoint> <agent>，stdin {"messages": [...]}，stdout 一行 assistant message）
# 從 demo/agent-hal/compact/ask.py 搬來（10-28 agent-round § 7 第 3 步）：原本自己連 OpenAI 相容網址、沒網址就用內建假腦；
# 現在問腦一律走 endpoint 格（假腦、LiteLLM 都是 endpoint），這裡不連網、不帶假腦。只給同資料夾的 _entry 用。
import json, os, re, subprocess, sys


def die(code, reason):
    print("compact: %s %s" % (code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


def flat(s, cut):
    s = " ".join((s or "").split())
    return s if len(s) <= cut else s[:cut] + "…"


def first_line(s, cut):
    for ln in (s or "").splitlines():
        if ln.strip():
            return flat(ln, cut)
    return "（沒有輸出）"


def ask(endpoint, agent, model, system, user):
    """問一次腦，回 content 字串。endpoint＝(路徑, env)。model 是空的就不帶（用 endpoint 格自己的設定）。
    endpoint 退非 0＝EndpointFailed（endpoint 自己已在 stderr 說了原因，這裡不轉述，P-21）。"""
    path, env = endpoint
    body = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if model:
        body["model"] = model
    e = dict(os.environ)
    e.update(env)
    try:
        r = subprocess.run(["aos-exec", path, agent], input=json.dumps(body, ensure_ascii=False),
                           stdout=subprocess.PIPE, text=True, env=e)
    except OSError as ex:
        die("EndpointFailed", "aos-exec 起不來：%s" % ex)
    if r.returncode != 0:
        die("EndpointFailed", "endpoint %s 退 %d" % (path, r.returncode))
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    try:
        msg = json.loads(lines[-1])
        content = msg.get("content")
    except (ValueError, IndexError, AttributeError) as ex:
        die("EndpointFailed", "endpoint 印的不是一則 assistant message：%s" % ex)
    return content if isinstance(content, str) else ""


def parse_json(content):
    """模型回的 JSON：容許包在 ``` 裡、前後有字；取第一個 { 到最後一個 }。讀不懂回 None（呼叫方走退路）。"""
    s = content or ""
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if m:
        s = m.group(1)
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j < i:
        return None
    try:
        v = json.loads(s[i:j + 1])
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def literal_note(it):
    """第 1 步的退路：模型沒給這個呼叫的一句話（或回的不是 JSON）就照字面拼。"""
    res = it.get("result")
    args = it.get("arguments")
    args = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)
    return "叫 %s（%s）→ %s" % (it["name"], flat(args, 50), first_line(res, 80) if res is not None else "沒有結果")
