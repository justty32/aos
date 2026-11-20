"""aos.gdb.handles - a.bp 交回去給人拿著的兩種物件：Breakpoint（a.bp.add.<種類>(...) 回的斷點，屬性每次讀都重新查）與 Pending（resume／step／pause 給 wait=False 時回的，is_done() 問好了沒）。

使用者 11-20 選項框（紀錄 thinking/2026-11/20/aos-gdb-問答-1120.md、aos-gdb-wait-1120.md）：
    a.bp.add「回物件、帶屬性」；屬性「每次讀都重新查」（斷點被刪掉後讀屬性會報錯）；id 純數字、種類放在屬性（.kind）。
    「不等」的時候「回一個可以查的物件。用is_done()」；pause、resume、step「三個都加」wait=。"""
import threading

from aos.gdb.look import Failed

FIELDS = ("kind", "how", "about", "enabled", "times", "once", "seen", "streak", "fired", "spent", "last_error", "here",
          "tools", "condition", "targets", "every_ms", "phase", "pid", "per_target")


class Breakpoint:
    """一個斷點：.id 固定（號碼 int，或自己取的名字 str）；其餘屬性＝a.bp.get(id) 那一列的欄（.kind＝種類，例 before_tool、tool_error、watch；
    .enabled、.fired、.about…），每次讀都重新查，所以會跟著變；斷點不在了（a.bp.rm 過）讀屬性＝Failed（code BreakpointGone）。
    改用 a.bp.set(b, ...)、刪用 a.bp.rm(b)；b == 3 比的是 id。"""

    def __init__(self, bp, id):
        object.__setattr__(self, "_bp", bp)
        object.__setattr__(self, "id", id)

    def _row(self):
        try:
            return self._bp.get(self.id)
        except Failed as e:
            if e.code != "BreakpointMissing":
                raise
            raise Failed("breakpoint %s" % self.id, "it is gone from %s (removed); a.bp.ls() lists the ones there are" % self._bp._a.name,
                         code="BreakpointGone") from None

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        row = self._row()
        if name not in row:
            raise AttributeError("breakpoint %s has no %s (it has: %s)" % (self.id, name, ", ".join(sorted(row))))
        return row[name]

    def __setattr__(self, name, value):
        raise AttributeError("a breakpoint's fields are read only; change them with a.bp.set(b, ...)")

    def __dir__(self):
        return ["id"] + list(FIELDS)

    def __eq__(self, other):
        if isinstance(other, Breakpoint):
            return (self.id, self._bp._a.daemon, self._bp._a.name) == (other.id, other._bp._a.daemon, other._bp._a.name)
        return not isinstance(other, bool) and self.id == other

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        try:
            r = self._row()
        except Failed:
            return "<breakpoint %s of %s: gone>" % (self.id, self._bp._a.name)
        state = ", ".join(x for x in ("enabled" if r["enabled"] else "disabled", "fired %d" % r["fired"],
                                      "stopped here" if r["here"] else "") if x)
        return "<breakpoint %s of %s: %s, %s (%s)>" % (self.id, self._bp._a.name, r["kind"], r["about"], state)


class Pending:
    """resume／step／pause 給 wait=False 時回的：動作已經送出，等它停下的那段在背景（這個 Python 行程裡的一條執行緒）跑。
    is_done()＝好了沒（停了、確定不會停、或等出錯了都算好了）；wait()＝等到好了，回跟 wait=True 時一樣的東西（.outcome、.head），
    背景裡丟的錯（例如 a.bp.timeout_s 到了的 Timeout）在 wait() 丟。wait() 裡按 Ctrl-C 只是這次不等了，背景照等。
    背景裡不印「still waiting」那一行（a.bp.report_s 不用在這裡）。"""

    def __init__(self, what, name, run=None, value=None):
        self._what, self._name = what, name
        self._done = threading.Event()
        self._out, self._err = value, None
        if run is None:
            self._done.set()
        else:
            threading.Thread(target=self._go, args=(run,), name=what, daemon=True).start()

    def _go(self, run):
        try:
            self._out = run()
        except BaseException as e:               # 什麼錯都留給 wait()
            self._err = e
        finally:
            self._done.set()

    def is_done(self):
        """好了沒（True＝wait() 馬上回）。"""
        return self._done.is_set()

    def wait(self):
        """等到好了，回結果（跟 wait=True 一樣）；背景丟的錯在這裡丟。"""
        while not self._done.wait(0.1):
            pass
        if self._err is not None:
            raise self._err
        return self._out

    def __repr__(self):
        if not self._done.is_set():
            return "<%s on %s: still waiting; .is_done() asks, .wait() waits>" % (self._what, self._name)
        if self._err is not None:
            return "<%s on %s: done, failed: %s>" % (self._what, self._name, self._err)
        return "<%s on %s: done: %s>" % (self._what, self._name, self._out.head)
