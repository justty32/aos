# kernel 的三個 hook 時機：這一家自己的規矩（能攔、能改哪些鍵、condition 比哪個欄、失敗＝停）、事件欄位與判決回話；跑 handler 一律交給共用引擎 aos.hook_run。
# 11-21（線 top-1121-hooknew，使用者「簡化到第四層」「發事件的程式自己決定」）：引擎只叫 handler、交回退出碼與 stdout；規矩寫在這裡，不讀宣告
#（宣告 kernel_hooks.json 只是參考，使用者 kernel 第 4 題「宣告這東西只是參考」）。被勾清單＝定義夾 interfaces.json 最外層 hookeds 指的檔
#（kernel_hookeds.json，kernel 第 3 題），每輪重讀；kernel.json 不再有 hooks。三個點都能攔（退 10）；hook 失敗（退 0／10 以外、逾時、起不來、
# stdout 不合）＝這一輪停（HookFailed，同以前 on_error 的預設 stop）。
import copy
import io
import json
import os

from aos import hook_lists, hook_point, hook_run

# 這一家自己發的三個點：condition 比哪個欄（None＝不收）、hook 能改哪些鍵。
POINTS = {"before_verdict": {"field": None, "change": ("body",)},
          "after_verdict": {"field": "verdict", "change": ("verdict", "error", "next")},
          "before_reply": {"field": None, "change": ("body",)}}


def check_entry(entry):
    hook_lists.check_entry(entry)
    if "condition" in entry:
        m = entry["condition"]
        if not ((isinstance(m, str) and m) or (isinstance(m, list) and all(isinstance(x, str) and x for x in m))):
            raise hook_lists.HooksBad("condition must be a non-empty string or an array of them")


OLD_KEY_MARK = "hooks_key_warned.txt"


def old_key(path, stack):
    """kernel.json 最外層還寫著 11-21 以前的 hooks 鍵：不擋（使用者 11-24「1.不報錯。」），照常跑，stderr 印一行 warning 說它被忽略、
    hook 要寫在哪。kernel 每拍是新行程，所以印過記在 $AOS_STACK/hooks_key_warned.txt（kernel.json 的路徑與 mtime），一樣就不再印；
    kernel.json 改了（mtime 變）再看一次，拿掉那鍵就刪記號。讀不到、不是 JSON 物件＝不管（讀設定那步自己會報）。"""
    path = path.partition("#")[0]
    try:
        with io.open(path, encoding="utf-8") as stream:
            doc = json.load(stream)
        stamp = "%s %d\n" % (os.path.abspath(path), os.stat(path).st_mtime_ns)
    except (OSError, ValueError):
        return
    mark = os.path.join(stack, OLD_KEY_MARK) if stack else None
    if not isinstance(doc, dict) or "hooks" not in doc:
        if mark and os.path.exists(mark):
            try:
                os.unlink(mark)
            except OSError:
                pass
        return
    try:
        with io.open(mark, encoding="utf-8") as stream:
            if stream.read() == stamp:
                return
    except (OSError, UnicodeError, TypeError):
        pass
    from aos import tool_io
    tool_io.warn("%s has a top-level \"hooks\" key, which is ignored since 11-21: no hook in it runs; put the hooks in the file named "
                 "by \"hookeds\" in the interfaces.json next to it (the templates use kernel_hookeds.json) and delete that key"
                 % os.path.abspath(path))
    if mark:
        try:
            tmp = os.path.join(stack, "." + OLD_KEY_MARK + ".tmp")
            with io.open(tmp, "w", encoding="utf-8") as stream:
                stream.write(stamp)
            os.replace(tmp, mark)
        except OSError:
            pass                                             # 寫不成＝下一拍再印一次


def load(def_dir):
    """定義夾 interfaces.json 的 hookeds 指的被勾清單 → {名: 格}；沒寫、檔不在＝{}。壞＝ValueError（HooksBad／InterfaceBad）。"""
    return hook_lists.load(hook_point.files(def_dir, "hookeds"), check_entry)


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


def matches(entry, data):
    field = POINTS.get(entry["event"], {}).get("field")
    if field is None or "condition" not in entry:
        return True
    m = entry["condition"]
    return data.get(field) in ([m] if isinstance(m, str) else m)


class Hooks:
    """這一輪的 hook 遙控器：names／fire；hook 失敗＝ctx.die("HookFailed")。"""

    def __init__(self, ctx):
        self.ctx = ctx

    def names(self, event, data):
        entries = self.ctx.cfg["hooks"]
        return [n for n in hook_run.names(entries, event) if matches(entries[n], data)]

    def fire(self, event, data, only=None):
        """照名字跑（前一個改的後一個看得到）；退 10＝攔下就停；only＝只跑這幾個（不再比 condition）。"""
        entries, ctx = self.ctx.cfg["hooks"], self.ctx
        result = {"data": copy.deepcopy(data), "changed": [], "blocked": False, "hook": None, "text": ""}
        for name in hook_run.names(entries, event):
            if (only is not None and name not in only) or (only is None and not matches(entries[name], data)):
                continue
            r = hook_run.run(name, entries[name], event, result["data"], ctx.stack)
            try:
                if r["error"]:
                    raise ValueError(r["error"])
                if r["code"] == hook_run.BLOCK:
                    result.update(blocked=True, hook=name, text=r["stdout"])
                    return result
                if r["code"] != 0:
                    raise ValueError("exited %d" % r["code"])
                got = {}
                if r["stdout"].strip():
                    try:
                        reply = json.loads(r["stdout"])
                    except ValueError as e:
                        raise ValueError("stdout is not JSON: %s" % e) from None
                    if not isinstance(reply, dict):
                        raise ValueError("stdout is not a JSON object")
                    for key in POINTS.get(event, {"change": ()})["change"]:
                        if key in reply:
                            check(ctx, event, key, reply[key])
                            got[key] = reply[key]
            except ValueError as e:
                ctx.die("HookFailed", "hook %s (event %s) failed: %s" % (name, event, e))
            for key, v in got.items():
                result["data"][key] = v
                if key not in result["changed"]:
                    result["changed"].append(key)
        return result


def open(ctx):
    """這一輪的 hook 遙控器：清單＝已讀好的 ctx.cfg["hooks"]（讀設定時 load 的）。"""
    return Hooks(ctx)


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
