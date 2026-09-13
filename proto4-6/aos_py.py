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


def b64(b):
    return _base64.b64encode(b).decode("ascii")


def unb64(s):
    return _base64.b64decode(s)


def _exec_path():
    return os.environ.get("AOS_EXEC", str(DEFAULT_EXEC))


def _llm_path():
    return os.environ.get("AOS_LLM", str(DEFAULT_LLM))


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def call(target, dir_target=None, timeout_ms=None, stdin=None, capture=False,
         read=None, read_err=None, json=False):
    """把 target 交給 aos-exec，並視選項接回 stdout、檔案或 JSON。"""
    argv = [_exec_path(), os.fspath(target)]
    if dir_target is not None:
        argv += ["--dir-target", os.fspath(dir_target)]
    if timeout_ms is not None:
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms < 0:
            raise ValueError("aos.call: timeout_ms 必須是非負整數")
        argv += ["--timeout-ms", str(timeout_ms)]
    stderr_target = os.environ.get("AOS_STEP_STDERR")
    if stderr_target:
        argv += ["--stderr", stderr_target]

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
    out_path = Path(out)
    req_path = Path(str(out_path) + ".req.json")
    req_path.write_text(_json.dumps(req, ensure_ascii=False) + "\n", encoding="utf-8")
    argv = [_llm_path(), "call", os.fspath(endpoint), os.fspath(req_path), os.fspath(out_path)]
    if timeout_ms is not None:
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms < 0:
            raise ValueError("aos.llm: timeout_ms 必須是非負整數")
        argv += ["--timeout-ms", str(timeout_ms)]
    subprocess.run(argv, check=False)
    try:
        result = _json.loads(out_path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {"ok": False, "error": {"kind": "no_result"}}
    except (OSError, UnicodeDecodeError, _json.JSONDecodeError):
        return {"ok": False, "error": {"kind": "no_result"}}


def llm_text(result):
    return result.get("text") if isinstance(result, dict) and result.get("ok") is True else None
