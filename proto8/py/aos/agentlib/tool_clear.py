"""tool_clear - 把一份 OpenAI 格式 history 裡舊的工具輸出（role: tool 的 content）換成一行英文佔位；純函數，不讀檔、不寫檔、不印東西。

給 agent-fsm 的 /compact 在叫腦寫摘要之前先用（templates/agent-fsm/compact.py 的 clear_old_tools），之後 aos-agent history clear-tools 共用同一套。
規劃與實測：thinking/2026-11/21/compact-改進規劃-1121/02-先清工具輸出.md；施工紀錄 thinking/2026-11/21/compact-第1刀-1121.md。

清法（預設）：
  - 只動 role: tool 列的 content；列本身留著（每個 tool_call 都要有對應的 tool 列），工具呼叫的 arguments 不動。
  - 不清：最後 keep_last 則工具輸出；最後一組工具呼叫（最後一則帶 tool_calls 的 assistant）的結果；短於 min_chars 字的；已經是佔位的；content 不是字串的。
對外：
    clear(history, keep_last=3, min_chars=300) -> (新的 history 列表, [(索引, 原列), ...])   原列表與列都不改
    is_placeholder(content) -> bool
"""

PREFIX = "[aos] tool output cleared"
PLACEHOLDER = PREFIX + " (%d chars from %s); the original is in history_removed.jsonl"
KEEP_LAST = 3
MIN_CHARS = 300


def is_placeholder(content):
    return isinstance(content, str) and content.startswith(PREFIX)


def _tool_names(history):
    names = {}
    for row in history:
        if isinstance(row, dict) and row.get("role") == "assistant":
            for call in row.get("tool_calls") or []:
                if isinstance(call, dict) and isinstance(call.get("id"), str):
                    fn = call.get("function")
                    name = fn.get("name") if isinstance(fn, dict) else None
                    names[call["id"]] = name if isinstance(name, str) and name else "a tool"
    return names


def _last_group(history):
    for i in range(len(history) - 1, -1, -1):
        row = history[i]
        if isinstance(row, dict) and row.get("role") == "assistant" and row.get("tool_calls"):
            return {c.get("id") for c in row["tool_calls"] if isinstance(c, dict)}
    return set()


def clear(history, keep_last=KEEP_LAST, min_chars=MIN_CHARS):
    tools = [i for i, row in enumerate(history) if isinstance(row, dict) and row.get("role") == "tool"]
    protect = set(tools[-keep_last:]) if keep_last > 0 else set()
    group = _last_group(history)
    names = _tool_names(history)
    new, removed = list(history), []
    for i in tools:
        row = history[i]
        content = row.get("content")
        if (i in protect or row.get("tool_call_id") in group or not isinstance(content, str)
                or len(content) < min_chars or is_placeholder(content)):
            continue
        new[i] = dict(row, content=PLACEHOLDER % (len(content), names.get(row.get("tool_call_id"), "a tool")))
        removed.append((i, row))
    return new, removed
