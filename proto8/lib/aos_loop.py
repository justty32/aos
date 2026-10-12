"""loop：一張實例表，每個實例照執行方式一次次呼叫 aos_inst.run()。daemon 的 lib，不碰檔案；純標準庫。

實例的 id＝`aos_inst.find(target)`（inst.json 的 realpath）。每個實例自己一條執行緒：
等暫停解除 → 重讀 inst.json、run() 一次 → 剩餘次數減一 → 等 interval_ms → 再來。

執行方式（add 沒給的用預設，set 只改有給的）：

    times        還要跑幾次（非負整數；None＝不限；預設 1）
    interval_ms  一次跑完到下一次開始隔多久（非負整數；預設 0）
    timeout_ms   每次最多跑多久（正整數；None＝不限；預設 None）
    grace_ms     收掉時 SIGTERM 之後等多久才 SIGKILL（非負整數；預設 2000）

狀態（get／list 回的 dict）：`id`、`state`（waiting／running／paused／done／removing）、剩餘 `times`、
跑過幾次 `runs`、其他執行方式、`last_error`（上一次 aos_inst 自己出的錯；沒有＝None）。
被收掉的那次也算跑過一次。次數跑完的實例留在表上（done），加次數就再跑。
remove／pause 的 `wait`：True＝等這次跑完，False＝當場收掉（按 run() 的 stop）。

方法都可以從任何執行緒呼叫；出錯丟 `LoopError`。
"""
import os
import threading
import time

import aos_inst

__all__ = ["HOW", "Loop", "LoopError"]

HOW = {"times": 1, "interval_ms": 0, "timeout_ms": None, "grace_ms": 2000}


class LoopError(Exception):
    """操作被拒。`code`＝錯誤代號，`msg`＝白話，`str(e)`＝「代號: 白話」。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _how(given, base):
    """把 given 裡的執行方式蓋在 base 上，驗型別。"""
    for k in given:
        if k not in HOW:
            raise LoopError("FieldType", "不認得的執行方式 %r" % (k,))
    how = dict(base, **given)
    ok = {"times": how["times"] is None or _int(how["times"]) and how["times"] >= 0,
          "interval_ms": _int(how["interval_ms"]) and how["interval_ms"] >= 0,
          "timeout_ms": how["timeout_ms"] is None or _int(how["timeout_ms"]) and how["timeout_ms"] > 0,
          "grace_ms": _int(how["grace_ms"]) and how["grace_ms"] >= 0}
    for k, good in ok.items():
        if not good:
            raise LoopError("FieldType", "%s 的值不對：%r" % (k, how[k]))
    return how


def _wait_arg(wait):
    if not isinstance(wait, bool):
        raise LoopError("FieldType", "wait 要是 True／False，不是 %r" % (wait,))
    return wait


class _Inst:
    """一個實例。欄位都在 loop 的 cond 底下改。"""

    def __init__(self, loop, ident, how):
        self.loop = loop
        self.id = ident
        self.how = how
        self.paused = False
        self.removing = False
        self.running = False
        self.runs = 0
        self.last_error = None
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, name=ident, daemon=True)

    def state(self):
        if self.removing:
            return "removing"
        if self.running:
            return "running"
        if self.paused:
            return "paused"
        return "done" if self.how["times"] == 0 else "waiting"

    def status(self):
        return dict(self.how, id=self.id, state=self.state(), runs=self.runs, last_error=self.last_error)

    def _loop(self):
        cond = self.loop.cond
        with cond:
            while True:
                while not self.removing and (self.paused or self.how["times"] == 0):
                    cond.wait()
                if self.removing:
                    break
                self.running = True
                self.stop.clear()
                how = dict(self.how)
                cond.release()
                try:
                    err = self._once(how)
                finally:
                    cond.acquire()
                self.running = False
                self.runs += 1
                self.last_error = err
                if self.how["times"]:
                    self.how["times"] -= 1
                deadline = time.monotonic() + self.how["interval_ms"] / 1000
                while not self.removing and self.how["times"] != 0 and time.monotonic() < deadline:
                    cond.wait(deadline - time.monotonic())
            del self.loop.insts[self.id]
            cond.notify_all()

    def _once(self, how):
        try:
            aos_inst.run(aos_inst.load(self.id), timeout_ms=how["timeout_ms"], grace_ms=how["grace_ms"],
                         stop=self.stop, stop_poll_ms=self.loop.stop_poll_ms)
            return None
        except aos_inst.InstError as e:
            return str(e)


class Loop:
    def __init__(self, stop_poll_ms=50):
        self.stop_poll_ms = stop_poll_ms
        self.cond = threading.Condition()
        self.insts = {}

    def _get(self, ident):
        if not isinstance(ident, str) or ident not in self.insts:
            raise LoopError("NotFound", "沒有實例 %r" % (ident,))
        return self.insts[ident]

    def add(self, target, **how):
        """新增實例並開始跑，回 id。"""
        if not isinstance(target, str):
            raise LoopError("FieldType", "target 要是字串路徑，不是 %r" % (target,))
        try:
            ident = aos_inst.find(target)
        except aos_inst.InstError as e:
            raise LoopError(e.code, e.msg)
        if not os.path.isfile(ident):
            raise LoopError("NotFound", "%s 不存在" % ident)
        with self.cond:
            if ident in self.insts:
                raise LoopError("Exists", "實例 %s 已經在了" % ident)
            inst = _Inst(self, ident, _how(how, HOW))
            self.insts[ident] = inst
            inst.thread.start()
        return ident

    def set(self, ident, **how):
        with self.cond:
            inst = self._get(ident)
            inst.how = _how(how, inst.how)
            self.cond.notify_all()

    def remove(self, ident, wait=True):
        with self.cond:
            inst = self._get(ident)
            inst.removing = True
            if not _wait_arg(wait):
                inst.stop.set()
            self.cond.notify_all()

    def pause(self, ident, wait=True):
        with self.cond:
            inst = self._get(ident)
            inst.paused = True
            if not _wait_arg(wait) and inst.running:
                inst.stop.set()

    def resume(self, ident):
        with self.cond:
            self._get(ident).paused = False
            self.cond.notify_all()

    def times(self, ident, delta):
        """剩餘次數加減 delta，最少減到 0。"""
        if not _int(delta):
            raise LoopError("FieldType", "delta 要是整數，不是 %r" % (delta,))
        with self.cond:
            inst = self._get(ident)
            if inst.how["times"] is None:
                raise LoopError("Conflict", "%s 是不限次數，不能加減" % ident)
            inst.how["times"] = max(0, inst.how["times"] + delta)
            self.cond.notify_all()

    def state(self, ident):
        """只回狀態字串：waiting／running／paused／done／removing。"""
        with self.cond:
            return self._get(ident).state()

    def get(self, ident):
        with self.cond:
            return self._get(ident).status()

    def list(self):
        with self.cond:
            return [i.status() for i in self.insts.values()]

    def shutdown(self):
        """所有實例當場收掉，等它們的執行緒都結束。"""
        with self.cond:
            threads = []
            for inst in self.insts.values():
                inst.removing = True
                inst.stop.set()
                threads.append(inst.thread)
            self.cond.notify_all()
        for t in threads:
            t.join()
