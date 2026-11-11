"""hooks - agent 的 hook 共用模組：讀 hooks 清單（定義那份疊 stack 那份、驗形狀）、挑出符合事件的 hook、用 aos-exec 跑、解回話。

圖紙：proto8/thinking/2026-11/10/self-family/hook/01-圖紙.md（使用者 11-10 晚「self_hook……事件發生時，執行指定aos函數」）。
agent-fsm 的四格、aos-eca-turn、aos-mcp、aos-agent hook 都用這份，不各自拼。純標準庫，lib 不 import py；
不印東西、不 sys.exit：錯丟 HooksBad（清單壞）／HookFailed（on_error stop 的 hook 自己失敗），由呼叫方說自己那一行。

對外（另兩條線要用，改了要一起改）：
    EVENTS[事件] = {"condition": 事件 JSON 裡拿來比 condition 的欄位名或 None（不收 condition）,
                    "intercept": 能改的鍵（tuple）, "block": 能不能攔（結束碼 10）}
    DEFAULTS = {"intercept": True, "async": False, "on_error": "stop", "timeout_ms": 60000}
                    （intercept 預設開：11-10 深夜使用者「3.幫我改成預設是開」；不能改的事件、async 的 hook＝自然不看回話、不報錯）
    格的鍵（11-10 深夜改名，使用者「hook這塊，主要走A, 但filter改condition。」）：event、handler、condition、intercept、async、on_error、timeout_ms
    declared(def_folder) -> 宣告的相對路徑字串 | None
    load(def_folder, stack) -> {名字: 格}；格＝原格的鍵＋DEFAULTS 補齊＋"from"（來自哪份檔的絕對路徑）＋"base"（解 exec 相對路徑的資料夾）
    nulled(def_folder, stack) -> [stack 那份設成 null 的名字]（排好）
    validate_entry(entry) -> None；不對丟 HooksBad（原因不含名字，呼叫方自己加）
    has(event, def_folder, stack) -> 有沒有 on==event 的 hook（不看 match）
    fire(event, data, def_folder, stack, warn=None) -> {"data": 改過的 data（新 dict）, "changed": [改過的鍵],
                    "blocked": bool, "hook": 攔下的 hook 名或 None, "text": 攔下那個 hook 的 stdout（字串）或 ""}
    tools_added(stack, tools, has_hook) -> [(name, path)]：這次比上次多出來的工具（tools＝[(name, path)]）
    clock_tick(def_folder, stack, warn=None) -> [跑了的 hook 名]：on_clock 的檢查（11-11 clock-hook）；沒有這種 hook＝只讀清單、不起行程
    clock_restart(stack) -> None：loop 起來時清掉 on_clock 的狀態檔（下一次檢查＝第一次、立刻跑）

11-11（thinking/2026-11/11/clock-hook）：事件多 after_start、after_stop（aos-loop 的 on_start／on_stop 叫 lib/agent/hook_fire 發，
使用者「hook 要加的事件：起來與停下」）與 on_clock（使用者「hook就可以添加一個類型……去看指定的clock proc……每隔十個cycle就幹嘛，
或是透過cycle換算，若超過十秒就幹嘛」；判斷在行程內做，到了才起 handler）。on_clock 才收的鍵＝CLOCK_KEYS。
"""
import copy
import json
import os
import signal
import subprocess
import time

if __package__:
    from .agent_files import declared_files
else:
    from agent_files import declared_files

EVENTS = {
    "before_queue": {"condition": None, "intercept": ("content",), "block": True},
    "after_queue": {"condition": None, "intercept": (), "block": False},
    "before_tool": {"condition": "name", "intercept": ("arguments",), "block": True},
    "after_tool": {"condition": "name", "intercept": ("content",), "block": False},
    "brain_failed": {"condition": "name", "intercept": (), "block": False},
    "tool_added": {"condition": "name", "intercept": (), "block": False},
    "after_start": {"condition": None, "intercept": (), "block": False},   # 11-11：loop 起來（on_start）
    "after_stop": {"condition": None, "intercept": (), "block": False},    # 11-11：loop 要退（on_stop；多 code、signal）
    "on_clock": {"condition": None, "intercept": (), "block": False},     # 11-11：時鐘走到了（clock_tick）
}
CLOCK_EVENT = "on_clock"                        # 事件名集中在這裡（11-11 先代定 clock_due，使用者改裁 on_clock）
CLOCK_KEYS = ("clock", "every_cycles", "every_ms")   # 只有 on_clock 收
CLOCK_STATE = "on_clock.json"                   # $AOS_STACK/hooks/<名>/on_clock.json：上次觸發（或基準）的 cycle
DEFAULTS = {"intercept": True, "async": False, "on_error": "stop", "timeout_ms": 60000}
BLOCK = 10                                       # 攔下（N-43：10＝「不要」，不是錯）
CELLS = "hooks"                                  # 小格：$AOS_STACK/hooks/<名>/
SEEN = "hook_tools_seen.json"                    # tool_added 上次看到的工具名單


class HooksBad(ValueError):
    """hooks 清單（或 interfaces.json 的宣告）讀不了、形狀不對。"""


class HookFailed(RuntimeError):
    """on_error: stop 的 hook 自己失敗（結束碼不是 0／10、逾時、起不來、回話不合）。"""


def declared(def_folder):
    """interfaces.json 的 aos-agent 宣告的 hooks 相對路徑；沒宣告＝None。宣告壞＝HooksBad。"""
    try:
        return declared_files(def_folder).get("hooks")
    except ValueError as e:
        raise HooksBad(str(e)) from e


def validate_entry(entry):
    """單格驗證；不認得的鍵不管（C-48）。不對＝HooksBad。"""
    if not isinstance(entry, dict):
        raise HooksBad("must be a JSON object or null")
    on = entry.get("event")
    if on not in EVENTS:
        raise HooksBad("event must be one of %s" % ", ".join(EVENTS))
    target = entry.get("handler")
    if not ((isinstance(target, str) and target) or (isinstance(target, dict) and target)):
        raise HooksBad("handler must be a non-empty string or a directive object")
    for key in ("intercept", "async"):
        if key in entry and not isinstance(entry[key], bool):
            raise HooksBad("%s must be true or false" % key)
    if "condition" in entry:
        m = entry["condition"]
        if not (isinstance(m, str) or (isinstance(m, list) and all(isinstance(x, str) for x in m))):
            raise HooksBad("condition must be a string or an array of strings")
        if EVENTS[on]["condition"] is None:
            raise HooksBad("event %s takes no condition" % on)
    if on == CLOCK_EVENT:
        given = [k for k in ("every_cycles", "every_ms") if k in entry]
        if len(given) != 1:
            raise HooksBad("event %s needs exactly one of every_cycles, every_ms" % on)
        n = entry[given[0]]
        if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
            raise HooksBad("%s must be a positive integer" % given[0])
        if "clock" in entry and not (isinstance(entry["clock"], str) and entry["clock"]):
            raise HooksBad("clock must be a non-empty string (a proc name, or the path of a clock file or of a folder with one)")
    else:
        for key in CLOCK_KEYS:
            if key in entry:
                raise HooksBad("%s is only for event %s" % (key, CLOCK_EVENT))
    if "on_error" in entry and entry["on_error"] not in ("stop", "continue"):
        raise HooksBad("on_error must be stop or continue")
    if "timeout_ms" in entry:
        t = entry["timeout_ms"]
        if not isinstance(t, int) or isinstance(t, bool) or t <= 0:
            raise HooksBad("timeout_ms must be a positive integer")


def _read(path):
    """一份清單 → {名字: 格或 None}；不在＝{}。"""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise HooksBad("cannot read %s: %s" % (path, e)) from e
    if not isinstance(doc, dict):
        raise HooksBad("%s must be a JSON object" % path)
    table = doc.get("hooks", {})
    if not isinstance(table, dict):
        raise HooksBad("hooks in %s must be a JSON object" % path)
    for name, entry in table.items():
        if not name or "/" in name or name.startswith("."):
            raise HooksBad("hook name %r in %s must be non-empty, without / and not start with ." % (name, path))
        if entry is not None:
            try:
                validate_entry(entry)
            except HooksBad as e:
                raise HooksBad("hook %s in %s: %s" % (name, path, e)) from None
    return table


