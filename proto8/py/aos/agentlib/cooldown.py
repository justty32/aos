"""cooldown - 失敗後冷卻的共用讀寫：$AOS_STACK/cooldown.json（不進 git）；aos-eca-turn 與 agent-fsm 的 wait.py 寫、aos-agent ctl ls／listen 讀。

two-machines 06（使用者 11-10 裁「失敗後冷卻，只拿一封試」）：交出去之後的失敗（eca 的 CliFailed／ReplyMissing、fsm 的
BrainFailed／SendFailed）記一筆，間隔 30 秒、1、2、4、8、15、30 分鐘，之後固定 30 分鐘；成功一次就刪檔（歸零）。
時間用牆上時鐘（要等的是外面的服務），UTC、ISO 8601 到秒、結尾 Z。格式（三方共用，改 key 要一起改）：

    {"failures": 4, "until": "2026-11-10T02:41:07Z", "at": "2026-11-10T02:33:07Z",
     "code": "CliFailed", "reason": "claude exited 1: usage limit reached", "dropped": 3}

failures＝這一串連續失敗幾次；until＝冷卻到幾點；at＝最後一次失敗的時間；code、reason＝最後一次的代號與原因；
dropped＝這一串掉了幾封信（eca 才加，fsm 重寄同一份請求、不掉信，一直是 0）。
選配兩欄（cooldown-1118，使用者 11-18 裁「寫進狀態檔」；只加欄、上面幾欄不動；aos-agent ctl ls 讀來顯示，listen 不看這兩欄、照舊認 stderr 結尾的錯誤行，使用者 11-18 裁「前綴補回」）：
    "retry": true|false   寫的那支（身體）接下來會不會自己重送：true＝冷卻到了自己再試（fsm 的 SendFailed、BudgetMissing、
                          retry true 的 BrainFailed；eca claude 的暫時錯）；false＝停在這個錯上、退 1 等人（或 auto_restart 重起後冷卻完才重寄）。
    "error": {"code", "msg"}  下層說的錯誤代號與原話一行（fsm＝llm kernel 回信的 error.code／msg，也就是 aos-llm 那行
                          「aos-llm: error: 代號 原因」的後半）；沒有下層的錯（eca、SendFailed）就不寫。
兩欄只在寫的人給了才有，每次失敗整份重寫（上一筆的不帶過來）。沒有這兩欄的檔照讀（自寫 body 的冷卻檔可能沒有）；
這兩欄型別不對＝只丟掉那一欄，其他照用。
檔壞了（不是 JSON 物件、欄位型別不對）當作沒有冷卻、照常做事；下一次失敗會整份重寫。純標準庫，lib 不 import py。"""
import datetime
import json
import os
import time

NAME = "cooldown.json"
STEPS_S = (30, 60, 120, 240, 480, 900, 1800)        # 第 n 次失敗等 STEPS_S[n-1]，之後固定最後一格


def path(stack):
    return os.path.join(stack, NAME)


def iso(t):
    return datetime.datetime.fromtimestamp(int(t), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(s):
    """ISO 字串 → epoch 秒；不是我們寫的格式＝None。"""
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def step_s(failures):
    """第 failures 次（從 1 起）失敗之後要等幾秒。"""
    return STEPS_S[min(max(failures, 1), len(STEPS_S)) - 1]


def read(stack):
    """讀 cooldown.json：不在或壞了＝None；好的＝dict（failures、dropped 一定是非負整數，until 一定解得開）。"""
    try:
        with open(path(stack), encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(rec, dict) or parse(rec.get("until")) is None:
        return None
    for key in ("failures", "dropped"):
        v = rec.get(key, 0)
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            return None
        rec[key] = v
    if "retry" in rec and not isinstance(rec["retry"], bool):
        del rec["retry"]                                # 選配欄壞了只丟那欄
    if "error" in rec and not (isinstance(rec["error"], dict) and isinstance(rec["error"].get("code"), str)
                               and isinstance(rec["error"].get("msg", ""), str)):
        del rec["error"]
    return rec


def state(stack, now=None):
    """('none', None)＝沒有冷卻；('cooling', rec)＝還沒到 until；('due', rec)＝冷卻到了（下一次只試一份）。"""
    rec = read(stack)
    if rec is None:
        return "none", None
    now = time.time() if now is None else now
    return ("cooling" if now < parse(rec["until"]) else "due"), rec


def one_line(s, n=500):
    return " ".join(str(s).split())[:n]


def error_of(error):
    """下層的 error 物件（例：llm kernel 回信的 error）→ 要寫進冷卻的 {"code", "msg"}；不是物件或沒有字串 code＝None。"""
    if not isinstance(error, dict) or not isinstance(error.get("code"), str) or not error["code"]:
        return None
    msg = error.get("msg")
    return {"code": one_line(error["code"], 100), "msg": one_line(msg if msg is not None else "")}


def _write(stack, old, failures, until, now, code, reason, dropped, retry, error):
    rec = {"failures": failures, "until": iso(until), "at": iso(now),
           "code": str(code), "reason": one_line(reason), "dropped": old.get("dropped", 0) + dropped}
    if isinstance(retry, bool):
        rec["retry"] = retry
    err = error_of(error)
    if err:
        rec["error"] = err
    tmp = os.path.join(stack, ".%s.%d.tmp" % (NAME, os.getpid()))   # N-05：先寫 . 開頭的暫存檔再改名
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, path(stack))
    return rec


def fail(stack, code, reason, dropped=0, now=None, retry=None, error=None):
    """記一次失敗：failures 加 1、until＝現在＋間隔、dropped 加上這次掉的封數；回寫進去的 dict。寫不成丟 OSError。
    retry（布林）＝這支之後會不會自己重送；error＝下層的 error 物件（取 code、msg）；沒給＝不寫那欄。"""
    now = time.time() if now is None else now
    old = read(stack) or {}
    failures = old.get("failures", 0) + 1
    return _write(stack, old, failures, now + step_s(failures), now, code, reason, dropped, retry, error)


def fail_until(stack, code, reason, until, dropped=0, now=None, retry=None, error=None):
    """同 fail，但冷卻到 until（epoch 秒）而不是照間隔表：kernel 說了額度什麼時候重置。failures 照樣加 1。寫不成丟 OSError。"""
    now = time.time() if now is None else now
    old = read(stack) or {}
    return _write(stack, old, old.get("failures", 0) + 1, until, now, code, reason, dropped, retry, error)


def clear(stack):
    """成功一次：刪檔（歸零）。本來就不在不算錯；刪不掉丟 OSError。"""
    try:
        os.remove(path(stack))
    except FileNotFoundError:
        pass
