"""cooldown - 失敗後冷卻的共用讀寫：$AOS_STACK/cooldown.json（不進 git）；aos-eca-turn 與 agent-fsm 的 wait.py 寫、aos-image status 讀。

two-machines 06（使用者 11-10 裁「失敗後冷卻，只拿一封試」）：交出去之後的失敗（eca 的 CliFailed／ReplyMissing、fsm 的
BrainFailed／SendFailed）記一筆，間隔 30 秒、1、2、4、8、15、30 分鐘，之後固定 30 分鐘；成功一次就刪檔（歸零）。
時間用牆上時鐘（要等的是外面的服務），UTC、ISO 8601 到秒、結尾 Z。格式（三方共用，改 key 要一起改）：

    {"failures": 4, "until": "2026-11-10T02:41:07Z", "at": "2026-11-10T02:33:07Z",
     "code": "CliFailed", "reason": "claude exited 1: usage limit reached", "dropped": 3}

failures＝這一串連續失敗幾次；until＝冷卻到幾點；at＝最後一次失敗的時間；code、reason＝最後一次的代號與原因；
dropped＝這一串掉了幾封信（eca 才加，fsm 重寄同一份請求、不掉信，一直是 0）。
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
    return rec


def state(stack, now=None):
    """('none', None)＝沒有冷卻；('cooling', rec)＝還沒到 until；('due', rec)＝冷卻到了（下一次只試一份）。"""
    rec = read(stack)
    if rec is None:
        return "none", None
    now = time.time() if now is None else now
    return ("cooling" if now < parse(rec["until"]) else "due"), rec


def fail(stack, code, reason, dropped=0, now=None):
    """記一次失敗：failures 加 1、until＝現在＋間隔、dropped 加上這次掉的封數；回寫進去的 dict。寫不成丟 OSError。"""
    now = time.time() if now is None else now
    old = read(stack) or {}
    failures = old.get("failures", 0) + 1
    rec = {"failures": failures, "until": iso(now + step_s(failures)), "at": iso(now),
           "code": str(code), "reason": " ".join(str(reason).split())[:500], "dropped": old.get("dropped", 0) + dropped}
    tmp = os.path.join(stack, ".%s.%d.tmp" % (NAME, os.getpid()))   # N-05：先寫 . 開頭的暫存檔再改名
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, path(stack))
    return rec


def clear(stack):
    """成功一次：刪檔（歸零）。本來就不在不算錯；刪不掉丟 OSError。"""
    try:
        os.remove(path(stack))
    except FileNotFoundError:
        pass
