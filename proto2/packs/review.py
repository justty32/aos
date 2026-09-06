"""review 工具包：看近期帳本、留下帶數字的教訓，並提醒自己回顧。"""

import datetime
import glob
import json
import os
import re


PROMPT = (
    "任務告一段落或收到回顧提醒時，先看最近摘要，再看長期規律。"
    "檢查目標有沒有完成、哪一步失敗、哪一步重複、哪個工具太貴、思考結論有沒有真的採用。"
    "只把會改變下次做法的事寫成教訓。格式固定為「同類任務／tag：原本平均 X 元／Y 格 → 改法 → "
    "之後平均 Z 元／W 格」，一條一行。偶發小事、措辭喜好、已經修好的單次錯誤，不要寫成教訓。"
    "先用教訓；只有某個工具包的做法反覆有問題，才改 prompt 覆蓋。"
    "只有同一串 shell 已手打三次，才造工具。"
)

EMPTY = {"type": "object", "properties": {}}
TOOLS = [
    {"name": "review_recent", "description": "回顧最近幾格或某個時間以後的工具帳。只回次數、時間、token、錢、繞路和最後結果，不回原文。",
     "parameters": {"type": "object", "properties": {
         "n_steps": {"type": "integer", "minimum": 1, "description": "往回看幾格"},
         "since": {"type": "string", "description": "起始時間，例如 2026-09-06T14:00:00"}}}},
    {"name": "review_patterns", "description": "看最近 30 天的花費規律。先列最貴工具，再列最貴任務、打轉工具和反覆錯誤。", "parameters": EMPTY},
    {"name": "review_thoughts", "description": "看一次或最近五次深度思考／分支的短結論、花費，以及後來有沒有採用。",
     "parameters": {"type": "object", "properties": {
         "id": {"type": "string", "description": "思考編號；不填就看最近五次"}}}},
    {"name": "lesson_add", "description": "新增一條帶金額與格數的教訓。格式：任務或 tag：原本平均 X 元／Y 格 → 改法 → 之後平均 Z 元／W 格。",
     "parameters": {"type": "object", "properties": {
         "text": {"type": "string", "description": "一行完整教訓"}}, "required": ["text"]}},
    {"name": "lessons_list", "description": "列最近 20 條教訓，新的在前面。", "parameters": EMPTY},
    {"name": "improve_prompt", "description": "整份換掉一個已開啟工具包的 prompt 覆蓋；下次走格才生效。",
     "parameters": {"type": "object", "properties": {
         "pack": {"type": "string", "description": "已開啟的工具包名字"},
         "text": {"type": "string", "description": "新的完整 prompt 內容"}},
         "required": ["pack", "text"]}},
]

REVIEW_TOOLS = {item["name"] for item in TOOLS}
PACK_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
LESSON = re.compile(
    r"^([^：\n]+)：原本平均 ([0-9]+(?:\.[0-9]+)?) 元／([0-9]+) 格 → (.+?) → "
    r"之後平均 ([0-9]+(?:\.[0-9]+)?) 元／([0-9]+) 格(?: 【無效】)?$"
)


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def _read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _row_cost(row):
    direct = _number(row.get("cost"))
    llm = row.get("llm_round")
    nested = _number(llm.get("cost")) if isinstance(llm, dict) else None
    return nested if nested is not None else direct


def _row_tokens(row):
    llm = row.get("llm_round")
    if not isinstance(llm, dict):
        return 0
    total = _number(llm.get("total_tokens"))
    if total is not None:
        return int(total)
    return sum(int(_number(llm.get(key)) or 0) for key in
               ("prompt_tokens", "completion_tokens", "reasoning_tokens", "cached_tokens"))


def _row_error(row):
    kind = row.get("error_kind") or row.get("error")
    if kind:
        return str(kind)
    return "失敗" if row.get("ok") is False else ""


def _parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _ledger_rows(home, days=None):
    cutoff = None
    if days is not None:
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    rows = []
    for path in sorted(glob.glob(os.path.join(home, "ledger", "????-??-??.jsonl"))):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        row = json.loads(line)
                    except (TypeError, ValueError):
                        continue
                    when = _parse_time(row.get("time")) if isinstance(row, dict) else None
                    if isinstance(row, dict) and (cutoff is None or when is None or when >= cutoff):
                        rows.append(row)
        except OSError:
            continue
    return rows


