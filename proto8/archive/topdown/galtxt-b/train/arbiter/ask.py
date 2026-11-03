# ask.py - 判斷器（train/arbiter，plan/round6.md §4）的單發腦函數：照 judge/tools/critic/ask.py 複製（critic 形），只改 render、fake、多一段「規則表」。
#   題目 new/<n>.json＝{"node", "a": {"move", "expected"（預期梯度，形狀同 changes.gradient）, "evidence"}, "b": {…}, "context"}；
#   答案 out/<n>.txt＝{"better": "a|b", "why": [...], "weights_used": {名字: 權重}, "by": "brain|rules|fake"}。
#   一定選一條（round6 §8-3：不給「都不好」）；腦回壞（不是 JSON、better 不是 a／b）＝ReplyBad 退 1。
#   固化（record 在 ≥ 8 次判斷後寫 priority_rules.json，stage script）：有規則表就先照表算——兩條預期梯度的每個 key（名字＝key 最後一段，是 val 取前一段），
#   值＝方向（規則表的 polarity）× delta ÷ 兩條中這個名字的最大 |delta|，乘權重加總；差 > tie 就照表定（不問腦，by rules），平手才問腦。
#   認領題目、history、量測（llm.jsonl）、寫答案那幾段跟 critic 一字不差。
# 假腦（沒給 AOS_BRAIN_URL）：固定選 a（測試開關 GALTXT_FAKE_ARBITER=b 改選 b），weights_used 固定。
import json, os, re, shutil, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone


def die(code, reason):
    print("arbiter: %s %s" % (code, reason), file=sys.stderr)
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


def key_name(k):
    segs = k.split(".")
    return segs[-2] if segs[-1] == "val" and len(segs) > 1 else segs[-1]


def lines_of(grad):
    out = []
    for node, d in (grad or {}).items():
        for k, v in (d or {}).items():
            if isinstance(v, dict) and "delta" in v:
                out.append("  %s ｜ %s：%s → %s（%+g）" % (node, k, v.get("from"), v.get("to"), v["delta"]))
            elif isinstance(v, dict):
                out.append("  %s ｜ %s：%s" % (node, k, json.dumps(v, ensure_ascii=False)))
    return out or ["  （空）"]


def render(q):
    out = ["【要改的節點】%s" % q.get("node", "")]
    ctx = q.get("context") or {}
    if ctx:
        out.append("【現況】" + "；".join("%s＝%s" % (k, json.dumps(v, ensure_ascii=False)) for k, v in ctx.items()))
    for label in ("a", "b"):
        c = q.get(label) or {}
        out += ["", "【候選 %s】%s" % (label, json.dumps(c.get("move") or {}, ensure_ascii=False)),
                "預期梯度（改動前後 _metainfo 的差；delta 是改後減改前）："] + lines_of(c.get("expected"))
        if c.get("evidence"):
            out.append("根據：" + "；".join(map(str, c["evidence"])))
    out += ["", "兩條只能選一條（一定要選）。請只輸出 JSON：{\"better\": \"a\" 或 \"b\", \"why\": [\"一句理由\", ...], "
            "\"weights_used\": {\"名字\": 權重, ...}}——weights_used 的名字用上面 key 的最後一段（例 llm_tokens、counter_argbad、total_mean、反差），"
            "權重是你這次判斷時各項有多重要（加總 1）。"]
    return "\n".join(out)


