"""toolsmith 工具包 — 把常用 shell 指令做成自己的工具，或開一個自製工具包骨架。"""
import json
import os
import re
import subprocess


TOOL_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
PACK_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

PROMPT = ("造工具：同一串 shell 指令常手打，就先用 tool_list 看有沒有，再用 tool_add 做成工具。"
          "shell 工具的參數 JSON 會從 stdin 送進指令。tool_add 完要立刻用 tool_try 試一次；"
          "正式工具清單下一格才會重載。要自己寫 Python 工具包時，用 tool_add 的 pack 參數開骨架。")

TOOLS = [
    {"name": "tool_add",
     "description": "新增一個自己的 shell 工具；或只給 pack，在自己 home 建立並啟用一個 Python 工具包骨架。",
     "parameters": {"type": "object", "properties": {
         "name": {"type": "string", "description": "shell 工具名"},
         "description": {"type": "string", "description": "一句話說這個 shell 工具做什麼"},
         "parameters": {"type": "object", "description": "工具參數的 JSON schema；不完整時會補成 object"},
         "command": {"type": "string", "description": "要保存的一句 shell 指令；參數 JSON 從 stdin 進去"},
         "pack": {"type": "string", "description": "要建立並啟用的 Python 工具包名字；使用這個時不用給其他欄位"}}}},
    {"name": "tool_list",
     "description": "列出目前的工具：名字、來自哪一包、用途；自製 shell 工具也會列出 command。",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "tool_remove",
     "description": "移除自製 shell 工具；或給 pack 關掉整包。工具包檔案不會刪掉。",
     "parameters": {"type": "object", "properties": {
         "name": {"type": "string", "description": "要移除的自製 shell 工具名"},
         "pack": {"type": "string", "description": "要關掉的工具包名字"}}}},
    {"name": "tool_try",
     "description": "同一格立刻試跑一個自製 shell 工具，回 exit／stdout／stderr。",
     "parameters": {"type": "object", "properties": {
         "name": {"type": "string", "description": "要試跑的自製 shell 工具名"},
         "args": {"type": "object", "description": "送到工具 stdin 的參數 JSON"}},
         "required": ["name"]}},
]


def _config(ctx):
    path = os.path.join(ctx.home, "tools.json")
    data = ctx.read_json(path, {})
    if not isinstance(data, dict):
        data = {}
    packs = [p for p in (data.get("packs") or []) if isinstance(p, str)]
    tools = [t for t in (data.get("tools") or []) if isinstance(t, dict)]
    data["packs"] = packs
    data["tools"] = tools
    return path, data, packs, tools


def _parameters(value):
    if not isinstance(value, dict):
        return {"type": "object", "properties": {}}
    value = dict(value)
    if value.get("type") == "object" or "properties" in value or "required" in value:
        value["type"] = "object"
        if not isinstance(value.get("properties"), dict):
            value["properties"] = {}
        return value
    return {"type": "object", "properties": value}


def _pack_skeleton(name):
    return '''"""%s 自製工具包。"""

PROMPT = ""
TOOLS = []


def run(name, args, ctx):
    return {"error": "%s 沒有這個工具：%%s" %% name}
''' % (name, name)


def _add_pack(args, ctx):
    name = args.get("pack")
    if not isinstance(name, str) or not PACK_NAME.fullmatch(name):
        return {"ok": False, "error": "pack 名只能用英文字開頭，後面用英數字或底線"}
    path, data, packs, _tools = _config(ctx)
    pack_dir = os.path.join(ctx.home, "packs")
    pack_path = os.path.join(pack_dir, name + ".py")
    if os.path.exists(pack_path):
        return {"ok": False, "error": "工具包已經存在：%s" % name}
    os.makedirs(pack_dir, exist_ok=True)
    with open(pack_path, "x", encoding="utf-8") as f:
        f.write(_pack_skeleton(name))
    if name not in packs:
        packs.append(name)
    ctx.write_json(path, data)
    return {"ok": True, "pack": name, "path": pack_path,
            "message": "骨架建好了；編輯 TOOLS、PROMPT、run，下一格會載入"}


