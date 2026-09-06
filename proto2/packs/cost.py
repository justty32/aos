"""cost 工具包：每次工具呼叫記一筆時間、字數、token 與價錢。"""
import datetime
import hashlib
import json
import os


PROMPT = ("成本：每次工具呼叫都會記下時間、回傳字數、下一輪用掉的 token 和價錢。"
          "回傳很長的工具最貴，因為內容會留在記憶裡，之後每輪都會再送一次。"
          "貴的工具少叫；能一次講完就別分兩次；只要一小段時別抓整包。"
          "想知道哪個工具最貴，用 cost_summary；想看剛才幾筆，用 cost_recent。")

TOOLS = [
    {"name": "cost_summary",
     "description": "按工具名看呼叫次數、平均時間、平均回傳字數、平均 prompt token 與總價錢。",
     "parameters": {"type": "object", "properties": {
         "day": {"type": "string", "description": "日期 YYYY-MM-DD；不填就是今天"}}}},
    {"name": "cost_recent",
     "description": "看最近幾次工具呼叫的帳。",
     "parameters": {"type": "object", "properties": {
         "n": {"type": "integer", "description": "要看幾筆；預設 10，最多 50"}}}},
]


def _day():
    return datetime.date.today().isoformat()


def _ledger_dir(ctx):
    return os.path.join(ctx.home, "ledger")


def _ledger_path(ctx, day):
    return os.path.join(_ledger_dir(ctx), day + ".jsonl")


