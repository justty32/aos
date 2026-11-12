# aos_eca/history.py - $AOS_STACK/history.jsonl 的讀、附加，與 .history_sum（⑩ history 被改過＝開新對話）。
import hashlib
import json
import os

import aos_flags

from .common import NAME, Fail, cli_session


# ---- history（$AOS_STACK/history.jsonl，一行一則 OpenAI message，只附加；P-41）----

def history_rows(stack):
    rows = []
    try:
        with open(os.path.join(stack, "history.jsonl"), encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    m = json.loads(line)
                except ValueError:
                    m = None
                if not isinstance(m, dict):
                    raise Fail("HistoryBad", "history.jsonl line %d is not a JSON object" % i)
                rows.append(m)
    except FileNotFoundError:
        pass
    except OSError as e:
        raise Fail("HistoryBad", "cannot read history.jsonl: %s" % e)
    return rows


SUM = ".history_sum"                                           # ⑩ 小格裡：上一輪結束時 history 的 sha256（或 edited）


def history_sum(stack):
    try:
        with open(os.path.join(stack, "history.jsonl"), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        return hashlib.sha256(b"").hexdigest()
    except OSError as e:
        raise Fail("HistoryBad", "cannot read history.jsonl: %s" % e)


def history_changed(stack, cell):
    """⑩ 交出去之前：history 跟上一輪結束時不一樣＝丟掉 CLI 的舊對話（下一步 ask 照 ⑧ 開新的、帶改過的紀錄）。"""
    seen = cell.read(SUM)
    if not seen or seen == history_sum(stack):
        return
    if cell.alive():
        aos_flags.warn(NAME, "history.jsonl was changed, but the screen is open, so the conversation there keeps its old record")
        return
    cli_session.drop_session(cell)
    aos_flags.warn(NAME, "history.jsonl was changed since the last turn; starting a new %s conversation that carries the changed record" % cell_kind(cell))


def cell_kind(cell):
    return os.path.basename(cell.path)


def note_sum(stack, cell, edited):
    try:
        with open(cell.file(SUM), "w", encoding="utf-8") as f:
            f.write(("edited" if edited else history_sum(stack)) + "\n")
    except (OSError, Fail) as e:
        aos_flags.warn(NAME, "cannot write %s: %s" % (cell.file(SUM), e))


def append_history(stack, msg):
    try:
        with open(os.path.join(stack, "history.jsonl"), "a", encoding="utf-8") as f:   # 一次寫一整行
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    except OSError as e:
        raise Fail("WriteFailed", "cannot append to history.jsonl: %s" % e)
