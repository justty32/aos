"""hook_clock - the agent's on_clock hooks: read the clock, compare with the cycle recorded last time, run the hook only when it is due (clock_tick); the first check after a loop start runs at once.

Design: proto8/thinking/2026-11/11/clock-hook (the user 11-11 "hook就可以添加一個類型……去看指定的clock proc……每隔十個cycle就幹嘛，
或是透過cycle換算，若超過十秒就幹嘛"; decided inside the process, a handler starts only when due). Moved out of hooks.py
11-20 (file size). The entry keys (CLOCK_KEYS) and their checks stay in hooks.py. Caller: the agent_hooks remote (clock_tick).
11-21 (line top-1121-hooknew, the user's fourth layer: aos-hook fire does nothing agent-specific): "a loop start" is no
longer told by after_start clearing the state; each hook's state records which loop run it saw (pid, started_at_ticks and
boot_id of STACK/state.json, the loop's own window), and a different one = the first check of a new start.
Standard library only; prints nothing, never exits.

API:
    CLOCK_STATE = "on_clock.json": $AOS_STACK/hookeds/NAME/on_clock.json, the cycle of the last run (or the base)
    clock_tick(def_folder, stack, warn=None) -> [names run]; no such hook = only the list is read, no process;
                    a failing hook = one warning (on_clock cannot be blocked; hooks.fire)
"""
import json
import os
import subprocess

from aos.agentlib import hooks

CLOCK_STATE = "on_clock.json"                   # $AOS_STACK/hookeds/NAME/on_clock.json: the cycle of the last run (or the base)
LOOP_KEYS = ("boot_id", "pid", "started_at_ticks")   # which run of the loop: from STACK/state.json (aos-loop's state window)


def _clock_file(entry, stack):
    """clock 鍵 → (時鐘檔絕對路徑, None) 或 (None, 為什麼找不到)。沒寫＝$AOS_CLOCK；路徑（有 / 或 . 開頭）：檔＝它、資料夾＝裡面的 clock
    （daemon 的 stack 就是這種佈局）；相對＝從 agent 的 stack 算。名字（沒有 /）＝經 aos-agent ctl ls --json 找那一列的 stack 裡的 clock。"""
    v = entry.get("clock")
    if v is None:
        path = os.environ.get("AOS_CLOCK", "")
        if not path:
            return None, "AOS_CLOCK is not set (no clock: not under a daemon tree with one)"
    elif "/" in v or v.startswith("."):
        path = v if os.path.isabs(v) else os.path.join(stack, v)
    else:
        try:
            result = subprocess.run(["aos-agent", "ctl", "ls", "--json"], stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=5)
            if result.returncode:
                return None, "cannot find clock %s: %s" % (v, result.stderr.strip() or "aos-agent ctl ls failed")
            rows = json.loads(result.stdout)
            row = next((r for r in rows if isinstance(r, dict) and r.get("name") == v), None)
        except (OSError, ValueError, TypeError, subprocess.TimeoutExpired) as e:
            return None, "cannot find clock %s with aos-agent ctl ls --json: %s" % (v, e)
        st = row.get("stack") if isinstance(row, dict) else None
        if not isinstance(st, str) or not os.path.isabs(st):
            return None, "proc %s is not on the daemon table with an absolute stack" % v
        path = os.path.join(st, "clock")
    path = os.path.abspath(path)
    if os.path.isdir(path):
        path = os.path.join(path, "clock")
    if not os.path.isfile(path):
        return None, "no clock file %s" % path
    return path, None


def _read_cycle(path):
    """時鐘檔的數字（同 tool_io.clock_now 的讀法：去前後空白、空＝0、十進位）；壞＝None。"""
    try:
        with open(path, "rb") as f:
            text = f.read().strip()
    except OSError:
        return None
    if not text:
        return 0
    return int(text) if text.isdigit() and int(text) < 9223372036854775807 else None


def _interval_ms():
    text = os.environ.get("AOS_CLOCK_INTERVAL", "")
    return int(text) if text.isdigit() and int(text) > 0 else 1000


