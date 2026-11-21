"""hook_clock - agent 的 on_clock hook：讀時鐘、比上次記的 cycle，到了才跑那個 hook（clock_tick）；loop 起來時清掉狀態（clock_restart）。

圖紙：proto8/thinking/2026-11/11/clock-hook（使用者 11-11「hook就可以添加一個類型……去看指定的clock proc……每隔十個cycle就幹嘛，
或是透過cycle換算，若超過十秒就幹嘛」；判斷在行程內做，到了才起 handler）。11-20 hook 介面第 2 刀後半從 hooks.py 搬出來（只因檔案大小）；
格的鍵（CLOCK_KEYS）與驗法（check_clock）留在 hooks.py。呼叫的人：agent_hooks 的遙控器（clock_tick）、aos-hook --agent 的
after_start（clock_restart）。純標準庫，不印東西、不 sys.exit。

對外：
    CLOCK_STATE = "on_clock.json"：$AOS_STACK/hooks/<名>/on_clock.json，上次觸發（或基準）的 cycle
    clock_tick(def_folder, stack, warn=None) -> [跑了的 hook 名]；沒有這種 hook＝只讀清單、不起行程；hook 停下＝HookFailed（同 hooks.fire）
    clock_restart(stack) -> None：清掉各 hook 小格的 on_clock.json（下一次檢查＝第一次、立刻跑）；刪不掉＝OSError
"""
import json
import os
import subprocess

from aos.agentlib import hooks

CLOCK_STATE = "on_clock.json"                   # $AOS_STACK/hooks/<名>/on_clock.json：上次觸發（或基準）的 cycle


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
    """on_clock 的檢查：每個 on_clock hook 讀它的時鐘、比 hooks/<名>/on_clock.json 記的 cycle，到了才跑那個 hook。
    到了＝cycle − 上次 ≥ 條件格數（every_cycles；every_ms＝ceil(every_ms ÷ AOS_CLOCK_INTERVAL)）；跑了就把上次記成這次的 cycle（不補跑：
    錯過的只寫進 missed）。第一次（沒有狀態檔、時鐘換了、cycle 倒退〔根重起、換台〕）＝立刻跑一次並記基準，事件 first: true、
    last_cycle: null、missed: 0（11-11 使用者選「起來就先觸發一次」：「一起來立刻跑一次，之後照間隔。每次睡醒、重起也都會先跑一次。」）；
    每次 loop 起來（aos-hook fire --agent … after_start）先 clock_restart 清掉狀態檔，所以睡醒、重起、auto_restart 後的第一次檢查也算第一次。
    找不到時鐘＝不跑、warning 只在原因變了時說一次（記在狀態檔）。回跑了的 hook 名。hook 停下＝HookFailed（同 fire）。
    寫不了狀態檔＝warning、這次不跑（免得每拍都跑）。"""
    entries = hooks.load(def_folder, stack)
    names = sorted(n for n, e in entries.items() if e["event"] == hooks.CLOCK_EVENT)
    ran = []
    for name in names:
        entry = entries[name]
        spath, st = _state(stack, name)
        source = entry.get("clock")
        named = isinstance(source, str) and "/" not in source and not source.startswith(".")
        cached = named and st.get("clock_source") == source and isinstance(st.get("clock"), str)
        clock, why = (st["clock"], None) if cached else _clock_file(entry, stack)
        cycle = _read_cycle(clock) if clock else None
        if cached and cycle is None:             # 記住的鐘讀不到：只重查一次，不退回直接讀 daemon 表
            clock, why = _clock_file(entry, stack)
            cycle = _read_cycle(clock) if clock else None
        if clock and cycle is None:
            why = "clock file %s does not hold a cycle number" % clock
        remembered = {"clock_source": source} if named else {}
        try:
            if why:
                if st.get("warned") != why:
                    if warn:
                        warn("hook %s (event %s) is not checked: %s" % (name, hooks.CLOCK_EVENT, why))
                    _put_state(spath, dict(st, warned=why))
                continue
            last = st.get("cycle")
            first = st.get("clock") != clock or not isinstance(last, int) or isinstance(last, bool) or cycle < last
            iv = _interval_ms()
            every = entry["every_cycles"] if "every_cycles" in entry else max(1, -(-entry["every_ms"] // iv))
            if not first and cycle - last < every:
                if st.get("warned") or (named and st.get("clock_source") != source):
                    _put_state(spath, dict(remembered, clock=clock, cycle=last))
                continue
            _put_state(spath, dict(remembered, clock=clock, cycle=cycle))             # 先記再跑：handler 失敗也不每拍重跑
        except OSError as e:
            if warn:
                warn("hook %s (event %s): cannot write %s: %s" % (name, hooks.CLOCK_EVENT, spath, e))
            continue
        data = {"clock": clock, "cycle": cycle, "interval_ms": iv, "first": first,   # first＝剛起來／沒基準／倒退的那一次
                "last_cycle": None if first else last, "missed": 0 if first else (cycle - last) // every - 1}
        if "config" in entry:                    # 11-15 compact-1115：格裡的 config 原樣帶給 handler（例 context_wrap 的門檻）
            data["config"] = entry["config"]
        hooks.fire(hooks.CLOCK_EVENT, data, def_folder, stack, warn=warn, only=[name], entries=entries)
        ran.append(name)
    return ran


def clock_restart(stack):
    """loop 起來的那一刻（aos-hook fire --agent … after_start）：刪掉各 hook 小格的 on_clock.json，下一次 clock_tick 就當第一次、立刻跑
    （使用者 11-11「每次睡醒、重起也都會先跑一次」）。刪不掉＝OSError 往上丟；沒有小格＝什麼都不做。"""
    cells = os.path.join(os.path.abspath(stack), hooks.CELLS)
    try:
        names = os.listdir(cells)
    except (FileNotFoundError, NotADirectoryError):
        return
    for name in names:
        try:
            os.remove(os.path.join(cells, name, CLOCK_STATE))
        except (FileNotFoundError, NotADirectoryError):
            pass
