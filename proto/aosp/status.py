"""狀態檔與三態。WRITER-BRIEF 4.5。

狀態檔路徑固定＝<結果落點>.status.json
"""
import os

from . import fsutil

# 三態
PENDING = "pending"   # 結果檔不在＝還沒好
OK = "ok"             # 結果檔在＝好了
FAILED = "failed"     # 狀態檔說壞了＝壞了

# reason 常用代碼（WRITER-BRIEF 4.5）
SPAWN_ERROR = "spawn_error"
TIMEOUT = "timeout"
KILLED = "killed"
AWAIT_TIMEOUT = "await_timeout"
BUDGET = "budget"
NO_DAEMON = "no_daemon"
REJECTED = "rejected"
BACKEND_ERROR = "backend_error"
QUEUE_TIMEOUT = "queue_timeout"


def status_path(result_path):
    return result_path + ".status.json"


def write_failed(result_path, reason, message, ext=None):
    fsutil.write_json(status_path(result_path), {
        "format_version": 1,
        "state": "failed",
        "reason": reason,
        "message": message,
        "at": fsutil.now_iso(),
        "ext": ext or {},
    })


def read_status(result_path):
    return fsutil.read_json(status_path(result_path))


def triple(result_path):
    """回傳 (態, 狀態檔內容或 None)。狀態檔優先於結果檔。"""
    st = read_status(result_path)
    if st is not None:
        return FAILED, st
    if os.path.exists(result_path):
        return OK, None
    return PENDING, None


def clear(result_path):
    """重跑前把上一輪的結果與狀態檔清掉。"""
    for p in (result_path, status_path(result_path)):
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass
