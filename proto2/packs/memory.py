"""memory 工具包 — 整理 prompts.json 與保存長期筆記。"""

import datetime
import json
import os
import re


NUDGE_CHARS = 40000
TRIM_CHARS = 80000

PROMPT = (
    "memory_summarize_old 交回舊原文後，下一輪寫好摘要一定要叫 memory_replace_old。"
    "self_note 只能追加，不能覆寫人格。"
)

TOOLS = [
    {"name": "memory_list", "description": "列一段記憶的序號、角色與前 60 字。",
     "parameters": {"type": "object", "properties": {
         "offset": {"type": "integer", "description": "預設 0"},
         "count": {"type": "integer", "description": "預設 20"}
     }}},
    {"name": "memory_summarize_old", "description": "取出較舊原文，不改記憶，等你交摘要。",
     "parameters": {"type": "object", "properties": {
         "keep_recent": {"type": "integer", "description": "保留最近幾則，預設 20"}
     }}},
    {"name": "memory_replace_old", "description": "把取出的舊對話換成你寫好的摘要。",
     "parameters": {"type": "object", "properties": {
         "summary": {"type": "string"}
     }, "required": ["summary"]}},
    {"name": "memory_forget", "description": "忘掉一段連續記憶，原文先備份。",
     "parameters": {"type": "object", "properties": {
         "from": {"type": "integer", "description": "起始序號，含"},
         "to": {"type": "integer", "description": "結束序號，含"}
     }, "required": ["from", "to"]}},
    {"name": "note_save", "description": "把以後還會用到的資料存成長期筆記。",
     "parameters": {"type": "object", "properties": {
         "title": {"type": "string"},
         "text": {"type": "string"}
     }, "required": ["title", "text"]}},
    {"name": "note_find", "description": "列長期筆記，給關鍵字則列出命中的行。",
     "parameters": {"type": "object", "properties": {
         "keyword": {"type": "string", "description": "不給就列全部檔名"}
     }}},
    {"name": "note_read", "description": "讀一份 note_find 找到的長期筆記。",
     "parameters": {"type": "object", "properties": {
         "name": {"type": "string"}
     }, "required": ["name"]}},
    {"name": "self_note", "description": "在自我提醒尾端追加一句，放進 system prompt。",
     "parameters": {"type": "object", "properties": {
         "text": {"type": "string"}
     }, "required": ["text"]}},
]


def _history_path(ctx):
    return os.path.join(ctx.home, "prompts.json")


def _history(ctx):
    data = ctx.read_json(_history_path(ctx), [])
    return data if isinstance(data, list) else []


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def _archive(ctx, messages):
    path = os.path.join(ctx.home, "memory", "forgotten", _stamp() + ".json")
    ctx.write_json(path, messages)
    return path


def _preview(message):
    if not isinstance(message, dict):
        return str(message)[:60]
    content = message.get("content")
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    return content.replace("\n", " ")[:60]


def _memory_list(args, ctx):
    history = _history(ctx)
    offset = int(args.get("offset", 0))
    count = int(args.get("count", 20))
    items = []
    for index, message in enumerate(history[offset:offset + count], offset):
        role = message.get("role") if isinstance(message, dict) else "unknown"
        items.append({"index": index, "role": role, "preview": _preview(message)})
    return {"offset": offset, "items": items}


def _summarize(args, ctx):
    history = _history(ctx)
    keep = int(args.get("keep_recent", 20))
    count = max(0, len(history) - keep)
    if count == 0:
        return {"error": "沒有可摘要的舊對話"}
    ctx.state["pending_summary"] = {"count": count}
    return {
        "old_messages": history[:count],
        "next": "請寫一段摘要，然後呼叫 memory_replace_old 交回來。",
    }


def _replace(args, ctx):
    pending = ctx.state.get("pending_summary")
    if not isinstance(pending, dict):
        return {"error": "沒有待換掉的舊對話；請先叫 memory_summarize_old"}
    summary = args.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return {"error": "summary 不能是空的"}
    history = _history(ctx)
    count = int(pending.get("count") or 0)
    old = history[:count]
    _archive(ctx, old)
    marker = {"role": "user", "content": "（前面的對話摘要）" + summary.strip()}
    new_history = [marker] + history[count:]
    ctx.write_json(_history_path(ctx), new_history)
    ctx.state.pop("pending_summary", None)
    return {"replaced": len(old), "remaining": len(new_history)}