def by_rules(q):
    """有 priority_rules.json（固化後）＝照表算兩條的分；差 > tie 回判決，平手（或沒有表）回 None。"""
    rules = None
    try:
        with open("priority_rules.json", encoding="utf-8") as f:
            rules = json.load(f)
    except (OSError, ValueError):
        return None
    weights, pol = rules.get("weights") or {}, rules.get("polarity") or {}
    flat = {}
    for label in ("a", "b"):
        for node, d in ((q.get(label) or {}).get("expected") or {}).items():
            for k, v in (d or {}).items():
                if isinstance(v, dict) and isinstance(v.get("delta"), (int, float)):
                    flat.setdefault(label, []).append((key_name(k), v["delta"]))
    scale = {}
    for xs in flat.values():
        for nm, dl in xs:
            scale[nm] = max(scale.get(nm, 0), abs(dl))
    score = {}
    for label in ("a", "b"):
        s = 0.0
        for nm, dl in flat.get(label, []):
            sign = 1 if nm in pol.get("higher_better", []) else -1 if nm in pol.get("lower_better", []) else 0
            if scale.get(nm):
                s += float(weights.get(nm, 0)) * sign * dl / scale[nm]
        score[label] = round(s, 4)
    if abs(score["a"] - score["b"]) <= float(rules.get("tie", 0.05)):
        return None
    better = "a" if score["a"] > score["b"] else "b"
    return {"better": better, "why": ["priority_rules：a %s、b %s（照 %s 的順序）" % (score["a"], score["b"], "＞".join(rules.get("order") or []))],
            "weights_used": weights, "by": "rules", "scores": score}


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
    """假腦：不讀題，固定選 a（GALTXT_FAKE_ARBITER=b 改選 b）；理由寫明是假的。"""
    better = "b" if os.environ.get("GALTXT_FAKE_ARBITER") == "b" else "a"
    verdict = {"better": better, "why": ["假腦：沒有真的讀題，固定選 %s" % better],
               "weights_used": {"total_mean": 0.4, "llm_tokens": 0.3, "counter_violations": 0.2, "counter_argbad": 0.1}}
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


ruled = by_rules(question)
url = os.environ.get("AOS_BRAIN_URL")
if ruled is not None:                            # 固化後：規則表分得出就不問腦（history 照記一則，形狀一致）
    record(now_iso(), "rules", 0, {})
    append({"role": "assistant", "content": json.dumps(ruled, ensure_ascii=False)})
elif url:
    append(ask(url))
else:
    record(now_iso(), "fake", 0, {})
    append(fake())


# ── act 那段（原 act.py）：把腦的最後一則回覆（content）驗過、寫成答案 out/<n>.txt、題目 cur/→done/
said = next((m for m in reversed(history) if isinstance(m, dict) and m.get("role") == "assistant"), None)
if said is None:
    die("HistoryBad", "history.jsonl 裡沒有 assistant 的訊息")
if said.get("tool_calls"):
    die("ReplyBad", "arbiter 不該叫工具，腦卻回了 tool_calls")
raw = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", said.get("content") or "")
try:
    verdict = json.loads(raw)
except ValueError as e:
    die("ReplyBad", ("回覆不是 JSON：%s（%s）" % (raw[:120], e)).replace("\n", " "))
if not isinstance(verdict, dict) or verdict.get("better") not in ("a", "b"):
    die("ReplyBad", "better 要是 a 或 b：%s" % raw[:120].replace("\n", " "))
verdict["why"] = [str(x) for x in verdict.get("why") or []] if isinstance(verdict.get("why"), list) else [str(verdict.get("why") or "")]
w = verdict.get("weights_used")
verdict["weights_used"] = {str(k): v for k, v in w.items() if isinstance(v, (int, float)) and not isinstance(v, bool)} if isinstance(w, dict) else {}
verdict.setdefault("by", "brain" if url else "fake")
content = json.dumps(verdict, ensure_ascii=False) + "\n"
os.makedirs(os.path.join(ws, "out"), exist_ok=True)
os.makedirs(os.path.join(ws, "done"), exist_ok=True)
tmp = os.path.join(ws, "out", "." + name + ".txt")
with open(tmp, "w", encoding="utf-8") as f:
    f.write(content)
os.replace(tmp, os.path.join(ws, "out", name + ".txt"))
shutil.move(os.path.join(ws, "cur", fname), os.path.join(ws, "done", fname))