def _money(rows):
    values = [_row_cost(row) for row in rows]
    known = [value for value in values if value is not None]
    return round(sum(known), 8) if known else None


def _last_result(home):
    paths = sorted(glob.glob(os.path.join(home, "outbox", "*.json")))
    if not paths:
        return {"replied": False}
    try:
        data = json.loads(_read_text(paths[-1]))
    except ValueError:
        data = {}
    content = data.get("content") if isinstance(data, dict) else ""
    return {"replied": True, "error": bool(data.get("error")) if isinstance(data, dict) else False,
            "chars": len(str(content or "")), "file": os.path.basename(paths[-1])}


def _review_state(ctx):
    state = ctx.state.get("review")
    if not isinstance(state, dict):
        state = {}
        ctx.state["review"] = state
    return state


def _review_done(ctx):
    state = _review_state(ctx)
    state["last_review_step"] = int(ctx.state.get("step") or 0)
    state["last_review_tool_calls"] = int(state.get("tool_calls") or 0)
    state["reminder_open"] = False


def _mark_ineffective(home):
    path = os.path.join(home, "memory", "lessons.md")
    lines = [line for line in _read_text(path).splitlines() if line.strip()]
    changed = 0
    out = []
    for line in lines:
        match = LESSON.match(line)
        if match and "【無效】" not in line:
            old_cost, old_steps = float(match.group(2)), int(match.group(3))
            new_cost, new_steps = float(match.group(5)), int(match.group(6))
            if new_cost >= old_cost and new_steps >= old_steps:
                line += " 【無效】"
                changed += 1
        out.append(line)
    if changed:
        _write_text(path, "\n".join(out) + "\n")
    return changed


def _review_recent(args, ctx):
    n_steps, since = args.get("n_steps"), args.get("since")
    if (n_steps is None) == (since is None):
        return {"error": "n_steps 和 since 要剛好填一個"}
    rows = _ledger_rows(ctx.home)
    if n_steps is not None:
        if not isinstance(n_steps, int) or isinstance(n_steps, bool) or n_steps < 1:
            return {"error": "n_steps 要是大於 0 的整數"}
        first = int(ctx.state.get("step") or 0) - n_steps
        rows = [row for row in rows if isinstance(row.get("step"), int) and row["step"] >= first]
        window = "最近 %d 格" % n_steps
    else:
        start = _parse_time(since)
        if start is None:
            return {"error": "since 看不懂，請用 2026-09-06T14:00:00 這種時間"}
        rows = [row for row in rows if _parse_time(row.get("time")) and _parse_time(row.get("time")) >= start]
        window = "從 %s" % since

    tools = {}
    errors = {}
    detours = []
    last_tool = None
    for row in rows:
        tool = str(row.get("tool") or "不知道")
        tools[tool] = tools.get(tool, 0) + 1
        error = _row_error(row)
        if error:
            errors[error] = errors.get(error, 0) + 1
        if tool == last_tool and (not detours or detours[-1] != "連續呼叫 %s" % tool):
            detours.append("連續呼叫 %s" % tool)
        last_tool = tool
    for kind, count in errors.items():
        if count >= 2:
            detours.append("同一錯誤重現：%s（%d 次）" % (kind, count))
    undone = [str(row.get("tool") or "") for row in rows
              if re.search(r"(^|_)(undo|revert|rollback|remove|delete)($|_)", str(row.get("tool") or ""))]
    if undone:
        detours.append("做了又撤回：%s" % "、".join(undone))
    large_chars = sum(int(_number(row.get("result_chars")) or 0) for row in rows
                      if (_number(row.get("result_chars")) or 0) >= 4000)
    final_chars = _last_result(ctx.home).get("chars") or 0
    if large_chars and final_chars * 10 < large_chars:
        detours.append("拿回很多內容，但最後只用了很短的回話（%d 字 → %d 字）" % (large_chars, final_chars))

    invalid = _mark_ineffective(ctx.home)
    _review_done(ctx)
    return {"window": window, "tool_calls": len(rows), "tools": tools,
            "errors": sum(errors.values()), "total_seconds": round(sum(_number(r.get("took_ms")) or 0 for r in rows) / 1000, 3),
            "total_tokens": sum(_row_tokens(row) for row in rows), "total_cost": _money(rows),
            "detours": detours, "last_result": _last_result(ctx.home), "lessons_marked_ineffective": invalid}


