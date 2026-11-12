# aos_eca/batch.py - 一批信的認領與讀信（開場白、冷卻時只拿一封、take-all）與 goal 提醒的題目與進展。
import json

from .common import NOT_FOUND, Fail, cli_cell, goal_state, mailbox_warning, must_post, names, post
from .history import history_rows
from .hook import before_queue


# ---- 一批 ----

def letter_body(box, sig):
    """好信回 (body, None)；壞信回 (None, 原因)。"""
    code, out = post(["see", box, sig])
    if code != 0:
        return None, "aos-post see exited %d" % code
    try:
        body = json.loads(out).get("body")
    except (ValueError, AttributeError):
        return None, "aos-post see did not print a JSON object"
    if not (isinstance(body, dict) and body.get("role") == "user" and isinstance(body.get("content"), str)
            and body["content"].strip()):
        return None, "body must be {\"role\": \"user\", \"content\": non-empty string}"
    return body, None


def opening(stack, box, path):
    """history 空、queue 也空、有開場白檔＝把開場白投進 queue（射後不理那種的第一則）。回 True＝投了。
    開場白檔＝--prompt 給的（main 已轉成絕對路徑）；沒給（None）＝沒有開場白，不找 prompt.txt（11-04 翻案）。"""
    if not path:
        return False
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:                                       # main 驗過之後才被刪掉；給了就要有
        raise Fail("PromptMissing", "prompt file not found: %s" % path)
    except OSError as e:
        raise Fail("AgentBad", "cannot read %s: %s" % (path, e))
    text = text[:-1] if text.endswith("\n") else text           # 結尾一個換行不算
    if not text.strip() or history_rows(stack):
        return False
    must_post(["send", "--ordered", box], json.dumps({"role": "user", "content": text}, ensure_ascii=False))
    return True


SEP = "\n\n"                                   # 一批好幾封時，各封 content 照順序用一個空行接起來（11-03 代定）


def pick_one(stack, box, prompt, template):
    """冷卻到了（06）：只拿最舊的一封好信——cur/ 先、照 letter_key；cur/ 沒有好信才從 new/ 用 aos-post take 一次認領一封。
    壞信照舊丟、記 mailbox_warning，再往下找。回 ([sig], [body], 丟了幾封)；一封好信都沒有＝([], [], 丟了幾封)。"""
    if not names(box, "new") and not names(box, "cur"):
        opening(stack, box, prompt)
    dropped = 0
    while True:
        for sig in names(box, "cur"):
            body, why = letter_body(box, sig)
            if body is not None:
                body = before_queue(stack, box, sig, body, template)
                if body is not None:
                    return [sig], [body], dropped
                dropped += 1
                continue
            post(["done", box, sig])
            mailbox_warning(stack, sig, why)
            dropped += 1
        code, _ = must_post(["take", box], ok=(0, NOT_FOUND))    # new/ 最前面一封 → cur/
        if code == NOT_FOUND:
            return [], [], dropped


def take_all(stack, box, prompt):
    """new/ 裡的信全部認領到 cur/（aos-post take-all；沒信退 NOT_FOUND＝剛好被撤回，不算錯）；一批幾封沒有上限（11-03）。
    history 空、queue 也空、給了開場白檔（--prompt）＝先投開場白再認領。"""
    if not names(box, "new") and not names(box, "cur") and not opening(stack, box, prompt):
        return
    if names(box, "new"):
        must_post(["take-all", box], ok=(0, NOT_FOUND))            # new/ → cur/


def goal_prompt(stack):
    """⑬ queue 空時：goal active、上一輪 CLI 答完了（或 history 還空）＝(題目, 交出去那刻要寫的 goal)；否則 None。goal.json 壞了＝當沒有。"""
    try:
        rec = goal_state.read(stack)
    except goal_state.GoalBad:
        return None
    if rec is None or rec["status"] != "active" or not goal_state.due(history_rows(stack)):   # history 還空＝開場題目
        return None
    return goal_state.plan(rec, False)


def transcript_now(cfg, cell):
    """(session id, 對話檔, 大小)：交出去之前記下，答完再比（⑬ 進展）。"""
    sid = cell.read("session.txt")
    found = cli_cell.transcripts(cfg["kind"], sid)
    return sid, (found[0] if found else None), goal_state.size(found[0] if found else None)


def note_progress(cfg, cell, stack, before):
    """⑬ 這輪 CLI 叫了 goal 以外的工具＝goal 計數歸零。同一段對話只看新長出來的那段。"""
    sid, file, size = before
    now = cell.read("session.txt")
    found = cli_cell.transcripts(cfg["kind"], now)
    if not found:
        return
    if goal_state.transcript_calls(found[0], size if now == sid and found[0] == file else 0):
        goal_state.progress(stack)
