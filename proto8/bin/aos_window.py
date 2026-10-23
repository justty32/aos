"""aos_window：ctl／state 兩扇窗（NORMS N-06～N-09、N-14、N-17、N-32、N-33）。aos-loop、aos-daemon 共用。純標準庫。

    ctl = aos_window.Ctl(路徑, extra)    extra＝{key: 驗證函數}，這支程式多認的 key（daemon 的 loops）
    ctl.read()                           回最後一份好的 ctl（dict；一份都沒讀到過＝{}）；ctl.warning＝最近一次的問題（好的就是 None）
    aos_window.write(路徑, dict)         先寫 . 開頭的暫存檔再改名（N-05）
    aos_window.heartbeat()               心跳欄位 {"pid","start_ticks","boot_id","at"}（N-32；at＝ISO 8601 UTC 到毫秒）
    aos_window.start_ticks(pid)          /proc/<pid>/stat 第 22 欄（還活著才有；非 Linux 或已死＝None）

ctl 認 paused、stop（布林）、max、interval_ms、seq（非負整數），加上 extra；其他 key 忽略（N-07 照 N-04）。
讀到壞的（不是 JSON 物件、型別不對、讀不了）整份不採用、維持上一份好的，原因放 warning（N-08，寫進 state 的 last_warning）。
檔不在＝還沒人寫，維持上一份好的、不算問題（本實作自定）。"""
import datetime
import json
import os

_BOOL = ("paused", "stop")
_NAT = ("max", "interval_ms", "seq")


def _nat(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


class Ctl:
    def __init__(self, path, extra=None):
        self.path, self.extra = path, extra or {}
        self.good, self.warning = {}, None

    def read(self):
        if self.path is None:
            return self.good
        try:
            with open(self.path, encoding="utf-8") as f:
                doc = json.load(f)
        except FileNotFoundError:
            return self.good
        except (OSError, ValueError) as e:
            self.warning = "ctl 讀不了或不是 JSON：%s" % e
            return self.good
        bad = _check(doc, self.extra)
        if bad:
            self.warning = "ctl 不採用：%s" % bad
        else:
            self.good, self.warning = doc, None
        return self.good


def _check(doc, extra):
    if not isinstance(doc, dict):
        return "要是 JSON 物件"
    for k in _BOOL:
        if k in doc and not isinstance(doc[k], bool):
            return "%s 要是 true／false" % k
    for k in _NAT:
        if k in doc and not _nat(doc[k]):
            return "%s 要是非負整數" % k
    for k, f in extra.items():
        if k in doc:
            bad = f(doc[k])
            if bad:
                return bad
    return None


def write(path, doc):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def start_ticks(pid):
    try:
        with open("/proc/%d/stat" % pid, encoding="utf-8") as f:
            return int(f.read().rpartition(")")[2].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _boot_id():
    try:
        with open("/proc/sys/kernel/random/boot_id", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


_ME = {}


def now():
    """ISO 8601 UTC 到毫秒（例 2026-10-23T01:58:45.123+00:00；10-23 命名統合：時間只留這一種寫法）。"""
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def heartbeat():
    if not _ME:
        _ME.update(pid=os.getpid(), start_ticks=start_ticks(os.getpid()), boot_id=_boot_id())
    return dict(_ME, at=now())
