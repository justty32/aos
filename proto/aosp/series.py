"""接力棒 .aos/series.json。欄位名照 WRITER-BRIEF 4.4。"""
from . import fsutil

RUNNING = "running"
DONE = "done"
FAILED = "failed"
STOPPED = "stopped"


def empty(batch_id=None):
    return {
        "format_version": 1,
        "batch_id": batch_id or fsutil.new_id(),
        "tick": 0,
        "series": [],
    }


def load(land):
    return fsutil.read_json(land.series)


def save(land, baton):
    """多寫者一律：寫 tmp -> fsync -> rename -> fsync 目錄。"""
    fsutil.write_json(land.series, baton)


def load_or_start(land, template="main", cursor=None):
    """沒有接力棒就從 main 開一條串。"""
    baton = load(land)
    if baton is not None:
        return baton, False
    baton = empty()
    baton["series"].append(new_series(template, cursor))
    save(land, baton)
    return baton, True


def new_series(template, cursor, parent=None, regs=None):
    return {
        "id": fsutil.new_id(),
        "template": template,
        "cursor": cursor,
        "status": RUNNING,
        "regs": dict(regs or {}),
        "parent": parent,
        "resources": None,
        "fail_reason": None,
        "ext": {},
    }


def running(baton):
    return [s for s in baton["series"] if s.get("status") == RUNNING]


def idle(baton):
    """閒著＝沒有 running 的串。"""
    return not running(baton)


def find(baton, series_id):
    for s in baton["series"]:
        if s["id"] == series_id:
            return s
    return None
