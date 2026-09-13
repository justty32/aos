#!/usr/bin/env python3
"""一次執行 JSON 陣列中的下一份 inst，進度存在程式旁邊。"""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "proto4-3"))
import aos_exec  # noqa: E402


DONE_EXIT = 100
HISTORY_LIMIT = 50
ALLOWED_KEYS = {"argv", "cwd", "stdin", "stdout", "stderr", "exit", "envs", "note"}


class StepError(Exception):
    pass


def fail(message):
    print(f"aos-step-json: {message}", file=sys.stderr)
    return 2


def paths_for(prog):
    state = prog.with_suffix(".state.json") if prog.suffix == ".json" else Path(str(prog) + ".state.json")
    current = prog.parent / ".aos-step-json" / "current.json"
    return state, current


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    with tmp.open("w", encoding="utf-8") as out:
        json.dump(value, out, ensure_ascii=False, separators=(",", ":"))
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)


def load_program(prog):
    try:
        source = prog.read_bytes()
    except OSError as exc:
        raise StepError(f"讀不到 PROG：{exc}") from exc
    try:
        value = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StepError(f"PROG 不是合法 JSON：{exc}") from exc
    if not isinstance(value, list):
        raise StepError("PROG 必須是一個 JSON 陣列")
    src = {"n": len(value), "sha256": hashlib.sha256(source).hexdigest()}
    return value, src


def load_state(path):
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StepError(f"狀態檔壞了：{exc}") from exc
    pc = state.get("pc") if isinstance(state, dict) else None
    if isinstance(pc, bool) or not isinstance(pc, int) or pc < 0:
        raise StepError("狀態檔壞了：pc 必須是非負整數")
    return state


def empty_state(n):
    return {"pc": 0, "n": n, "done": False}


def warn_if_changed(state, current_src):
    old = state.get("src")
    if state["pc"] > 0 and isinstance(old, dict) and old.get("sha256") != current_src["sha256"]:
        print(
            "aos-step-json: PROG 改過了（上次 %s 個、現在 %s 個），pc=%s 可能已經錯位；確定要重來就 --reset"
            % (old.get("n", "?"), current_src["n"], state["pc"]),
            file=sys.stderr,
        )


def prepare_inst(element, pc, base):
    if not isinstance(element, dict):
        raise StepError(f"第 {pc} 個元素（0 起算）不是物件")
    if "argv" not in element:
        raise StepError(f"第 {pc} 個元素（0 起算）沒有 argv")
    unknown = set(element) - ALLOWED_KEYS
    if unknown:
        raise StepError(f"第 {pc} 個元素（0 起算）有未知欄位：{sorted(unknown)[0]}")
    if "note" in element and not isinstance(element["note"], str):
        raise StepError(f"第 {pc} 個元素（0 起算）的 note 必須是字串")
    inst = copy.deepcopy(element)
    inst.pop("note", None)
    cwd = inst.get("cwd", str(base))
    if not isinstance(cwd, str):
        raise StepError(f"第 {pc} 個元素（0 起算）的 cwd 必須是字串")
    if not os.path.isabs(cwd):
        cwd = os.path.join(base, cwd)
    inst["cwd"] = os.path.abspath(cwd)
    return inst


def record(state, src, pc, code, kind, elapsed_ms, success):
    item = {
        "pc": pc,
        "exit": code,
        "kind": kind,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ms": elapsed_ms,
    }
    history = state.get("history", [])
    if not isinstance(history, list):
        history = []
    state.update({
        "pc": pc + 1 if success else pc,
        "n": src["n"],
        "done": success and pc + 1 >= src["n"],
        "last": item,
        "history": (history + [item])[-HISTORY_LIMIT:],
    })
    if success:
        state["src"] = src


def step(prog, stderr_override):
    state_path, current_path = paths_for(prog)
    try:
        program, src = load_program(prog)
        state = load_state(state_path) or empty_state(len(program))
    except StepError as exc:
        return fail(str(exc))

    warn_if_changed(state, src)
    pc = state["pc"]
    if pc >= len(program):
        state.update({"n": len(program), "done": True, "src": src})
        atomic_json(state_path, state)
        return DONE_EXIT

    try:
        inst = prepare_inst(program[pc], pc, prog.parent)
    except StepError as exc:
        return fail(str(exc))
    atomic_json(current_path, inst)

    started = time.monotonic()
    code, kind = aos_exec.run_target(str(current_path), stderr=stderr_override)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    success = kind == aos_exec.CHILD and code == 0
    record(state, src, pc, code, kind, elapsed_ms, success)
    atomic_json(state_path, state)

    if success:
        return 0
    if kind == aos_exec.CHILD:
        print(f"aos-step-json: 第 {pc} 個元素（0 起算）失敗：exit={code}", file=sys.stderr)
        return code
    if kind == aos_exec.AOS:
        print(
            f"aos-step-json: 第 {pc} 個元素 aos-exec 自己失敗（125），加 --stderr - 看原因",
            file=sys.stderr,
        )
        return 125
    return 2


def main(argv=None):
    parser = argparse.ArgumentParser(prog="aos-step-json", description="一次執行 JSON 陣列中的下一份 inst")
    parser.add_argument("prog", metavar="PROG.json")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--status", action="store_true", help="印出目前狀態 JSON")
    modes.add_argument("--reset", action="store_true", help="刪除狀態檔，從第 0 格重來")
    parser.add_argument("--stderr", metavar="PATH", help="原樣轉給 aos-exec；- 代表印到目前 stderr")
    args = parser.parse_args(argv)

    prog = Path(args.prog).resolve()
    if not prog.is_file():
        return fail(f"找不到程式：{args.prog}")
    state_path, _ = paths_for(prog)
    if args.reset:
        try:
            state_path.unlink(missing_ok=True)
        except OSError as exc:
            return fail(f"刪不掉狀態檔：{exc}")
        return 0
    if args.status:
        try:
            state = load_state(state_path)
            if state is None:
                program, _ = load_program(prog)
                state = empty_state(len(program))
        except StepError as exc:
            return fail(str(exc))
        print(json.dumps(state, ensure_ascii=False, separators=(",", ":")))
        return 0
    return step(prog, args.stderr)


if __name__ == "__main__":
    sys.exit(main())
