# aos_eca/retry.py - 暫時錯後欠著的信存於 retry.json，提供原子讀寫、清除與續做提示。
import datetime
import json
import os


NAME = "retry.json"


def path(stack):
    return os.path.join(stack, NAME)


def read(stack):
    """缺檔、壞 JSON 或欄位型別不對都當作沒有欠帳。"""
    try:
        with open(path(stack), encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError, RecursionError):
        return None
    if not isinstance(rec, dict):
        return None
    letters = rec.get("letters")
    if not isinstance(letters, list) or not all(isinstance(v, str) for v in letters):
        return None
    for key, minimum in (("attempt", 1), ("tools", 0)):
        value = rec.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            return None
    if not all(isinstance(rec.get(key), str) for key in ("code", "cause", "reason", "at")):
        return None
    try:
        datetime.datetime.strptime(rec["at"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return rec


def clear(stack):
    """成功時清帳；原本沒有檔不算錯，其他 OSError 交給呼叫者。"""
    try:
        os.remove(path(stack))
    except FileNotFoundError:
        pass


def note(stack, letters, code, reason, info):
    """合併信名、累加嘗試與工具次數；先寫暫存檔再改名，OSError 不攔。"""
    old = read(stack) or {}
    info = info if isinstance(info, dict) else {}
    tools = info.get("tools", 0)
    if not isinstance(tools, int) or isinstance(tools, bool) or tools < 0:
        tools = 0
    cause = info.get("cause")
    if not isinstance(cause, str):
        cause = "unknown"
    owed = list(dict.fromkeys(old.get("letters", []) + list(letters)))
    rec = {"letters": owed, "attempt": old.get("attempt", 0) + 1,
           "code": str(code), "cause": cause, "reason": str(reason),
           "tools": old.get("tools", 0) + tools,
           "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    tmp = os.path.join(stack, ".%s.%d.tmp" % (NAME, os.getpid()))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, path(stack))
    return rec


def prompt(rec):
    text = ("[aos] retry: the last turn failed before you answered (%s: %s). "
            % (rec["code"], rec["reason"]))
    if rec["letters"]:
        text += ("Its messages (%d letters) are already in this conversation, or in the record above. "
                 "Go on from where it stopped and answer them now." % len(rec["letters"]))
    else:
        text += ("Its prompt is already in this conversation, or in the record above. "
                 "Go on from where it stopped and answer it now.")
    if rec["tools"] > 0:
        text += (" You had already called tools in that turn (%d calls): "
                 "check what is already done before doing anything again." % rec["tools"])
    return text
