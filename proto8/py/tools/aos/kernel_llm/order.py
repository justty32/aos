# 問腦的排隊：priority 與期限、aging、排序與後端黏著，窗 queue.json 的讀寫。
import calendar
import functools
import json
import math
import os
import re

import runner
import tool_io
from budget import MAX, dumps, is_count
from tool_io import Error

ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(\.\d+)?(?:[Zz]|([+-])(\d{2}):(\d{2}))$")
HIGH = 1


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _level(value):
    if value is None:
        return 0
    if isinstance(value, str) and value in ("low", "normal", "high"):
        return ("low", "normal", "high").index(value) - 1
    if _number(value):                                   # 數字只看正負
        return -1 if value < 0 else 1 if value > 0 else 0
    raise Error("PriorityBad", 'level must be "low", "normal", "high" or a number, got ' + dumps(value))


def _deadline(value):
    if _number(value) and math.isfinite(value):
        return float(value)
    match = ISO.match(value) if isinstance(value, str) else None
    if match:
        year, month, day, hour, minute, second = (int(part) for part in match.groups()[:6])
        if 1 <= month <= 12 and 1 <= day <= 31 and hour <= 23 and minute <= 59 and second <= 60:
            offset = 0
            if match.group(8):
                offset = (int(match.group(9)) * 60 + int(match.group(10))) * 60 * (-1 if match.group(8) == "-" else 1)
            fraction = float("0" + match.group(7)) if match.group(7) else 0.0
            return calendar.timegm((year, month, day, hour, minute, second)) - offset + fraction
    raise Error("PriorityBad", "deadline must be ISO 8601 with a time zone (e.g. 2026-10-24T18:00:00+08:00) "
                               "or epoch seconds, got " + dumps(value))


def parse_priority(value):
    """信裡的 priority → (級數 -1／0／1, 期限的牆鐘 epoch 秒或 None)；壞了丟 PriorityBad。"""
    if isinstance(value, dict):
        deadline = value.get("deadline")
        return _level(value.get("level")), None if deadline is None else _deadline(deadline)
    if value is None or isinstance(value, str) or _number(value):
        return _level(value), None
    raise Error("PriorityBad", 'priority must be "low", "normal", "high", a number or {"level", "deadline"}, got '
                + dumps(value))


def read_queue(stack):
    """讀 queue.json：每封信第一次看到的時間與各後端最後掛的包；沒有＝空帳，讀不懂＝QueueBad。"""
    path = os.path.join(stack, "queue.json")
    queue = {"original": None, "seen_at_ms": {}, "seen_at_cycles": {}, "on_clock": False, "backends": {}}
    try:
        with open(path, "rb") as stream:
            text = stream.read()
    except FileNotFoundError:
        return queue
    except OSError as error:
        raise Error("QueueBad", "cannot read %s: %s" % (path, error.strerror)) from None
    try:
        doc = json.loads(text)
    except (ValueError, UnicodeError):
        doc = None
    if not isinstance(doc, dict) or any(key in doc and not isinstance(doc[key], dict)
                                        for key in ("seen_at_ms", "seen_at_cycles")):
        raise Error("QueueBad", path + " must be an object with optional seen_at_ms/seen_at_cycles objects "
                                       "(delete it to start over)")
    queue.update(original=doc, seen_at_ms=doc.get("seen_at_ms", {}), seen_at_cycles=doc.get("seen_at_cycles", {}))
    if "backends" in doc:
        backends = doc["backends"]
        if not isinstance(backends, dict):
            raise Error("QueueBad", path + " backends must be an object")
        for name in backends:
            state = backends[name]
            if not (isinstance(state, dict) and isinstance(state.get("pack"), str)
                    and _number(state.get("switched_at")) and is_count(state.get("counter_switches"))
                    and state["counter_switches"] <= MAX):
                raise Error("QueueBad", "%s backends.%s must contain pack (string), switched_at (epoch seconds), "
                                        "counter_switches (non-negative integer)" % (path, name))
        queue["backends"] = backends
    return queue


def write_queue(stack, queue):
    """跟讀進來的不同才寫；沒時鐘不寫 seen_at_cycles，沒後端記錄不寫 backends。"""
    doc = {"seen_at_ms": dict(sorted(queue["seen_at_ms"].items()))}
    if queue["on_clock"]:
        doc["seen_at_cycles"] = dict(sorted(queue["seen_at_cycles"].items()))
    if queue["backends"]:
        doc["backends"] = queue["backends"]
    if doc == queue["original"]:
        return
    try:
        runner.write_json(os.path.join(stack, "queue.json"), doc)
    except runner.Failed as error:
        raise Error(error.code, error.msg) from None


def _stamp(value):
    return is_count(value) and value <= MAX


def waited(old, name, now_ms, now_cycle):
    """照上一輪的帳算這封信等了幾格，回 (seen_at_ms, seen_at_cycles 或 None, 等了幾格)。
    有時鐘數格；沒有時鐘、或第一次記錄時沒時鐘值，用牆鐘差除以一格的長度。"""
    seen_ms = old["seen_at_ms"].get(name)
    known = _stamp(seen_ms)
    if not known:
        seen_ms = now_ms
    seen_cycle = old["seen_at_cycles"].get(name)
    if now_cycle is not None and (not known or _stamp(seen_cycle)):
        if not known:
            seen_cycle = now_cycle
        return seen_ms, seen_cycle, max(0, now_cycle - seen_cycle)
    return seen_ms, None, max(0, now_ms - seen_ms) // tool_io.clock_interval_ms()


def effective(waiting, aging_cycles):
    """這封信現在算幾級：宣告級數＋等了幾格÷aging_cycles，不封頂。"""
    return waiting["level"] + waiting["waited"] // aging_cycles


def sort(waitings, aging_cycles, backends):
    """級數大的先 → 期限近的先（有寫的在前）→ 同後端黏著最後掛的包 → 包的速度 → 等得久 → 先寄。"""
    def compare(a, b):
        ea, eb = effective(a, aging_cycles), effective(b, aging_cycles)
        if ea != eb:
            return -1 if ea > eb else 1
        da, db = a["deadline"], b["deadline"]
        if (da is None) != (db is None):
            return -1 if da is not None else 1
        if da is not None and da != db:
            return -1 if da < db else 1
        if a["pack"]["speed"] != b["pack"]["speed"]:
            return -1 if a["pack"]["speed"] < b["pack"]["speed"] else 1
        if a["waited"] != b["waited"]:
            return -1 if a["waited"] > b["waited"] else 1
        return (a["id"] > b["id"]) - (a["id"] < b["id"])

    ordered = sorted(waitings, key=functools.cmp_to_key(compare))
    # 黏著只在同一個後端的信之間換位置，別的後端留在原位（兩兩比較會在後端之間繞成圈）。
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and effective(ordered[start], aging_cycles) == effective(ordered[end], aging_cycles) \
                and ordered[start]["deadline"] == ordered[end]["deadline"]:
            end += 1
        positions = {}
        for index in range(start, end):
            backend = ordered[index]["pack"]["backend"]
            if backend is not None and backend in backends:
                positions.setdefault(backend, []).append(index)
        for backend, indexes in positions.items():
            last = backends[backend]["pack"]
            peers = [ordered[index] for index in indexes]
            peers = [w for w in peers if w["endpoint"] == last] + [w for w in peers if w["endpoint"] != last]
            for index, peer in zip(indexes, peers):
                ordered[index] = peer
        start = end
    return ordered
