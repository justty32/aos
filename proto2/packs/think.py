"""think 工具包：把難題丟給 thinker，結果留在 thoughts/。"""
import datetime
import json
import os


MAX_TOKENS = 6000
MAX_STEPS = 3
MAX_WAIT_S = 600
MAX_USD = 0.10

PROMPT = ("1. 要同時權衡三件以上的事、錯了很難回頭，或一般作法試了兩次仍卡住，才深度思考。\n"
          "2. 能查到、能算出、能用一次小實驗驗證的事，先直接做，不要深度思考。\n"
          "3. 一個問題最多開一份；送出後系統會睡著，結果回來會直接接回對話。")

_BUDGET = {"type": "object", "description": "可選。只能把預設上限往下調。", "properties": {
    "max_tokens": {"type": "integer", "description": "最多輸出 token，預設 6000"},
    "max_steps": {"type": "integer", "description": "最多幾步，預設 3"},
    "wait_s": {"type": "number", "description": "最多等幾秒，預設 600"},
    "max_usd": {"type": "number", "description": "估計最多花幾美元，預設 0.10"},
}}

TOOLS = [
    {"name": "think", "description": "把一個難題交給深思模型。當格只排隊，不等結果。",
     "parameters": {"type": "object", "properties": {
         "question": {"type": "string", "description": "要想清楚的問題"}, "budget": _BUDGET},
         "required": ["question"]}},
    {"name": "think_steps", "description": "把問題分成最多三步深思；每步只看原題和上一步結論。",
     "parameters": {"type": "object", "properties": {
         "question": {"type": "string", "description": "要分步想清楚的問題"}, "budget": _BUDGET},
         "required": ["question"]}},
    {"name": "critique", "description": "用深思模型檢查草稿，最多找三個重要漏洞並給最小修法。",
     "parameters": {"type": "object", "properties": {
         "draft": {"type": "string", "description": "要檢查的答案或計畫"}, "budget": _BUDGET},
         "required": ["draft"]}},
    {"name": "thoughts_list", "description": "列出最近的思考編號、題目、狀態、步數與用量。",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "thought_read", "description": "重讀一份思考的題目、各步短結論、最後結論與用量。",
     "parameters": {"type": "object", "properties": {
         "id": {"type": "string", "description": "思考編號"}}, "required": ["id"]}},
]


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _new_id():
    now = datetime.datetime.now()
    return "%s-%06d" % (now.strftime("%Y%m%d-%H%M%S"), now.microsecond)


def _budget(value, stepped=False):
    value = value if isinstance(value, dict) else {}
    def cap(name, default, low, high, cast):
        try:
            return max(low, min(high, cast(value.get(name, default))))
        except (TypeError, ValueError):
            return default
    return {"max_tokens": cap("max_tokens", MAX_TOKENS, 1, MAX_TOKENS, int),
            "max_steps": cap("max_steps", MAX_STEPS if stepped else 1,
                             1, MAX_STEPS if stepped else 1, int),
            "wait_s": cap("wait_s", MAX_WAIT_S, 0.001, MAX_WAIT_S, float),
            "max_usd": cap("max_usd", MAX_USD, 0.0, MAX_USD, float)}


def _engines(ctx):
    data = ctx.read_json(os.path.join(ctx.llm_dir(), "engines.json"), [])
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def _engine(ctx):
    engines = _engines(ctx)
    for row in engines:
        if row.get("role") == "thinker" and row.get("name"):
            return row["name"], row
    own = ctx.read_json(os.path.join(ctx.home, "llm.json"), {})
    defaults = ctx.read_json(os.path.join(ctx.llm_dir(), "defaults.json"), {})
    name = (own.get("engine") if isinstance(own, dict) else None) or \
           (defaults.get("engine") if isinstance(defaults, dict) else None) or \
           (engines[0].get("name") if engines else None)
    return name, next((row for row in engines if row.get("name") == name), {})


