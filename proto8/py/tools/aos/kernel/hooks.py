# kernel 的三個 hook 時機：設定、事件欄位與判決回話；發事件經 aos.hook_point 的 hook 遙控器（open，錯交 ctx.die），執行一律交給共用引擎。
import json
import os

from aos import hook_point, hook_run


# 11-20 hook 第 3 刀：三個點只寫在同夾的 hook_points.json（使用者待裁第 14 題「一起搬」）；EVENTS 由它算出，驗清單用。
POINTS_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "hook_points.json")
POINTS = hook_point.read([POINTS_FILE])
EVENTS = hook_point.engine_table(POINTS)


def load(table, path):
    if not isinstance(table, dict):
        raise hook_run.HooksBad("hooks must be an object of named entries")
    entries = {}
    for name, entry in table.items():
        try:
            hook_run.validate_name(name)
            hook_run.validate_entry(entry, EVENTS)
        except hook_run.HooksBad as error:
            raise hook_run.HooksBad("hook %s: %s" % (name, error)) from None
        entries[name] = hook_run.complete(entry, path)
    return entries


def check(ctx, event, key, value):
    if event == "after_verdict" and key == "verdict" and value == "hold" and not ctx.can_hold:
        raise ValueError("verdict hold in stdout is not supported by this station")
    if event == "after_verdict" and key == "verdict" and value not in ("pass", "refuse", "hold"):
        raise ValueError("verdict in stdout must be pass, refuse or hold")
    if event == "after_verdict" and key == "next" and value is not None:
        # 替這一封指定下一站：只有會轉寄的包收；配不配得上這一站的設定由包自己說。
        if ctx.check_next is None:
            raise ValueError("next in stdout is not supported by this station (it does not forward letters)")
        if not isinstance(value, str) or not os.path.isabs(value):
            raise ValueError("next in stdout must be an absolute mailbox path or null")
        ctx.check_next(value)


def open(ctx):
    """這一輪的 hook 遙控器：點＝同夾 hook_points.json 的宣告（第 3 刀；宣告的 change 型別先驗、check 接著驗）、清單＝已讀好的 ctx.cfg["hooks"]；
    hook 停下（HookFailed／HooksBad）＝ctx.die（11-20 hook 介面第 2 刀，原本 round.py 自己接）。"""
    return hook_point.open(POINTS, entries=lambda: ctx.cfg["hooks"], stack=ctx.stack, fail=ctx.die, warn=ctx.warn,
                           check=lambda event, key, value: check(ctx, event, key, value))


def request_data(name, letter):
    return dict(letter=name, **{key: letter.get(key) for key in
                               ("sender", "sent_at", "reply_to", "body")})


def rejected(result):
    text = result["text"].strip()
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):
        data = None
    error = data.get("error") if isinstance(data, dict) else None
    if (isinstance(error, dict) and error.get("code") == "BudgetMissing"
            and isinstance(error.get("msg"), str) and error["msg"]
            and ("resets_at" not in error or error["resets_at"] is None
                 or isinstance(error["resets_at"], str))):
        extra = {"scope": "hook", "hook": result["hook"]}
        if "resets_at" in error:
            extra["resets_at"] = error["resets_at"]
        return "BudgetMissing", error["msg"], extra
    return "HookRejected", text or "blocked by hook %s" % result["hook"]


def before_verdict(ctx, name, letter):
    result = ctx.hooks.fire("before_verdict", request_data(name, letter))
    if not result["blocked"]:
        letter["body"] = result["data"]["body"]
    return result


def after_verdict(ctx, name, letter, verdict, detail, decided=False):
    """decided＝這封留著（或排著）的信已有人表態 pass、這次是重判：hook 再回 hold 不算數。"""
    data = request_data(name, letter)
    first = None   # 包原本的拒因（code, 它自己帶的額外鍵）；沒有拒因時是 None。
    error = None
    if verdict == "refuse":
        pack_extra = dict(detail[2]) if len(detail) > 2 and isinstance(detail[2], dict) else {}
        error = dict(pack_extra, code=detail[0], msg=detail[1])  # code/msg 最後寫：額外鍵蓋不掉它們
        first = (detail[0], pack_extra)
    data.update(verdict=verdict, error=error)
    if ctx.can_hold:
        data["decision"] = "pass" if decided else None  # null＝沒人表態過。
    if ctx.check_next is not None:
        data["next"] = None  # null＝沒指定，照站原本的下一站。
    # 比對沿用引擎的語意：condition 看最初判決（names 只比這一次）；逐格 fire 才能把預設拒因歸給正確的 hook。
    for hook in ctx.hooks.names("after_verdict", data):
        before = data["verdict"]
        result = ctx.hooks.fire("after_verdict", data, only=[hook])  # only：不再比 condition，前一格改判不會改變名單
        if result["blocked"]:
            return "refuse", rejected(result)
        data = result["data"]
        ignored = decided and data["verdict"] == "hold"
        if ignored:
            data["verdict"] = before  # 已有人表態：不再留，照這一格之前的判決走。
        error = data["error"]
        missing_error = not ignored and "verdict" in result["changed"] and "error" not in result["changed"]
        if data["verdict"] == "refuse" and (missing_error or not (
                isinstance(error, dict) and isinstance(error.get("code"), str)
                and isinstance(error.get("msg"), str))):
            data["error"] = {"code": "HookRejected", "msg": "refused by hook %s" % hook}
        if data["verdict"] != "refuse":
            data["error"] = None
    final = data["verdict"]
    if final == "pass" and data.get("next"):
        ctx.route[name] = data["next"]  # 只有放行才用得上；留隊的信出隊時 hook 會再跑一次。
    if final == "refuse":
        error = data["error"]
        extra = {key: value for key, value in error.items() if key not in ("code", "msg")}
        if first is not None and error["code"] != first[0]:
            # hook 改了 code：包原本那些額外鍵講的是舊的拒因，丟掉；hook 自己加或改過的鍵留著。
            extra = {key: value for key, value in extra.items()
                     if key not in first[1] or first[1][key] != value}
        return final, (error["code"], error["msg"], extra) if extra else (error["code"], error["msg"])
    if final == "hold":
        return final, None  # 留著時給的 next 不記；有人表態 pass、重判那一次 hook 再給才算。
    return final, detail if final == verdict else None


def before_reply(ctx, original, letter):
    data = {"letter": original["letter"], "sender": original.get("sender"),
            "reply_to": original["reply_to"], "reply_sender": letter.get("sender"),
            "body": letter["body"]}
    result = ctx.hooks.fire("before_reply", data)
    if result["blocked"]:
        return {"applied": False, "error": {"code": "HookRejected",
                "msg": "reply blocked by hook %s: %s" % (result["hook"], result["text"].strip())}}
    return result["data"]["body"]