def _group_row(group, row):
    group["calls"] += 1
    group["seconds"] += (_number(row.get("took_ms")) or 0) / 1000
    group["steps"] += int(_number(row.get("round_steps")) or 0)
    cost = _row_cost(row)
    if cost is not None:
        group["known_cost"] = True
        group["cost"] += cost
    if row.get("time"):
        group["last"] = str(row["time"])


def _group_result(name, group, extra=None):
    out = {"name": name, "calls": group["calls"],
           "cost": round(group["cost"], 8) if group["known_cost"] else None,
           "steps": group["steps"], "seconds": round(group["seconds"], 3), "last": group["last"]}
    if extra:
        out.update(extra)
    return out


def _blank_group():
    return {"calls": 0, "cost": 0.0, "known_cost": False, "steps": 0, "seconds": 0.0, "last": ""}


def _task_key(row):
    return row.get("task_tag") or row.get("task_key") or row.get("task") or "未標任務"


def _patterns(rows):
    by_tool, by_task, repeated_errors = {}, {}, {}
    repeat_rows = {}
    previous = None
    for row in rows:
        tool = str(row.get("tool") or "不知道")
        task = str(_task_key(row))
        by_tool.setdefault(tool, _blank_group())
        by_task.setdefault(task, _blank_group())
        _group_row(by_tool[tool], row)
        _group_row(by_task[task], row)
        error = _row_error(row)
        if error:
            key = "%s／%s" % (tool, error)
            item = repeated_errors.setdefault(key, {"count": 0, "last": ""})
            item["count"] += 1
            item["last"] = str(row.get("time") or item["last"])
        marker = row.get("args_mark") or row.get("args_marker") or row.get("args_fingerprint")
        same = previous and previous[0] == tool and (error or marker) and previous[1] == (error or marker)
        if same:
            repeat_rows.setdefault(tool, []).extend([] if repeat_rows.get(tool) else [previous[2]])
            repeat_rows[tool].append(row)
        previous = (tool, error or marker, row)

    expensive_tools = [_group_result(name, group) for name, group in by_tool.items()]
    expensive_tasks = [_group_result(name, group) for name, group in by_task.items()]
    expensive_tools.sort(key=lambda x: (x["cost"] is not None, x["cost"] or 0, x["calls"]), reverse=True)
    expensive_tasks.sort(key=lambda x: (x["cost"] is not None, x["cost"] or 0, x["calls"]), reverse=True)
    loops = []
    for name, items in repeat_rows.items():
        group = _blank_group()
        for row in items:
            _group_row(group, row)
        loops.append(_group_result(name, group, {"repeats": max(1, len(items) - 1)}))
    loops.sort(key=lambda x: (x["cost"] is not None, x["cost"] or 0, x["repeats"]), reverse=True)
    errors = [{"problem": name, **item} for name, item in repeated_errors.items() if item["count"] >= 2]
    errors.sort(key=lambda x: (x["count"], x["last"]), reverse=True)
    return expensive_tools[:10], expensive_tasks[:10], loops[:10], errors[:10]


def _review_patterns(ctx):
    rows = _ledger_rows(ctx.home, 30)
    tools, tasks, loops, errors = _patterns(rows)
    invalid = _mark_ineffective(ctx.home)
    _review_done(ctx)
    return {"window_days": 30, "records": len(rows), "expensive_tools": tools,
            "expensive_tasks": tasks, "repeated_without_progress": loops,
            "repeated_errors": errors, "lessons_marked_ineffective": invalid}


def _thought_dirs(home):
    found = []
    for kind in ("thoughts", "branches"):
        for path in glob.glob(os.path.join(home, kind, "*")):
            if os.path.isdir(path):
                found.append((os.path.getmtime(path), kind, path))
    return sorted(found, reverse=True)


def _short(text, n=300):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n] + "…"


