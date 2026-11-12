# aos_eca/handoff.py - 一批信交給 CLI 的前後（一般一輪與 slash 交給 claude 的那幾條共用）：交出去那刻收信、交出去後失敗記冷卻、成功收尾。
import aos_flags

from .common import NAME, Fail, cli_ask, cooldown, must_post
from .history import append_history, history_sum
from .hook import fire


class Handoff:
    """一批（good＝信名、bodies＝接進 history 的 user 訊息）交給 CLI：ask 問、拿回答；回答接進 history 之後叫 done。
    first＝選填、不帶參數：交出去那刻、接進 history 之前叫一次（⑬ goal 計數）。mid＝交出去那刻的 history（⑩；沒交出去或收信出錯＝None）。"""

    def __init__(self, template, stack, box, good, bodies, first=None):
        self.template, self.stack, self.box, self.good, self.bodies, self.first = template, stack, box, good, bodies, first
        self.given, self.mid, self.late, self.after = False, None, None, None

    def handed(self):                                               # ④ 交出去就算完成（11-03）：user 接進 history、收信
        self.given = True
        try:
            if self.first:
                self.first()
            for body in self.bodies:
                append_history(self.stack, body)
            for sig in self.good:
                must_post(["done", self.box, sig])
            self.mid = history_sum(self.stack)                      # ⑩ 交出去那刻的 history
        except Fail as e:
            self.late = e                                           # CLI 已經在跑，等它答完再報
            return
        try:
            for sig, body in zip(self.good, self.bodies):           # hook：接進 history、收掉之後，每封一次
                fire("after_queue", {"letter": sig, "content": body["content"]}, self.template, self.stack)
        except Fail as e:
            self.after = e                                          # 回答照樣接進 history，最後才報（不掉回答）

    def ask(self, cfg, cell, ws, prompt, on_busy, reseed=None):
        """cli_ask.ask → 回答文字；None＝SessionBad（只有 --on-busy yield 會丟，一定在交出去之前：整批留 cur/，下一次再試）。"""
        try:
            text = cli_ask.ask(cfg, cell, self.template, ws, self.stack, prompt, on_busy, self.handed, reseed)
        except Fail as e:
            if e.code == "SessionBad":
                return None
            if self.given and e.code in ("CliFailed", "ReplyMissing"):   # ⑨ 交出去之後的失敗：記冷卻（這批掉了）
                fire("brain_failed", {"name": e.code, "reason": str(e)}, self.template, self.stack)   # hook 停下＝HookFailed，冷卻不記（同 agent-fsm wait）
                try:
                    cooldown.fail(self.stack, e.code, e, dropped=len(self.good))
                except OSError as w:
                    aos_flags.warn(NAME, "cannot write %s: %s" % (cooldown.path(self.stack), w))
            raise
        if self.late:
            raise self.late
        return text

    def done(self):
        """回答接進 history 之後：冷卻歸零（⑨ 成功一次），after_queue 停下的最後才報。"""
        try:
            cooldown.clear(self.stack)
        except OSError as w:
            aos_flags.warn(NAME, "cannot remove %s: %s" % (cooldown.path(self.stack), w))
        if self.after:
            raise self.after
