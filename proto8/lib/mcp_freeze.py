# mcp_freeze.py - 把一支外部 MCP 工具凍結成包檔 mcp_tools 的一格（登記名、$ref 展開、說明前綴與截斷、_metainfo）與兩份 mcp_tools 的差異；純函式（external-mcp 07 步 4）
"""純函式：不起行程、不讀檔。錯一律丟 tool_io.Error（NameBad）；提醒交給呼叫者給的 warn(句子)。

圖紙：thinking/2026-11/12/external-mcp/07-fsm施工單.md 的「介面定死」與「步 4」。
結果的 parameters 不留任何 `$` 開頭的鍵（`$` 是 aos 指示詞）；_entry 裡的 {"$env", "$path"} 是 aos 自己的指示詞，刻意的。"""
import copy
import json
import re

from mcp_server_file import NAME_RE
from tool_io import Error

NAME_MAX = 64
DESC_MAX = 1024
PARAM_DESC_MAX = 300
REF_DEPTH = 10
TIMEOUT_MS = 60000
EMPTY_OBJECT = {"type": "object", "properties": {}}


def registry_name(server, tool):
    """<server>_<tool>：轉小寫、非 [a-z0-9_] 換 _、連續 _ 併一個；server 名不合、工具名空、超過 64 字＝NameBad。"""
    if not isinstance(server, str) or not NAME_RE.match(server) or server == "aos":
        raise Error("NameBad", "server name %r must match [a-z][a-z0-9_]* (at most 32 chars) and not be aos" % (server,))
    if not isinstance(tool, str) or not tool:
        raise Error("NameBad", "tool name %r must be a non-empty string" % (tool,))
    name = re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]", "_", ("%s_%s" % (server, tool)).lower()))
    if len(name) > NAME_MAX:
        raise Error("NameBad", "registry name %s is longer than %d chars" % (name, NAME_MAX))
    return name


def _pointer(root, ref):
    """本地 JSON 指標 #/a/b（~0、~1 跳脫）；找不到＝None。"""
    node = root
    for part in ref[2:].split("/") if ref != "#" else []:
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return None
    return node


def _clean(node, root, stack, warn):
    if isinstance(node, list):
        return [_clean(v, root, stack, warn) for v in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if ref is not None:
        if not isinstance(ref, str) or not ref.startswith("#"):
            warn("$ref %r is not a local reference; replaced with {}" % (ref,))
            return {}
        if ref in stack:
            warn("$ref %s is a cycle; replaced with {}" % ref)
            return {}
        if len(stack) >= REF_DEPTH:
            warn("$ref %s is nested deeper than %d; replaced with {}" % (ref, REF_DEPTH))
            return {}
        target = _pointer(root, ref)
        if not isinstance(target, dict):
            warn("$ref %s does not resolve to an object; replaced with {}" % ref)
            return {}
        merged = dict(target)
        merged.update((k, v) for k, v in node.items() if k != "$ref")
        return _clean(merged, root, stack + [ref], warn)
    out = {}
    for k, v in node.items():
        if k.startswith("$"):
            continue
        if k == "description" and isinstance(v, str):
            out[k] = v[:PARAM_DESC_MAX]
        else:
            out[k] = _clean(v, root, stack, warn)
    return out


def clean_schema(schema, warn):
    """本地 $ref 就地展開（深度 10、遇環停）、拿掉所有 $ 鍵、description 截 300 字；頂層不是 object＝換空物件並 warn。"""
    if not isinstance(schema, dict):
        warn("inputSchema is not an object; replaced with an empty object schema")
        return copy.deepcopy(EMPTY_OBJECT)
    out = _clean(schema, schema, [], warn)
    out.setdefault("type", "object")
    if out["type"] != "object":
        warn("inputSchema type is %s, not object; replaced with an empty object schema" % json.dumps(out["type"]))
        return copy.deepcopy(EMPTY_OBJECT)
    return out


def freeze_tool(server_name, pack_basename, tool, transport, warn=lambda s: None):
    """tools/list 的一支 → (登記名, mcp_tools 那一格)。warn 收到的句子前面加上工具原名。"""
    name = tool.get("name") if isinstance(tool, dict) else None
    reg = registry_name(server_name, name)
    desc = tool.get("description")
    desc = desc if isinstance(desc, str) else ""
    hints = tool.get("annotations")
    hints = hints if isinstance(hints, dict) else {}
    meta = {"summary": "%s on the MCP server %s" % (name, server_name)}
    meta["side_effect"] = hints.get("readOnlyHint") is not True
    if isinstance(hints.get("idempotentHint"), bool):
        meta["idempotent"] = hints["idempotentHint"]
    meta["resource"] = ["net"] if hints.get("openWorldHint") is True or transport == "http" else []
    meta["timeout_ms"] = TIMEOUT_MS
    params = clean_schema(tool.get("inputSchema"), lambda s: warn("%s: %s" % (name, s)))
    return reg, {
        "_entry": ["python3", {"$env": "AOS_HOME", "$path": "/lib/base/mcp_tool/_entry"},
                   "--pack", pack_basename, "--tool", name],
        "_tooldef": {"description": ("[MCP server %s] %s" % (server_name, desc))[:DESC_MAX], "parameters": params},
        "_metainfo": meta}


def _show(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)


def diff_tools(old_mcp_tools, new_mcp_tools):
    """兩份 mcp_tools 的差異行：+ 名、- 名、~ 名: description／parameters changed（後面各一行 before、after）；沒差＝[]。"""
    lines = []
    for name in sorted(set(old_mcp_tools) | set(new_mcp_tools)):
        if name not in old_mcp_tools:
            lines.append("+ %s" % name)
        elif name not in new_mcp_tools:
            lines.append("- %s" % name)
        else:
            old = old_mcp_tools[name].get("_tooldef", {})
            new = new_mcp_tools[name].get("_tooldef", {})
            for key in ("description", "parameters"):
                if old.get(key) != new.get(key):
                    lines += ["~ %s: %s changed" % (name, key),
                              "    before: %s" % _show(old.get(key)),
                              "    after:  %s" % _show(new.get(key))]
    return lines