def _layers(def_folder, stack):
    rel = declared(def_folder)
    if not rel:
        return None, {}, {}
    mine = os.path.abspath(os.path.join(def_folder, rel))
    own = os.path.abspath(os.path.join(stack, rel))
    return (mine, own), _read(mine), _read(own)


def load(def_folder, stack):
    """定義那份疊 stack 那份（同名蓋過、null＝關掉）；回 {名字: 格}，格帶 from／base 與預設值。沒宣告或檔不在＝{}。"""
    paths, base, top = _layers(def_folder, stack)
    out = {}
    for path, table in ((paths and paths[0], base), (paths and paths[1], top)):
        for name, entry in table.items():
            if entry is None:
                out.pop(name, None)
                continue
            full = dict(DEFAULTS, **entry)
            full["from"], full["base"] = path, os.path.dirname(path)
            out[name] = full
    return out


def nulled(def_folder, stack):
    """stack 那份設成 null 的名字（排好；給 aos-agent hook ls -l）。"""
    return sorted(n for n, e in _layers(def_folder, stack)[2].items() if e is None)


def has(event, def_folder, stack):
    return any(e["event"] == event for e in load(def_folder, stack).values())


def _matches(entry, event, data):
    field = EVENTS[event]["condition"]
    if field is None or "condition" not in entry:
        return True
    m = entry["condition"]
    return data.get(field) in ([m] if isinstance(m, str) else m)


def _stop_group(p):
    """TERM 整群、寬限 2 秒後 KILL（同 agent-fsm act.py）。"""
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        p.poll()
        try:
            os.killpg(p.pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.02)
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _target(entry):
    """handler → aos-exec 的目標（絕對路徑）；解不開＝丟 OSError 帶原因（當成起不來）。指示詞物件照 aos-agent tools 的 check_pointer 解。"""
    t = entry["handler"]
    if isinstance(t, dict):
        try:
            r = subprocess.run(["aos-directive"], input=json.dumps({"v": t}), stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, cwd=entry["base"])
            t = json.loads(r.stdout).get("v") if r.returncode == 0 else None
        except (OSError, ValueError, AttributeError) as e:
            raise OSError("cannot resolve handler directive: %s" % e) from e
        if not isinstance(t, str) or not t:
            raise OSError("handler directive did not resolve to a non-empty path")
    return t if os.path.isabs(t) else os.path.join(entry["base"], t)


def _run(name, entry, event, data, stack):
    """跑一個 hook。回 (結束碼, stdout 字串)；async true＝(None, "")。自己失敗丟 OSError／TimeoutError 帶原因。"""
    cell = os.path.join(os.path.abspath(stack), CELLS, name)
    os.makedirs(cell, exist_ok=True)
    doc = {"event": event, "hook": name, "stack": os.path.abspath(stack)}
    doc.update({k: v for k, v in data.items() if k not in doc})
    path, tmp = os.path.join(cell, "event.json"), os.path.join(cell, ".event.json.tmp")   # N-05：先寫暫存再改名
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    argv = ["aos-exec", "--stack", cell + "/", _target(entry)]
    wait = not entry["async"]
    with open(path, "rb") as stdin:
        p = subprocess.Popen(argv, stdin=stdin, stdout=subprocess.PIPE if wait else subprocess.DEVNULL,
                             start_new_session=True)   # 自成一群；stderr 不攔、原樣透出
    if not wait:
        return None, ""
    limit = entry["timeout_ms"] / 1000.0
    try:
        try:
            out, _ = p.communicate(timeout=limit)
        except subprocess.TimeoutExpired:
            _stop_group(p)
            try:
                p.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                p.stdout.close()
                p.wait()
            raise TimeoutError("did not finish in %d ms (its process group was killed)" % entry["timeout_ms"])
    except BaseException as e:                   # Ctrl-C／TERM：hook 不再跟自己的群，離開前收掉
        if not isinstance(e, TimeoutError):
            _stop_group(p)
            p.wait()
        raise
    return p.returncode, out.decode("utf-8", "replace")


