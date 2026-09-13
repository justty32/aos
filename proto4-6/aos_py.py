#!/usr/bin/env python3
"""逐步 Python 程式可直接使用的 aos 小模組。"""

import base64 as _base64
import json as _json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
DEFAULT_EXEC = HERE.parent / "proto4-3" / "aos-exec"
DEFAULT_LLM = HERE.parent / "proto4-5" / "aos-llm"
DEFAULT_KERNEL = HERE.parent / "proto4-3" / "aos-kernel"


class Wait:
    def __init__(self, path):
        self.path = os.fspath(path)


def wait_for(path):
    return Wait(path)


def b64(b):
    return {"$b64": _base64.b64encode(b).decode("ascii")}


def unb64(value):
    if isinstance(value, dict):
        value = value["$b64"]
    return _base64.b64decode(value)


def _exec_path():
    return os.environ.get("AOS_EXEC", str(DEFAULT_EXEC))


def _llm_path():
    return os.environ.get("AOS_LLM", str(DEFAULT_LLM))


def _kernel_path():
    return os.environ.get("AOS_KERNEL", str(DEFAULT_KERNEL))


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def call(target, dir_target=None, timeout_ms=None, stdin=None, capture=False,
         read=None, read_err=None, json=False, args=None):
    """把 target 交給 aos-exec，並視選項接回 stdout、檔案或 JSON。"""
    target = os.fspath(target)
    if args is not None:
        if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
            raise ValueError("aos.call: args 必須是字串 list")
        if target.endswith(".json") or Path(target).is_dir():
            raise ValueError("aos.call: args 只能用在普通檔案目標；inst 目標的參數寫在 inst.json 的 argv 裡")
    argv = [_exec_path(), target]
    if dir_target is not None:
        argv += ["--dir-target", os.fspath(dir_target)]
    if timeout_ms is not None:
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms < 0:
            raise ValueError("aos.call: timeout_ms 必須是非負整數")
        argv += ["--timeout-ms", str(timeout_ms)]
    stderr_target = os.environ.get("AOS_STEP_STDERR")
    if stderr_target:
        argv += ["--stderr", stderr_target]
    if args is not None:
        argv += ["--", *args]

    completed = subprocess.run(
        argv, input=stdin, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE, check=False,
    )
    err = completed.stderr
    if stderr_target == "-" and err:
        print(err, file=sys.stderr, end="")
    if completed.returncode == 125:
        kind = "aos"
    elif completed.returncode == 2 and err.startswith("aos-exec:"):
        kind = "usage"
    else:
        kind = "child"

    out = completed.stdout if capture else None
    if read is not None:
        out = _read(read)
    if read_err is not None:
        err = _read(read_err)
    decoded = None
    if json and out not in (None, ""):
        try:
            decoded = _json.loads(out)
        except (TypeError, _json.JSONDecodeError):
            pass
    return {"code": completed.returncode, "kind": kind, "out": out,
            "err": err, "value": decoded}


def call_dir(dir, **opts):
    if not Path(dir).is_dir():
        raise ValueError(f"aos.call_dir: 不是資料夾：{dir}")
    return call(dir, **opts)


def call_json(path, **opts):
    if Path(path).suffix != ".json":
        raise ValueError(f"aos.call_json: 不是 .json 路徑：{path}")
    return call(path, **opts)


def ok(result):
    return result.get("kind") == "child" and result.get("code") == 0


def value(result):
    return result.get("value") if result.get("value") is not None else result.get("out")


def llm(endpoint, req, out, timeout_ms=None):
    if not isinstance(req, dict):
        raise ValueError("aos.llm: req 必須是 dict")
    endpoint_path = Path(endpoint).absolute()
    out_path = Path(out).absolute()
    req_path = Path(str(out_path) + ".req.json")
    req_path.write_text(_json.dumps(req, ensure_ascii=False) + "\n", encoding="utf-8")
    result = call(
        _llm_path(),
        args=["call", os.fspath(endpoint_path), os.fspath(req_path), os.fspath(out_path)],
        timeout_ms=timeout_ms, read=out_path, json=True,
    )
    if result["err"] and os.environ.get("AOS_STEP_STDERR") != "-":
        print(result["err"], file=sys.stderr, end="")
    return (result["value"] if isinstance(result["value"], dict)
            else {"ok": False, "error": {"kind": "no_result"}})


def llm_text(result):
    return result.get("text") if isinstance(result, dict) and result.get("ok") is True else None


def llm_submit(K, req: dict, name: str) -> str:
    if not isinstance(req, dict):
        raise ValueError("aos.llm_submit: req 必須是 dict")
    if not isinstance(name, str) or not name:
        raise ValueError("aos.llm_submit: name 必須是非空字串")
    req_path = Path.cwd() / (name + ".req.json")
    req_path.write_text(_json.dumps(req, ensure_ascii=False) + "\n", encoding="utf-8")
    kernel = Path(K).resolve()
    result = call(
        _kernel_path(), args=["llm", os.fspath(kernel), os.fspath(req_path), "--name", name],
        capture=True,
    )
    if not ok(result):
        detail = result["err"].strip() or result["out"].strip()
        raise RuntimeError(f"aos.llm_submit: aos-kernel 回 {result['code']}: {detail}")
    return str(kernel / "llm" / "results" / (name + ".json"))
