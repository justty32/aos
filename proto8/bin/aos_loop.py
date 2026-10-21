"""aos_loop：反覆跑的程式的骨架（aos-loop、aos-daemon 共用；daemon.json 是 loop.json 的超集，N-28）。純標準庫。

    import aos_loop
    sys.exit(aos_loop.cli(aos_loop.Loop, sys.argv))

命令列（10-21 plan § 2）：`程式 [--cfg 設定檔] [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] [XXX [args...]]`，
旗標放 XXX 前面、規則同 aos-exec（aos_flags）。起跑時 旗標 ＞ 設定檔 ＞ 預設；命令列 XXX 蓋過設定檔的 run，
XXX 後的 args 每拍原樣接在目標後面。沒 --cfg 也沒 XXX＝usage 錯。

設定檔（loop.json）的 key（旗標名＝key 名底線換連字號）：
    run           每拍跑的目標：字串＝aos-exec 的目標（每拍 `aos-exec -- <run> args...`；相對路徑照 cwd，loop 不轉）；
                  只收字串，要內嵌單子寫 "loop.json#/body"（單子放在 body）；loop 必填（或命令列給 XXX）
    max           最多幾拍（非負整數；沒寫＝不限）
    interval_ms   一拍結束到下一拍開始至少隔幾毫秒（非負整數；loop 沒寫＝0）
    ctl, state    兩扇窗的檔名，在 $AOS_STACK 底下（N-09、N-13）；沒寫＝不開、不提醒；寫了卻沒設 AOS_STACK＝退 1
其他 key 忽略（body、_exec…）。跑的途中 ctl 蓋過上面這些（每圈讀一次、後到先贏）。

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

import re

import aos_beat
import aos_flags
import aos_inst
import aos_window

STOP = 10


class ConfigError(Exception):
    pass


def _nat(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


class Loop:
    prog = "aos-loop"
    max_default = None        # None＝不限（10-21 plan L8，原 10）
    interval_default = 0
    need_run = True
    ctl_extra = {}            # ctl 多認的 key：{key: 驗證函數（回錯誤字串或 None）}

    def __init__(self, opts, rest):
        """opts＝命令列旗標（aos_flags 解出來的字串），rest＝[XXX, args...]（可能是空的）。"""
        path = opts.get("cfg")
        cfg = {}
        if path is not None:
            try:
                with open(path, encoding="utf-8") as f:
                    cfg = json.load(f)
            except (OSError, ValueError) as e:
                raise ConfigError("讀不到或不是 JSON：%s（%s）" % (path, e))
            if not isinstance(cfg, dict):
                raise ConfigError("設定檔要是 JSON 物件")
        self.cfg = cfg = dict(cfg)
        for k in ("max", "interval_ms"):      # 旗標 ＞ 設定檔 ＞ 預設（L5）
            if k in opts:
                if not re.fullmatch(r"[0-9]+", opts[k]):
                    raise ConfigError("--%s 要是非負整數" % k.replace("_", "-"))
                cfg[k] = int(opts[k])
        for k in ("ctl", "state"):
            if k in opts:
                cfg[k] = opts[k]
        run = rest[0] if rest else cfg.get("run")
        self.args = rest[1:]
        if isinstance(run, dict):
            raise ConfigError("run 要是 aos-exec 的目標（字串）；要內嵌單子寫 loop.json#/body")
        if run is not None and not isinstance(run, str):
            raise ConfigError("run 要是 aos-exec 的目標（字串）")
        if run is None and self.need_run:
            raise ConfigError("沒有東西可跑（設定檔沒有 run，命令列也沒給 XXX）")
        self.run = run
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
                    b = aos_beat.run(self.run, args=self.args)
                except aos_inst.InstError as e:
                    self.say(str(e))
                    return self.end(1, "done")
                if b["received"]:
                    return self.end(128 + b["received"], "stopped")
                if b["code"] == STOP:
                    return self.end(0, "done")
                if b["code"]:
                    self.say("第 %d 圈 %s 失敗，結束碼 %d" % (self.lap, self.run, b["code"]))
                    return self.end(b["code"], "done")
            next_at = time.monotonic() + iv / 1000


# 旗標表（aos_flags）：旗標名＝設定檔的 key 名底線換連字號（C-54）
FLAGS = {"--cfg": "cfg", "--max": "max", "--interval-ms": "interval_ms", "--ctl": "ctl", "--state": "state"}


def cli(cls, argv):
    """命令列：`程式 [--cfg 設定檔] [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] [XXX [args...]]`。"""
    aos_beat.block()
    usage = "%s [--cfg 設定檔.json] [--max N] [--interval-ms N] [--ctl 檔] [--state 檔] [XXX [args...]]" % cls.prog
    try:
        opts, rest = aos_flags.parse(argv[1:], FLAGS)
    except aos_flags.Error as e:
        print("%s: usage: %s（%s）" % (cls.prog, usage, e), file=sys.stderr)
        return 1
    if "cfg" not in opts and not rest:
        print("%s: usage: %s（沒有 --cfg 也沒有 XXX）" % (cls.prog, usage), file=sys.stderr)
        return 1
    try:
        me = cls(opts, rest)
    except ConfigError as e:
        print("%s: %s" % (cls.prog, e), file=sys.stderr)
        return 1
    return me.main()