def _json_text(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _args_mark(args):
    text = json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _result_status(tool, result):
    if isinstance(result, dict):
        if result.get("error"):
            return False, "tool_error"
        if "exit" in result:
            code = result.get("exit")
            if code is None:
                return False, "timeout"
            if isinstance(code, int) and code != 0:
                return False, "exit_%d" % code
    if isinstance(result, str) and result.startswith("沒有這個工具："):
        return False, "unknown_tool"
    return True, None


def _read_lines(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return rows


def _write_lines(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _append_line(path, row):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(_read_lines(path))


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _usage_numbers(usage):
    usage = usage if isinstance(usage, dict) else {}
    completion_details = usage.get("completion_tokens_details")
    completion_details = completion_details if isinstance(completion_details, dict) else {}
    prompt_details = usage.get("prompt_tokens_details")
    prompt_details = prompt_details if isinstance(prompt_details, dict) else {}
    return {
        "prompt_tokens": _number(usage.get("prompt_tokens")),
        "completion_tokens": _number(usage.get("completion_tokens")),
        "reasoning_tokens": _number(usage.get("reasoning_tokens")) or
                            _number(completion_details.get("reasoning_tokens")),
        "cached_tokens": _number(usage.get("cached_tokens")) or
                         _number(prompt_details.get("cached_tokens")) or
                         _number(usage.get("prompt_cache_hit_tokens")),
    }


def _price(ctx, result=None):
    if not isinstance(result, dict):
        result = ctx.read_json(os.path.join(ctx.home, "llm-result.json"), {})
    aos = result.get("aos") if isinstance(result, dict) else {}
    aos = aos if isinstance(aos, dict) else {}
    engine_name = aos.get("engine")
    where = ctx.find_llm()
    engines = ctx.read_json(os.path.join(where, "engines.json"), []) if where else []
    if not isinstance(engines, list):
        return None
    for engine in engines:
        if isinstance(engine, dict) and engine.get("name") == engine_name:
            price = engine.get("price")
            return price if isinstance(price, dict) else None
    return None


def _result_mark(ctx):
    try:
        return os.stat(os.path.join(ctx.home, "llm-result.json")).st_mtime_ns
    except OSError:
        return None


def _money(tokens, price):
    if not isinstance(price, dict):
        return None
    input_price = _number(price.get("input"))
    output_price = _number(price.get("output"))
    cached_price = _number(price.get("cached")) if "cached" in price else input_price
    reasoning_price = (_number(price.get("reasoning"))
                       if "reasoning" in price else output_price)
    prompt = tokens["prompt_tokens"]
    cached = min(prompt, tokens["cached_tokens"])
    completion = tokens["completion_tokens"]
    reasoning = min(completion, tokens["reasoning_tokens"])
    amount = ((prompt - cached) * input_price + cached * cached_price +
              (completion - reasoning) * output_price + reasoning * reasoning_price)
    return round(amount / 1000000.0, 12)


def _scaled(value, share):
    value = value * share
    return int(value) if float(value).is_integer() else round(value, 6)


def _summary_rows(rows):
    work = {}
    for row in rows:
        llm = row.get("llm_round")
        if not isinstance(llm, dict):
            continue
        tool = str(row.get("tool") or "")
        rec = work.setdefault(tool, {"calls": 0, "ms": 0, "chars": 0,
                                     "prompt": 0, "cost": 0, "known": True,
                                     "last": ""})
        rec["calls"] += 1
        rec["ms"] += _number(row.get("took_ms"))
        rec["chars"] += _number(row.get("result_chars"))
        rec["prompt"] += _number(llm.get("prompt_tokens"))
        if llm.get("cost") is None:
            rec["known"] = False
        else:
            rec["cost"] += _number(llm.get("cost"))
        rec["last"] = str(row.get("time") or rec["last"])
    out = {}
    for tool, rec in sorted(work.items()):
        calls = rec["calls"]
        out[tool] = {
            "calls": calls,
            "avg_ms": round(rec["ms"] / calls, 3),
            "avg_result_chars": round(rec["chars"] / calls, 3),
            "avg_prompt_tokens": round(rec["prompt"] / calls, 3),
            "total_cost": round(rec["cost"], 12) if rec["known"] else None,
            "last": rec["last"],
        }
    return out


def _total(rows):
    calls = sum(row["calls"] for row in rows.values())
    if not calls:
        return {"calls": 0, "avg_ms": 0, "avg_result_chars": 0,
                "avg_prompt_tokens": 0, "total_cost": 0}
    known = all(row["total_cost"] is not None for row in rows.values())
    return {
        "calls": calls,
        "avg_ms": round(sum(row["avg_ms"] * row["calls"] for row in rows.values()) / calls, 3),
        "avg_result_chars": round(sum(row["avg_result_chars"] * row["calls"]
                                      for row in rows.values()) / calls, 3),
        "avg_prompt_tokens": round(sum(row["avg_prompt_tokens"] * row["calls"]
                                       for row in rows.values()) / calls, 3),
        "total_cost": (round(sum(row["total_cost"] for row in rows.values()), 12)
                       if known else None),
    }


def _all_rows(ctx):
    box = _ledger_dir(ctx)
    rows = []
    if not os.path.isdir(box):
        return rows
    for name in sorted(os.listdir(box)):
        if name.endswith(".jsonl"):
            rows.extend(_read_lines(os.path.join(box, name)))
    return rows


def _save_summary(ctx):
    ctx.write_json(os.path.join(_ledger_dir(ctx), "summary.json"),
                   _summary_rows(_all_rows(ctx)))


def _close_pending(ctx, usage=None, step_offset=1, result=None):
    pending = ctx.state.get("pending_ledger")
    if not isinstance(pending, list) or not pending:
        return False
    explicit_usage = isinstance(usage, dict)
    if not isinstance(result, dict):
        result = ctx.read_json(os.path.join(ctx.home, "llm-result.json"), {})
    aos = result.get("aos") if isinstance(result, dict) else None
    result_usage = aos.get("usage") if isinstance(aos, dict) else None
    state_usage = ctx.state.get("last_usage")
    current_usage = usage if explicit_usage else state_usage
    if not isinstance(current_usage, dict):
        return False
    current_mark = json.dumps(current_usage, sort_keys=True, ensure_ascii=False)
    old_mark = pending[0].get("usage_mark")
    result_changed = _result_mark(ctx) != pending[0].get("result_mark")
    if result_changed and isinstance(result_usage, dict):
        current_usage = result_usage
        current_mark = json.dumps(current_usage, sort_keys=True, ensure_ascii=False)
    current_step = int(ctx.state.get("step") or 0)
    if not explicit_usage and current_mark == old_mark and not (
            result_changed and isinstance(result_usage, dict)):
        return False
    if not explicit_usage and current_step <= int(pending[0].get("step") or 0):
        return False

    tokens = _usage_numbers(current_usage)
    total_chars = sum(max(0, int(item.get("result_chars") or 0)) for item in pending)
    count = len(pending)
    price = _price(ctx, result)
    by_day = {}
    for item in pending:
        chars = max(0, int(item.get("result_chars") or 0))
        share = chars / total_chars if total_chars else 1.0 / count
        part = {key: _scaled(value, share) for key, value in tokens.items()}
        part["cost"] = _money(part, price)
        day = str(item.get("day") or _day())
        by_day.setdefault(day, []).append((item, part))

    for day, changes in by_day.items():
        path = _ledger_path(ctx, day)
        rows = _read_lines(path)
        for item, part in changes:
            line = int(item.get("line") or 0)
            if 1 <= line <= len(rows):
                rows[line - 1]["round_steps"] = max(
                    0, current_step - int(item.get("step") or 0) - step_offset)
                rows[line - 1]["llm_round"] = part
        _write_lines(path, rows)
    ctx.state["pending_ledger"] = []
    _save_summary(ctx)
    return True


def on_act(ctx, tool, args, result, took_ms):
    _close_pending(ctx)
    day = _day()
    ok, error_kind = _result_status(tool, result)
    text = _json_text(result)
    usage = ctx.state.get("last_usage")
    usage_mark = json.dumps(usage, sort_keys=True, ensure_ascii=False)
    row = {"time": datetime.datetime.now().isoformat(timespec="seconds"),
           "step": int(ctx.state.get("step") or 0), "tool": str(tool or ""),
           "args_chars": len(_json_text(args)), "args_mark": _args_mark(args),
           "result_chars": len(text), "took_ms": int(took_ms),
           "round_steps": None, "ok": ok, "error_kind": error_kind,
           "llm_round": None}
    line = _append_line(_ledger_path(ctx, day), row)
    pending = ctx.state.get("pending_ledger")
    if not isinstance(pending, list):
        pending = []
        ctx.state["pending_ledger"] = pending
    pending.append({"day": day, "line": line, "step": row["step"],
                    "result_chars": row["result_chars"], "usage_mark": usage_mark,
                    "result_mark": _result_mark(ctx)})


def on_idle(ctx):
    _close_pending(ctx)


def on_reply(ctx, msg):
    _close_pending(ctx)


def on_result(ctx, kind, name, result):
    if kind != "main":
        return
    on_main_result(ctx, name, result)


def on_main_result(ctx, name, result):
    aos = result.get("aos") if isinstance(result, dict) else None
    usage = aos.get("usage") if isinstance(aos, dict) else None
    _close_pending(ctx, usage=usage, result=result)


def on_system_prompt(ctx):
    _close_pending(ctx)
    return ""


def run(name, args, ctx):
    _close_pending(ctx)
    if name == "cost_summary":
        day = args.get("day") or _day()
        rows = _summary_rows(_read_lines(_ledger_path(ctx, day)))
        return {"day": day, "tools": rows, "total": _total(rows)}
    if name == "cost_recent":
        try:
            n = int(args.get("n") or 10)
        except (TypeError, ValueError):
            n = 10
        n = min(50, max(1, n))
        return _all_rows(ctx)[-n:]
    return {"error": "cost 沒有這個工具：%s" % name}