def _changes(event, out):
    """intercept 的 hook 結束碼 0／10 時 stdout → {鍵: 值}；stdout 空＝{}。不合丟 ValueError。"""
    if not out.strip():
        return {}
    try:
        reply = json.loads(out)
    except ValueError as e:
        raise ValueError("stdout is not JSON: %s" % e) from None
    if not isinstance(reply, dict):
        raise ValueError("stdout is not a JSON object")
    got = {}
    for key in EVENTS[event]["intercept"]:
        if key not in reply:
            continue
        v = reply[key]
        if key == "content" and not (isinstance(v, str) and (v.strip() or event != "before_queue")):
            raise ValueError("content in stdout must be a %sstring" % ("non-empty " if event == "before_queue" else ""))
        got[key] = v
    return got


def fire(event, data, def_folder, stack, warn=None, only=None, entries=None):
    """跑 on==event、match 符合的 hook（照名字排序；前一個改過的後一個看得到；被攔下就停）。
    沒宣告、沒有符合的＝什麼都不做（不起子行程）。warn＝收一行英文的函式（on_error continue 時叫）；None＝不說。
    only＝只跑這些名字（clock_tick 一個一個發）；entries＝已讀好的清單（不重讀）。"""
    if event not in EVENTS:
        raise ValueError("unknown hook event %s" % event)
    result = {"data": copy.deepcopy(data), "changed": [], "blocked": False, "hook": None, "text": ""}
    entries = load(def_folder, stack) if entries is None else entries
    names = sorted(n for n, e in entries.items() if e["event"] == event and _matches(e, event, data)
                   and (only is None or n in only))
    for name in names:
        entry = entries[name]
        try:
            try:
                code, out = _run(name, entry, event, result["data"], stack)
            except (OSError, TimeoutError) as e:
                raise ValueError(str(e)) from None
            if code is None:
                continue
            if code not in (0, BLOCK):
                raise ValueError("exited %d" % code)
            if not entry["intercept"] or not (EVENTS[event]["intercept"] or EVENTS[event]["block"]):
                continue                         # 不看回話：關掉的、或這個事件本來沒東西能改能擋（不報錯）
            got = _changes(event, out) if not (code == BLOCK and EVENTS[event]["block"]) else {}
        except ValueError as e:
            why = "hook %s (event %s) failed: %s" % (name, event, e)
            if entry["on_error"] == "stop":
                raise HookFailed(why) from None
            if warn:
                warn(why + "; going on without it (on_error: continue)")
            continue
        if code == BLOCK and EVENTS[event]["block"]:
            result.update(blocked=True, hook=name, text=out)
            return result
        for key, v in got.items():
            result["data"][key] = v
            if key not in result["changed"]:
                result["changed"].append(key)
    return result