def _add_tool(args, ctx):
    name = args.get("name")
    description = args.get("description")
    command = args.get("command")
    if not isinstance(name, str) or not TOOL_NAME.fullmatch(name):
        return {"ok": False, "error": "工具名只能用英數字、底線或減號"}
    if not isinstance(description, str) or not description.strip():
        return {"ok": False, "error": "description 要用一句話說明工具做什麼"}
    if not isinstance(command, str) or not command.strip():
        return {"ok": False, "error": "command 要是一句 shell 指令"}
    path, data, _packs, tools = _config(ctx)
    if any(t.get("name") == name for t in tools):
        return {"ok": False, "error": "工具已經存在：%s；請先用 tool_remove 移除" % name}
    tools.append({"name": name, "description": description.strip(),
                  "parameters": _parameters(args.get("parameters")),
                  "command": command})
    ctx.write_json(path, data)
    return {"ok": True, "name": name,
            "message": "工具加好了；現在用 tool_try 試跑，正式清單下一格生效"}


def _list(ctx):
    _path, _data, _packs, tools = _config(ctx)
    rows = []
    seen = set()
    for pack_name, module in ctx.loaded:
        for tool in getattr(module, "TOOLS", []):
            name = tool.get("name")
            if name and name not in seen:
                seen.add(name)
                rows.append({"name": name, "from": pack_name,
                             "description": tool.get("description", "")})
    for tool in tools:
        name = tool.get("name")
        if name and name not in seen:
            seen.add(name)
            rows.append({"name": name, "from": "custom",
                         "description": tool.get("description", ""),
                         "command": tool.get("command", "")})
    return rows


def _remove(args, ctx):
    pack = args.get("pack")
    path, data, packs, tools = _config(ctx)
    if isinstance(pack, str) and pack:
        if pack not in packs:
            return {"ok": False, "error": "沒有開這個工具包：%s" % pack}
        data["packs"] = [p for p in packs if p != pack]
        ctx.write_json(path, data)
        return {"ok": True, "pack": pack,
                "message": "工具包關掉了；骨架檔還留著，下一格生效"}

    name = args.get("name")
    if not isinstance(name, str) or not name:
        return {"ok": False, "error": "請給 name，或用 pack 關掉整包"}
    kept = [t for t in tools if t.get("name") != name]
    if len(kept) != len(tools):
        data["tools"] = kept
        ctx.write_json(path, data)
        return {"ok": True, "name": name, "message": "工具移除了；下一格生效"}
    for pack_name, module in ctx.loaded:
        if any(t.get("name") == name for t in getattr(module, "TOOLS", [])):
            return {"ok": False,
                    "error": "那是 %s 包的工具；要關整包請用 tool_remove 的 pack 參數" % pack_name}
    return {"ok": False, "error": "找不到自製工具：%s" % name}


def _try(args, ctx):
    name = args.get("name")
    _path, _data, _packs, tools = _config(ctx)
    tool = next((t for t in tools if t.get("name") == name), None)
    if tool is None:
        return {"error": "找不到自製工具：%s" % (name or "")}
    stdin = json.dumps(args.get("args") if isinstance(args.get("args"), dict) else {},
                       ensure_ascii=False)
    done = subprocess.run(tool.get("command", ""), shell=True, input=stdin,
                          capture_output=True, text=True, cwd=ctx.world)
    return {"exit": done.returncode, "stdout": ctx.truncate(done.stdout),
            "stderr": ctx.truncate(done.stderr)}


def run(name, args, ctx):
    if name == "tool_add":
        return _add_pack(args, ctx) if args.get("pack") else _add_tool(args, ctx)
    if name == "tool_list":
        return _list(ctx)
    if name == "tool_remove":
        return _remove(args, ctx)
    if name == "tool_try":
        return _try(args, ctx)
    return {"error": "toolsmith 沒有這個工具：%s" % name}
