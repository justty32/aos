"""ctl.json 與 state.json：loop、daemon 共用的那一層（NORMS N-11「設定檔讀一次 → ctl 蓋過 → state 回報」的後兩段）。純標準庫。

- ctl.json（宣告式；N-06～N-08）：`parse_ctl()` 驗內容、`want()` 算期望狀態（ctl 沒寫的欄位回到初始值，規矩只在這裡）、
  `CtlFile` 看有沒有變、變了才讀（壞檔維持上一次、印一次）。
- state.json：`STATES`（七個狀態值）、`state_doc()`（共同骨架）、`read_state()`、`StateFile`（內容有變才寫）；
  欄位、狀態值、讀、寫都只在這裡。
- `write_json()`：先寫 `.名字.tmp` 再改名。

規矩的白話說明在 aos_loop、aos_daemon 的檔頭與 lib README；這裡只放實作。
"""
import json
import os
import sys

__all__ = ["CtlFile", "STATES", "StateFile", "parse_ctl", "read_state", "state_doc", "want", "write_json"]

_MODES = ("after", "fixed")


def _int(v, least=0):
    return isinstance(v, int) and not isinstance(v, bool) and v >= least


# ---- ctl.json ----

def _flag(v):
    """paused／stop 的值 → (val, now)。`true`＝(True, False)。不對回 None。"""
    if isinstance(v, bool):
        return (v, False)
    if isinstance(v, dict) and isinstance(v.get("val"), bool) and isinstance(v.get("now", False), bool):
        return (v["val"], v.get("now", False))
    return None


def parse_ctl(doc):
    """驗 ctl.json 的內容，回只含有寫的欄位的 dict（paused／stop 變成 (val, now)）；不對丟 ValueError。"""
    if not isinstance(doc, dict):
        raise ValueError("ctl 要是物件")
    out = {}
    for k in ("paused", "stop"):
        if k in doc:
            out[k] = _flag(doc[k])
            if out[k] is None:
                raise ValueError("%s 要是 true／false 或 {\"val\": 布林, \"now\": 布林}，不是 %r" % (k, doc[k]))
    for k, ok in (("times", lambda v: v is None or _int(v)), ("interval_ms", _int),
                  ("interval_mode", lambda v: v in _MODES)):
        if k in doc:
            if not ok(doc[k]):
                raise ValueError("%s 的值不對：%r" % (k, doc[k]))
            out[k] = doc[k]
    return out


def want(initial, ctl):
    """期望狀態＝初始值（loop.json）蓋上 ctl.json 有寫的欄位。ctl 沒寫的欄位回到初始值——這條規矩只在這裡。"""
    return dict(initial, **ctl)


class CtlFile:
    """一個 ctl.json：`poll()` 看有沒有變、變了就讀、驗、採用；`good`＝上一次採用的內容（parse_ctl 的結果）。"""

    def __init__(self, path, name="loop"):
        self.path = path
        self.name = name
        self.key = None
        self.good = {}
        self.mtime = None
        self.said = None

    def _say(self, msg):
        if self.said != msg:
            self.said = msg
            print("%s: %s" % (self.name, msg), file=sys.stderr)

    def poll(self):
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            if self.key is not None:
                self._say("CtlMissing: ctl.json %s 不見了，維持上一次的狀態" % self.path)
            return
        except OSError as e:
            self._say("CtlReadFailed: 看不了 ctl.json %s：%s" % (self.path, e))
            return
        key = (st.st_ino, st.st_mtime_ns, st.st_size)
        if key == self.key:
            return
        self.key = key
        try:
            with open(self.path, encoding="utf-8") as f:
                doc = json.loads(f.read())
            self.good = parse_ctl(doc)
        except (OSError, ValueError) as e:
            self._say("CtlBad: ctl.json %s 整份不採用（%s），維持上一次的狀態" % (self.path, e))
            return
        self.mtime = st.st_mtime
        self.said = None


def write_json(path, doc):
    """先寫同資料夾的 `.名字.tmp` 再改名蓋過去。失敗丟 OSError（暫存檔清掉）。"""
    d, name = os.path.split(path)
    tmp = os.path.join(d, "." + name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


# ---- state.json（loop 和 daemon 共用：欄位、讀、寫都只在這裡）----

STATES = ("starting", "waiting", "running", "paused", "done", "stopping", "stopped")   # loop、daemon 共用，各取子集


def state_doc(ident, state, w, ctl, runs, last_error, **extra):
    """一份狀態物件。共同骨架：id、state（STATES 之一）、pid、runs、times、interval_ms、interval_mode、ctl_mtime、
    last_error；各層擴充放 extra（loop：skipped、last_code；daemon：skipped、loops＝個數）。"""
    assert state in STATES, state
    st = {"id": ident, "state": state, "pid": os.getpid(), "runs": runs, "times": w["times"],
          "interval_ms": w["interval_ms"], "interval_mode": w["interval_mode"], "last_error": last_error}
    st.update(extra)
    st["ctl_mtime"] = ctl.mtime if ctl else None
    return st


def read_state(path):
    """讀一份 state.json，回 dict；不在、讀不了、不是物件回 None。"""
    try:
        with open(path, encoding="utf-8") as f:
            st = json.loads(f.read())
    except (OSError, ValueError):
        return None
    return st if isinstance(st, dict) else None


class StateFile:
    """state.json 的寫者：內容有變才寫（暫存再改名），寫不了印一次、不算錯。path＝None 就什麼都不做。"""

    def __init__(self, path, name):
        self.path, self.name = path, name
        self.written = self.said = None

    def write(self, st):
        if self.path is None or st == self.written:
            return
        try:
            write_json(self.path, st)
            self.written = st
        except OSError as e:
            msg = "%s: StateWriteFailed: 寫不了 state.json %s：%s" % (self.name, self.path, e)
            if self.said != msg:
                self.said = msg
                print(msg, file=sys.stderr)
