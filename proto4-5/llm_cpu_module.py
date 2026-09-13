"""把 llm-cpu 排程層掛進 aos-kernel 的薄 module。"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

import llm_cpu_home as home
import llm_cpu_manage as manage
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


def _duplicate(root, request_id, request):
    kind, old_hash = home.existing_request_sha256(root, request_id)
    if kind is None:
        return None, False
    return kind, old_hash == home.request_sha256(request)


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
        kind, same = ((None, False) if request_id is None else
                      _duplicate(root, request_id, request))
        if kind:
            if same:
                return True, "同一張請求已存在於 %s：%s" % (kind, request_id)
            return False, ("id 已經存在於 %s：%s；要重問就 `aos-kernel llm rm K %s` 或換名字"
                           % (kind, request_id, request_id))
        request_id = home.submit_object(root, request, request_id)
    except (OSError, ValueError, TypeError) as exc:
        return False, str(exc)
    return True, "排進去了：id=%s；結果會在 %s" % (
        request_id, root / "results" / (request_id + ".json"))


def tick(h, cfg, st):
    root = _root(h)
    notes = []
    if _ensure_home(h):
        note = ("llm module：建了 %s/；請把 endpoints.json 裡 local 的 model "
                "換成 aos-llm models 看到的 id" % root)
        print(note)
        notes.append(note)
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
    warning = ("  ⚠ local 的 model 還沒換"
               if any(endpoint.get("model") == "loaded-model-id"
                      for endpoint in endpoints.values()) else "")
    return "llm: queued %d  running %d  done %d  endpoints: %s%s" % (
        _queued(root), state["running"], done, slots, warning)


def cli(h, cfg, argv):
    if argv and argv[0] == "ls":
        if len(argv) != 1:
            print("用法：aos-kernel llm ls K", file=sys.stderr)
            return 2
        return manage.show(_root(h))
    if argv and argv[0] == "rm":
        if len(argv) != 2:
            print("用法：aos-kernel llm rm K NAME", file=sys.stderr)
            return 2
        return manage.remove(_root(h), argv[1])
    parser = argparse.ArgumentParser(
        prog="aos-kernel llm",
        usage=("aos-kernel llm [K] REQ.json|- [--name NAME] [--wait SECS] [--json]\n"
               "       aos-kernel llm ls K\n"
               "       aos-kernel llm rm K NAME"))
    parser.add_argument("request", metavar="REQ.json|-")
    parser.add_argument("--name")
    parser.add_argument("--wait", type=float, metavar="SECS")
    parser.add_argument("--json", action="store_true",
                        help="等待完成後印完整結果 JSON")
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
    result_path = _root(h) / "results" / (request_id + ".json")
    kind, same = _duplicate(_root(h), request_id, request)
    if kind:
        if not same:
            print(("aos-kernel llm: id 已經存在於 %s：%s；要重問就 "
                   "`aos-kernel llm rm K %s` 或換名字") %
                  (kind, request_id, request_id), file=sys.stderr)
            return 1
        if args.wait is None:
            print("同一張請求已存在；結果檔：%s" % result_path)
            return 0
        return _wait_result(result_path, args.wait, args.json)
    name = "%d-llm.json" % time.time_ns()
    error = _write_call(h, name, {"op": "llm", "id": request_id,
                                  "request": request})
    if error:
        print("aos-kernel llm: 單子寫不進去：%s" % error, file=sys.stderr)
        return 1
    reply = _wait_reply(h, cfg, name)
    if reply is None:
        pending = Path(h.syscalls) / name
        try:
            pending.unlink()
            print("kernel 沒回應；請求沒送出去，已撤單")
        except FileNotFoundError:
            _print_still_running(result_path)
        except OSError as exc:
            print("kernel 沒回應；撤單失敗，請求可能仍會執行：%s" % exc)
        return 1
    if not reply.get("ok"):
        print(reply.get("msg", ""))
        return 1
    if args.wait is None:
        print("結果檔：%s；下一回合處理" % result_path)
        return 0
    return _wait_result(result_path, args.wait, args.json)


def _wait_result(result_path, seconds, print_json):
    until = time.monotonic() + seconds
    while True:
        try:
            result = home.read_json(result_path)
        except (OSError, ValueError):
            if time.monotonic() >= until:
                break
            time.sleep(0.05)
            continue
        if print_json:
            print(json.dumps(result, ensure_ascii=False))
        elif result.get("ok") is True:
            print(result.get("text") or "")
        else:
            error = result.get("error") or {}
            print("LLM 失敗：%s: %s" %
                  (error.get("kind", "unknown"), error.get("msg", "")))
        print("結果檔：%s" % result_path)
        return 0 if result.get("ok") is True else 1
    _print_still_running(result_path)
    return 1


def _print_still_running(result_path):
    print("已送出，kernel 還沒做完；結果會出現在 %s；不要的話完成後刪掉這個檔" %
          result_path)


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
