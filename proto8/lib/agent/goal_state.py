"""goal_state - agent 的 goal 共用讀寫與判斷：<agent stack>/goal.json；aos-agent goal 寫、agent-fsm idle.py 與 aos-eca-turn 讀寫（丟提醒、記數）。

11-11 goal（thinking 2026-11/11/goal/02）：使用者「當agent自己停下來時(在沒有新user prompt的情況下，自己不再呼叫工具)，自動丟goal給他」；
裁定：一支工具 goal 分動作、連續沒進展才算（有叫工具就歸零）、暫停中有新信不自動 resume、fsm 和 eca 都做。格式（三方共用，改 key 要一起改）：

    {"text": "Write the report.", "status": "active", "reason": "", "reminded": 2, "limit": 10,
     "set_by": "agent", "updated_by": "outside", "updated_at": "2026-11-11T08:00:00Z"}

status＝active｜paused｜done｜abandoned；reminded＝連續沒進展被丟了幾次（有進展歸零、set／resume 歸零）；limit＝上限（預設 10）；
set_by／updated_by＝agent（這隻自己，經工具）｜outside（人、父 agent）｜aos（到上限自動暫停）。時間 UTC、ISO 8601 到秒、結尾 Z。
寫法：先寫 . 開頭的暫存檔再改名（N-05）。檔不在＝沒有 goal；壞了（不是 JSON 物件、欄位型別不對）＝read 丟 GoalBad。
提醒文字照 `[aos] goal: …`（py/aos_flags.py 的 NOTE_KINDS 登記 goal；lib 不 import py，這裡自己拼同一個格式，同 mail_notify）。純標準庫。"""
import datetime
import json
import os

NAME = "goal.json"
DEFAULT_LIMIT = 10
MAX_LIMIT = 1000
MAX_TEXT = 1000                                     # 目標文字最多幾個字（每次提醒都帶，太長會灌爆 history）
TOOL = "goal"                                       # 叫這支工具本身不算進展（工具名的最後一段，eca 經 aos-mcp 是 mcp__aos__goal）
STATUSES = ("active", "paused", "done", "abandoned")
BYS = ("agent", "outside", "aos")
PREFIX = "[aos] goal: "
SUMMARY = "[aos] summary:"                          # aos-agent history summarize 寫的那則的開頭（progressed 找不到提醒時的界線）
ECA_CALL_TYPES = ("tool_use", "function_call", "custom_tool_call", "local_shell_call", "mcp_tool_call")


class GoalBad(Exception):
    """goal.json 讀不懂（不是 JSON 物件、欄位不對）。"""


def path(stack):
    return os.path.join(stack, NAME)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check(rec):
    """形狀對＝回 rec；不對＝GoalBad（原因一句）。"""
    if not isinstance(rec, dict):
        raise GoalBad("goal.json is not a JSON object")
    if not isinstance(rec.get("text"), str) or not rec["text"].strip():
        raise GoalBad("goal.json text must be a non-empty string")
    if rec.get("status") not in STATUSES:
        raise GoalBad("goal.json status must be one of %s" % ", ".join(STATUSES))
    for key, low in (("reminded", 0), ("limit", 1)):
        v = rec.get(key)
        if not isinstance(v, int) or isinstance(v, bool) or v < low:
            raise GoalBad("goal.json %s must be an integer >= %d" % (key, low))
    if not isinstance(rec.get("reason", ""), str):
        raise GoalBad("goal.json reason must be a string")
    return rec


def read(stack):
    """不在＝None；壞了＝GoalBad；好的＝dict。"""
    try:
        with open(path(stack), encoding="utf-8") as f:
            rec = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError, UnicodeError) as e:
        raise GoalBad("cannot read %s: %s" % (NAME, getattr(e, "strerror", None) or e))   # 不印 stack 的絕對路徑（11-12 線 errpath），同上面幾句
    return check(rec)


def write(stack, rec):
    """整份寫回（暫存檔＋改名）；寫不成丟 OSError。"""
    check(rec)
    tmp = os.path.join(stack, ".%s.%d.tmp" % (NAME, os.getpid()))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, path(stack))


def clear(stack):
    """刪 goal.json；本來不在＝False。"""
    try:
        os.remove(path(stack))
        return True
    except FileNotFoundError:
        return False


def new(text, limit, by):
    return {"text": text.strip(), "status": "active", "reason": "", "reminded": 0, "limit": limit,
            "set_by": by, "updated_by": by, "updated_at": now_iso()}


def changed(rec, by, **fields):
    out = dict(rec, **fields)
    out.update(updated_by=by, updated_at=now_iso())
    return out


def reminder(rec):
    """丟給腦的那則（reminded 已是這次的號碼）。"""
    return (PREFIX + "%s (reminder %d of %d. Keep working on it; when it is finished call the goal tool with op done; "
            "if you are waiting for someone, op pause.)" % (rec["text"], rec["reminded"], rec["limit"]))