def _loop_run(stack):
    """[boot_id, pid, started_at_ticks] of the loop now running in stack (its state.json); none readable = None."""
    try:
        with open(os.path.join(stack, "state.json"), encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    return [doc.get(k) for k in LOOP_KEYS] if isinstance(doc, dict) else None


def _state(stack, name):
    path = os.path.join(os.path.abspath(stack), hooks.CELLS, name, CLOCK_STATE)
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        return path, doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return path, {}


def _put_state(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = os.path.join(os.path.dirname(path), ".%s.%d.tmp" % (CLOCK_STATE, os.getpid()))   # N-05：先寫暫存再改名
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def clock_tick(def_folder, stack, warn=None):
    """The on_clock check: each on_clock hook reads its clock and compares with hookeds/NAME/on_clock.json; due = run it.
    Due = cycle - last >= its cycles (every_cycles; every_ms = ceil(every_ms / AOS_CLOCK_INTERVAL)); after a run the last cycle is
    this one (no catching up: what was missed only goes into missed). The first time (no state file, another clock, the cycle
    went back [root restarted, other machine], or another run of the loop than the state saw: a start, a wake, a restart) =
    run at once and record the base: first true, last_cycle null, missed 0 (the user 11-11 "一起來立刻跑一次，之後照間隔。
    每次睡醒、重起也都會先跑一次。"). No clock = not run, a warning only when the reason changed (kept in the state file).
    Cannot write the state file = a warning and no run this time (so it does not run every tick). Returns the names run."""
    entries = hooks.load(def_folder, stack)
    names = sorted(n for n, e in entries.items() if e["event"] == hooks.CLOCK_EVENT)
    run_id = _loop_run(stack) if names else None
    ran = []
    for name in names:
        entry = entries[name]
        spath, st = _state(stack, name)
        source = entry.get("clock")
        named = isinstance(source, str) and "/" not in source and not source.startswith(".")
        cached = named and st.get("clock_source") == source and isinstance(st.get("clock"), str)
        clock, why = (st["clock"], None) if cached else _clock_file(entry, stack)
        cycle = _read_cycle(clock) if clock else None
        if cached and cycle is None:             # the remembered clock cannot be read: look it up once more
            clock, why = _clock_file(entry, stack)
            cycle = _read_cycle(clock) if clock else None
        if clock and cycle is None:
            why = "clock file %s does not hold a cycle number" % clock
        remembered = dict({"clock_source": source} if named else {}, loop=run_id)
        try:
            if why:
                if st.get("warned") != why:
                    if warn:
                        warn("hook %s (event %s) is not checked: %s" % (name, hooks.CLOCK_EVENT, why))
                    _put_state(spath, dict(st, warned=why))
                continue
            last = st.get("cycle")
            first = (st.get("clock") != clock or not isinstance(last, int) or isinstance(last, bool) or cycle < last
                     or st.get("loop") != run_id)
            iv = _interval_ms()
            every = entry["every_cycles"] if "every_cycles" in entry else max(1, -(-entry["every_ms"] // iv))
            if not first and cycle - last < every:
                if st.get("warned") or (named and st.get("clock_source") != source):
                    _put_state(spath, dict(remembered, clock=clock, cycle=last))
                continue
            _put_state(spath, dict(remembered, clock=clock, cycle=cycle))             # record first, then run: a failing handler does not run every tick
        except OSError as e:
            if warn:
                warn("hook %s (event %s): cannot write %s: %s" % (name, hooks.CLOCK_EVENT, spath, e))
            continue
        data = {"clock": clock, "cycle": cycle, "interval_ms": iv, "first": first,
                "last_cycle": None if first else last, "missed": 0 if first else (cycle - last) // every - 1}
        if "config" in entry:                    # 11-15 compact-1115: the entry's config goes to the handler as it is
            data["config"] = entry["config"]
        hooks.fire(hooks.CLOCK_EVENT, data, entries, stack, warn=warn, only=[name])
        ran.append(name)
    return ran
