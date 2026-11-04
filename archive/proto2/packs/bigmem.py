"""bigmem 工具包 — 非阻塞地跟獨立記憶世界交換 requests/results。"""
import json
import os


PROMPT = "長期記憶是非同步的：送出後睡著，結果回來才接續。"

TOOLS = [
    {"name": "mem_put", "description": "存一件長期記憶。",
     "parameters": {"type": "object", "properties": {
         "text": {"type": "string"},
         "tags": {"type": "array", "items": {"type": "string"}}},
         "required": ["text"]}},
    {"name": "mem_find", "description": "用文字或標籤找長期記憶。",
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string"},
         "limit": {"type": "integer", "description": "預設 10、上限 50"}},
         "required": ["query"]}},
    {"name": "mem_get", "description": "用 id 讀一筆記憶全文。",
     "parameters": {"type": "object", "properties": {
         "id": {"type": "string"}}, "required": ["id"]}},
    {"name": "mem_forget", "description": "刪掉一筆長期記憶。",
     "parameters": {"type": "object", "properties": {
         "id": {"type": "string"}}, "required": ["id"]}},
    {"name": "mem_archive_history", "description": "歸檔一段對話，原處縮成一句。",
     "parameters": {"type": "object", "properties": {
         "from": {"type": "integer", "description": "起始序號，從 0 起"},
         "to": {"type": "integer", "description": "結束序號，含此則"}},
         "required": ["from", "to"]}},
]


def _mem_dir(ctx):
    conf = ctx.read_json(os.path.join(ctx.home, "llm.json"), {})
    conf = conf if isinstance(conf, dict) else {}
    where = conf.get("mem_dir") or os.environ.get("AOS_MEM_DIR") or ""
    if not where:
        return None
    return ctx.world_of(where)


def _queue(ctx, op, args, archive=None):
    mem = _mem_dir(ctx)
    if not mem:
        return {"error": "沒設定記憶世界；請在 llm.json 加 mem_dir，或設定 AOS_MEM_DIR"}
    name = ctx.send("mem", {"op": op, "agent": ctx.name, "args": args},
                    target=mem, timeout_s=600)
    item = {"op": op}
    if archive:
        item["archive"] = archive
    ctx.write_json(os.path.join(ctx.home, "side", "mem-meta", name), item)
    ctx.sleep_until("mem", name)
    return {"queued": True, "request": name}


def _archive(args, ctx):
    try:
        start = int(args.get("from"))
        end = int(args.get("to"))
    except (TypeError, ValueError):
        return {"error": "from 和 to 要是整數"}
    history = ctx.read_json(os.path.join(ctx.home, "prompts.json"), [])
    if (not isinstance(history, list) or start < 0 or end < start
            or end >= len(history)):
        return {"error": "找不到這段對話：%s 到 %s" % (start, end)}
    picked = history[start:end + 1]
    text = json.dumps(picked, ensure_ascii=False, indent=2)
    answer = _queue(ctx, "put", {
        "text": text, "tags": ["history"], "kind": "history",
        "source": "prompts.json:%d-%d" % (start, end),
    }, archive={"from": start, "to": end, "messages": len(picked), "chars": len(text)})
    if answer.get("queued"):
        answer.update({"messages": len(picked), "chars": len(text)})
    return answer


def run(name, args, ctx):
    if name == "mem_put":
        text = args.get("text")
        if not isinstance(text, str) or not text:
            return {"error": "text 不能空白"}
        tags = args.get("tags") if isinstance(args.get("tags"), list) else []
        return _queue(ctx, "put", {"text": text, "tags": [str(x) for x in tags]})
    if name == "mem_find":
        query = args.get("query")
        if not isinstance(query, str):
            return {"error": "query 要是文字"}
        try:
            limit = int(args.get("limit") or 10)
        except (TypeError, ValueError):
            limit = 10
        return _queue(ctx, "find", {"query": query, "limit": max(1, min(limit, 50))})
    if name == "mem_get":
        return _queue(ctx, "get", {"id": str(args.get("id") or "")})
    if name == "mem_forget":
        return _queue(ctx, "forget", {"id": str(args.get("id") or "")})
    if name == "mem_archive_history":
        return _archive(args, ctx)
    return {"error": "bigmem 沒有這個工具：%s" % name}


def _finish_archive(ctx, item, result):
    if not result.get("ok"):
        return False
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    memory_id = data.get("id")
    archive = item.get("archive") if isinstance(item.get("archive"), dict) else None
    if not archive or not memory_id:
        return False
    history_path = os.path.join(ctx.home, "prompts.json")
    history = ctx.read_json(history_path, [])
    start, end = archive.get("from"), archive.get("to")
    if not isinstance(history, list) or not isinstance(start, int) or not isinstance(end, int):
        return False
    history[start:end + 1] = [{"role": "system", "content": "已歸檔 id=%s" % memory_id}]
    ctx.write_json(history_path, history)
    return True


def on_result(ctx, kind, name, result):
    item = ctx.read_json(os.path.join(ctx.home, "side", "mem-meta", name), {})
    archived = _finish_archive(ctx, item, result) if isinstance(result, dict) else False
    if result.get("error"):
        return None
    return "記憶請求完成%s：%s" % (
        "，原對話已歸檔" if archived else "", ctx.truncate(json.dumps(result, ensure_ascii=False)))
