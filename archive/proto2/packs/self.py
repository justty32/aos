"""self 工具包 — 看自己的狀況、身分、時間與花費。"""

import datetime
import os
import re


MEMORY_LIMIT = 80000

PROMPT = "只想看時間用 self_time，較便宜；別為了看時間叫 self_status。"

TOOLS = [
    {"name": "self_status",
     "description": "看自己的格數、開機時間、記憶長度、資料夾大小與 LLM 用量。",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "self_cost",
     "description": "看某天這台引擎用了多少 token、幾次請求，估算美元。",
     "parameters": {"type": "object", "properties": {
         "day": {"type": "string", "description": "YYYY-MM-DD，預設今天"}
     }}},
    {"name": "self_who",
     "description": "看自己是誰、住哪、父是誰、時鐘、小孩、連哪個 LLM。",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "self_time",
     "description": "看本地時間、開機時間與已開機秒數，不掃資料夾。",
     "parameters": {"type": "object", "properties": {}}},
]


def _configured_engine(ctx):
    llm_dir = ctx.find_llm()
    if not llm_dir:
        return None, None
    engines = ctx.read_json(os.path.join(llm_dir, "engines.json"), [])
    engines = [e for e in engines if isinstance(e, dict)] if isinstance(engines, list) else []
    own = ctx.read_json(os.path.join(ctx.home, "llm.json"), {})
    defaults = ctx.read_json(os.path.join(llm_dir, "defaults.json"), {})
    own = own if isinstance(own, dict) else {}
    defaults = defaults if isinstance(defaults, dict) else {}
    wanted = own.get("engine") or defaults.get("engine")
    if not wanted and engines:
        wanted = engines[0].get("name")
    for engine in engines:
        if engine.get("name") == wanted:
            return llm_dir, engine
    return llm_dir, None


def _number(row, *names):
    for name in names:
        value = row.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return 0


def _cost(row, price):
    if not isinstance(price, dict):
        return None
    prompt = _number(row, "prompt_tokens")
    completion = _number(row, "completion_tokens")
    reasoning = _number(row, "reasoning_tokens",
                        "completion_tokens_details.reasoning_tokens")
    cached = _number(row, "cached_tokens", "prompt_cache_hit_tokens",
                     "prompt_tokens_details.cached_tokens")
    input_price = _number(price, "input")
    output_price = _number(price, "output")
    reasoning_price = price.get("reasoning")
    cached_price = price.get("cached")
    reasoning_price = output_price if not isinstance(reasoning_price, (int, float)) else reasoning_price
    cached_price = input_price if not isinstance(cached_price, (int, float)) else cached_price
    total = (max(0, prompt - cached) * input_price
             + cached * cached_price
             + max(0, completion - reasoning) * output_price
             + reasoning * reasoning_price) / 1000000
    return round(total, 8)


def _self_status(ctx):
    status = ctx.status()
    chars = int((status.get("memory") or {}).get("chars") or 0)
    status["history_chars"] = chars
    status["history_tokens"] = chars // 3
    status["history_pct"] = round(chars * 100 / MEMORY_LIMIT, 1)
    return status


def _self_cost(args, ctx):
    day = args.get("day") or datetime.date.today().isoformat()
    if not isinstance(day, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", day):
        return {"error": "day 要寫成 YYYY-MM-DD"}
    llm_dir, engine = _configured_engine(ctx)
    if not llm_dir or not engine:
        return {"error": "找不到自己正在用的 LLM 引擎"}
    book = ctx.read_json(os.path.join(llm_dir, "usage", day + ".json"), {})
    book = book if isinstance(book, dict) else {}
    rows = book.get("by-model") or book.get("by_model") or book
    rows = rows if isinstance(rows, dict) else {}
    key = "%s|%s" % (engine.get("base_url") or "", engine.get("model") or "")
    row = rows.get(key)
    row = row if isinstance(row, dict) else {}
    return {
        "prompt_tokens": _number(row, "prompt_tokens"),
        "completion_tokens": _number(row, "completion_tokens"),
        "requests": _number(row, "requests"),
        "cost_usd": _cost(row, engine.get("price")),
    }


def _self_who(ctx):
    parent = ctx.parent()
    kids = ctx.kids()
    names = sorted(str(name) for name in kids)
    parent_path = None
    if parent:
        parent_path = parent.get("dir") or parent.get("parent")
    return {
        "name": ctx.name,
        "world": ctx.world,
        "parent": parent_path,
        "clock": ctx.clock_of(ctx.world),
        "kids": {"count": len(names), "names": names},
        "llm_dir": ctx.find_llm(),
    }


def _self_time(ctx):
    status = ctx.status()
    memory = status.get("memory") or {}
    return {
        "now": datetime.datetime.now().isoformat(timespec="seconds"),
        "started": memory.get("started"),
        "uptime_s": memory.get("uptime_s"),
    }


def run(name, args, ctx):
    if name == "self_status":
        return _self_status(ctx)
    if name == "self_cost":
        return _self_cost(args, ctx)
    if name == "self_who":
        return _self_who(ctx)
    if name == "self_time":
        return _self_time(ctx)
    return {"error": "self 沒有這個工具：%s" % name}
