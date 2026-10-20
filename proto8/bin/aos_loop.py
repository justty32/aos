"""aos_loop：反覆跑的程式的骨架（aos-loop、aos-daemon 共用；daemon.json 是 loop.json 的超集，N-28）。純標準庫。

    import aos_loop
    sys.exit(aos_loop.Loop(設定檔路徑).main())

設定檔（loop.json）的 key：
    run           每拍跑的身體：字串＝子資料夾（`aos-exec` 它）、物件＝一張單子（行程內 aos_inst.run()）；loop 必填
    max           最多幾拍（非負整數；loop 沒寫＝10）
    interval_ms   一拍結束到下一拍開始至少隔幾毫秒（非負整數；loop 沒寫＝0）
    ctl, state    兩扇窗的檔名，在 $AOS_STACK 底下（N-09、N-13）；沒寫＝不開、不提醒；寫了卻沒設 AOS_STACK＝退 1
其他 key 忽略。

每圈：看有沒有收到訊號 → 讀 ctl（N-06～N-08；能蓋 max、interval_ms，認 paused、stop、seq）→ tend()（子類別的事）
→ stop 就結束、拍滿 max 就結束 → paused 或還沒到下一拍的時間就睡一下（最多 1 秒，期間每 50 毫秒看一次訊號）、回頭再看
→ 跑一拍（aos_beat.run）。拍的結束碼 0＝下一拍、10＝要求停（以 0 結束）、其他非 0＝失敗（stderr 一行、以原碼結束）。
state 只在拍與拍之間寫（心跳只在兩拍之間跳，使用者 10-20「照預設」）：每圈寫一次、結束時寫最後一份。
收到 SIGINT／SIGTERM／SIGHUP：轉給正在跑的那拍、等它結束、不起下一拍，以 128＋N 結束（P-36）。
結束前呼叫 finish()（子類別收自己起的東西）。自己的錯退 1，stderr 一行「程式名: 原因」。"""
import json
import os
import sys
import time

import aos_beat
import aos_inst
import aos_window

STOP = 10


class ConfigError(Exception):
    pass


def _nat(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


class Loop:
    prog = "aos-loop"
    max_default = 10          # None＝不限
    interval_default = 0
    need_run = True
    ctl_extra = {}            # ctl 多認的 key：{key: 驗證函數（回錯誤字串或 None）}

    def __init__(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError) as e:
            raise ConfigError("讀不到或不是 JSON：%s（%s）" % (path, e))
        if not isinstance(cfg, dict):
            raise ConfigError("設定檔要是 JSON 物件")
        self.cfg = cfg
        run = cfg.get("run")
        if run is None and self.need_run or run is not None and not isinstance(run, (str, dict)):
            raise ConfigError('run 要是子資料夾或單子（{"run": …, "max": 圈數}）')
        self.run = run
        self.ref_base = os.path.dirname(os.path.realpath(path))   # 單子裡 $ref 的起點（N-45）
        self.max = cfg.get("max", self.max_default)
        if not (self.max is None and "max" not in cfg or _nat(self.max)):
            raise ConfigError("max 要是非負整數")
        self.interval = cfg.get("interval_ms", self.interval_default)
        if not _nat(self.interval):
            raise ConfigError("interval_ms 要是非負整數")
        self.stack = os.environ.get("AOS_STACK")
        win = {}
        for k in ("ctl", "state"):
            v = cfg.get(k)
            if v is None:
                win[k] = None
                continue
            if not isinstance(v, str) or not v:
                raise ConfigError("%s 要是檔名" % k)
            if not self.stack:
                raise ConfigError("寫了 %s 卻沒設定 AOS_STACK" % k)
            win[k] = os.path.join(self.stack, v)
        self.ctl = aos_window.Ctl(win["ctl"], self.ctl_extra)
        self.state_path = win["state"]
        self.lap, self.ctl_now = 0, {}

    # 子類別蓋這三個
    def tend(self, ctl):
        """每圈讀完 ctl 後呼叫。"""

    def finish(self):
        """結束前呼叫（不論為什麼結束）。"""

    def info(self):
        """寫進 state 的額外欄位。"""
        return {}

    def say(self, msg):
        print("%s: %s" % (self.prog, msg), file=sys.stderr)

    def write(self, state, **more):
        if self.state_path is None:
            return
        c = self.ctl_now
        doc = {"kind": "state", "state": state, "lap": self.lap,
               "max": c.get("max", self.max), "interval_ms": c.get("interval_ms", self.interval),
               "paused": c.get("paused", False), "ctl_seq": c.get("seq"), "last_warning": self.ctl.warning}
        doc.update(self.info())
        doc.update(more)
        doc.update(aos_window.beat())
        aos_window.write(self.state_path, doc)

    def end(self, code, state):
        self.finish()
        self.write(state, code=code)
        return code

    def nap(self, secs):
        """睡 secs 秒（最多 1 秒），收到訊號就提早醒。"""
        until = time.monotonic() + min(secs, 1.0)
        while not aos_beat.take():
            left = until - time.monotonic()
            if left <= 0:
                return
            time.sleep(min(left, 0.05))

    def main(self):
        next_at = 0.0
        while True:
            if aos_beat.take():
                return self.end(128 + aos_beat.take(), "stopped")
            self.ctl_now = c = self.ctl.read()
            mx, iv = c.get("max", self.max), c.get("interval_ms", self.interval)
            try:
                self.tend(c)
            except aos_inst.InstError as e:
                self.say(str(e))
                return self.end(1, "stopped")
            if c.get("stop"):
                return self.end(0, "stopped")
            if mx is not None and self.lap >= mx:
                return self.end(0, "done")
            wait = next_at - time.monotonic()
            if c.get("paused") or wait > 0:
                self.write("paused" if c.get("paused") else "waiting")
                self.nap(1.0 if c.get("paused") else wait)
                continue
            self.lap += 1
            self.write("running")
            if self.run is not None:
                try:
                    b = aos_beat.run(self.run, self.ref_base)
                except aos_inst.InstError as e:
                    self.say(str(e))
                    return self.end(1, "done")
                if b["received"]:
                    return self.end(128 + b["received"], "stopped")
                if b["code"] == STOP:
                    return self.end(0, "done")
                if b["code"]:
                    name = self.run if isinstance(self.run, str) else " ".join(map(str, self.run.get("argv", ["?"])))
                    self.say("第 %d 圈 %s 失敗，結束碼 %d" % (self.lap, name, b["code"]))
                    return self.end(b["code"], "done")
            next_at = time.monotonic() + iv / 1000


def cli(cls, argv):
    """命令列：`程式 設定檔`。"""
    aos_beat.block()
    if len(argv) < 2:
        print("%s: usage: %s 設定檔.json" % (cls.prog, cls.prog), file=sys.stderr)
        return 1
    try:
        me = cls(argv[1])
    except ConfigError as e:
        print("%s: %s" % (cls.prog, e), file=sys.stderr)
        return 1
    return me.main()
