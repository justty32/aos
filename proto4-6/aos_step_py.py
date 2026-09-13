#!/usr/bin/env python3
"""一次執行普通 Python 檔裡的下一個頂層公開函式。"""

import argparse
import importlib.util
import inspect
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback

import aos_py
from step_common import (HISTORY_LIMIT, StepError, atomic_json, binary_default,
                         binary_object_hook, check_waiting, load_state, now,
                         set_waiting, source_info, WAITING_EXIT, waiting_line,
                         warn_if_changed)


DONE_EXIT = 100
TOOL = "aos-step-py"


def fail(message):
    print(f"{TOOL}: {message}", file=sys.stderr)
    return 2


def paths_for(prog):
    state = prog.with_suffix(".state.json") if prog.suffix == ".py" else Path(str(prog) + ".state.json")
    error = Path(str(prog) + ".error")
    return state, error


def empty_state(steps):
    return {"state": {}, "pc": 0, "n": len(steps), "done": False,
            "steps": [fn.__name__ for fn in steps]}


def read_source(prog):
    try:
        return prog.read_bytes()
    except OSError as exc:
        raise StepError(f"讀不到 PROG：{exc}") from exc


def load_program(prog, pc, source):
    spec = importlib.util.spec_from_file_location("__aos_step__", prog)
    if spec is None or spec.loader is None:
        raise StepError("載不起 PROG：無法建立 Python module")
    module = importlib.util.module_from_spec(spec)
    module.here = str(prog.parent)
    module.pc = pc
    module.aos = aos_py
    try:
        # 直接編譯這次讀到的 bytes，避免同一秒改成同大小內容時誤吃舊 pyc。
        exec(compile(source, str(prog), "exec"), module.__dict__)
    except BaseException as exc:
        first = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        raise StepError(f"載不起 PROG：{first}") from exc
    steps = [value for value in vars(module).values()
             if inspect.isfunction(value)
             and value.__module__ == module.__name__
             and not value.__name__.startswith("_")]
    steps.sort(key=lambda fn: fn.__code__.co_firstlineno)
    return steps, source_info(source, len(steps))


def warn_if_step_changed(state, names):
    pc = state["pc"]
    old = state.get("steps")
    if (pc > 0 and isinstance(old, list) and pc < len(old) and pc < len(names)
            and old[pc] != names[pc]):
        print(f"{TOOL}: 第 {pc} 格函式名對不上（上次 {old[pc]}、現在 {names[pc]}），仍照目前程式執行",
              file=sys.stderr)