def _priority(ctx):
    own = ctx.read_json(os.path.join(ctx.home, "llm.json"), {})
    defaults = ctx.read_json(os.path.join(ctx.llm_dir(), "defaults.json"), {})
    value = own.get("priority") if isinstance(own, dict) else None
    if value is None and isinstance(defaults, dict):
        value = defaults.get("priority")
    try:
        return int(value or 0) - 1
    except (TypeError, ValueError):
        return -1


def _dir(ctx, thought_id):
    if not thought_id or os.path.basename(str(thought_id)) != str(thought_id):
        return None
    return os.path.join(ctx.home, "thoughts", str(thought_id))


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(text).strip() + "\n")
    os.replace(tmp, path)


def _ensure_ignored(ctx):
    path = os.path.join(ctx.home, ".gitignore")
    old = ""
    if os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            old = f.read()
    if "thoughts/" not in [line.strip() for line in old.splitlines()]:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(old + ("" if not old or old.endswith("\n") else "\n") + "thoughts/\n")
        os.replace(tmp, path)


def _content(result):
    try:
        return str(result["choices"][0]["message"].get("content") or "").strip()
    except (KeyError, IndexError, TypeError):
        return ""


def _parsed(text):
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        data = None
    if not isinstance(data, dict):
        return {"conclusion": text.strip(), "action": "", "risk": ""}
    return {"conclusion": str(data.get("conclusion") or data.get("summary") or text).strip(),
            "action": str(data.get("action") or "").strip(),
            "risk": str(data.get("risk") or data.get("uncertainty") or "").strip(),
            "reasons": data.get("reasons") if isinstance(data.get("reasons"), list) else [],
            "items": data.get("items") if isinstance(data.get("items"), list) else []}


def _usage(result, engine):
    aos = result.get("aos") if isinstance(result, dict) else {}
    raw = aos.get("usage") if isinstance(aos, dict) else None
    if not isinstance(raw, dict):
        raw = result.get("usage") if isinstance(result, dict) else {}
    raw = raw if isinstance(raw, dict) else {}
    details = raw.get("completion_tokens_details") or {}
    prompts = raw.get("prompt_tokens_details") or {}
    reasoning = details.get("reasoning_tokens") or raw.get("reasoning_tokens") or 0
    cached = prompts.get("cached_tokens") or raw.get("prompt_cache_hit_tokens") or 0
    prompt = raw.get("prompt_tokens") or 0
    completion = raw.get("completion_tokens") or 0
    price = engine.get("price") if isinstance(engine, dict) else None
    cost = None
    if isinstance(price, dict):
        cost = (max(0, prompt - cached) * float(price.get("input") or 0) +
                cached * float(price.get("cached") or 0) +
                max(0, completion - reasoning) * float(price.get("output") or 0) +
                reasoning * float(price.get("reasoning") or price.get("output") or 0)) / 1000000
    return {"prompt_tokens": prompt, "completion_tokens": completion,
            "reasoning_tokens": reasoning, "cached_tokens": cached,
            "total_tokens": raw.get("total_tokens") or prompt + completion,
            "cost_usd": cost, "raw": raw}


def _add_usage(total, usage):
    for key in ("prompt_tokens", "completion_tokens", "reasoning_tokens",
                "cached_tokens", "total_tokens"):
        total[key] = (total.get(key) or 0) + (usage.get(key) or 0)
    if usage.get("cost_usd") is not None:
        total["cost_usd"] = (total.get("cost_usd") or 0) + usage["cost_usd"]
    elif "cost_usd" not in total:
        total["cost_usd"] = None
    return total


