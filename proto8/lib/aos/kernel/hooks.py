# kernel 的三個 hook 時機：設定、事件欄位與判決回話，執行一律交給共用引擎。
import os

import hook_run


EVENTS = {
    "before_verdict": {"condition": None, "intercept": ("body",), "block": True},
    "after_verdict": {"condition": "verdict", "intercept": ("verdict", "error", "next"), "block": True},
    "before_reply": {"condition": None, "intercept": ("body",), "block": True},
}


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


def fire(ctx, event, data, entries=None):
    return hook_run.fire(event, data, ctx.cfg["hooks"] if entries is None else entries,
                         ctx.stack, EVENTS, warn=ctx.warn,
                         check=lambda event, key, value: check(ctx, event, key, value))


def request_data(name, letter):
    return dict(letter=name, **{key: letter.get(key) for key in
                               ("sender", "sent_at", "reply_to", "body")})


def rejected(result):
    return "HookRejected", result["text"].strip() or "blocked by hook %s" % result["hook"]


def before_verdict(ctx, name, letter):
    result = fire(ctx, "before_verdict", request_data(name, letter))
    if not result["blocked"]:
        letter["body"] = result["data"]["body"]
    return result


def after_verdict(ctx, name, letter, verdict, detail, decided=False):
    """decided＝這封留著（或排著）的信已有人表態 pass、這次是重判：hook 再回 hold 不算數。"""
    data = request_data(name, letter)
    data.update(verdict=verdict, error=dict(zip(("code", "msg"), detail)) if verdict == "refuse" else None)
    if ctx.can_hold:
        data["decision"] = "pass" if decided else None  # null＝沒人表態過。
    if ctx.check_next is not None:
        data["next"] = None  # null＝沒指定，照站原本的下一站。
    # 比對沿用引擎的語意：condition 看最初判決；逐格 fire 才能把預設拒因歸給正確的 hook。
    eligible = {n: e for n, e in ctx.cfg["hooks"].items()
                if e["event"] == "after_verdict" and hook_run.matches(e, EVENTS, data)}
    for hook in sorted(eligible):
        entry = dict(eligible[hook])
        entry.pop("condition", None)  # 上面已比過；前一格改判不會改變這次要通知的名單。
        before = data["verdict"]
        result = fire(ctx, "after_verdict", data, {hook: entry})
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
        return final, (data["error"]["code"], data["error"]["msg"])
    if final == "hold":
        return final, None  # 留著時給的 next 不記；有人表態 pass、重判那一次 hook 再給才算。
    return final, detail if final == verdict else None


def before_reply(ctx, original, letter):
    data = {"letter": original["letter"], "sender": original.get("sender"),
            "reply_to": original["reply_to"], "reply_sender": letter.get("sender"),
            "body": letter["body"]}
    result = fire(ctx, "before_reply", data)
    if result["blocked"]:
        return {"applied": False, "error": {"code": "HookRejected",
                "msg": "reply blocked by hook %s: %s" % (result["hook"], result["text"].strip())}}
    return result["data"]["body"]
