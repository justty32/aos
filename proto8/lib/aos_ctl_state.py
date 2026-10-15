"""ctl.json 與 state.json：loop、daemon 共用的那一層（NORMS N-11「設定檔讀一次 → ctl 蓋過 → state 回報」的後兩段）。純標準庫。

- ctl.json（宣告式；N-06～N-08）：`parse_ctl()` 驗內容、`want()` 算期望狀態（ctl 沒寫的欄位回到初始值，規矩只在這裡）、
  `CtlFile` 每次讀、內容變了才採用（壞檔維持上一次；原因記在 `warning`，由 loop／daemon 寫進 state 窗的 `last_warning`，
  不寫 stderr——N-43：照設計預料到的狀況不在 stderr 噴東西，10-15 使用者「都按照推薦。」）。寫的人可以帶流水號 `seq`（非負整數），
  讀的人在 state 回報 `ctl_seq`＝上次採用的那份的 seq（N-14 回音以序號為準；暫定 c）。
- state.json：`STATES`（七個狀態值）、`state_doc()`（共同骨架）、`read_state()`、`StateFile`（內容有變才寫，
  沒變也每 `BEAT_MS` 碰一次；寫不了＝記在 `failed`，loop／daemon 看到就收工、退 1——窗壞了同 N-19 窗缺）；欄位、狀態值、讀、寫都只在這裡。心跳（N-17）：骨架帶 `pid`、`started`（/proc 的啟動時間，
  clock ticks）、`boot_id`，寫的時候蓋上 `beat`（寫的那一刻，epoch 秒）。
- `require()`：窗必填（N-19：loop／daemon 的 `state`、`ctl` 缺 key 或 null＝報錯不執行）。
- `write_json()`：先寫 `.名字.tmp` 再改名。

規矩的白話說明在 aos_loop、aos_daemon 的檔頭與 lib README；這裡只放實作。
"""
import json
import os
import time

from aos_cli import expand, is_int

__all__ = ["BEAT_MS", "CtlFile", "STATES", "StateFile", "parse_ctl", "proc_started", "read_state", "require", "state_doc", "want",
           "write_json"]

BEAT_MS = 1000      # 心跳：state 內容沒變也每隔這麼久碰一次（N-17；預設值未定，暫定 1 秒）

_MODES = ("after", "fixed")


def _int(v, least=0):
    return is_int(v, least)


# ---- ctl.json ----

def _flag(v):
    """paused／stop 的值 → (val, now)。`true`＝(True, False)。不對回 None。"""
    v = expand(v)
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
                  ("interval_mode", lambda v: v in _MODES), ("seq", _int)):
        if k in doc:
            if not ok(doc[k]):
                raise ValueError("%s 的值不對：%r" % (k, doc[k]))
            out[k] = doc[k]
    return out


def want(initial, ctl):
    """期望狀態＝初始值（loop.json）蓋上 ctl.json 有寫的欄位。ctl 沒寫的欄位回到初始值——這條規矩只在這裡。"""
    return dict(initial, **ctl)


class CtlFile:
    """一個 ctl.json：`poll()` 每次讀整份、跟上一次讀到的 bytes 比，變了才驗、採用；`good`＝上一次採用的內容（parse_ctl 的結果）。

    不用 (ino, mtime, size) 判斷有沒有變：ext4 的 mtime 粒度約 4 ms、改名蓋過去的 inode 會交替重用，
    4 ms 內的等長改動會撞同一把 key 而漏掉。ctl.json 很小，直接讀內容比和 stat 差不多便宜。
    `seq`（state 的 ctl_seq 回音，N-14）＝上一次採用的內容裡的 `seq`（沒寫＝None），`good` 裡不放 seq。
    `warning`＝現在為什麼沒採用（「代號: 白話」；採用了＝None），loop／daemon 放進 state 窗的 `last_warning`。"""

    def __init__(self, path, name="loop"):
        self.path = path
        self.name = name
        self.raw = None       # 上一次讀到的 bytes；None＝還沒讀到過
        self.parsed = None    # raw 的 parse_ctl 結果；raw 是壞的＝None
        self.err = None       # raw 是壞的時的原因
        self.good = {}
        self.seq = None
        self.warning = None

    def _say(self, code, msg):
        self.warning = "%s: %s" % (code, msg)

    def poll(self):
        try:
            with open(self.path, "rb") as f:
                raw = f.read()
        except FileNotFoundError:
            if self.raw is not None:
                self._say("CtlMissing", "ctl.json %s 不見了，維持上一次的狀態" % self.path)
            return
        except OSError as e:
            self._say("CtlReadFailed", "看不了 ctl.json %s：%s" % (self.path, e))
            return
        if raw != self.raw:
            self.raw = raw
            try:
                self.parsed, self.err = parse_ctl(json.loads(raw.decode("utf-8"))), None
            except ValueError as e:
                self.parsed, self.err = None, e
        if self.parsed is None:
            self._say("CtlBad", "ctl.json %s 整份不採用（%s），維持上一次的狀態" % (self.path, self.err))
            return
        self.good = {k: v for k, v in self.parsed.items() if k != "seq"}
        self.seq = self.parsed.get("seq")
        self.warning = None