def tools_added(stack, tools, has_hook):
    """tool_added 的「多了誰」：有 hook 生效＝記這次的名單到 $AOS_STACK/hook_tools_seen.json，回比上次多出來的 [(name, path)]；
    第一次（檔不在或壞了）只記不回；沒有 hook＝刪檔、回 []。寫不成丟 OSError。"""
    path = os.path.join(stack, SEEN)
    if not has_hook:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return []
    try:
        with open(path, encoding="utf-8") as f:
            seen = json.load(f)
        if not (isinstance(seen, list) and all(isinstance(x, str) for x in seen)):
            seen = None
    except (OSError, ValueError):
        seen = None
    names = sorted({n for n, _ in tools})
    if seen != names:
        tmp = os.path.join(stack, ".%s.%d.tmp" % (SEEN, os.getpid()))
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(names, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    if seen is None:
        return []
    return [(n, p) for n, p in tools if n not in set(seen)]


# ---- on_clock（11-11 clock-hook）----

def _clock_file(entry, stack):
    """clock 鍵 → (時鐘檔絕對路徑, None) 或 (None, 為什麼找不到)。沒寫＝$AOS_CLOCK；路徑（有 / 或 . 開頭）：檔＝它、資料夾＝裡面的 clock
    （daemon 的 stack 就是這種佈局）；相對＝從 agent 的 stack 算。名字（沒有 /）＝$AOS_DAEMON 表上那一列的 stack 裡的 clock。"""
    v = entry.get("clock")
    if v is None:
        path = os.environ.get("AOS_CLOCK", "")
        if not path:
            return None, "AOS_CLOCK is not set (no clock: not under a daemon tree with one)"
    elif "/" in v or v.startswith("."):
        path = v if os.path.isabs(v) else os.path.join(stack, v)
    else:
        daemon = os.environ.get("AOS_DAEMON", "")
        if not daemon:
            return None, "clock %s is a proc name but AOS_DAEMON is not set" % v
        try:
            with open(os.path.join(daemon, "procs_state.json"), encoding="utf-8") as f:
                row = (json.load(f).get("procs") or {}).get(v)
        except (OSError, ValueError, AttributeError) as e:
            return None, "cannot read the daemon table %s: %s" % (os.path.join(daemon, "procs_state.json"), e)
        st = row.get("stack") if isinstance(row, dict) else None
        if not isinstance(st, str) or not st:
            return None, "proc %s is not on the daemon table %s" % (v, daemon)
        path = st if os.path.isabs(st) else os.path.join(daemon, st)
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
    path = os.path.join(os.path.abspath(stack), CELLS, name, CLOCK_STATE)
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
    每次 loop 起來（hook_fire after_start）先 clock_restart 清掉狀態檔，所以睡醒、重起、auto_restart 後的第一次檢查也算第一次。
    找不到時鐘＝不跑、warning 只在原因變了時說一次（記在狀態檔）。回跑了的 hook 名。hook 停下＝HookFailed（同 fire）。
    寫不了狀態檔＝warning、這次不跑（免得每拍都跑）。"""
    entries = load(def_folder, stack)
    names = sorted(n for n, e in entries.items() if e["event"] == CLOCK_EVENT)
    ran = []
    for name in names:
        entry = entries[name]
        spath, st = _state(stack, name)
        clock, why = _clock_file(entry, stack)
        cycle = _read_cycle(clock) if clock else None
        if clock and cycle is None:
            why = "clock file %s does not hold a cycle number" % clock
        try:
            if why:
                if st.get("warned") != why:
                    if warn:
                        warn("hook %s (event %s) is not checked: %s" % (name, CLOCK_EVENT, why))
                    _put_state(spath, dict(st, warned=why))
                continue
            last = st.get("cycle")
            first = st.get("clock") != clock or not isinstance(last, int) or isinstance(last, bool) or cycle < last
            iv = _interval_ms()
            every = entry["every_cycles"] if "every_cycles" in entry else max(1, -(-entry["every_ms"] // iv))
            if not first and cycle - last < every:
                if st.get("warned"):
                    _put_state(spath, {"clock": clock, "cycle": last})
                continue
            _put_state(spath, {"clock": clock, "cycle": cycle})             # 先記再跑：handler 失敗也不每拍重跑
        except OSError as e:
            if warn:
                warn("hook %s (event %s): cannot write %s: %s" % (name, CLOCK_EVENT, spath, e))
            continue
        data = {"clock": clock, "cycle": cycle, "interval_ms": iv, "first": first,   # first＝剛起來／沒基準／倒退的那一次
                "last_cycle": None if first else last, "missed": 0 if first else (cycle - last) // every - 1}
        fire(CLOCK_EVENT, data, def_folder, stack, warn=warn, only=[name], entries=entries)
        ran.append(name)
    return ran


def clock_restart(stack):
    """loop 起來的那一刻（hook_fire after_start）：刪掉各 hook 小格的 on_clock.json，下一次 clock_tick 就當第一次、立刻跑
    （使用者 11-11「每次睡醒、重起也都會先跑一次」）。刪不掉＝OSError 往上丟；沒有小格＝什麼都不做。"""
    cells = os.path.join(os.path.abspath(stack), CELLS)
    try:
        names = os.listdir(cells)
    except (FileNotFoundError, NotADirectoryError):
        return
    for name in names:
        try:
            os.remove(os.path.join(cells, name, CLOCK_STATE))
        except (FileNotFoundError, NotADirectoryError):
            pass
