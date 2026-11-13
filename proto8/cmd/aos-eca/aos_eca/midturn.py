# aos_eca/midturn.py - 等 CLI 回答的這段時間又來的信：馬上認領、過 hook、交給 cli_ask 投進 CLI（More）；信的寄件人欄（unnamed）。
"""11-13 使用者裁「馬上送，eca他會自己處理」：畫面開著的 claude 身走收件 socket 時（lib/agent/cli_ask.live_a2a），這一輪還在等回答，
queue 又來信就不等這輪講完——一次認領一封、照樣過 before_queue、投進 CLI（它手上那步工具做完就讀到），投出去才接進 history、收信、
跑 after_queue（Handoff.extra）。停手不再拿的情況（那封留在 cur/，下一輪照一般流程處理）：來的是 slash 指令（那是操作 CLI，要等這輪
講完由 aos 這層做）、hook 或 aos-post 出錯（下一輪在一般流程報）、投不出去。貼字與非互動那兩條路不叫這裡。"""
from .common import NOT_FOUND, Fail, mailbox_warning, must_post, names, post
from .batch import letter_body
from .hook import before_queue
from .slash import slash_of


def unnamed(body):
    """接進 history 的樣子：不帶寄件人（body 的 name 只給訊息信封用）。"""
    return {k: v for k, v in body.items() if k != "name"}


class More:
    def __init__(self, hand, template, stack, box):
        self.hand, self.template, self.stack, self.box = hand, template, stack, box
        self.stopped, self.pending = False, None

    def take(self):
        """queue 有新信＝認領最前面一封，回 [(寄件人名字或 None, 內文)]；沒有、停手了、上一封還沒結＝[]。壞信照舊丟、記 mailbox_warning。"""
        if self.stopped or self.pending or not (names(self.box, "new") or names(self.box, "cur")):
            return []
        if self.hand.late:                                             # 第一批收信就出錯了：不再加
            self.stopped = True
            return []
        try:
            if not names(self.box, "cur"):
                must_post(["take", self.box], ok=(0, NOT_FOUND))       # new/ 最前面一封 → cur/
            for sig in names(self.box, "cur"):
                if sig in self.hand.good:                              # 已經交出去的（收信那步沒成）：不重投
                    continue
                body, why = letter_body(self.box, sig)
                if body is None:
                    post(["done", self.box, sig])
                    mailbox_warning(self.stack, sig, why)
                    continue
                body = before_queue(self.stack, self.box, sig, body, self.template)
                if body is None:
                    continue
                if slash_of([body], None):
                    self.stopped = True
                    return []
                self.pending = (sig, body)
                return [(body.get("name"), body["content"])]
        except Fail:
            self.stopped = True
        return []

    def sent(self):
        sig, body = self.pending
        self.pending = None
        self.hand.extra(sig, unnamed(body))

    def unsent(self):
        self.stopped, self.pending = True, None