def write_json(path, doc):
    """先寫同資料夾的 `.名字.tmp` 再改名蓋過去。所在的那一層資料夾沒有就建**一層**（像 mkdir、不 -p：frame 的
    `loop/state.json`、`fsm/state.json` 由窗的寫者自己建，10-15 盤點 P3；再上層也沒有＝照樣寫不了）。失敗丟 OSError（暫存檔清掉）。"""
    d, name = os.path.split(path)
    tmp = os.path.join(d, "." + name + ".tmp")
    try:
        if d:
            try:
                os.mkdir(d)
            except FileExistsError:
                pass
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


def proc_started(pid="self"):
    """一個行程的啟動時間（/proc/<pid>/stat 第 22 欄，clock ticks）；行程不在、讀不到＝None（非 Linux）。
    pid＋啟動時間對得上＝同一個行程（N-15、N-17）。"""
    try:
        with open("/proc/%s/stat" % pid) as f:
            return int(f.read().rsplit(")", 1)[1].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _proc():
    """(這個行程的啟動時間, 開機 id)；讀不到＝None。"""
    started = proc_started()
    try:
        with open("/proc/sys/kernel/random/boot_id") as f:
            boot = f.read().strip()
    except OSError:
        boot = None
    return started, boot


def state_doc(ident, state, w, ctl, runs, last_error, **extra):
    """一份狀態物件。共同骨架：id、state（STATES 之一）、pid、started、boot_id、runs、times、interval_ms、interval_mode、
    last_error、ctl_seq；各層擴充放 extra（loop：skipped、last_code、last_warning；daemon 再加 loops＝個數）。
    last_warning＝跑起來之後預料到、不結束也不算錯的意外（「代號: 白話」；沒有＝null），取代以前寫 stderr 的警告（N-08、N-29）。"""
    assert state in STATES, state
    started, boot = _proc()
    st = {"id": ident, "state": state, "pid": os.getpid(), "started": started, "boot_id": boot, "runs": runs,
          "times": w["times"], "interval_ms": w["interval_ms"], "interval_mode": w["interval_mode"], "last_error": last_error}
    st.update(extra)
    st["ctl_seq"] = ctl.seq if ctl else None
    return st


def require(cfg, keys, err):
    """窗必填（N-19）：keys 裡哪個缺 key 或是 null 就丟 err("WindowMissing", ...)。"""
    for k in keys:
        if cfg.get(k) is None:
            raise err("WindowMissing", "%s 必填（N-19：會反覆跑的程式一定要開 %s 窗）" % (k, k))


def read_state(path):
    """讀一份 state.json，回 dict；不在、讀不了、不是物件回 None。"""
    try:
        with open(path, encoding="utf-8") as f:
            st = json.loads(f.read())
    except (OSError, ValueError):
        return None
    return st if isinstance(st, dict) else None


class StateFile:
    """state.json 的寫者：內容有變才寫（暫存再改名），沒變也每 beat_ms 碰一次（心跳，蓋上 `beat`）；
    寫不了＝`failed` 記原因（「白話」），不丟例外：用的人（loop／daemon）看到就收工、退 1。path＝None 就什麼都不做。"""

    def __init__(self, path, name, beat_ms=BEAT_MS):
        self.path, self.name, self.beat_ms = path, name, beat_ms
        self.written = self.failed = None
        self.beat = 0

    def write(self, st):
        now = time.time()
        if self.path is None or st == self.written and now - self.beat < self.beat_ms / 1000:
            return
        try:
            write_json(self.path, dict(st, beat=round(now, 3)))
            self.written, self.beat = st, now
        except OSError as e:
            self.failed = self.failed or "%s: 寫不了 state.json %s：%s" % (self.name, self.path, e)
