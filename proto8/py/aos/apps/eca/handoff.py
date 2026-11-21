# aos/apps/eca/handoff.py - 一批信交給 CLI 的前後（一般一輪與 slash 交給 claude 的那幾條共用）：交出去那刻收信、交出去後失敗記冷卻、成功收尾。
from aos import flags as aos_flags
from aos import ws as aos_ws

from .common import NAME, Fail, cli_ask, cooldown, letters_drop, letters_take, must_post, quiet
from . import retry
from .history import append_history, history_sum, note_sum


class Handoff:
    """一批（good＝信名、bodies＝接進 history 的 user 訊息）交給 CLI：ask 問、拿回答；回答接進 history 之後叫 done。
    hooks＝這一輪的 hook 遙控器（hook.open_hooks；定義資料夾＝hooks.def_folder，也給 cli_ask）。
    first＝選填、不帶參數：交出去那刻、接進 history 之前叫一次（⑬ goal 計數）。mid＝交出去那刻的 history（⑩；沒交出去或收信出錯＝None）。"""

    def __init__(self, hooks, stack, box, good, bodies, first=None, owed=None, redo=False):
        self.hooks, self.template = hooks, hooks.def_folder
        self.stack, self.box, self.good, self.bodies, self.first = stack, box, good, bodies, first
        self.owed, self.redo = list(owed or ()), redo
        self.retrying = owed is not None                            # 續做輪（retry.json 的欠帳；goal 輪欠的是 0 封也算）
        self.given, self.mid, self.late, self.after = False, None, None, None
        self.left = []                                              # 已經 done（離開 queue）的信名：失敗時只把這些記成 dropped failed

    def answer_to(self):
        return list(self.owed) + self.good

    def handed(self):                                               # ④ 交出去就算完成（11-03）：user 接進 history、收信
        self.given = True
        try:
            if self.first:
                self.first()
            letters_take(self.stack, self.good)                     # 回答配對：先記 pending，再接 history（帶 aos.letter）、再收信
            lead = len(self.bodies) - len(self.good)                # 前面不是信的（goal 題目）不帶 aos
            for i, body in enumerate(self.bodies):
                append_history(self.stack, aos_ws.mark_letter(body, self.good[i - lead]) if i >= lead else body)
            for sig in self.good:
                must_post(["done", self.box, sig])
                self.left.append(sig)
            self.mid = history_sum(self.stack)                      # ⑩ 交出去那刻的 history
        except Fail as e:
            self.late = e                                           # CLI 已經在跑，等它答完再報
            return
        try:
            for sig, body in zip(self.good, self.bodies):           # hook：接進 history、收掉之後，每封一次
                self.hooks.fire("after_queue", {"letter": sig, "content": body["content"]})
        except Fail as e:
            self.after = e                                          # 回答照樣接進 history，最後才報（不掉回答）

    def extra(self, sig, body):
        """等回答時又交出去的一封（11-13 馬上送）：同 handed 那幾步——接進 history、收信、after_queue；出錯一樣留到最後報。"""
        try:
            letters_take(self.stack, [sig])
            append_history(self.stack, aos_ws.mark_letter(body, sig))
            must_post(["done", self.box, sig])
            self.left.append(sig)
            self.mid = history_sum(self.stack)
        except Fail as e:
            self.late = self.late or e
            return
        self.good.append(sig)
        self.bodies.append(body)
        try:
            self.hooks.fire("after_queue", {"letter": sig, "content": body["content"]})
        except Fail as e:
            self.after = self.after or e

    def ask(self, cfg, cell, ws, prompt, on_busy, reseed=None, parts=None, more=None):
        """cli_ask.ask → 回答文字；None＝SessionBad（交出去之前，整批留 cur/）或已記錄冷卻的 claude 暫時失敗。
        parts＝[(寄件人名字或 None, 內文)]，一封一項（11-13：畫面開著的 claude 身一封一個署名信封）；more＝等回答時又來的信（midturn.More）。"""
        # 11-15（使用者「很久沒動靜算黃色，不殺掉」）：一輪 CLI 在跑、小格的紀錄檔滿 10 分鐘都沒變＝寫 $AOS_STACK/quiet.json（只標記），
        # 又有動靜或這輪結束就收掉；預設不限時，所以「慢」不再算失敗。
        watch = quiet.Watch(self.stack, "cli_turn", [cell.file(n) for n in ("live.jsonl", "turns.jsonl", "busy.txt", "transcripts")])
        try:
            with watch:
                text = cli_ask.ask(cfg, cell, self.template, ws, self.stack, prompt, on_busy, self.handed, reseed, parts, more)
                if cfg["kind"] == "claude" and text is not None and not isinstance(text, str):
                    raise Fail("CliFailed", "the CLI's answer is not text (%s)" % type(text).__name__)
        except Fail as e:
            if e.code == "SessionBad":
                return None
            if self.given and e.code in ("CliFailed", "ReplyMissing"):   # ⑨ 交出去之後的失敗：claude 分暫時／永久，codex 照舊
                if cfg["kind"] == "claude":
                    return self._claude_failed(cfg, cell, e)
                letters_drop(self.stack, self.left, "failed")       # 回答配對：已收掉的信不會有回答了（還在 cur/ 的下一輪再交）
                self.hooks.fire("brain_failed", {"name": e.code, "reason": str(e)})   # hook 失敗＝一行 warning（brain_failed 不能攔，11-21）
                try:
                    cooldown.fail(self.stack, e.code, e, dropped=len(self.good), retry=False)   # 照舊報錯退 1：停在這個錯上（cooldown-1118 的 retry 欄）
                except OSError as w:
                    aos_flags.warn(NAME, "cannot write %s: %s" % (cooldown.path(self.stack), w))
            raise
        if self.late:
            raise self.late
        return text

    def _claude_failed(self, cfg, cell, e):
        info = getattr(e, "info", None)
        info = info if isinstance(info, dict) else None
        cool = cooldown.read(self.stack) or {}
        old = retry.read(self.stack)
        temporary = bool(info and info.get("retry") is True and not self.late and not self.after)
        attempt = max(cool.get("failures", 0) + 1, old["attempt"] + 1 if old else 0)
        reason = str(e)
        if temporary and attempt >= retry.MAX_FAILURES:                # 上限到了：這次當永久錯
            temporary = False
            reason += " (gave up after %d temporary failures in a row)" % attempt
            e = Fail(e.code, reason)
        if temporary:
            edited = self.mid is not None and history_sum(self.stack) != self.mid
            note_sum(self.stack, cell, edited)
            if self.redo:
                try:
                    rec = retry.note(self.stack, self.owed + self.left, e.code, str(e), info)
                except OSError as w:
                    aos_flags.warn(NAME, "cannot write %s: %s" % (retry.path(self.stack), w))
                    temporary = False
                else:
                    attempt, dropped = rec["attempt"], 0
            else:
                letters_drop(self.stack, self.left, "failed")
                dropped = len(self.left)
        if not temporary:
            letters_drop(self.stack, self.owed + self.left, "failed")
            if self.retrying:
                try:
                    retry.clear(self.stack)
                except OSError as w:
                    aos_flags.warn(NAME, "cannot remove %s: %s" % (retry.path(self.stack), w))
            dropped = len(self.owed) + len(self.left)
        event = {"name": e.code, "reason": reason, "code": e.code, "retry": temporary,
                 "attempt": attempt, "dropped": dropped}
        if temporary:
            event["wait_s"] = cooldown.step_s(cool.get("failures", 0) + 1)
        if info:
            status = info.get("status")
            if isinstance(status, int) and not isinstance(status, bool):
                event["status"] = status
            if isinstance(info.get("cause"), str):
                event["cause"] = info["cause"]
        self.hooks.fire("brain_failed", event)
        try:
            cooldown.fail(self.stack, e.code, e, dropped=dropped, retry=temporary)   # 暫時＝退 0、冷卻完自己接著試；永久＝退 1 停下
        except OSError as w:
            aos_flags.warn(NAME, "cannot write %s: %s" % (cooldown.path(self.stack), w))
        if temporary:
            return None
        raise e

    def done(self):
        """回答接進 history 之後：冷卻歸零（⑨ 成功一次），after_queue 停下的最後才報。"""
        try:
            cooldown.clear(self.stack)
        except OSError as w:
            aos_flags.warn(NAME, "cannot remove %s: %s" % (cooldown.path(self.stack), w))
        if self.after:
            raise self.after
