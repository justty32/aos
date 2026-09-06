"""branch — 同一題分兩、三條 LLM 旁線想，再由主線收攏。"""
import datetime
import json
import os


MAX_DIRECTIONS = 3
DEFAULT_PER_BRANCH_TOKENS = 1500
MAX_TOTAL_TOKENS = 4500
SUMMARY_CHARS = 800

PROMPT = """branch 用法：
只有同一題真的有兩到三條不同走法，先各自想完再比較會更清楚時，才用 fork。
方向不要重疊；可以用「做法」「最可能失敗的地方」「完全不同的假設」切開。
每個方向只寫一件事。送出後系統會睡著；全到齊才叫一次 join。
join 後由你自己選一條，或合併各條的好處。某條已經做完整件事時，才用 adopt 接手它的整段記憶。
第一版不做巢狀分支。"""

TOOLS = [
    {
        "name": "fork",
        "description": "把同一題丟給兩到三個不重疊的 LLM 方向同時想。",
        "parameters": {
            "type": "object",
            "properties": {
                "directions": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 3,
                    "items": {"type": "string"},
                    "description": "兩到三個互不重疊的思考方向。",
                },
                "budget": {
                    "type": "object",
                    "description": "可選。只能把預設上限往下調。",
                    "properties": {
                        "per_branch_tokens": {"type": "integer", "minimum": 1, "maximum": 1500},
                        "total_tokens": {"type": "integer", "minimum": 1, "maximum": 4500},
                        "max_cost_usd": {"type": "number", "minimum": 0},
                    },
                    "additionalProperties": False,
                },
            },
            "required": ["directions"],
            "additionalProperties": False,
        },
    },
    {
        "name": "join",
        "description": "全到齊後，一次收回這組分支的全部短結論。",
        "parameters": {
            "type": "object",
            "properties": {"branch_id": {"type": "string", "description": "fork 回傳的 id。"}},
            "required": ["branch_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "adopt",
        "description": "用已完成的某條分支整段記憶取代現在主線。",
        "parameters": {
            "type": "object",
            "properties": {
                "branch_id": {"type": "string", "description": "fork 回傳的 id。"},
                "n": {"type": "integer", "minimum": 1, "maximum": 3, "description": "第幾條，從 1 開始。"},
            },
            "required": ["branch_id", "n"],
            "additionalProperties": False,
        },
    },
]


def _error(text):
    return {"error": text}


def _new_id():
    now = datetime.datetime.now()
    return "%s-%06d" % (now.strftime("%Y%m%d-%H%M%S"), now.microsecond)


def _root(ctx, branch_id):
    return os.path.join(ctx.home, "branches", branch_id)


def _meta(ctx, branch_id):
    return ctx.read_json(os.path.join(_root(ctx, branch_id), "meta.json"), {})


def _usage(result):
    aos = result.get("aos") if isinstance(result, dict) else None
    usage = aos.get("usage") if isinstance(aos, dict) else None
    return usage if isinstance(usage, dict) else {}


def _engine_name(ctx, result=None):
    aos = result.get("aos") if isinstance(result, dict) else None
    if isinstance(aos, dict) and aos.get("engine"):
        return aos["engine"]
    conf = ctx.read_json(os.path.join(ctx.home, "llm.json"), {})
    return conf.get("engine") if isinstance(conf, dict) else None


def _price(ctx, engine_name):
    engines = ctx.read_json(os.path.join(ctx.llm_dir(), "engines.json"), [])
    if not isinstance(engines, list):
        return None
    chosen = None
    for engine in engines:
        if not isinstance(engine, dict):
            continue
        if engine.get("name") == engine_name:
            chosen = engine
            break
        if chosen is None:
            chosen = engine
    price = chosen.get("price") if isinstance(chosen, dict) else None
    return price if isinstance(price, dict) else None


def _cost(ctx, usage, engine_name):
    price = _price(ctx, engine_name)
    if price is None:
        return None
    input_price = price.get("input", price.get("in"))
    output_price = price.get("output", price.get("out"))
    if not isinstance(input_price, (int, float)) or not isinstance(output_price, (int, float)):
        return None
    prompt = usage.get("prompt_tokens") or 0
    completion = usage.get("completion_tokens") or 0
    return round((prompt * input_price + completion * output_price) / 1000000, 8)


def _add_usage(total, usage):
    for key, value in usage.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total[key] = total.get(key, 0) + value


def _summary(result):
    if result.get("error"):
        text = "這條失敗：%s" % result.get("error")
    else:
        try:
            text = result["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError, AttributeError):
            text = "這條失敗：回覆裡找不到總結"
    text = str(text)
    if len(text) > SUMMARY_CHARS:
        text = text[:790] + "…（已截斷）"
    return text


def _fork_tool_result(base, branch_id, count):
    """branch 請求要接上當前 fork tool_call，否則 OpenAI 訊息串不完整。"""
    if not base or not isinstance(base[-1], dict):
        return []
    calls = base[-1].get("tool_calls")
    if not isinstance(calls, list):
        return []
    for call in calls:
        fn = call.get("function") if isinstance(call, dict) else None
        if isinstance(fn, dict) and fn.get("name") == "fork" and call.get("id"):
            content = json.dumps({"text": "開了 %d 條，id=%s" % (count, branch_id)}, ensure_ascii=False)
            return [{"role": "tool", "tool_call_id": call["id"], "content": content}]
    return []


def _budget(args, count):
    budget = args.get("budget") or {}
    if not isinstance(budget, dict):
        return None, "budget 要是一個物件"
    per_branch = budget.get("per_branch_tokens", DEFAULT_PER_BRANCH_TOKENS)
    total = budget.get("total_tokens", MAX_TOTAL_TOKENS)
    max_cost = budget.get("max_cost_usd")
    if (not isinstance(per_branch, int) or isinstance(per_branch, bool)
            or per_branch < 1 or per_branch > DEFAULT_PER_BRANCH_TOKENS):
        return None, "per_branch_tokens 要在 1 到 1500 之間"
    if (not isinstance(total, int) or isinstance(total, bool)
            or total < 1 or total > MAX_TOTAL_TOKENS):
        return None, "total_tokens 要在 1 到 4500 之間"
    if count * per_branch > total:
        return None, "%d 條共要 %d token，超過 total_tokens=%d" % (count, count * per_branch, total)
    if (max_cost is not None
            and (not isinstance(max_cost, (int, float)) or isinstance(max_cost, bool) or max_cost < 0)):
        return None, "max_cost_usd 要是不小於 0 的數字"
    return {"per_branch_tokens": per_branch, "total_tokens": total,
            "max_cost_usd": max_cost}, None


def _estimated_cost(ctx, base, count, per_branch):
    price = _price(ctx, _engine_name(ctx))
    if price is None:
        return None
    input_price = price.get("input", price.get("in"))
    output_price = price.get("output", price.get("out"))
    if not isinstance(input_price, (int, float)) or not isinstance(output_price, (int, float)):
        return None
    input_tokens = max(1, len(json.dumps(base, ensure_ascii=False)) // 3)
    return round(count * (input_tokens * input_price + per_branch * output_price) / 1000000, 8)


def _do_fork(args, ctx):
    if int(ctx.state.get("branch_depth") or 0) > 0:
        return _error("第一版不能在分支裡再 fork")
    directions = args.get("directions")
    if not isinstance(directions, list) or not 2 <= len(directions) <= MAX_DIRECTIONS:
        return _error("directions 要放兩到三個方向")
    if any(not isinstance(item, str) or not item.strip() for item in directions):
        return _error("每個方向都要是一句不為空的話")
    budget, problem = _budget(args, len(directions))
    if problem:
        return _error(problem)

    base = ctx.read_json(os.path.join(ctx.home, "prompts.json"), [])
    base = base if isinstance(base, list) else []
    estimated = _estimated_cost(ctx, base, len(directions), budget["per_branch_tokens"])
    if (budget["max_cost_usd"] is not None and estimated is not None
            and estimated > budget["max_cost_usd"]):
        return _error("預估最多花 %.8f 美元，超過 max_cost_usd" % estimated)

    branch_id = _new_id()
    root = _root(ctx, branch_id)
    actual = 0 if estimated is not None else None
    ctx.write_json(os.path.join(root, "base.json"), base)
    lines = []
    pending = []
    bridge = _fork_tool_result(base, branch_id, len(directions))
    for number, direction in enumerate(directions, 1):
        label = "%02d" % number
        prompts = list(base) + bridge + [{
            "role": "user",
            "content": "你負責這條：%s。只想這條。想完只回一段總結，不要叫工具。" % direction.strip(),
        }]
        ctx.write_json(os.path.join(root, label, "prompts.json"), prompts)
        request = ctx.send(
            "branch",
            {"messages": prompts, "params": {"max_tokens": budget["per_branch_tokens"]}},
            timeout_steps=120)
        pending.append(request)
        lines.append({"n": number, "direction": direction.strip(), "request": request,
                      "status": "pending", "usage": {}, "cost_usd": None})

    meta = {"id": branch_id, "mode": "llm", "directions": [d.strip() for d in directions],
            "budget": budget,
            "estimated_max_tokens": len(directions) * budget["per_branch_tokens"],
            "estimated_max_cost_usd": estimated, "actual_cost_usd": actual,
            "lines": lines}
    ctx.write_json(os.path.join(root, "meta.json"), meta)
    ctx.sleep_until("branch", pending[0])
    return {"text": "開了 %d 條，id=%s" % (len(directions), branch_id),
            "branch_id": branch_id, "count": len(directions),
            "estimated_max_tokens": meta["estimated_max_tokens"],
            "estimated_max_cost_usd": estimated, "actual_cost_usd": actual}


def _receive(ctx, branch_id, request, result):
    meta = _meta(ctx, branch_id)
    lines = meta.get("lines") if isinstance(meta.get("lines"), list) else []
    line = next((item for item in lines
                 if isinstance(item, dict) and item.get("request") == request), None)
    if line is None:
        return False
    text = _summary(result)
    label = "%02d" % int(line["n"])
    with open(os.path.join(_root(ctx, branch_id), label, "summary.md"),
              "w", encoding="utf-8") as f:
        f.write(text + "\n")
    prompts_path = os.path.join(_root(ctx, branch_id), label, "prompts.json")
    prompts = ctx.read_json(prompts_path, [])
    prompts = prompts if isinstance(prompts, list) else []
    ctx.write_json(prompts_path, prompts + [{"role": "assistant", "content": text}])

    usage = _usage(result)
    cost = _cost(ctx, usage, _engine_name(ctx, result))
    line.update({"status": "done", "summary": text, "usage": usage, "cost_usd": cost})
    completed = [item for item in lines
                 if isinstance(item, dict) and item.get("status") == "done"]
    known_costs = [item.get("cost_usd") for item in completed
                   if item.get("cost_usd") is not None]
    meta["actual_cost_usd"] = (round(sum(known_costs), 8)
                               if len(known_costs) == len(completed) else None)
    ctx.write_json(os.path.join(_root(ctx, branch_id), "meta.json"), meta)
    return True


def _find_branch_for_request(ctx, request):
    box = os.path.join(ctx.home, "branches")
    for branch_id in os.listdir(box) if os.path.isdir(box) else []:
        meta = _meta(ctx, branch_id)
        for line in meta.get("lines") or []:
            if isinstance(line, dict) and line.get("request") == request:
                return branch_id
    return None


def on_result(ctx, kind, name, result):
    if kind != "branch":
        return
    branch_id = _find_branch_for_request(ctx, name)
    if branch_id is None:
        ctx.log("找不到分支請求屬於哪個 id：%s" % name)
        return
    _receive(ctx, branch_id, name, result)
    meta = _meta(ctx, branch_id)
    pending = [line["request"] for line in meta.get("lines") or []
               if isinstance(line, dict) and line.get("status") == "pending"]
    if pending:
        ctx.sleep_until("branch", pending[0])
        return None
    if result.get("error"):
        return None
    return "%d 條分支都到齊了。現在只叫一次 join。" % len(meta.get("lines") or [])


def _do_join(args, ctx):
    branch_id = args.get("branch_id")
    meta = _meta(ctx, branch_id)
    if not meta:
        return _error("找不到這個分支：%s" % branch_id)
    pending = [line for line in meta.get("lines") or []
               if isinstance(line, dict) and line.get("status") == "pending"]
    if pending:
        return _error("分支還沒到齊；系統會等齊再叫醒你")

    rows = []
    total_usage = {}
    for line in meta.get("lines") or []:
        if not isinstance(line, dict):
            continue
        row = {"n": line.get("n"), "direction": line.get("direction"),
               "summary": line.get("summary") or "", "usage": line.get("usage") or {},
               "cost_usd": line.get("cost_usd")}
        rows.append(row)
        _add_usage(total_usage, row["usage"])
    text = "\n\n".join("方向 %s：%s\n%s" % (row["n"], row["direction"], row["summary"])
                         for row in rows)
    return {"text": text, "branch_id": branch_id, "branches": rows,
            "total_usage": total_usage, "actual_cost_usd": meta.get("actual_cost_usd")}


def _do_adopt(args, ctx):
    branch_id = args.get("branch_id")
    n = args.get("n")
    meta = _meta(ctx, branch_id)
    if not meta:
        return _error("找不到這個分支：%s" % branch_id)
    line = next((item for item in (meta.get("lines") or [])
                 if isinstance(item, dict) and item.get("n") == n), None)
    if line is None:
        return _error("這組分支沒有第 %s 條" % n)
    if line.get("status") != "done":
        return _error("第 %s 條還沒完成" % n)
    prompts = ctx.read_json(os.path.join(_root(ctx, branch_id), "%02d" % n, "prompts.json"), None)
    if not isinstance(prompts, list):
        return _error("第 %s 條的完整記憶不見了" % n)
    ctx.write_json(os.path.join(ctx.home, "prompts.json"), prompts)
    ctx.state["branch_depth"] = 1
    ctx.state["adopted_branch"] = {"id": branch_id, "n": n}
    ctx.state["branch_adopt_cleanup"] = True
    return {"text": "已接手分支 %s 的第 %d 條" % (branch_id, n),
            "branch_id": branch_id, "n": n}


def on_system_prompt(ctx):
    """adopt 後，清掉舊主線框架自動追加的 adopt 工具結果。"""
    if not ctx.state.pop("branch_adopt_cleanup", False):
        return ""
    path = os.path.join(ctx.home, "prompts.json")
    prompts = ctx.read_json(path, [])
    if isinstance(prompts, list) and prompts and isinstance(prompts[-1], dict) and prompts[-1].get("role") == "tool":
        ctx.write_json(path, prompts[:-1])
    return ""


def run(name, args, ctx):
    if name == "fork":
        return _do_fork(args, ctx)
    if name == "join":
        return _do_join(args, ctx)
    if name == "adopt":
        return _do_adopt(args, ctx)
    return _error("沒有這個 branch 工具：%s" % name)
