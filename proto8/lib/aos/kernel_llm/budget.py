# 問腦的額度與用量帳：總額、每包、每寄件人的上限與窗，used.json 的讀寫。
import json
import os
import time

import runner
import tool_io
from tool_io import Error

MAX = 2 ** 63 - 1
USED_SHAPE = ('{"window", "since", "counter_calls", "counter_tokens", "counter_all_calls", "counter_all_tokens", '
              '"packs"?: {name: {"counter_calls", "counter_tokens"}}, '
              '"senders"?: {sender: {"counter_calls", "counter_tokens"}}}')


def is_count(value):
    """非負整數（布林、小數不算）。"""
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value


def dumps(value):
    """錯誤訊息裡印一個 JSON 值：鍵照原順序，逗號冒號後空一格。"""
    return json.dumps(value, ensure_ascii=False)


def sender_key(sender, stack):
    """寄件人路徑改成相對 kernel stack 的帳目 key，整棵搬家後照用。"""
    if not sender:
        return ""
    return os.path.relpath(os.path.abspath(sender), os.path.abspath(stack))


def _limit(value, at):
    if not isinstance(value, dict):
        raise Error("CfgBad", '%s must be {"max_calls", "max_tokens"}, got %s' % (at, dumps(value)))
    limit = {"max_calls": None, "max_tokens": None}
    for key in value:
        if key not in limit:
            raise Error("CfgBad", "%s.%s is not allowed (only max_calls, max_tokens; the window and spent are "
                                  "the kernel's budget.window, budget.spent)" % (at, key))
        if value[key] is None:
            continue
        if not is_count(value[key]):
            raise Error("CfgBad", "%s.%s must be a non-negative integer (limit per window), got %s"
                        % (at, key, dumps(value[key])))
        limit[key] = value[key]
    return limit


def parse(value, base, stack):
    """讀 kernel.json 的 budget；senders 的相對 key 從設定檔所在夾算，記帳用相對 stack 的 key。"""
    budget = {"max_calls": None, "max_tokens": None, "window": "day", "wait": False, "senders": {}, "warnings": []}
    if value is None:
        return budget
    if not isinstance(value, dict):
        raise Error("CfgBad", 'budget must be {"max_calls", "max_tokens", "window", "spent"}, got ' + dumps(value))
    for key in ("max_calls", "max_tokens"):
        limit = value.get(key)
        if limit is None:
            continue
        if not is_count(limit):
            raise Error("CfgBad", "budget.%s must be a non-negative integer (limit per window), got %s"
                        % (key, dumps(limit)))
        budget[key] = limit
    window = value.get("window")
    if window is not None:
        if window not in ("hour", "day", "all") or not isinstance(window, str):
            raise Error("CfgBad", 'budget.window must be "hour", "day" or "all", got ' + dumps(window))
        budget["window"] = window
    spent = value.get("spent")
    if spent is not None:
        if spent not in ("refuse", "wait") or not isinstance(spent, str):
            raise Error("CfgBad", 'budget.spent must be "refuse" or "wait", got ' + dumps(spent))
        budget["wait"] = spent == "wait"
    senders = value.get("senders")
    if senders is not None:
        if not isinstance(senders, dict):
            raise Error("CfgBad", 'budget.senders must be {sender: {"max_calls", "max_tokens"}} '
                                  "(sender = the letter's envelope sender, a path), got " + dumps(senders))
        for key in senders:
            if not key:
                raise Error("CfgBad", "budget.senders: a sender must be a non-empty path")
            sender = os.path.abspath(os.path.join(base, key))
            who = sender_key(sender, stack)
            if who in budget["senders"]:
                raise Error("CfgBad", "budget.senders: %s names the same sender (%s) as another key" % (key, sender))
            budget["senders"][who] = dict(_limit(senders[key], "budget.senders." + key), key=key)
            budget["warnings"] += sender_key_warnings(key, sender, base, stack)
    return budget


def sender_key_warnings(key, sender, base, stack):
    """budget.senders 的一個 key 對不上任何 proc 的提醒（B09；11-13 線修 T39）。寄件人＝proc 的 stack（$AOS_STACK）：
    解出來不是資料夾、或是資料夾卻沒有 state.json（不是起過的 proc 的 stack，多半寫成了工作區）＝這格多半不會生效。
    used.json 的 key 是相對 kernel stack 的；照抄進 kernel.json（相對設定檔所在夾）就會錯位，對得上時順便點出來。"""
    if os.path.isdir(sender):
        if os.path.exists(os.path.join(sender, "state.json")):
            return []
        return ["budget.senders key %s is a folder but not a proc stack (no state.json): %s; the sender of a brain "
                "request is the asking proc's stack ($AOS_STACK), not its workspace, so this limit only applies if "
                "a proc runs with exactly that stack" % (dumps(key), sender)]
    line = ("budget.senders key %s is not a folder: %s (relative keys count from %s, the kernel config's folder; "
            "an absolute path avoids the mix-up); this limit only applies to letters whose sender is exactly that path"
            % (dumps(key), sender, base))
    from_stack = os.path.abspath(os.path.join(stack, key))
    if from_stack != sender and os.path.isdir(from_stack):
        line += ("; counted from the kernel stack (as used.json keys are) it would be %s, write that path instead"
                 % from_stack)
    return [line]


def warn(budget, stack):
    """每輪是新行程，提醒只在內容變了才印；印過的全文記在 budget_warned.txt。"""
    text = "".join(line + "\n" for line in budget["warnings"])
    path = os.path.join(stack, "budget_warned.txt")
    try:
        with open(path, encoding="utf-8") as stream:
            was = stream.read()
    except (OSError, UnicodeError):
        was = None
    if not text:
        if was is not None:
            try:
                os.unlink(path)
            except OSError:
                pass
        return
    if was == text:
        return
    for line in budget["warnings"]:
        tool_io.warn(line)
    try:
        tmp = os.path.join(stack, ".budget_warned.txt.tmp")
        with open(tmp, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(tmp, path)
    except OSError:
        pass                                             # 寫不成＝下一輪再印一次


def window_since(window, now):
    """這一刻所在那一窗的起點：本地時間、帶時區；all 沒有起點。"""
    if window == "all":
        return None
    local = time.localtime(now)
    start = time.mktime((local.tm_year, local.tm_mon, local.tm_mday, local.tm_hour if window == "hour" else 0,
                         0, 0, 0, 0, -1))
    begin = time.localtime(start)
    offset = abs(begin.tm_gmtoff)
    return "%s%s%02d:%02d" % (time.strftime("%Y-%m-%dT%H:%M:%S", begin), "-" if begin.tm_gmtoff < 0 else "+",
                              offset // 3600, offset % 3600 // 60)


def _roll(used, window):
    since = window_since(window, time.time())
    if used["window"] != window or used["since"] != since:
        used.update(window=window, since=since, calls=0, tokens=0, packs={}, senders={})


def _cells_ok(cells):
    return isinstance(cells, dict) and all(
        isinstance(cell, dict) and is_count(cell.get("counter_calls")) and is_count(cell.get("counter_tokens"))
        for cell in cells.values())


def read_used(stack, window):
    """讀 used.json；沒有＝全 0，換窗了這一窗歸零、開機以來的總數照留。"""
    path = os.path.join(stack, "used.json")
    used = {"window": "", "since": None, "calls": 0, "tokens": 0, "all_calls": 0, "all_tokens": 0,
            "packs": {}, "senders": {}}
    try:
        with open(path, "rb") as stream:
            text = stream.read()
    except FileNotFoundError:
        text = None
    except OSError as error:
        raise Error("UsedBad", "cannot read %s: %s" % (path, error.strerror)) from None
    if text is not None:
        try:
            doc = json.loads(text)
        except (ValueError, UnicodeError):
            doc = None
        ok = isinstance(doc, dict) and isinstance(doc.get("window"), str) and (
            doc.get("since") is None or isinstance(doc.get("since"), str))
        ok = ok and all(is_count(doc.get(key)) for key in
                        ("counter_calls", "counter_tokens", "counter_all_calls", "counter_all_tokens"))
        ok = ok and all(key not in doc or _cells_ok(doc[key]) for key in ("packs", "senders"))
        if not ok:
            raise Error("UsedBad", "%s must be %s (delete it to count from 0)" % (path, USED_SHAPE))
        used.update(window=doc["window"], since=doc.get("since"), calls=doc["counter_calls"],
                    tokens=doc["counter_tokens"], all_calls=doc["counter_all_calls"],
                    all_tokens=doc["counter_all_tokens"], packs=doc.get("packs", {}), senders=doc.get("senders", {}))
    _roll(used, window)
    return used


def _count_in(cells, name, tokens):
    cell = cells.get(name)
    if not isinstance(cell, dict):
        cell = cells[name] = {}
    cell["counter_calls"] = cell.get("counter_calls", 0) + 1
    cell["counter_tokens"] = cell.get("counter_tokens", 0) + tokens


def add_used(stack, used, tokens, endpoint="", sender=""):
    """跑過的一封記上去並寫回 used.json；tokens 是整數或 None（沒回報只算次數）。"""
    _roll(used, used["window"])
    amount = tokens if is_count(tokens) else 0
    used["calls"] += 1
    used["tokens"] += amount
    used["all_calls"] += 1
    used["all_tokens"] += amount
    if endpoint:
        _count_in(used["packs"], endpoint, amount)
    if sender:
        _count_in(used["senders"], sender_key(sender, stack), amount)
    try:
        runner.write_json(os.path.join(stack, "used.json"), {
            "window": used["window"], "since": used["since"], "counter_calls": used["calls"],
            "counter_tokens": used["tokens"], "counter_all_calls": used["all_calls"],
            "counter_all_tokens": used["all_tokens"], "packs": used["packs"], "senders": used["senders"]})
    except runner.Failed as error:
        raise Error(error.code, error.msg) from None


def spent(budget, used, started):
    """照這一窗的帳，再開第 started＋1 封會不會超過總額。"""
    if budget["max_calls"] is not None and used["calls"] + started >= budget["max_calls"]:
        return True
    return budget["max_tokens"] is not None and used["tokens"] >= budget["max_tokens"]


def spent_of(cells, name, max_calls, max_tokens, started):
    """同 spent，看 packs 或 senders 裡的一格。"""
    cell = cells.get(name)
    calls = cell.get("counter_calls", 0) if isinstance(cell, dict) else 0
    tokens = cell.get("counter_tokens", 0) if isinstance(cell, dict) else 0
    if max_calls is not None and calls + started >= max_calls:
        return True
    return max_tokens is not None and tokens >= max_tokens


def tokens_of(reply):
    """回信的 usage 換成 token 數；沒回報或形狀不對回 None。"""
    if not isinstance(reply, dict) or not isinstance(reply.get("usage"), dict):
        return None
    usage = reply["usage"]
    total = usage.get("total_tokens")
    if is_count(total):
        return total
    prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if total is None and is_count(prompt) and is_count(completion):
        return prompt + completion
    return None
