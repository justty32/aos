"""把 llm-cpu 排程層掛進 aos-kernel 的薄 module。"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

import llm_cpu_home as home
import llm_cpu_tick as ticker

NAME = "llm"
OPS = ("llm",)


def _root(h):
    return Path(h.dir) / NAME


def _ensure_home(h):
    root = _root(h)
    if root.exists():
        return False
    if home.init_home(root, make_inst=False, quiet=True) != 0:
        raise RuntimeError("建不了 %s" % root)
    return True


def handle(h, cfg, st, ticket):
    root = _root(h)
    request = ticket.get("request")
    request_id = ticket.get("id")
    if request_id is not None and not isinstance(request_id, str):
        return False, "llm id 必須是字串或 null"
    try:
        default, endpoints = home.load_endpoints(root)
        _, _, error = ticker.validate_request(request, default, endpoints)
        if error:
            return False, error
        request_id = home.submit_object(root, request, request_id)
    except (OSError, ValueError, TypeError) as exc:
        return False, str(exc)
    return True, "排進去了：id=%s；結果會在 %s" % (
        request_id, root / "results" / (request_id + ".json"))


def tick(h, cfg, st):
    root = _root(h)
    notes = []
    if _ensure_home(h):
        notes.append("llm module：建了 %s/，去改 endpoints.json" % root)
    ticker.tick(root)
    state = _state(root)
    notes.append("llm: queued %d running %d" % (_queued(root), state["running"]))
    return notes


def status(h, cfg):
    root = _root(h)
    if not root.is_dir():
        return None
    state = _state(root)
    try:
        _, endpoints = home.load_endpoints(root)
    except Exception as exc:
        return "llm: %s" % str(exc).replace("\n", " ")
    counts = state.get("endpoints", {})
    slots = ", ".join("%s %s/%s" % (
        name, counts.get(name, 0), endpoint.get("max_concurrent", "-"))
        for name, endpoint in endpoints.items()
        if endpoint.get("kind") == "openai" and endpoint.get("enabled", True) is True)
    done = len(list((root / "requests" / "done").glob("*.json")))
    return "llm: queued %d  running %d  done %d  endpoints: %s" % (
        _queued(root), state["running"], done, slots)


def cli(h, cfg, argv):
    parser = argparse.ArgumentParser(prog="aos-kernel llm")
    parser.add_argument("request", metavar="REQ.json|-")
    parser.add_argument("--name")
    parser.add_argument("--wait", type=float, metavar="SECS")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    if args.wait is not None and args.wait < 0:
        print("aos-kernel llm: --wait 不能是負數", file=sys.stderr)
        return 2
    try:
        if args.request == "-":
            request = json.load(sys.stdin)
        else:
            with open(args.request, encoding="utf-8") as stream:
                request = json.load(stream)
    except (OSError, ValueError) as exc:
        print("aos-kernel llm: 請求讀不到：%s" % exc, file=sys.stderr)
        return 2
    request_id = args.name or str(time.time_ns())
    name = "%d-llm.json" % time.time_ns()
    error = _write_call(h, name, {"op": "llm", "id": request_id,
                                  "request": request})
    if error:
        print("aos-kernel llm: 單子寫不進去：%s" % error, file=sys.stderr)
        return 1
    reply = _wait_reply(h, cfg, name)
    if reply is None:
        print("kernel 沒回應（daemon 在跑嗎？aos-kernel ls K 看看）")
        return 1
    print(reply.get("msg", ""))
    if not reply.get("ok"):
        return 1
    if args.wait is None:
        return 0
    result_path = _root(h) / "results" / (request_id + ".json")
    until = time.monotonic() + args.wait
    while time.monotonic() < until:
        try:
            result = home.read_json(result_path)
        except (OSError, ValueError):
            time.sleep(0.05)
            continue
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("ok") is True else 1
    print("還沒好：結果會在 %s" % result_path)
    return 3


def _state(root):
    try:
        state = home.read_json(root / "state.json")
    except Exception:
        state = {}
    return {"running": state.get("running", 0)
            if isinstance(state.get("running", 0), int) else 0,
            "endpoints": state.get("endpoints", {})
            if isinstance(state.get("endpoints"), dict) else {}}


def _queued(root):
    return len(list((root / "requests").glob("*.json")))


def _write_call(h, name, call):
    path = Path(h.syscalls) / name
    tmp = path.with_name(path.name + ".tmp")
    try:
        home.atomic_json(tmp, call)
        os.replace(tmp, path)
        return None
    except OSError as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        return exc


def _wait_reply(h, cfg, name):
    path = Path(h.syscalls_done) / name
    until = time.monotonic() + max(3.0, 3 * cfg["interval_ms"] / 1000.0)
    while time.monotonic() < until:
        if path.exists():
            try:
                reply = home.read_json(path)
                path.unlink()
                return reply
            except (OSError, ValueError):
                return None
        time.sleep(0.05)
    return None
