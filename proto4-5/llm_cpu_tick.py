"""llm-cpu 的一格：收尾、驗件、排序、分發、寫狀態。"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import llm_cpu_home as home

GRACE_MS = 5000


def _error_result(root, request_id, endpoint, kind, message, status=None,
                  retryable=False):
    return {
        "ok": False, "id": request_id, "endpoint": endpoint,
        "model": None, "text": None, "finish_reason": None,
        "usage": {"prompt": None, "completion": None, "total": None,
                  "cached": None, "reasoning": None},
        "ms": 0, "raw": None,
        "error": {"kind": kind, "msg": message, "status": status,
                  "retryable": retryable},
    }


def _write_error(root, request_id, endpoint, kind, message, status=None,
                 retryable=False):
    home.atomic_json(root / "results" / (request_id + ".json"),
                     _error_result(root, request_id, endpoint, kind, message,
                                   status, retryable))


def _move_done(root, path):
    destination = root / "requests" / "done" / path.name
    if destination.exists():
        destination.unlink()
    os.replace(path, destination)


def _pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _timeout_ms(req, endpoints):
    value = req.get("timeout_ms")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    endpoint = endpoints.get(req.get("_aos", {}).get("endpoint"), {})
    value = endpoint.get("timeout_ms")
    return value if isinstance(value, int) and value > 0 else 0


def _finish_running(root, endpoints, events):
    for path in sorted((root / "requests" / "running").glob("*.json")):
        request_id = path.stem
        result_path = root / "results" / path.name
        if result_path.exists():
            _move_done(root, path)
            events.append("done:%s" % request_id)
            continue
        try:
            req = home.read_json(path)
            meta = req.get("_aos", {}) if isinstance(req, dict) else {}
            endpoint = meta.get("endpoint")
            pid = meta.get("pid")
            started = float(meta.get("started"))
        except Exception as exc:
            _write_error(root, request_id, None, "worker_died",
                         "running 記錄壞了：%s" % exc)
            _move_done(root, path)
            events.append("worker_died:%s" % request_id)
            continue
        if not _pid_alive(pid):
            _write_error(root, request_id, endpoint, "worker_died",
                         "worker 已結束，但沒有留下結果")
            _move_done(root, path)
            events.append("worker_died:%s" % request_id)
            continue
        limit = _timeout_ms(req, endpoints)
        if limit and (time.time() - started) * 1000 > limit + GRACE_MS:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            _write_error(root, request_id, endpoint, "timeout",
                         "worker 超過 timeout_ms 加 5000ms")
            _move_done(root, path)
            events.append("timeout:%s" % request_id)


def _validate(path, default, endpoints):
    try:
        req = home.read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return None, None, "不是合法 JSON：%s" % exc
    if not isinstance(req, dict):
        return req, None, "請求必須是 JSON 物件"
    messages = req.get("messages")
    if not isinstance(messages, list) or not messages:
        return req, None, "messages 必須是非空陣列"
    if "model" in req:
        return req, None, "不准指定 model；model 固定在 endpoint 設定，本機一次只能載一顆"
    if "priority" in req and (not isinstance(req["priority"], int)
                              or isinstance(req["priority"], bool)):
        return req, None, "priority 必須是整數"
    if "timeout_ms" in req and (not isinstance(req["timeout_ms"], int)
                                or isinstance(req["timeout_ms"], bool)
                                or req["timeout_ms"] <= 0):
        return req, None, "timeout_ms 必須是正整數"
    if "params" in req and not isinstance(req["params"], dict):
        return req, None, "params 必須是 JSON 物件"
    endpoint_name = req.get("endpoint", default)
    if not isinstance(endpoint_name, str) or endpoint_name not in endpoints:
        return req, endpoint_name, "endpoint 名字不認得：%s" % endpoint_name
    endpoint = endpoints[endpoint_name]
    if endpoint.get("kind") != "openai":
        return req, endpoint_name, "這版還不支援 process 型 endpoint"
    if endpoint.get("enabled", True) is not True:
        return req, endpoint_name, "endpoint 沒有啟用：%s" % endpoint_name
    required = ("base_url", "model", "max_concurrent", "timeout_ms")
    if any(key not in endpoint for key in required):
        return req, endpoint_name, "endpoint 設定缺少必要欄位"
    if not isinstance(endpoint["base_url"], str) or not endpoint["base_url"]:
        return req, endpoint_name, "endpoint base_url 必須是非空字串"
    if not isinstance(endpoint["model"], str) or not endpoint["model"]:
        return req, endpoint_name, "endpoint model 必須是非空字串"
    if (not isinstance(endpoint["max_concurrent"], int)
            or isinstance(endpoint["max_concurrent"], bool)
            or endpoint["max_concurrent"] < 1):
        return req, endpoint_name, "endpoint max_concurrent 必須是正整數"
    if (not isinstance(endpoint["timeout_ms"], int)
            or isinstance(endpoint["timeout_ms"], bool)
            or endpoint["timeout_ms"] <= 0):
        return req, endpoint_name, "endpoint timeout_ms 必須是正整數"
    if ("api_key_env" in endpoint
            and (not isinstance(endpoint["api_key_env"], str)
                 or not endpoint["api_key_env"])):
        return req, endpoint_name, "endpoint api_key_env 必須是非空字串"
    return req, endpoint_name, None


def _reject_bad(root, default, endpoints, events):
    valid = []
    for path in sorted((root / "requests").glob("*.json")):
        req, endpoint, error = _validate(path, default, endpoints)
        if error:
            _write_error(root, path.stem, endpoint, "bad_request", error)
            _move_done(root, path)
            events.append("bad_request:%s" % path.stem)
        else:
            valid.append((path, req, endpoint))
    return valid


def _counts(root):
    counts = {}
    for path in (root / "requests" / "running").glob("*.json"):
        try:
            endpoint = home.read_json(path).get("_aos", {}).get("endpoint")
            counts[endpoint] = counts.get(endpoint, 0) + 1
        except Exception:
            pass
    return counts


def _dispatch(root, valid, endpoints, events):
    counts = _counts(root)
    valid.sort(key=lambda row: (-row[1].get("priority", 0),
                                row[0].stat().st_mtime_ns, row[0].name))
    for path, req, endpoint_name in valid:
        endpoint = endpoints[endpoint_name]
        if counts.get(endpoint_name, 0) >= endpoint["max_concurrent"]:
            continue
        request_id = path.stem
        running = root / "requests" / "running" / path.name
        req["_aos"] = {"endpoint": endpoint_name, "pid": None,
                       "started": time.time()}
        home.atomic_json(path, req)
        os.replace(path, running)
        log = open(root / "log" / (request_id + ".log"), "ab")
        try:
            proc = subprocess.Popen(
                [sys.executable, str(Path(__file__).with_name("llm_cpu.py")),
                 "worker", str(root), request_id],
                start_new_session=True, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=log)
        except Exception as exc:
            log.close()
            _write_error(root, request_id, endpoint_name, "spawn",
                         "worker 起不來：%s" % exc)
            _move_done(root, running)
            events.append("spawn_error:%s" % request_id)
            continue
        finally:
            if not log.closed:
                log.close()
        req["_aos"]["pid"] = proc.pid
        home.atomic_json(running, req)
        counts[endpoint_name] = counts.get(endpoint_name, 0) + 1
        events.append("dispatch:%s@%s" % (request_id, endpoint_name))
    return counts


def tick(directory):
    root = Path(directory).absolute()
    events = []
    try:
        default, endpoints = home.load_endpoints(root)
    except Exception as exc:
        home.emergency_tick_log(root, exc)
        return
    _finish_running(root, endpoints, events)
    valid = _reject_bad(root, default, endpoints, events)
    counts = _dispatch(root, valid, endpoints, events)
    try:
        old = home.read_json(root / "state.json")
        ticks = int(old.get("ticks", 0)) + 1
    except Exception:
        ticks = 1
    running = sum(counts.values())
    home.atomic_json(root / "state.json", {
        "ticks": ticks, "running": running,
        "endpoints": {name: counts.get(name, 0) for name in endpoints},
    })
    with open(root / "llm-cpu.log", "a", encoding="utf-8") as stream:
        stream.write("%s tick=%d queued=%d running=%d %s\n" % (
            home.now_text(), ticks,
            len(list((root / "requests").glob("*.json"))), running,
            " ".join(events) if events else "idle"))