def _forget(args, ctx):
    history = _history(ctx)
    start = int(args.get("from", -1))
    end = int(args.get("to", -1))
    if start < 0 or end < start or end >= len(history):
        return {"error": "from／to 不在記憶範圍內"}
    old = history[start:end + 1]
    _archive(ctx, old)
    new_history = history[:start] + history[end + 1:]
    ctx.write_json(_history_path(ctx), new_history)
    return {"forgotten": len(old), "remaining": len(new_history)}


def _safe_title(title):
    name = re.sub(r"[^\w.-]+", "-", str(title), flags=re.UNICODE).strip("._-")
    return name or "note"


def _note_save(args, ctx):
    title = str(args.get("title") or "").strip()
    text = str(args.get("text") or "").strip()
    if not title or not text:
        return {"error": "title 和 text 都不能是空的"}
    path = os.path.join(ctx.home, "memory", "notes",
                        "%s-%s.md" % (_safe_title(title), _stamp()))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# %s\n\n%s\n" % (title, text))
    return {"path": path}


def _note_find(args, ctx):
    folder = os.path.join(ctx.home, "memory", "notes")
    keyword = args.get("keyword")
    keyword = str(keyword) if keyword is not None else ""
    found = []
    if not os.path.isdir(folder):
        return {"notes": found}
    for name in sorted(n for n in os.listdir(folder) if n.endswith(".md")):
        path = os.path.join(folder, name)
        if not keyword:
            found.append({"name": name})
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = [line.rstrip("\n") for line in f if keyword.lower() in line.lower()]
        except OSError:
            lines = []
        if lines:
            found.append({"name": name, "matches": lines})
    return {"notes": found}


def _note_read(args, ctx):
    name = str(args.get("name") or "")
    if not name or os.path.basename(name) != name:
        return {"error": "name 要填 note_find 列出的檔名"}
    path = os.path.join(ctx.home, "memory", "notes", name)
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return {"error": "找不到筆記：%s" % name}
    return {"name": name, "content": ctx.truncate(content)}


def _self_note(args, ctx):
    text = str(args.get("text") or "").strip().replace("\n", " ")
    if not text:
        return {"error": "text 不能是空的"}
    path = os.path.join(ctx.home, "memory", "self-note.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text + "\n")
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = sum(1 for _ in f)
    return {"path": path, "lines": lines}


def run(name, args, ctx):
    handlers = {
        "memory_list": _memory_list,
        "memory_summarize_old": _summarize,
        "memory_replace_old": _replace,
        "memory_forget": _forget,
        "note_save": _note_save,
        "note_find": _note_find,
        "note_read": _note_read,
        "self_note": _self_note,
    }
    handler = handlers.get(name)
    if not handler:
        return {"error": "memory 沒有這個工具：%s" % name}
    return handler(args, ctx)


def on_system_prompt(ctx):
    path = os.path.join(ctx.home, "memory", "self-note.md")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
    except OSError:
        return ""
    return "你給自己的長期提醒：\n" + text if text else ""


def on_idle(ctx):
    history = _history(ctx)
    chars = len(json.dumps(history, ensure_ascii=False))
    if chars > TRIM_CHARS:
        count = len(history) // 2
        old = history[:count]
        _archive(ctx, old)
        marker = {"role": "user", "content": "（前面 %d 則太長被截掉了）" % len(old)}
        ctx.write_json(_history_path(ctx), [marker] + history[count:])
        ctx.state.pop("pending_summary", None)
        return
    if chars > NUDGE_CHARS:
        if ctx.state.get("nudged_at_step") is None:
            path = ctx.put_mail(ctx.world, "self",
                                "你的記憶太長了，先用 memory_summarize_old 整理一下")
            if path:
                ctx.state["nudged_at_step"] = int(ctx.state.get("step") or 0)
        return
    ctx.state.pop("nudged_at_step", None)
