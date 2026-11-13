# 掛 proc 的先來先掛排隊窗與寄件人期限。
import datetime
import json

import letters
import tool_io


def utc_ms(text):
    """信封 UTC 時間轉成整數毫秒，不用浮點數比較期限。"""
    value = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("sent_at must include a timezone")
    delta = value - datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000


def utc_text(milliseconds):
    """Gregorian 每 400 年重複；極大期限用 ISO 擴展年份，不限制合法整數。"""
    cycles, remainder = divmod(milliseconds, 146097 * 86400000)
    value = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(milliseconds=remainder)
    year = value.year + cycles * 400
    prefix = "%04d" % year if year <= 9999 else "+%06d" % year
    return prefix + value.isoformat(timespec="milliseconds")[4:].replace("+00:00", "Z")


def queue_view(path, warn):
    try:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)["queued"]
        if not isinstance(rows, list) or any(
                not isinstance(row, dict) or not isinstance(row.get("letter"), str)
                or not isinstance(row.get("queued_at"), str) for row in rows):
            raise ValueError("queued must contain letter and queued_at objects")
        return {row["letter"]: row for row in rows}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, KeyError, TypeError) as e:
        # 11-07 sol 審查 #5：壞窗不整輪退 1（模式 1 會每拍退、隊列卡死），當空窗、隊序從 cur/ 照處理順序重排。
        warn("cannot read queue.json (%s); starting with an empty queue rebuilt from requests/cur/" % e)
        return {}


def write_queue(path, rows, die):
    """原子換窗；空隊也寫出，移掉已撤信或已放行的舊列。"""
    letters.write_json(path, {"queued": rows}, "queue.json", die)


def expiry_message(letter, was_queued):
    body = letter.get("body")
    wait = body.get("queue_wait_ms") if isinstance(body, dict) else None
    if not wait:
        return None
    elapsed = tool_io.utc_now_epoch_ms() - utc_ms(letter["sent_at"])
    if elapsed < wait:
        return None
    return ("queued %d ms, no slot freed (queue_wait_ms %d)" % (elapsed, wait)
            if was_queued else
            "already expired when the kernel received it (queue_wait_ms %d)" % wait)


def queue_row(name, letter, fresh, previous, die):
    """續用原排隊時間；新進隊才讀 cycle，期限仍由信封起算。"""
    body = letter["body"]
    row = {"letter": name, "names": fresh,
           "queued_at": previous.get(name, {}).get("queued_at") or
           datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")}
    if name in previous and "queued_at_cycles" in previous[name]:
        row["queued_at_cycles"] = previous[name]["queued_at_cycles"]
    elif name not in previous:
        try:
            cycle = tool_io.now_cycle()
        except tool_io.Error as error:
            die(error.code, str(error))
        if cycle is not None:
            row["queued_at_cycles"] = cycle
    if "queue_wait_ms" in body:
        row["expires_at"] = utc_text(utc_ms(letter["sent_at"]) + body["queue_wait_ms"])
    return row
