# turns.py - 把 history.jsonl（原樣、只附加的完整紀錄）切成「一題一題」，並按這題的意圖挑出要給腦看的舊題
# recall 工具與 brain.py 共用（同 agent-meg 把 heap.py 放在 tools/memory/ 裡、brain 從那裡 import）。
# 一題＝從一則 user 開始，到一則沒有 tool_calls 的 assistant 為止；中間的 tool_calls／tool 結果是「過程」，結論只看最後那則 assistant。
import json, re

Q_CUT, A_CUT = 40, 60            # 目錄每題一行：問題前 40 字、答案前 60 字
OPEN_A_CUT = 800                 # 展開的舊題：答案最多 800 字
DIR_MAX = 50                     # 目錄最多列最近 50 題，更早的只說有幾題
PICK_MAX = 2                     # 照字面挑的相關舊題最多 2 題（另加上一題、指代、第 N 題）
ANAPHORA = re.compile(r"剛剛|剛才|上一|上個|前一|上次|前面|之前|那個|那題|這個|它")
ORDINAL = re.compile(r"第\s*([0-9]+|[一二三四五六七八九十兩]+)\s*[題個]")
CN = {"一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
STOP = {"什麼", "多少", "是多", "一下", "幫我", "我們", "你的", "我的", "可以", "這個", "那個", "怎麼", "現在",
        "告訴", "訴我", "請問", "一句", "回答", "是哪", "哪一", "哪個", "the", "is", "a", "of", "what"}


class HistoryBad(Exception):
    pass


def load(path):
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except ValueError as e:
                        raise HistoryBad("history.jsonl 第 %d 行不是 JSON：%s" % (n, e))
    except FileNotFoundError:
        pass
    return out


def split(history):
    """回 (done, current)：done＝做完的題（no 從 1 起）、current＝還沒答完那題的訊息（可能是空的）。"""
    done, start = [], None
    for i, m in enumerate(history):
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role == "user" and start is None:
            start = i
        elif role == "assistant" and not m.get("tool_calls") and start is not None:
            msgs = history[start:i + 1]
            tools = [c.get("function", {}).get("name", "?") for x in msgs if x.get("role") == "assistant"
                     for c in (x.get("tool_calls") or []) if isinstance(c, dict)]
            done.append({"no": len(done) + 1, "question": text(history[start]), "answer": text(m),
                         "tools": tools, "msgs": msgs})
            start = None
    return done, (history[start:] if start is not None else [])


def text(m):
    c = m.get("content")
    return c if isinstance(c, str) else ("" if c is None else json.dumps(c, ensure_ascii=False))


def flat(s, cut):
    s = " ".join((s or "").split())
    return s if len(s) <= cut else s[:cut] + "…"


def line(t):
    used = "（用了 %s）" % "、".join(sorted(set(t["tools"]))) if t["tools"] else ""
    return "#%d 問：%s → 答：%s%s" % (t["no"], flat(t["question"], Q_CUT), flat(t["answer"], A_CUT), used)


def directory(done):
    if not done:
        return ""
    shown = done[-DIR_MAX:]
    head = "## 先前對話的目錄（共 %d 題，一題一行；要細節用 recall 工具）" % len(done)
    more = ["（更早還有 %d 題沒列，用 recall 的 search 找）" % (len(done) - len(shown))] if len(shown) < len(done) else []
    return "\n".join([head] + more + [line(t) for t in shown])


def tokens(s):
    s = (s or "").lower()
    out = set(re.findall(r"[a-z0-9_.\-]+", s))
    for run in re.findall(r"[㐀-鿿豈-﫿]+", s):
        out |= {run} if len(run) == 1 else {run[i:i + 2] for i in range(len(run) - 1)}
    return out - STOP


def score(q, done):
    """每題跟這個問題重疊多少（字面：英數詞＋中文兩字一組），常見到一半以上的題都有的字不算。"""
    qt = tokens(q)
    bags = [tokens(t["question"] + "\n" + t["answer"]) for t in done]
    common = {w for w in qt if len(done) >= 4 and sum(w in b for b in bags) > len(done) / 2}
    return [len((qt - common) & b) for b in bags]


def ordinal(q):
    out = []
    for g in ORDINAL.findall(q):
        if g.isdigit():
            out.append(int(g))
        elif g == "十":
            out.append(10)
        elif g.startswith("十"):
            out.append(10 + CN.get(g[1:], 0))
        elif g.endswith("十"):
            out.append(CN.get(g[0], 0) * 10)
        elif "十" in g:
            a, b = g.split("十", 1)
            out.append(CN.get(a, 0) * 10 + CN.get(b, 0))
        else:
            out.append(CN.get(g, 0))
    return [n for n in out if n > 0]


def choose(q, done):
    """按意圖挑要展開的舊題；回 [(no, 原因)]，照時間順序。"""
    why = {}
    if done:
        why[done[-1]["no"]] = "上一題"
        if ANAPHORA.search(q) and len(done) >= 2:
            why.setdefault(done[-2]["no"], "指代")
    for n in ordinal(q):
        if 1 <= n <= len(done):
            why.setdefault(n, "第 %d 題" % n)
    ranked = sorted(((s, t["no"]) for s, t in zip(score(q, done), done) if s >= 2), reverse=True)
    for s, n in ranked:
        if sum(r.startswith("字面") for r in why.values()) >= PICK_MAX:
            break
        why.setdefault(n, "字面重疊 %d" % s)
    return sorted(why.items())


def opened(t):
    """展開一題給腦看：user 問題＋assistant 結論（過程不帶）。"""
    a = t["answer"]
    if len(a) > OPEN_A_CUT:
        a = a[:OPEN_A_CUT] + "…（截斷，recall 的 read 看全文）"
    return [{"role": "user", "content": t["question"]}, {"role": "assistant", "content": a}]


def estimate(messages):
    """粗估 token：英數每 4 字 1 個、其他（中文等）每字 1 個；只拿來比大小，不是真的計費數。"""
    s = json.dumps(messages, ensure_ascii=False)
    ascii_n = sum(1 for ch in s if ord(ch) < 128)
    return (ascii_n + 3) // 4 + (len(s) - ascii_n)
