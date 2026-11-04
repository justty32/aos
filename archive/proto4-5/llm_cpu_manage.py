"""kernel module 的 LLM 查單與刪單；直接讀寫 K/llm，不經 syscall。"""
import datetime as dt
import os
from pathlib import Path
import signal
import sys
import time

import llm_cpu_home as home


def _mtime_text(path):
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return "?"
    return dt.datetime.fromtimestamp(stamp, dt.timezone.utc).isoformat(timespec="milliseconds")


def _request_fields(path, default):
    try:
        req = home.read_json(path)
    except Exception:
        return "?", _mtime_text(path)
    meta = req.get("_aos", {}) if isinstance(req, dict) else {}
    endpoint = meta.get("endpoint") or req.get("endpoint") or default
    submitted = meta.get("submitted") or _mtime_text(path)
    return endpoint, submitted


def show(root):
    root = Path(root).absolute()
    try:
        default, _ = home.load_endpoints(root)
    except Exception as exc:
        print("aos-kernel llm ls: %s" % str(exc).replace("\n", " "), file=sys.stderr)
        return 1
    queued = {path.stem: path for path in (root / "requests").glob("*.json")}
    running = {path.stem: path for path in (root / "requests" / "running").glob("*.json")}
    archived = {path.stem: path for path in (root / "requests" / "done").glob("*.json")}
    results = {path.stem: path for path in (root / "results").glob("*.json")}
    done = {name: archived.get(name) or running.get(name) or queued.get(name) or path
            for name, path in results.items()}
    done.update({name: path for name, path in archived.items() if name not in done})
    groups = (
        ("queued", [queued[name] for name in sorted(queued) if name not in results]),
        ("running", [running[name] for name in sorted(running) if name not in results]),
        ("done", [done[name] for name in sorted(done)]),
    )
    for title, paths in groups:
        print("%s:" % title)
        for path in paths:
            endpoint, submitted = _request_fields(path, default)
            line = "  %s  endpoint=%s  submitted=%s" % (path.stem, endpoint, submitted)
            if title == "done":
                result_path = (root / "results" / path.name).absolute()
                try:
                    result = home.read_json(result_path)
                    outcome = ("ok=true" if result.get("ok") is True else
                               "error.kind=%s" % (result.get("error") or {}).get("kind", "?"))
                except Exception:
                    outcome = "ok=?"
                line += "  result=%s  %s" % (result_path, outcome)
            print(line)
    return 0


def _alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        stat = Path("/proc/%d/stat" % pid).read_text(encoding="utf-8")
        if stat.rsplit(")", 1)[1].strip().startswith("Z"):
            return False
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _kill_worker(path):
    try:
        pid = home.read_json(path).get("_aos", {}).get("pid")
    except Exception as exc:
        return "running 記錄讀不到 worker pid：%s" % exc
    if not isinstance(pid, int) or pid <= 0:
        return "running 記錄沒有可砍的 worker pid"
    for sig, seconds in ((signal.SIGTERM, 1.0), (signal.SIGKILL, 1.0)):
        if not _alive(pid):
            return None
        try:
            os.killpg(pid, sig)
        except ProcessLookupError:
            return None
        except OSError as exc:
            return "砍不掉 worker pid=%d：%s" % (pid, exc)
        until = time.monotonic() + seconds
        while _alive(pid) and time.monotonic() < until:
            time.sleep(0.02)
    return None if not _alive(pid) else "砍不掉 worker pid=%d" % pid


def remove(root, request_id):
    root = Path(root).absolute()
    if not home.validate_id(request_id):
        print("aos-kernel llm rm: NAME 只能用英數、點、底線、減號", file=sys.stderr)
        return 1
    queued = root / "requests" / (request_id + ".json")
    running = root / "requests" / "running" / (request_id + ".json")
    done = root / "requests" / "done" / (request_id + ".json")
    result = root / "results" / (request_id + ".json")
    targets = (queued, running, done, result)
    if not any(path.exists() for path in targets):
        print("aos-kernel llm rm: 沒有這個名字：%s" % request_id, file=sys.stderr)
        return 1
    if running.exists():
        error = _kill_worker(running)
        if error:
            print("aos-kernel llm rm: %s" % error, file=sys.stderr)
            return 1
    try:
        for path in targets:
            path.unlink(missing_ok=True)
    except OSError as exc:
        print("aos-kernel llm rm: 刪不乾淨：%s" % exc, file=sys.stderr)
        return 1
    print("刪掉了：%s" % request_id)
    return 0
