"""ref 工具包 — 把太大的 JSON 工具結果收進本地 refs/。"""
import datetime
import json
import os
import uuid


LIMIT = 6000
HARD_LIMIT = 20000

PROMPT = "看到 `$ref` 就是這裡有東西被收起來了，需要才用 ref_expand 展開。"

TOOLS = [
    {"name": "ref_expand", "description": "展開一個 ref:// 指標，可只讀其中一段。",
     "parameters": {"type": "object", "properties": {
         "ref": {"type": "string", "description": "ref:// 開頭的指標"},
         "path": {"type": "string", "description": "可選 JSON 路徑，例如 #/choices/0"},
         "max_chars": {"type": "integer", "description": "預設 6000，上限 20000"}},
         "required": ["ref"]}},
    {"name": "ref_collapse", "description": "把對話中一則 JSON 內容收起來。",
     "parameters": {"type": "object", "properties": {
         "message_index": {"type": "integer", "description": "訊息序號，從 0 起"}},
         "required": ["message_index"]}},
    {"name": "ref_list", "description": "列最近 20 個本地指標。",
     "parameters": {"type": "object", "properties": {}}},
]


def _text(value):
    return json.dumps(value, ensure_ascii=False)


def _save(ctx, value, source, chars=None):
    ref_id = uuid.uuid4().hex
    path = os.path.join(ctx.home, "refs", ref_id + ".json")
    ctx.write_json(path, value)
    size = chars if chars is not None else len(_text(value))
    meta = ctx.state.get("ref_meta")
    if not isinstance(meta, dict):
        meta = {}
        ctx.state["ref_meta"] = meta
    meta[ref_id] = {
        "chars": size,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "source": source,
    }
    return ref_id, {"$ref": "ref://" + ref_id,
                    "preview": _text(value)[:200], "chars": size}


def _result_json(result):
    """回（要保存的值、實際會進 tool content 的字串）；不是 JSON 就回 None。"""
    if isinstance(result, str):
        try:
            return json.loads(result), result
        except ValueError:
            return None
    try:
        return result, _text(result)
    except (TypeError, ValueError):
        return None


def on_act(ctx, tool, args, result, took_ms):
    ready = _result_json(result)
    if ready is None:
        return
    value, original = ready
    if len(original) <= LIMIT:
        return
    _ref_id, pointer = _save(ctx, value, "工具 " + str(tool), len(original))
    return pointer


def _parse_ref(value):
    if not isinstance(value, str) or not value.startswith("ref://"):
        raise ValueError("指標要用 ref:// 開頭")
    rest = value[6:]
    ref_id, mark, fragment = rest.partition("#")
    if (not ref_id or os.path.basename(ref_id) != ref_id
            or not all(c.isalnum() for c in ref_id)):
        raise ValueError("ref 指標不對")
    return ref_id, ("#" + fragment if mark else "")


def _select(value, path):
    if not path or path == "#":
        return value
    pointer = path[1:] if path.startswith("#") else path
    if not pointer.startswith("/"):
        raise ValueError("JSON 路徑要像 #/choices/0")
    here = value
    for raw in pointer[1:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(here, list):
            try:
                here = here[int(key)]
            except (ValueError, IndexError):
                raise ValueError("JSON 路徑不存在：%s" % path)
        elif isinstance(here, dict) and key in here:
            here = here[key]
        else:
            raise ValueError("JSON 路徑不存在：%s" % path)
    return here


def _expand(args, ctx):
    try:
        ref_id, embedded = _parse_ref(args.get("ref"))
    except ValueError as e:
        return {"error": str(e)}
    filename = os.path.join(ctx.home, "refs", ref_id + ".json")
    if not os.path.isfile(filename):
        return {"error": "找不到這個指標：ref://%s" % ref_id}
    value = ctx.read_json(filename, None)
    if value is None:
        return {"error": "這個指標的 JSON 讀不出來：ref://%s" % ref_id}
    try:
        value = _select(value, args.get("path") or embedded)
    except ValueError as e:
        return {"error": str(e)}
    try:
        maximum = int(args.get("max_chars") or LIMIT)
    except (TypeError, ValueError):
        maximum = LIMIT
    maximum = max(1, min(maximum, HARD_LIMIT))
    full = _text(value)
    if len(full) > maximum:
        return {"text": full[:maximum], "chars": len(full),
                "returned_chars": maximum, "truncated": True,
                "note": "這是截短的文字片段，不是完整 JSON"}
    return {"value": value, "chars": len(full),
            "returned_chars": len(full), "truncated": False}


def _collapse(args, ctx):
    try:
        index = int(args.get("message_index"))
    except (TypeError, ValueError):
        return {"error": "message_index 要是整數"}
    path = os.path.join(ctx.home, "prompts.json")
    history = ctx.read_json(path, [])
    if not isinstance(history, list) or index < 0 or index >= len(history):
        return {"error": "找不到第 %s 則對話" % index}
    msg = history[index]
    content = msg.get("content") if isinstance(msg, dict) else None
    try:
        value = json.loads(content) if isinstance(content, str) else content
    except ValueError:
        return {"error": "第 %s 則內容不是 JSON" % index}
    if not isinstance(value, (dict, list)):
        return {"error": "第 %s 則內容不是 JSON 物件或陣列" % index}
    chars = len(_text(value))
    ref_id, pointer = _save(ctx, value, "對話 %s" % index, chars)
    msg["content"] = _text(pointer)
    ctx.write_json(path, history)
    return {"ref": "ref://" + ref_id, "chars": chars,
            "path": "refs/%s.json" % ref_id}


def _list(ctx):
    box = os.path.join(ctx.home, "refs")
    names = []
    if os.path.isdir(box):
        names = [n for n in os.listdir(box)
                 if n.endswith(".json") and os.path.isfile(os.path.join(box, n))]
    names.sort(key=lambda n: os.path.getmtime(os.path.join(box, n)), reverse=True)
    meta = ctx.state.get("ref_meta")
    meta = meta if isinstance(meta, dict) else {}
    rows = []
    for name in names[:20]:
        ref_id = name[:-5]
        filename = os.path.join(box, name)
        item = meta.get(ref_id) if isinstance(meta.get(ref_id), dict) else {}
        value = ctx.read_json(filename, None)
        rows.append({"ref": "ref://" + ref_id,
                     "chars": item.get("chars", len(_text(value))),
                     "bytes": os.path.getsize(filename),
                     "time": item.get("time") or datetime.datetime.fromtimestamp(
                         os.path.getmtime(filename)).isoformat(timespec="seconds"),
                     "source": item.get("source") or "未知"})
    return {"total": len(names), "refs": rows}


def run(name, args, ctx):
    if name == "ref_expand":
        return _expand(args, ctx)
    if name == "ref_collapse":
        return _collapse(args, ctx)
    if name == "ref_list":
        return _list(ctx)
    return {"error": "ref 沒有這個工具：%s" % name}
