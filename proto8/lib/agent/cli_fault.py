# cli_fault.py - claude -p 失敗時從 result 行與 stream 判斷暫時或永久，並計算這輪工具呼叫數。
import json


PERMANENT_TYPES = frozenset((
    "invalid_request_error", "authentication_error", "permission_error",
    "not_found_error", "request_too_large", "billing_error",
))
RETRY_TYPES = frozenset((
    "rate_limit_error", "overloaded_error", "api_error", "timeout_error",
))


def _events(lines):
    """忽略壞行與非物件；呼叫者傳入的是 stream 的原始 JSON 行。"""
    if isinstance(lines, str):
        lines = lines.splitlines()
    if not isinstance(lines, (list, tuple)):
        return
    for line in lines:
        if isinstance(line, (str, bytes, bytearray)):
            try:
                line = json.loads(line)
            except (ValueError, RecursionError):
                continue
        if isinstance(line, dict):
            yield line


def tool_calls(lines):
    """只數 assistant.message.content 中的 tool_use；壞欄位視為不存在。"""
    count = 0
    for ev in _events(lines):
        message = ev.get("message")
        if ev.get("type") != "assistant" or not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, list):
            count += sum(isinstance(block, dict) and block.get("type") == "tool_use"
                         for block in content)
    return count


def classify_claude(out, code, timed_out, lines):
    """依分類表由上往下取第一條；認不出的失敗一律永久，不讀檔或丟例外。"""
    status = out.get("api_error_status") if isinstance(out, dict) else None
    if not isinstance(status, int) or isinstance(status, bool):
        status = None
    rec = {"retry": False, "cause": "unknown", "status": status, "tools": tool_calls(lines)}

    def result(cause, retry=False):
        return dict(rec, cause=cause, retry=retry)

    if timed_out is True:
        return result("turn_timeout")
    if not isinstance(out, dict):
        return result("no_result")
    subtype = out.get("subtype")
    if subtype in ("error_max_turns", "error_max_budget_usd"):
        return result(subtype)
    if status is not None and 400 <= status <= 499 and status not in (408, 409, 429):
        return result("api_%d" % status)
    error_type = out.get("api_error_type")
    if not isinstance(error_type, str):
        error_type = None
    if error_type in PERMANENT_TYPES:
        return result(error_type)
    terminal = out.get("terminal_reason")
    if not isinstance(terminal, str):
        terminal = None
    if terminal in (None, "api_error"):
        if status in (408, 409, 429) or (status is not None and 500 <= status <= 599):
            return result("api_%d" % status, True)
        if error_type in RETRY_TYPES:
            return result(error_type, True)
        if out.get("api_error") == "connection_failed":
            return result("connection_failed", True)
    if any(ev.get("type") == "system" and ev.get("subtype") == "api_retry" for ev in _events(lines)):
        return result("api_retry_exhausted", True)
    if isinstance(subtype, str) and subtype.startswith("error_"):
        return result(subtype)
    return rec
