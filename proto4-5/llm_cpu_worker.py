"""llm-cpu 的背景 worker；HTTP 細節全由 aos_llm 負責。"""
import json
import os
from pathlib import Path
import sys
import time

import aos_llm
import llm_cpu_home as home


def _usage(raw):
    return aos_llm._usage(raw)


def _write_usage(root, result):
    usage = result.get("usage") or _usage(None)
    row = {
        "at": home.now_text(), "id": result["id"],
        "endpoint": result.get("endpoint"), "model": result.get("model"),
        "prompt": usage.get("prompt"), "completion": usage.get("completion"),
        "total": usage.get("total"), "cached": usage.get("cached"),
        "reasoning": usage.get("reasoning"), "ms": result.get("ms"),
        "ok": result.get("ok", False),
    }
    data = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    if len(data) >= 4096:
        data = (json.dumps({**row, "model": None}, ensure_ascii=False,
                           separators=(",", ":")) + "\n").encode()
    fd = os.open(root / "usage.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o666)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def run(directory, request_id):
    root = Path(directory).absolute()
    started = time.monotonic()
    try:
        req = home.read_json(root / "requests" / "running" / (request_id + ".json"))
        endpoint_name = req["_aos"]["endpoint"]
        _, endpoints = home.load_endpoints(root)
        request = dict(req)
        request["id"] = request_id
        result = aos_llm.call(endpoints[endpoint_name], request)
    except BaseException as exc:
        result = aos_llm._error(
            request_id, None, None, None, started, "internal",
            "%s: %s" % (type(exc).__name__, exc))
    try:
        home.atomic_json(root / "results" / (request_id + ".json"), result)
        _write_usage(root, result)
    except BaseException as exc:
        print("worker 寫結果失敗：%s" % exc, file=sys.stderr)
        return 1
    return 0