def _used_later(home, conclusion, meta, path):
    explicit = meta.get("adopted", meta.get("adopt"))
    if explicit is not None:
        return "有採用" if bool(explicit) else "未採用"
    if os.path.isfile(os.path.join(path, "adopt.json")):
        return "有採用"
    needle = _short(conclusion, 40)
    if len(needle) >= 8:
        hay = _read_text(os.path.join(home, "prompts.json"))
        for outbox in glob.glob(os.path.join(home, "outbox", "*.json")):
            hay += _read_text(outbox)
        if needle in hay:
            return "有採用"
    return "不知道"


def _thought_one(home, kind, path):
    meta = {}
    try:
        value = json.loads(_read_text(os.path.join(path, "meta.json")) or "{}")
        meta = value if isinstance(value, dict) else {}
    except ValueError:
        pass
    conclusion = _read_text(os.path.join(path, "conclusion.md"))
    if not conclusion:
        conclusion = meta.get("conclusion") or meta.get("summary") or "沒有短結論"
    cost = _number(meta.get("cost"))
    usage = meta.get("usage")
    if cost is None and isinstance(usage, dict):
        cost = _number(usage.get("cost"))
    return {"id": os.path.basename(path), "kind": kind.rstrip("s"),
            "question": _short(meta.get("question") or meta.get("topic") or "不知道"),
            "conclusion": _short(conclusion), "cost": cost,
            "adopted": _used_later(home, conclusion, meta, path)}


def _review_thoughts(args, ctx):
    wanted = args.get("id")
    if wanted is not None and (not isinstance(wanted, str) or not wanted or os.path.basename(wanted) != wanted or wanted in (".", "..")):
        return {"error": "id 只能是一個思考編號，不能是路徑"}
    found = _thought_dirs(ctx.home)
    if wanted:
        found = [item for item in found if os.path.basename(item[2]) == wanted]
        if not found:
            return {"error": "找不到這次思考：%s" % wanted}
    rows = [_thought_one(ctx.home, kind, path) for _mtime, kind, path in found[:1 if wanted else 5]]
    _review_done(ctx)
    return {"thoughts": rows}


def _lesson_add(args, ctx):
    text = args.get("text")
    if not isinstance(text, str) or "\n" in text or not LESSON.match(text.strip()):
        return {"error": "教訓要一行，格式是：任務或 tag：原本平均 0.12 元／8 格 → 改法 → 之後平均 0.08 元／6 格"}
    text = text.strip()
    path = os.path.join(ctx.home, "memory", "lessons.md")
    lines = [line for line in _read_text(path).splitlines() if line.strip()]
    lines.append(text)
    archived = 0
    if len(lines) > 100:
        old, lines = lines[:20], lines[20:]
        archive = os.path.join(ctx.home, "memory", "lessons-archive", datetime.date.today().isoformat() + ".md")
        before = _read_text(archive)
        _write_text(archive, before + ("" if not before or before.endswith("\n") else "\n") + "\n".join(old) + "\n")
        archived = len(old)
    _write_text(path, "\n".join(lines) + "\n")
    return {"lesson": text, "count": len(lines), "archived": archived}


def _lessons_list(ctx):
    path = os.path.join(ctx.home, "memory", "lessons.md")
    lines = [line for line in _read_text(path).splitlines() if line.strip()]
    return {"count": len(lines), "lessons": list(reversed(lines[-20:]))}


def _improve_prompt(args, ctx):
    pack, text = args.get("pack"), args.get("text")
    if not isinstance(pack, str) or not PACK_NAME.match(pack):
        return {"error": "pack 名字只能用英數字、底線和減號"}
    enabled = [name for name, _module in ctx.loaded]
    if pack not in enabled:
        return {"error": "只能改已開啟的工具包：%s" % ("、".join(enabled) or "目前沒有")}
    if not isinstance(text, str):
        return {"error": "text 要是一段文字"}
    path = os.path.join(ctx.home, "prompt-overrides", pack + ".md")
    old = _read_text(path)
    _write_text(path, text)
    return {"path": path, "chars": len(text), "old_chars": len(old), "notice": "下次走格才會生效"}


