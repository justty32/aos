#!/usr/bin/env python3
"""aos-step-json 與 aos-step-py 共用的狀態檔小工具。"""

from datetime import datetime, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import sys


HISTORY_LIMIT = 50
WAITING_EXIT = 101


class StepError(Exception):
    pass


def binary_default(value):
    if isinstance(value, (bytes, bytearray)):
        return {"$b64": base64.b64encode(value).decode("ascii")}
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def binary_object_hook(value):
    if len(value) == 1 and isinstance(value.get("$b64"), str):
        return base64.b64decode(value["$b64"])
    return value


def atomic_json(path, value, *, default=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    with tmp.open("w", encoding="utf-8") as out:
        json.dump(value, out, ensure_ascii=False, separators=(",", ":"), default=default)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)


def load_state(path, *, object_hook=None):
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"), object_hook=object_hook)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StepError(f"狀態檔壞了：{exc}") from exc
    pc = state.get("pc") if isinstance(state, dict) else None
    if isinstance(pc, bool) or not isinstance(pc, int) or pc < 0:
        raise StepError("狀態檔壞了：pc 必須是非負整數")
    return state


def source_info(source, n):
    return {"n": n, "sha256": hashlib.sha256(source).hexdigest()}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def wait_path(path, here):
    if not isinstance(path, (str, os.PathLike)):
        raise StepError("wait_for 路徑必須是字串或 path-like")
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path(here) / candidate
    return str(candidate.resolve())


def set_waiting(state, path, here, pc):
    state["waiting"] = {
        "for": wait_path(path, here),
        "since": now(),
        "after_pc": pc,
        "checks": 0,
    }
    state["done"] = False


def waiting_line(state):
    waiting = state.get("waiting")
    if waiting is None:
        return None
    if not isinstance(waiting, dict):
        raise StepError("狀態檔壞了：waiting 必須是物件")
    path = waiting.get("for")
    since = waiting.get("since")
    checks = waiting.get("checks")
    after_pc = waiting.get("after_pc")
    if (not isinstance(path, str) or not os.path.isabs(path)
            or not isinstance(since, str)
            or isinstance(checks, bool) or not isinstance(checks, int) or checks < 0
            or isinstance(after_pc, bool) or not isinstance(after_pc, int) or after_pc < 0):
        raise StepError("狀態檔壞了：waiting 欄位不合法")
    return f"在等 {path}（已看 {checks} 次，從 {since} 起）"


def check_waiting(state, state_path, *, default=None):
    """回 True 表示仍在等；檔案到了就記 wait history、回 False。"""
    line = waiting_line(state)
    if line is None:
        return False
    waiting = state["waiting"]
    if not Path(waiting["for"]).exists():
        waiting["checks"] += 1
        atomic_json(state_path, state, default=default)
        print(f"在等 {waiting['for']}（第 {waiting['checks']} 次）", file=sys.stderr)
        return True
    item = {
        "pc": waiting["after_pc"],
        "step": "(wait)",
        "exit": 0,
        "waited_checks": waiting["checks"],
        "at": now(),
        "ms": 0,
    }
    history = state.get("history", [])
    if not isinstance(history, list):
        history = []
    state["history"] = (history + [item])[-HISTORY_LIMIT:]
    state.pop("waiting")
    atomic_json(state_path, state, default=default)
    return False


def warn_if_changed(tool, state, current_src):
    old = state.get("src")
    if state["pc"] > 0 and isinstance(old, dict) and old.get("sha256") != current_src["sha256"]:
        print(
            "%s: PROG 改過了（上次 %s 個、現在 %s 個），pc=%s 可能已經錯位；確定要重來就 --reset"
            % (tool, old.get("n", "?"), current_src["n"], state["pc"]),
            file=sys.stderr,
        )
