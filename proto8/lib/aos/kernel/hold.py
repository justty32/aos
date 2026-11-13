# 「先留著等表態」：hold.json 記留著的信，decisions/<信名>.json 是別人對某一封的表態（pass／refuse）。
import datetime
import json
import os

import letters
import queue_fifo
import tool_io

REFUSED = ("HoldRefused", "refused by the decision for this letter")


def window(ctx):
    return os.path.join(ctx.stack, "hold.json")


def decision_path(ctx, name):
    return os.path.join(ctx.stack, "decisions", name + ".json")


def view(ctx):
    """上一輪留著的信 {信名: 列}；壞窗 warning 後當空窗（那些信這輪當新信重判）。"""
    try:
        with open(window(ctx), encoding="utf-8") as stream:
            rows = json.load(stream)["held"]
        if not isinstance(rows, list) or any(
                not isinstance(row, dict) or not isinstance(row.get("letter"), str) for row in rows):
            raise ValueError("held must contain objects with letter")
        return {row["letter"]: row for row in rows}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, KeyError, TypeError) as error:
        ctx.warn("cannot read hold.json (%s); starting with nothing held, letters in requests/cur/ are judged again" % error)
        return {}


def decision(ctx, name):
    """沒人表態回 None；表態了回 ("pass", None) 或 ("refuse", (code, msg))。讀不懂的表態檔 warning 後刪掉、當沒表態。"""
    path = decision_path(ctx, name)
    try:
        with open(path, encoding="utf-8") as stream:
            said = json.load(stream)
        if not isinstance(said, dict) or said.get("verdict") not in ("pass", "refuse"):
            raise ValueError("verdict must be pass or refuse")
    except FileNotFoundError:
        return None
    except (OSError, ValueError, UnicodeError) as error:
        ctx.warn("decision for letter %s is broken (%s); removed, the letter stays as it was" % (name, error))
        drop(ctx, name)
        return None
    if said["verdict"] == "pass":
        return "pass", None
    error = said.get("error")
    if isinstance(error, dict) and isinstance(error.get("code"), str) and isinstance(error.get("msg"), str):
        return "refuse", (error["code"], error["msg"])
    return "refuse", REFUSED


def drop(ctx, name):
    try:
        os.unlink(decision_path(ctx, name))
    except FileNotFoundError:
        pass
    except OSError as error:
        ctx.die("StateBad", "cannot remove the decision for letter %s: %s" % (name, error))


def row(ctx, name, letter):
    """新留下的一列：信名、何時留下；寄件人給了合法期限就多記到期時刻。"""
    entry = {"letter": name, "held_at": datetime.datetime.now(datetime.timezone.utc)
             .isoformat(timespec="milliseconds").replace("+00:00", "Z")}
    try:
        cycle = tool_io.now_cycle()
    except tool_io.Error as error:
        ctx.die(error.code, str(error))
    if cycle is not None:
        entry["held_at_cycles"] = cycle
    body = letter.get("body")
    wait = body.get("queue_wait_ms") if isinstance(body, dict) else None
    if isinstance(wait, int) and not isinstance(wait, bool) and wait > 0:
        try:
            entry["expires_at"] = queue_fifo.utc_text(queue_fifo.utc_ms(letter["sent_at"]) + wait)
        except (ValueError, TypeError, KeyError, OverflowError):
            pass
    return entry


def finish(ctx):
    """換窗（有留著的信或窗本來就在才寫）；已離站的信的表態檔收掉。"""
    if ctx.held or os.path.exists(window(ctx)):
        letters.write_json(window(ctx), {"held": ctx.held}, "hold.json", ctx.die)
    folder = os.path.join(ctx.stack, "decisions")
    if not os.path.isdir(folder):
        return
    waiting = {entry["letter"] for entry in ctx.held} | {entry["letter"] for entry in ctx.queued}
    for filename in os.listdir(folder):
        if filename.endswith(".json") and filename[:-5] not in waiting:
            drop(ctx, filename[:-5])
