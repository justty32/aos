# ask.py - compact 問腦：OpenAI 相容 {url}/chat/completions，回 (content, usage)；沒設網址＝假腦（照字面拼，demo／測試用）
# 網址：COMPACT_URL，沒設就沿用 AOS_BRAIN_URL（agent 的腦在哪，compact 就問哪）；key：AOS_BRAIN_KEY 有設才帶。
# usage 取回覆的 usage.prompt_tokens／completion_tokens；回覆沒帶（或假腦）就用字數粗估，標 estimated。
import json, os, re, sys, urllib.error, urllib.request


def die(code, reason):
    print("compact: %s %s" % (code, reason.replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


def estimate(s):
    """粗估 token：中日韓一字一個，其餘四字一個（同 agent-kai 的粗估）。"""
    s = s or ""
    wide = sum(1 for ch in s if ord(ch) >= 0x2E80)
    return wide + (len(s) - wide + 3) // 4


def url():
    return os.environ.get("COMPACT_URL") or os.environ.get("AOS_BRAIN_URL") or ""


def ask(model, system, user, data, fake):
    """問一次腦。data 是同一份輸入的結構化版本，只給假腦用。回 (content 字串, usage dict)。"""
    base = url()
    if not base:
        content = fake(data)
        return content, {"prompt_tokens": estimate(system) + estimate(user),
                         "completion_tokens": estimate(content), "estimated": True}
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    headers = {"Content-Type": "application/json"}
    if os.environ.get("AOS_BRAIN_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["AOS_BRAIN_KEY"]
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions",
                                 json.dumps(body, ensure_ascii=False).encode("utf-8"), headers)
    try:
        with urllib.request.urlopen(req, timeout=int(os.environ.get("COMPACT_TIMEOUT_S") or 120)) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        die("BrainFailed", "HTTP %d：%s" % (e.code, e.read()[:200].decode("utf-8", "replace")))
    except (urllib.error.URLError, OSError) as e:
        die("BrainFailed", "%s 連不上或逾時：%s" % (base, getattr(e, "reason", e)))
    try:
        reply = json.loads(raw)
        content = reply["choices"][0]["message"].get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
        die("ReplyBad", "回覆不是 OpenAI 的形狀（%s: %s）" % (type(e).__name__, e))
    u = reply.get("usage") if isinstance(reply.get("usage"), dict) else {}
    if isinstance(u.get("prompt_tokens"), int) and isinstance(u.get("completion_tokens"), int):
        usage = {"prompt_tokens": u["prompt_tokens"], "completion_tokens": u["completion_tokens"], "estimated": False}
    else:
        usage = {"prompt_tokens": estimate(system) + estimate(user), "completion_tokens": estimate(content),
                 "estimated": True}
    return content, usage


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


# ---- 假腦：照字面拼，不懂意思；只是讓「三步」不連網也走得完 ----

def flat(s, cut):
    s = " ".join((s or "").split())
    return s if len(s) <= cut else s[:cut] + "…"


def first_line(s, cut):
    for ln in (s or "").splitlines():
        if ln.strip():
            return flat(ln, cut)
    return "（沒有輸出）"


def fake_note(data):
    notes = []
    for c in data["calls"]:
        res = c.get("result")
        ok = res is not None and not re.match(r"\s*(錯|error|Error|ERROR|Traceback|ToolFailed)", res)
        notes.append({"id": c["id"], "ok": ok,
                      "line": "叫 %s（%s）→ %s" % (c["name"], flat(c.get("arguments"), 50),
                                                  first_line(res, 80) if res is not None else "沒有結果")})
    return json.dumps({"notes": notes}, ensure_ascii=False)


KEEP_WORDS = re.compile(r"[0-9]|決定|改成|記住|不要|一定|千萬")


def fake_segment(data):
    out, keep = [], []
    for ln in data["lines"]:
        who = {"user": "使用者", "assistant": "助手", "tool_note": "工具"}.get(ln["role"], ln["role"])
        out.append("%s：%s" % (who, flat(ln["text"], 50)))
        if ln["role"] == "user" and KEEP_WORDS.search(ln["text"]) and len(keep) < data["max_keep"]:
            keep.append({"n": ln["n"], "tag": "user_words", "why": "使用者原話帶數字或決定"})
    return json.dumps({"summary": "\n".join(out), "keep": keep}, ensure_ascii=False)


def fake_final(data):
    parts = ([data["old_summary"]] if data.get("old_summary") else []) + data["segments"]
    return json.dumps({"summary": "\n".join(parts), "keep": data["candidates"][:data["max_keep"]]},
                      ensure_ascii=False)
