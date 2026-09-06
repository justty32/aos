"""bigmem 工具包 — 非阻塞地跟獨立記憶世界交換 requests/results。"""
import datetime
import json
import os
import uuid


PROMPT = ("長期記憶：mem_put 存、mem_find 找、mem_get 讀全文、mem_forget 忘記。"
          "工具先回 queued；排完就直接回話，不要在同一輪輪詢。回到 idle 後結果才會進 mem 信箱。"
          "看到新信通知再讀結果。長對話可用 mem_archive_history 歸檔。")

TOOLS = [
    {"name": "mem_put", "description": "把一件日後還會用到的事放進長期記憶。",
     "parameters": {"type": "object", "properties": {
         "text": {"type": "string", "description": "要記住的內容"},
         "tags": {"type": "array", "items": {"type": "string"}, "description": "簡短標籤"}},
         "required": ["text"]}},
    {"name": "mem_find", "description": "用文字或標籤找長期記憶。",
     "parameters": {"type": "object", "properties": {
         "query": {"type": "string", "description": "要找的字"},
         "limit": {"type": "integer", "description": "最多幾筆，預設 10，最高 50"}},
         "required": ["query"]}},
    {"name": "mem_get", "description": "用記憶 id 讀完整一筆。",
     "parameters": {"type": "object", "properties": {
         "id": {"type": "string", "description": "記憶 id"}}, "required": ["id"]}},
    {"name": "mem_forget", "description": "刪掉一筆長期記憶。",
     "parameters": {"type": "object", "properties": {
         "id": {"type": "string", "description": "記憶 id"}}, "required": ["id"]}},
    {"name": "mem_archive_history", "description": "歸檔一段對話；成功後原處才會縮成一句。",
     "parameters": {"type": "object", "properties": {
         "from": {"type": "integer", "description": "第一則序號，從 0 開始"},
         "to": {"type": "integer", "description": "最後一則序號，從 0 開始，包含這則"}},
         "required": ["from", "to"]}},
]


def _mem_dir(ctx):
    conf = ctx.read_json(os.path.join(ctx.home, "llm.json"), {})
    conf = conf if isinstance(conf, dict) else {}
    where = conf.get("mem_dir") or os.environ.get("AOS_MEM_DIR") or ""
    if not where:
        return None
    return os.path.abspath(os.path.join(ctx.world, where)) if not os.path.isabs(where) else os.path.abspath(where)


def _queue(ctx, op, args, archive=None):
    mem = _mem_dir(ctx)
    if not mem:
        return {"error": "沒設定記憶世界；請在 llm.json 加 mem_dir，或設定 AOS_MEM_DIR"}
    name = "%s-mem-%s-%s.json" % (
        ctx.name, datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f"), uuid.uuid4().hex[:8])
    request = {"request": name, "op": op, "agent": ctx.name, "args": args}
    ctx.write_json(os.path.join(mem, "requests", name), request)
    pending = ctx.state.get("bigmem_pending")
    if not isinstance(pending, list):
        pending = []
        ctx.state["bigmem_pending"] = pending
    item = {"name": name, "op": op}
    if archive:
        item["archive"] = archive
    pending.append(item)
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


def on_idle(ctx):
    pending = ctx.state.get("bigmem_pending")
    if not isinstance(pending, list) or not pending:
        return
    mem = _mem_dir(ctx)
    if not mem:
        ctx.log("有記憶請求在等，但現在找不到記憶世界")
        return
    left = []
    for item in pending:
        name = item.get("name") if isinstance(item, dict) else ""
        path = os.path.join(mem, "results", name)
        if not name or not os.path.isfile(path):
            left.append(item)
            continue
        result = ctx.read_json(path, {"request": name, "ok": False, "error": "結果 JSON 讀不出來"})
        try:
            os.remove(path)
        except OSError:
            pass
        archived = _finish_archive(ctx, item, result) if isinstance(result, dict) else False
        content = json.dumps(result, ensure_ascii=False)
        ctx.put_mail(ctx.world, "mem", content, request=name,
                     op=item.get("op"), archived=archived)
    ctx.state["bigmem_pending"] = left
