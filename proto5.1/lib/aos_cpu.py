"""共用 CPU 檔案佇列：讀驗身分、交件、認領、收屍、原子發布。

執行 payload 由呼叫者提供；execute 期間不持鎖。規範：../spec/cpu-queue.md。
"""
from contextlib import contextmanager
import fcntl
import json
import os
import tempfile
import time

import aos_agent_info
from aos_agent_info import AgentError
from aos_directives import Context, DirectiveError, Document, resolve_located

__all__ = ["load", "queue_lock", "submit", "tick"]
GRACE_SECONDS = 30


def load(dir, cpu_type, env=None):
    """讀驗 cpu info.json，回 dir／metainfo；不建立資料夾、不讀請求。"""
    dir = os.path.abspath(dir)
    path = os.path.join(dir, "info.json")
    if not os.path.exists(path):
        raise AgentError("NotAnAgent", "%s 沒有 info.json，不是 %s 資料夾" % (dir, cpu_type))
    obj = _read_json(path)
    try:
        top = resolve_located(obj, Context(Document(path, obj), base_dir=dir, env=env), [])
        obj = aos_agent_info._no_options(top.value, top.position)
        if not isinstance(obj, dict):
            raise AgentError("NotAnObject", "%s 必須是 JSON 物件" % path)
        loc = aos_agent_info._field(obj, "_metainfo", top)
        if loc is None:
            raise AgentError("NotAnAgent", "%s 缺少 _metainfo，不是 %s" % (path, cpu_type))
        mi = loc.value
        if not isinstance(mi, dict):
            raise AgentError("MetainfoInvalid", "%s 的 _metainfo 必須是物件" % path)
        kind = aos_agent_info._inner(mi["_type"], loc, "_type").value if "_type" in mi else None
        if kind != cpu_type:
            raise AgentError("NotAnAgent", "%s 的 _metainfo._type 必須是 %s" % (path, cpu_type))
        if "_version" not in mi:
            raise AgentError("MetainfoInvalid", "%s 的 _metainfo 缺少 _version" % path)
        version = aos_agent_info._inner(mi["_version"], loc, "_version").value
        if type(version) is not int or version != 1:
            raise AgentError("UnsupportedVersion", "%s 的 _metainfo._version 只認整數 1" % path)
    except DirectiveError as e:
        raise AgentError(e.code, e.msg)
    return {"dir": dir, "metainfo": {"_type": cpu_type, "_version": 1}}


@contextmanager
def queue_lock(dir):
    """送件／認領／完成共用的短鎖；先建立三個佇列資料夾，離開就解鎖。"""
    try:
        for part in ("requests", "running", "done"):
            os.makedirs(os.path.join(dir, part), exist_ok=True)
        with open(os.path.join(dir, ".queue.lock"), "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError as e:
        raise AgentError("ReadFailed", "%s 的佇列檔案操作失敗：%s" % (dir, e))


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, UnicodeDecodeError) as e:
        raise AgentError("JsonSyntax", "%s 不是合法 JSON：%s" % (path, e))
    except OSError as e:
        raise AgentError("ReadFailed", "讀不到 %s：%s" % (path, e))


def _request(path, validate=None):
    req = _read_json(path)
    _validate_request(req, path)
    if validate is not None:
        validate(req, path)
    return req


def _validate_request(req, path):
    if not isinstance(req, dict):
        raise AgentError("NotAnObject", "%s 必須是 JSON 物件" % path)
    result = req.get("result")
    if not isinstance(result, str) or not os.path.isabs(result) or "\0" in result:
        raise AgentError("FieldTypeMismatch", "%s 的 result 必須是絕對路徑字串" % path)


def submit(dir, name, request):
    """原子交件；name 是含 .json 的單一檔名，三處同名一律拒收。"""
    if (not isinstance(name, str) or not name.endswith(".json") or
            os.path.basename(name) != name or "\0" in name):
        raise AgentError("FieldTypeMismatch", "請求名稱必須是含 .json 的單一檔名")
    _validate_request(request, name)
    with queue_lock(dir):
        if any(os.path.lexists(os.path.join(dir, part, name)) for part in ("requests", "running", "done")):
            raise FileExistsError("cpu 三處已有同名請求：%s" % name)
        path = os.path.join(dir, "requests", name)
        _write_result(path, request)
    return path


def _names(dir):
    return sorted(n for n in os.listdir(dir) if n.endswith(".json"))


def _write_result(path, result):
    """同目錄唯一 .tmp 再 replace；失敗不移走 running，留給下一次收屍。"""
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=os.path.dirname(path),
                                         prefix=os.path.basename(path) + ".", suffix=".tmp", delete=False) as f:
            tmp = f.name
            json.dump(result, f, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)


def _reap(dir, validate, timeout_ms):
    """鎖內收掉所有過期 running；已有結果表示可能崩在發布後，保留它。"""
    count = 0
    for name in _names(os.path.join(dir, "running")):
        path = os.path.join(dir, "running", name)
        done = os.path.join(dir, "done", name)
        if os.path.lexists(done):
            continue
        req = _request(path, validate)
        timeout = timeout_ms(req) if timeout_ms else aos_agent_info.DEFAULT_TIMEOUT_MS
        if time.time() - os.stat(path).st_mtime <= timeout / 1000 + GRACE_SECONDS:
            continue
        if not os.path.lexists(req["result"]):
            _write_result(req["result"], {"ok": False, "error": "cpu 執行逾時或上次中止（%d ms + 30 秒）" % timeout})
        os.rename(path, done)
        count += 1
    return count


def tick(dir, execute, *, validate=None, timeout_ms=None):
    """收屍再認領一份：有處理（含只收屍）回 0，沒事回 101；讀驗錯丟 AgentError。"""
    dir = os.path.abspath(dir)
    claimed = None
    with queue_lock(dir):
        reaped = _reap(dir, validate, timeout_ms)
        for name in _names(os.path.join(dir, "requests")):
            src = os.path.join(dir, "requests", name)
            running = os.path.join(dir, "running", name)
            if any(os.path.lexists(os.path.join(dir, part, name)) for part in ("running", "done")):
                continue
            req = _request(src, validate)
            try:
                # rename 不會更新 mtime：排隊很久也要從認領這刻算執行逾時。
                os.utime(src, None)
                os.rename(src, running)
            except FileNotFoundError:
                continue
            stat = os.stat(running)
            claimed = (running, os.path.join(dir, "done", name), req, (stat.st_dev, stat.st_ino))
            break
    if claimed is None:
        return 0 if reaped else 101
    running, done, req, identity = claimed
    result = execute(req)
    with queue_lock(dir):
        try:
            stat = os.stat(running)
        except FileNotFoundError:
            return 0                # 已被另一顆 cpu 收屍，遲到的執行回覆不准覆蓋結果
        if (stat.st_dev, stat.st_ino) != identity or os.path.lexists(done):
            return 0
        _write_result(req["result"], result)
        os.rename(running, done)
    return 0