def run(name, args, ctx):
    args = args if isinstance(args, dict) else {}
    if name == "review_recent":
        return _review_recent(args, ctx)
    if name == "review_patterns":
        return _review_patterns(ctx)
    if name == "review_thoughts":
        return _review_thoughts(args, ctx)
    if name == "lesson_add":
        return _lesson_add(args, ctx)
    if name == "lessons_list":
        return _lessons_list(ctx)
    if name == "improve_prompt":
        return _improve_prompt(args, ctx)
    return {"error": "review 沒有這個工具：%s" % name}


def on_act(ctx, tool, args, result, took_ms):
    if tool in REVIEW_TOOLS:
        return
    state = _review_state(ctx)
    state["tool_calls"] = int(state.get("tool_calls") or 0) + 1
    state["idle_streak"] = 0


def _task_cost_trigger(rows, notices):
    groups = {}
    for row in rows:
        task_id = row.get("task_id")
        if task_id is None:
            continue
        key = str(_task_key(row))
        ident = str(task_id)
        groups.setdefault((key, ident), []).append(row)
    by_key = {}
    for (key, ident), items in groups.items():
        cost = _money(items)
        if cost is not None:
            by_key.setdefault(key, []).append((str(items[-1].get("time") or ""), ident, cost))
    for key, tasks in by_key.items():
        tasks.sort()
        if len(tasks) < 2:
            continue
        latest = tasks[-1]
        older = [cost for _time, _ident, cost in tasks[:-1]]
        average = sum(older) / len(older)
        signature = "%s/%s" % (key, latest[1])
        if average > 0 and latest[2] > average * 2 and notices.get("task") != signature:
            return "單一任務花費超過同類平均兩倍", ("task", signature)
    return None


def _cost_trigger(ctx, state):
    conf = ctx.read_json(os.path.join(ctx.home, "llm.json"), {})
    review = conf.get("review") if isinstance(conf, dict) else None
    if not isinstance(review, dict):
        review = {}
    rows = _ledger_rows(ctx.home, 30)
    notices = state.setdefault("cost_notices", {})

    today = datetime.date.today().isoformat()
    daily = _number(review.get("daily_cost"))
    today_rows = [row for row in rows if str(row.get("time") or "").startswith(today)]
    today_cost = _money(today_rows)
    if daily is not None and today_cost is not None and today_cost > daily and notices.get("daily") != today:
        return "今天花費超過 %.6g 元門檻" % daily, ("daily", today)

    task = _task_cost_trigger(rows, notices)
    if task:
        return task

    limits = review.get("tool_cost")
    if isinstance(limits, dict):
        for tool, limit in limits.items():
            limit = _number(limit)
            recent = [row for row in rows if row.get("tool") == tool][-3:]
            costs = [_row_cost(row) for row in recent]
            if limit is not None and len(recent) == 3 and all(cost is not None and cost > limit for cost in costs):
                signature = "%s/%s" % (tool, recent[-1].get("time") or recent[-1].get("step") or len(rows))
                if notices.get("tool") != signature:
                    return "%s 連續三次超過成本門檻" % tool, ("tool", signature)
    return None


def on_idle(ctx):
    state = _review_state(ctx)
    step = int(ctx.state.get("step") or 0)
    last_idle = state.get("last_idle_step")
    state["idle_streak"] = int(state.get("idle_streak") or 0) + 1 if last_idle == step - 1 else 1
    state["last_idle_step"] = step
    if state.get("reminder_open"):
        return

    reason = None
    cost = _cost_trigger(ctx, state)
    if cost:
        reason, (kind, signature) = cost
        state.setdefault("cost_notices", {})[kind] = signature
    else:
        new_calls = int(state.get("tool_calls") or 0) - int(state.get("last_review_tool_calls") or 0)
        if state["idle_streak"] >= 3 and new_calls >= 10:
            reason = "連續三格沒事，而且上次回顧後多了 %d 次工具呼叫" % new_calls
    if reason:
        path = ctx.put_mail(ctx.world, "self", "該回顧了", reason=reason)
        if path:
            state["reminder_open"] = True
            state["last_reminder_step"] = step


def on_system_prompt(ctx):
    lessons = _lessons_list(ctx)["lessons"]
    if not lessons:
        return ""
    return "最近 20 條教訓（新的在前面）：\n" + "\n".join(lessons)
