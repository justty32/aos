#!/usr/bin/env python3
"""工具宣告、文字 tool call 救回與工具執行。"""

import json
from pathlib import Path

from common import read_json


class ToolConfigError(Exception):
    pass


def load_tools(agent_dir):
    tools = {}
    root = Path(agent_dir) / "tools"
    if not root.exists():
        return tools
    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        spec_path = folder / "tool.json"
        try:
            spec = read_json(spec_path)
            description = spec["description"]
            parameters = spec["parameters"]
            if not isinstance(description, str) or not isinstance(parameters, dict):
                raise ValueError
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            raise ToolConfigError(f"工具設定壞了：{spec_path}") from exc
        # LM Studio 之類的服務要求 parameters 一定是 object 且有 properties，少了就補空的。
        parameters = {"type": "object", **parameters}
        parameters.setdefault("properties", {})
        tools[folder.name] = {
            "type": "function",
            "function": {
                "name": folder.name,
                "description": description,
                "parameters": parameters,
            },
        }
    return tools


def first_json_object(text):
    start = None
    depth = 0
    quoted = False
    escaped = False
    for index, char in enumerate(text):
        if start is None:
            if char == "{":
                start = index
                depth = 1
            continue
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:index + 1])
                except json.JSONDecodeError:
                    return None
    return None


def recover_text_call(text, known_names, step):
    stripped = text.strip()
    smells = ("<tool_call>", "[TOOL_CALLS]", "<function=")
    candidate = None
    if stripped.startswith(smells):
        candidate = first_json_object(stripped)
    elif stripped.startswith("{") and stripped.endswith("}"):
        try:
            candidate = json.loads(stripped)
        except json.JSONDecodeError:
            candidate = None
    if not isinstance(candidate, dict) or candidate.get("name") not in known_names:
        return None
    arguments = candidate.get("arguments", {})
    return [{
        "id": f"call_{step}_1",
        "type": "function",
        "function": {
            "name": candidate["name"],
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }]


def looks_like_text_call(text):
    stripped = text.strip()
    return (stripped.startswith(("<tool_call>", "[TOOL_CALLS]", "<function="))
            or (stripped.startswith("{") and stripped.endswith("}")))


def run_tool(agent_dir, call, limit, aos_py):
    function = call.get("function") if isinstance(call, dict) else None
    name = function.get("name") if isinstance(function, dict) else None
    raw_args = function.get("arguments", "{}") if isinstance(function, dict) else "{}"
    run = Path(agent_dir) / "tools" / str(name) / "run"
    if not run.is_file():
        return "沒有這個工具"
    if isinstance(raw_args, dict):
        args_text = json.dumps(raw_args, ensure_ascii=False)
    else:
        args_text = str(raw_args)
    try:
        parsed = json.loads(args_text)
        args_text = json.dumps(parsed, ensure_ascii=False)
    except json.JSONDecodeError as exc:
        return f"參數不是 JSON：{exc.msg}"
    try:
        result = aos_py.call(run, stdin=args_text, capture=True, timeout_ms=60000)
        content = result.get("out") or ""
        if result.get("code") != 0:
            error = (result.get("err") or "")[:500]
            content = f"[exit {result.get('code')}] {error}\n{content}"
    except Exception as exc:
        content = f"工具執行失敗：{exc}"
    if len(content) > limit:
        content = content[:limit] + "…（截斷）"
    return content
