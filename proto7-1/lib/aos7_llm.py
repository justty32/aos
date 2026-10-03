"""agent 的 LLM 後端：fake（決定性、離線，演「兩個 agent 互傳 ping」）與 OpenAI 相容（urllib POST /chat/completions）。

對外只有 think(cfg, goal, letters, me) → {"plan": [...], "tokens": int, "note": str}。
plan 是工具動作清單（spec.md 第 10 節）：[{"tool": "send"|"write"|"none", ...}]。
"""
import json
import re
import urllib.error
import urllib.request

PING = re.compile(r"^\s*ping\s+(\d+)\s*$")

SYSTEM_RULES = """你是一個住在資料夾裡的 agent，只能用工具動作做事。
你只回一個 JSON 陣列（plan），不要回別的文字、不要 markdown。每一項是下列其中一種：
  {"tool": "send", "to": "<對方 node id>", "body": "<信的內容>"}
  {"tool": "write", "path": "<相對你自己資料夾的路徑>", "text": "<檔案內容>"}
  {"tool": "none"}
信件的 from 就是對方的 node id，回信就 send 給它。"""


def build_prompt(cfg, goal, letters, me):
    """組 system＋user 兩段文字（fake 也用它算 tokens，兩種後端看到的是同一份輸入）。"""
    system = SYSTEM_RULES + "\n\n你的 node id：%s\n你的人設：%s" % (me, cfg.get("persona", ""))
    user = {"goal": goal, "letters": [{"from": l.get("from"), "round": l.get("round"), "body": l.get("body")}
                                      for l in letters]}
    return system, json.dumps(user, ensure_ascii=False)


def think(cfg, goal, letters, me):
    """依 agent.json 的 llm 欄位選後端。回 {"plan", "tokens", "note"}；後端出錯也不丟例外，plan 退成 none。"""
    system, user = build_prompt(cfg, goal, letters, me)
    llm = cfg.get("llm", "fake")
    if llm == "fake":
        return {"plan": fake_plan(cfg, goal, letters), "tokens": (len(system) + len(user)) // 4, "note": "fake"}
    if isinstance(llm, dict) and llm.get("url") and llm.get("model"):
        return openai_think(llm, system, user)
    return {"plan": [{"tool": "none"}], "tokens": 0, "note": "agent.json 的 llm 看不懂：%r" % (llm,)}


def fake_plan(cfg, goal, letters):
    """決定性假腦：goal.say_first 先開口；收到 ping N 回 ping N+1，N 到 max_ping 改寫 work/done.txt。"""
    max_ping = cfg.get("max_ping", 6)
    plan = []
    if goal and isinstance(goal.get("say_first"), dict):
        s = goal["say_first"]
        plan.append({"tool": "send", "to": s.get("to"), "body": s.get("body", "")})
    for l in letters:
        m = PING.match(str(l.get("body", "")))
        if not m:
            continue
        n = int(m.group(1))
        if n >= max_ping:
            plan.append({"tool": "write", "path": "work/done.txt",
                         "text": "收到 ping %d（來自 %s），到上限 %d，停。\n" % (n, l.get("from"), max_ping)})
        else:
            plan.append({"tool": "send", "to": l.get("from"), "body": "ping %d" % (n + 1)})
    return plan or [{"tool": "none"}]


def parse_plan(text):
    """從模型回覆挖出 JSON 陣列；挖不到回 None。容忍 ```json 圍欄、前後廢話、單一物件、<think> 段。"""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    text = re.sub(r"```(?:json)?", "", text)
    for opener, closer in (("[", "]"), ("{", "}")):
        i, j = text.find(opener), text.rfind(closer)
        if i < 0 or j <= i:
            continue
        try:
            obj = json.loads(text[i:j + 1])
        except ValueError:
            continue
        obj = obj if isinstance(obj, list) else [obj]
        if all(isinstance(x, dict) and isinstance(x.get("tool"), str) for x in obj):
            return obj
    return None


def openai_think(llm, system, user):
    """OpenAI 相容端點問一次；連不上、回應壞、plan 解不出都退成 none 並在 note 說明。"""
    url = llm["url"].rstrip("/") + "/chat/completions"
    body = {"model": llm["model"], "temperature": llm.get("temperature", 0),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if llm.get("max_tokens"):
        body["max_tokens"] = llm["max_tokens"]
    headers = {"Content-Type": "application/json"}
    if llm.get("api_key"):
        headers["Authorization"] = "Bearer " + llm["api_key"]
    req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=llm.get("timeout_s", 120)) as resp:
            obj = json.loads(resp.read())
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"plan": [{"tool": "none"}], "tokens": 0, "note": "呼叫失敗：%s" % e}
    usage = obj.get("usage") if isinstance(obj, dict) else None
    tokens = usage.get("total_tokens", 0) if isinstance(usage, dict) else 0
    try:
        content = obj["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, TypeError, AttributeError):
        return {"plan": [{"tool": "none"}], "tokens": tokens, "note": "回應缺 choices[0].message"}
    plan = parse_plan(content)
    if plan is None:
        return {"plan": [{"tool": "none"}], "tokens": tokens,
                "note": "plan 解析失敗，原文前 200 字：%s" % " ".join(content.split())[:200]}
    return {"plan": plan, "tokens": tokens, "note": "ok"}