def write_error(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def exception_first_line(exc):
    text = str(exc).splitlines()
    return text[0] if text else type(exc).__name__


def json_type(exc):
    match = re.search(r"Object of type ([^ ]+) is not JSON serializable", str(exc))
    return match.group(1) if match else type(exc).__name__


def exception_line(exc, prog, fallback):
    wanted = prog.resolve()
    matches = [frame.lineno for frame in traceback.extract_tb(exc.__traceback__)
               if Path(frame.filename).resolve() == wanted]
    return matches[-1] if matches else fallback


def report_step_error(prog, error_path, pc, fn, detail, trace, line=None):
    write_error(error_path, trace)
    line = fn.__code__.co_firstlineno if line is None else line
    print(f"{TOOL}: 第 {pc} 格 {fn.__name__}（0 起算，PROG 第 {line} 行）失敗：{detail}"
          f"（全文：{prog.name}.error 或 --status）", file=sys.stderr)
    return 1


def step(prog, stderr_override):
    state_path, error_path = paths_for(prog)
    try:
        saved = load_state(state_path, object_hook=binary_object_hook)
        if saved is not None and check_waiting(saved, state_path, default=binary_default):
            return WAITING_EXIT
        pc = saved["pc"] if saved else 0
        source = read_source(prog)
        steps, src = load_program(prog, pc, source)
    except StepError as exc:
        return fail(str(exc))

    state = saved or empty_state(steps)
    names = [fn.__name__ for fn in steps]
    warn_if_changed(TOOL, state, src)
    warn_if_step_changed(state, names)
    if pc >= len(steps):
        state.update({"n": len(steps), "done": True, "steps": names, "src": src})
        atomic_json(state_path, state, default=binary_default)
        return DONE_EXIT

    user_state = state.get("state")
    if not isinstance(user_state, dict):
        return fail("狀態檔壞了：state 必須是物件")
    fn = steps[pc]
    started = time.monotonic()
    old_stderr = os.environ.get("AOS_STEP_STDERR")
    if stderr_override is not None:
        os.environ["AOS_STEP_STDERR"] = stderr_override
    try:
        returned = fn(user_state)
    except BaseException as exc:
        line = exception_line(exc, prog, fn.__code__.co_firstlineno)
        return report_step_error(prog, error_path, pc, fn, exception_first_line(exc),
                                 traceback.format_exc(), line)
    finally:
        if stderr_override is not None:
            if old_stderr is None:
                os.environ.pop("AOS_STEP_STDERR", None)
            else:
                os.environ["AOS_STEP_STDERR"] = old_stderr

    try:
        json.dumps(user_state, ensure_ascii=False, default=binary_default)
    except (TypeError, ValueError) as exc:
        detail = f"state 裡有 JSON 放不進的東西：{json_type(exc)}"
        return report_step_error(prog, error_path, pc, fn, detail, traceback.format_exc())

    elapsed = int((time.monotonic() - started) * 1000)
    item = {"pc": pc, "step": fn.__name__, "exit": 0, "at": now(), "ms": elapsed}
    history = state.get("history", [])
    if not isinstance(history, list):
        history = []
    result = {"state": user_state, "pc": pc + 1, "n": len(steps),
              "done": pc + 1 >= len(steps), "steps": names, "src": src,
              "last": item, "history": (history + [item])[-HISTORY_LIMIT:]}
    if isinstance(returned, aos_py.Wait):
        try:
            set_waiting(result, returned.path, prog.parent, pc)
        except StepError as exc:
            return report_step_error(prog, error_path, pc, fn, str(exc), traceback.format_exc())
    atomic_json(state_path, result, default=binary_default)
    error_path.unlink(missing_ok=True)
    print(f"第 {pc} 格 ok（{fn.__name__}）", file=sys.stderr)
    return 0


def status(prog):
    state_path, error_path = paths_for(prog)
    try:
        saved = load_state(state_path, object_hook=binary_object_hook)
        pc = saved["pc"] if saved else 0
        source = read_source(prog)
        steps, _ = load_program(prog, pc, source)
    except StepError as exc:
        return fail(str(exc))
    current = saved or empty_state(steps)
    print(json.dumps(current, ensure_ascii=False, separators=(",", ":"),
                     default=binary_default))
    try:
        line = waiting_line(current)
    except StepError as exc:
        return fail(str(exc))
    if line:
        print(line, file=sys.stderr)
    if error_path.exists():
        try:
            print(error_path.read_text(encoding="utf-8"), file=sys.stderr, end="")
        except OSError as exc:
            print(f"{TOOL}: 讀不到錯誤全文：{exc}", file=sys.stderr)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog=TOOL, description="一次執行 Python 檔裡的下一個頂層函式")
    parser.add_argument("prog", metavar="PROG.py")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--status", action="store_true", help="印出目前狀態 JSON")
    modes.add_argument("--reset", action="store_true", help="刪除狀態檔，從第 0 格重來")
    parser.add_argument("--stderr", metavar="PATH", help="給 aos.call 底下的 aos-exec；- 代表目前 stderr")
    args = parser.parse_args(argv)
    prog = Path(args.prog).resolve()
    if not prog.is_file():
        return fail(f"找不到程式：{args.prog}")
    state_path, error_path = paths_for(prog)
    if args.reset:
        try:
            state_path.unlink(missing_ok=True)
            error_path.unlink(missing_ok=True)
        except OSError as exc:
            return fail(f"刪不掉狀態：{exc}")
        return 0
    if args.status:
        return status(prog)
    return step(prog, args.stderr)


if __name__ == "__main__":
    sys.exit(main())