def limit_note(rec):
    return PREFIX + "reminder limit %d reached; goal paused (op resume to go on). Goal: %s" % (rec["limit"], rec["text"])


def plan(rec, progressed):
    """要不要丟、丟什麼：rec 不是 active＝None；否則回 (文字, 新的 rec)，不寫檔（呼叫的人在交出去那刻寫）。
    progressed＝上次提醒之後有叫工具做事＝先歸零。到上限＝那則是 limit_note、新 rec 改成 paused（之後不再丟）。"""
    if rec is None or rec["status"] != "active":
        return None
    reminded = 0 if progressed else rec["reminded"]
    if reminded >= rec["limit"]:
        out = changed(rec, "aos", status="paused", reminded=reminded,
                      reason="reminder limit %d reached without progress" % rec["limit"])
        return limit_note(rec), out
    out = dict(rec, reminded=reminded + 1)          # 提醒不算誰改了 goal：updated_* 不動
    return reminder(out), out


def is_goal_tool(name):
    """工具名的最後一段是 goal（agent-fsm 的登記名 goal；eca 經 aos-mcp 是 mcp__aos__goal、aos.goal 之類）。"""
    if not isinstance(name, str):
        return False
    return name.replace(".", "__").split("__")[-1] == TOOL


def is_reminder(m):
    return isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str) and m["content"].startswith(PREFIX)


def is_summary(m):
    """aos-agent history summarize（self_history、do_task end 都經它）寫的那則：content 開頭 [aos] summary:（角色不管）。"""
    return isinstance(m, dict) and isinstance(m.get("content"), str) and m["content"].startswith(SUMMARY)


def stopped(history):
    """history 最後一則是沒有 tool_calls 的 assistant＝腦自己停下來了（給了最後答案）。"""
    return bool(history) and isinstance(history[-1], dict) and history[-1].get("role") == "assistant" and not history[-1].get("tool_calls")


def due(history):
    """該不該丟（goal 是不是 active 另外看）：腦停下來了，或 history 還是空的（還沒答過任何一輪：外面先 set 了 goal，
    它就是開場題目；11-11 稍後使用者「也丟，當開場題目」）。"""
    return not history or stopped(history)


def progressed(history):
    """上次提醒之後有沒有新的動靜：只看 history（11-11 稍後使用者「兩者不要耦合太深，就goal那邊稍微檢查一下history就好」）。
    從最後一則往回找，碰到 assistant 叫了 goal 以外的工具（do_task 的 start／end 也是）＝True。停在哪：最近一則 [aos] goal: 提醒；
    history 裡一則提醒都找不到（被 do_task end 摺掉、被 summarize 掉、被改掉）＝停在最近一則 [aos] summary:（history 在那裡被改寫過，
    提醒多半在被摺掉的那段裡；摺完留下的 do_task end 那則在它後面，照樣算到）；提醒和 summary 都沒有＝False（不歸零，保守：寧可早停不要無限丟）。
    agent-fsm 用（eca 的工具來回在 CLI 裡、history 沒有，見 transcript_calls）。"""
    has_reminder = any(is_reminder(m) for m in history)
    if not has_reminder and not any(is_summary(m) for m in history):
        return False
    for m in reversed(history):
        if is_reminder(m) or (not has_reminder and is_summary(m)):
            return False
        if isinstance(m, dict) and m.get("role") == "assistant" and isinstance(m.get("tool_calls"), list):
            for c in m["tool_calls"]:
                fn = c.get("function") if isinstance(c, dict) else None
                if not is_goal_tool(fn.get("name") if isinstance(fn, dict) else None):
                    return True
    return False


def _calls(node, found):
    if isinstance(node, dict):
        if node.get("type") in ECA_CALL_TYPES:
            found.append(node.get("name") or node.get("tool") or "")
        for v in node.values():
            _calls(v, found)
    elif isinstance(node, list):
        for v in node:
            _calls(v, found)


def transcript_calls(file, offset=0):
    """eca：CLI 自己的對話檔（jsonl）從 offset byte 起有幾次叫了 goal 以外的工具（claude 的 tool_use、codex 的 function_call 等）。
    讀不到＝0（不歸零）。未經真 CLI 驗證：只認上面那幾種 type。"""
    try:
        with open(file, "rb") as f:
            f.seek(offset)
            data = f.read()
    except OSError:
        return 0
    found = []
    for line in data.decode("utf-8", "replace").splitlines():
        try:
            _calls(json.loads(line), found)
        except ValueError:
            continue
    return sum(1 for n in found if not is_goal_tool(n))


def size(file):
    try:
        return os.path.getsize(file) if file else 0
    except OSError:
        return 0


def progress(stack):
    """eca：這輪有叫工具做事＝active 的 goal 歸零（reminded > 0 才寫）。壞檔或寫不成＝安靜（下一次照數）。"""
    try:
        rec = read(stack)
        if rec is not None and rec["status"] == "active" and rec["reminded"]:
            write(stack, dict(rec, reminded=0))
    except (GoalBad, OSError):
        pass