def _messages(mode, question, previous="", step=1):
    if mode == "critique":
        system = ("檢查草稿。最多三條。只回 JSON："
                  '{"items":[{"problem":"漏洞或反例","why":"為什麼重要","fix":"最小修法"}],'
                  '"conclusion":"總結","action":"最小修法","risk":"主要風險"}')
        user = question
    elif mode == "think_steps":
        system = ('只做這一步，回短結論。只回 JSON：{"conclusion":"本步結論",'
                  '"action":"建議動作","risk":"仍不確定處"}')
        user = "原問題：%s" % question
        if previous:
            user += "\n上一步結論：%s" % previous
        user += "\n這是第 %d 步。" % step
    else:
        system = ('深入權衡後只回 JSON：{"conclusion":"短結論","reasons":["最多三個理由"],'
                  '"action":"建議動作","risk":"仍不確定處"}')
        user = question
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _send(ctx, thought_id, mode, question, budget, step, previous=""):
    engine_name, engine = _engine(ctx)
    meta = ctx.read_json(os.path.join(_dir(ctx, thought_id), "meta.json"), {})
    used = ((meta.get("usage") or {}).get("completion_tokens") or 0)
    left = max(1, budget["max_tokens"] - used)
    request_tokens = left if mode != "think_steps" else max(1, left // (budget["max_steps"] - step + 1))
    body = {"messages": _messages(mode, question, previous, step),
            "params": {"max_tokens": request_tokens}}
    name = ctx.send("think", body, priority=_priority(ctx), engine=engine_name,
                    timeout_s=budget["wait_s"])
    meta.update({"request": name, "engine": engine_name, "status": "waiting",
                 "request_step": step,
                 "current": {"mode": mode, "question": question, "budget": budget,
                             "step": step, "engine": engine_name, "engine_data": engine}})
    ctx.write_json(os.path.join(_dir(ctx, thought_id), "meta.json"), meta)
    ctx.sleep_until("think", name)
    return name


def _next_estimate(job, meta):
    """用下一發最多可能輸出的 token 估錢；沒單價就不猜。"""
    price = job.get("engine_data", {}).get("price")
    if not isinstance(price, dict):
        return None
    used = ((meta.get("usage") or {}).get("completion_tokens") or 0)
    left = max(1, job["budget"]["max_tokens"] - used)
    requests_left = max(1, job["budget"]["max_steps"] - job["step"])
    tokens = max(1, left // requests_left)
    rate = max(float(price.get("output") or 0), float(price.get("reasoning") or 0))
    return tokens * rate / 1000000


def _start(ctx, mode, text, budget_value):
    thought_id = _new_id()
    budget = _budget(budget_value, mode == "think_steps")
    folder = _dir(ctx, thought_id)
    _ensure_ignored(ctx)
    os.makedirs(folder, exist_ok=True)
    ctx.write_json(os.path.join(folder, "meta.json"), {
        "id": thought_id, "kind": mode, "question": text, "status": "waiting",
        "created_at": _now(), "finished_at": None, "budget": budget, "step": 0,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0,
                  "cached_tokens": 0, "total_tokens": 0, "cost_usd": None}})
    _send(ctx, thought_id, mode, text, budget, 1)
    word = "批評" if mode == "critique" else "想"
    return {"text": "開始%s了 id=%s" % (word, thought_id), "thought_id": thought_id}


def _finish(ctx, meta, final, status="done"):
    folder = _dir(ctx, meta["id"])
    meta.update({"status": status, "finished_at": _now(), "final": final})
    meta.pop("current", None)
    ctx.write_json(os.path.join(folder, "meta.json"), meta)
    _write_text(os.path.join(folder, "conclusion.md"), final.get("conclusion") or "（沒有結論）")


def run(name, args, ctx):
    if name == "think":
        return _start(ctx, "think", str(args.get("question") or ""), args.get("budget"))
    if name == "think_steps":
        return _start(ctx, "think_steps", str(args.get("question") or ""), args.get("budget"))
    if name == "critique":
        return _start(ctx, "critique", str(args.get("draft") or ""), args.get("budget"))
    if name == "thoughts_list":
        box = os.path.join(ctx.home, "thoughts")
        rows = []
        for thought_id in sorted(os.listdir(box), reverse=True)[:20] if os.path.isdir(box) else []:
            meta = ctx.read_json(os.path.join(box, thought_id, "meta.json"), {})
            if meta:
                rows.append({"id": thought_id, "question": ctx.truncate(meta.get("question") or "", 80),
                             "status": meta.get("status"), "steps": meta.get("step") or 0,
                             "usage": meta.get("usage") or {}, "finished_at": meta.get("finished_at")})
        return rows
    if name == "thought_read":
        thought_id = str(args.get("id") or "")
        folder = _dir(ctx, thought_id)
        meta = ctx.read_json(os.path.join(folder or "", "meta.json"), {})
        if not meta:
            return {"error": "找不到這份思考：%s" % thought_id}
        steps = []
        for number in range(1, int(meta.get("step") or 0) + 1):
            row = ctx.read_json(os.path.join(folder, "%02d.json" % number), {})
            if row:
                steps.append({"step": number, "conclusion": ctx.truncate(row.get("conclusion") or "")})
        final = meta.get("final") if isinstance(meta.get("final"), dict) else {}
        return {"id": thought_id, "question": ctx.truncate(meta.get("question") or ""),
                "status": meta.get("status"), "steps": steps,
                "conclusion": ctx.truncate(final.get("conclusion") or ""), "usage": meta.get("usage") or {}}
    return {"error": "think 沒有這個工具：%s" % name}


def on_result(ctx, kind, name, result):
    meta = None
    box = os.path.join(ctx.home, "thoughts")
    for thought_id in os.listdir(box) if os.path.isdir(box) else []:
        candidate = ctx.read_json(os.path.join(box, thought_id, "meta.json"), {})
        if isinstance(candidate, dict) and candidate.get("request") == name:
            meta = candidate
            break
    job = meta.get("current") if isinstance(meta, dict) else None
    if not isinstance(job, dict):
        ctx.log("收到找不到對照的深思結果：%s" % name)
        return
    folder = _dir(ctx, meta["id"])
    usage = _usage(result, job.get("engine_data") or {})
    meta["usage"] = _add_usage(meta.get("usage") or {}, usage)
    text = _content(result)
    final = _parsed(text)
    if result.get("error"):
        final = {"conclusion": "思考失敗：%s" % result.get("error"), "action": "", "risk": ""}
    elif final.get("conclusion"):
        meta["best"] = final
    elif isinstance(meta.get("best"), dict):
        final = meta["best"]
    ctx.write_json(os.path.join(folder, "%02d.json" % job["step"]), {
        "step": job["step"], "conclusion": final.get("conclusion") or "",
        "usage": usage, "result": result})
    meta["step"] = job["step"]
    over = (not text or
            (meta["usage"].get("completion_tokens") or 0) >= job["budget"]["max_tokens"])
    cost = meta["usage"].get("cost_usd")
    over = over or (cost is not None and cost >= job["budget"]["max_usd"])
    estimate = _next_estimate(job, meta)
    over = over or (cost is not None and estimate is not None and
                    cost + estimate > job["budget"]["max_usd"])
    if (job["mode"] == "think_steps" and not result.get("error") and not over and
            job["step"] < job["budget"]["max_steps"]):
        ctx.write_json(os.path.join(folder, "meta.json"), meta)
        _send(ctx, meta["id"], job["mode"], job["question"], job["budget"],
              job["step"] + 1, final.get("conclusion") or "")
        return
    if job["mode"] == "critique" and final.get("items"):
        lines = []
        for number, item in enumerate(final["items"][:3], 1):
            if isinstance(item, dict):
                lines.append("%d. %s；%s；最小修法：%s" %
                             (number, item.get("problem") or "", item.get("why") or "",
                              item.get("fix") or ""))
        final["conclusion"] = "\n".join(lines) or final.get("conclusion") or ""
    status = "error" if result.get("error") else ("budget_exceeded" if over else "done")
    _finish(ctx, meta, final, status)
    if result.get("error"):
        return None
    return "深思完成：%s%s%s" % (
        final.get("conclusion") or "（沒有結論）",
        "；動作：" + final["action"] if final.get("action") else "",
        "；風險：" + final["risk"] if final.get("risk") else "")
