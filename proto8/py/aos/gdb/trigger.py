"""aos.gdb.trigger - 條件觸發器的共用零件：觸發器檔（trigger.json）長什麼樣、條件怎麼判、連續幾次才算、停的時候留的字條（gdb/log.jsonl）；REPL 那邊（aos.gdb）與 hook handler（lib/tools/agent/gdb_trigger）都用這份。

圖紙：proto8/thinking/2026-11/19/aos-gdb-1119（乙案）、08-Argon審與採納、aos-gdb-lib-第一版.md。使用者 11-19：斷點＝「特定條件發生時，暫停loop或fsm，
停下來等待檢閱」，條件主要由 hook 承載、「hook不用動」。所以這裡不改 hook 機制：觸發器就是一個普通 hook，handler 是同一支 gdb_trigger，
它讀自己小格（$AOS_STACK＝<agent stack>/hooks/<名>/）裡的 trigger.json 判條件，成立就先留字條、再叫 `aos-agent ctl pause --no-wait`。

檔：
    <agent stack>/hooks/<hook 名>/trigger.json   設定（REPL 寫、handler 讀）：
        {"kind": "always" | "tool_error" | "sh" | "py", "event": 事件, "tools": [工具名] 或 null, "times": N, "once": bool,
         "block": bool, "agent": 表上的名字, "daemon": daemon stack 的絕對路徑或 null, "sh": 字串,
         "py": {"code": base64 marshal, "defaults": [..], "source": 字串或 null, "python": "3.12"} 或 {"expr": 字串}, "about": 一句英文}
    <agent stack>/hooks/<hook 名>/count.json     handler 記的數：{"seen", "streak", "fired", "last_error"}
    <agent stack>/gdb/log.jsonl                  字條（只往後加）：{"kind": "stop" | "pause_failed" | "resume", "at", "by", "trigger", ...}；
                                                 by＝誰寫的（"hook"＝觸發器、"repl"＝aos.gdb；將來外面的觀察者寫 "watch"）。
條件：always＝事件來了就算；tool_error＝after_tool 的 code 不是 0 或逾時（看 agent-fsm 交給 hook 的 code／timed_out，不猜內容）；
    sh＝`sh -c 字串`、事件 JSON 在 stdin、stdout 丟掉，退 0＝算、退 10＝不算、其他＝條件壞了；
    py＝函式 f(event)（REPL 的 def／lambda，marshal 帶過去）或運算式字串（變數 ev），回真值＝算；看得到 json、re、os 與內建。
tools：有給就只算這些工具的事件；其他工具的事件＝條件不成立（連續次數歸零：「連續 N 次」是連著的 N 個同類事件，Argon A6）。
不印東西、不 sys.exit；錯丟 Bad（設定不對）。"""
import base64
import datetime
import dis
import json
import marshal
import os
import re
import subprocess
import sys
import types

KINDS = ("always", "tool_error", "sh", "py")
SPEC = "trigger.json"
COUNT = "count.json"
LOG_DIR = "gdb"
LOG = "log.jsonl"
PREFIX = "gdb_"                                  # 觸發器的 hook 名一律以此開頭（ls 時認得出是誰裝的）
NO = 10                                          # sh 條件：10＝查了不算（N-43）；handler 擋下工具也是 10
SH_TIMEOUT_S = 20                                # sh 條件自己的上限；hook 的 timeout_ms 給得比它大
MODULES = {"json": json, "re": re, "os": os}     # py 條件看得到的模組（其餘只有內建）


class Bad(ValueError):
    """觸發器設定不對、或條件自己壞了（句子英文、不含觸發器名）。"""


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")


def _globals_of(code):
    """一個 code 物件（含裡面的 lambda、內層函式）讀到的全域名字。"""
    names = {i.argval for i in dis.get_instructions(code) if i.opname in ("LOAD_GLOBAL", "LOAD_NAME")}
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            names |= _globals_of(c)
    return names


def _unknown_globals(code):
    import builtins
    return sorted(n for n in _globals_of(code) if n not in MODULES and not hasattr(builtins, n))


def pack_py(cond):
    """REPL 給的 py 條件 → trigger.json 的 py 欄。cond＝函式（def／lambda）或運算式字串（變數 ev）。
    用到外層變數、REPL 裡別的名字、預設值不是 JSON 的＝當場丟 Bad（Argon A7：下斷點那一刻就說，不等跑到一半）。"""
    if isinstance(cond, str):
        try:
            code = compile(cond, "<condition>", "eval")
        except SyntaxError as e:
            raise Bad("py expression does not parse: %s" % e) from None
        bad = [n for n in _unknown_globals(code) if n != "ev"]
        if bad:
            raise Bad("py expression uses names it will not have: %s (it sees ev, json, re, os and builtins)" % ", ".join(bad))
        return {"expr": cond}
    if not isinstance(cond, types.FunctionType):
        raise Bad("py must be a function (def or lambda) taking the event, or an expression string using ev")
    code = cond.__code__
    if code.co_freevars:
        raise Bad("the function uses outer variables (%s); pass them as defaults (lambda ev, x=x: ...), it runs in another process"
                  % ", ".join(code.co_freevars))
    defaults = list(cond.__defaults__ or ())
    if code.co_argcount < 1 or code.co_argcount - len(defaults) != 1:
        raise Bad("the function must take the event as its one argument without a default (more arguments need defaults)")
    try:
        json.dumps(defaults)
    except (TypeError, ValueError):
        raise Bad("the function's defaults must be plain JSON values (numbers, strings, lists, dicts)") from None
    bad = _unknown_globals(code)
    if bad:
        raise Bad("the function uses names it will not have: %s (it sees json, re, os and builtins; pass other values as defaults)"
                  % ", ".join(bad))
    try:
        import inspect
        source = inspect.getsource(cond).strip()
    except (OSError, TypeError):
        source = None
    return {"code": base64.b64encode(marshal.dumps(code)).decode("ascii"), "defaults": defaults,
            "source": source, "python": "%d.%d" % sys.version_info[:2]}


def unpack_py(py):
    """trigger.json 的 py 欄 → 只收事件一個參數的函式；Python 版本不同或解不開丟 Bad。"""
    env = dict(MODULES, __builtins__=__builtins__)
    if "expr" in py:
        try:
            code = compile(py["expr"], "<condition>", "eval")
        except SyntaxError as e:
            raise Bad("py expression does not parse: %s" % e) from None
        return lambda ev: eval(code, dict(env, ev=ev))
    have = "%d.%d" % sys.version_info[:2]
    if py.get("python") != have:
        raise Bad("the function was packed by Python %s, this is Python %s (add the trigger again from this Python)" % (py.get("python"), have))
    try:
        code = marshal.loads(base64.b64decode(py["code"]))
    except (KeyError, ValueError, TypeError, EOFError) as e:
        raise Bad("cannot unpack the function: %s" % e) from None
    return types.FunctionType(code, env, "condition", tuple(py.get("defaults") or ()))


def validate(spec):
    """trigger.json 的形狀；不對丟 Bad。"""
    if not isinstance(spec, dict):
        raise Bad("%s must be a JSON object" % SPEC)
    if spec.get("kind") not in KINDS:
        raise Bad("kind must be one of %s" % ", ".join(KINDS))
    times = spec.get("times", 1)
    if not isinstance(times, int) or isinstance(times, bool) or times < 1:
        raise Bad("times must be a whole number >= 1")
    tools = spec.get("tools")
    if tools is not None and not (isinstance(tools, list) and tools and all(isinstance(t, str) and t for t in tools)):
        raise Bad("tools must be null or a non-empty list of tool names")
    if not (isinstance(spec.get("agent"), str) and spec["agent"]):
        raise Bad("agent must be the agent's name on the daemon table")
    if spec["kind"] == "sh" and not (isinstance(spec.get("sh"), str) and spec["sh"].strip()):
        raise Bad("kind sh needs a non-empty sh string")
    if spec["kind"] == "py" and not (isinstance(spec.get("py"), dict) and ("expr" in spec["py"] or "code" in spec["py"])):
        raise Bad("kind py needs py with code or expr")
    if spec["kind"] == "tool_error" and spec.get("event") != "after_tool":
        raise Bad("kind tool_error only works on event after_tool")


def check(spec, event):
    """條件對這次事件成不成立 → True／False；條件自己壞了丟 Bad（句子說為什麼）。"""
    tools = spec.get("tools")
    if tools is not None and event.get("name") not in tools:
        return False
    kind = spec["kind"]
    if kind == "always":
        return True
    if kind == "tool_error":
        return bool(event.get("timed_out")) or event.get("code") not in (0, None)
    if kind == "sh":
        try:
            r = subprocess.run(["sh", "-c", spec["sh"]], input=json.dumps(event, ensure_ascii=False).encode("utf-8"),
                               stdout=subprocess.DEVNULL, timeout=SH_TIMEOUT_S, start_new_session=True)
        except subprocess.TimeoutExpired:
            raise Bad("the sh condition did not finish in %d s" % SH_TIMEOUT_S) from None
        except OSError as e:
            raise Bad("cannot run sh: %s" % e) from None
        if r.returncode == 0:
            return True
        if r.returncode == NO:
            return False
        raise Bad("the sh condition exited %d (0 = hit, 10 = no hit)" % r.returncode)
    fn = unpack_py(spec["py"])
    out = sys.stdout
    sys.stdout = sys.stderr                      # 使用者函式裡的 print 不進 hook 的 stdout（Argon A1）
    try:
        return bool(fn(event))
    except Exception as e:                       # 使用者的函式：什麼錯都算條件壞了，不讓 hook 失敗
        raise Bad("the py condition raised %s: %s" % (type(e).__name__, e)) from None
    finally:
        sys.stdout = out


def step(spec, count, event):
    """記一次事件、判條件、算連續次數。回 (新的 count, 這次該不該停, 條件壞了的句子或 None)。不碰檔。
    once 停過一次之後什麼都不做；停了就把連續次數歸零（續了之後要再連續 times 次才再停）。"""
    count = dict({"seen": 0, "streak": 0, "fired": 0, "last_error": None}, **(count or {}))
    if spec.get("once") and count["fired"]:
        return count, False, None
    count["seen"] += 1
    try:
        hit = check(spec, event)
    except Bad as e:
        count["last_error"] = str(e)
        count["streak"] = 0
        return count, False, str(e)
    count["streak"] = count["streak"] + 1 if hit else 0
    if count["streak"] < spec.get("times", 1):
        return count, False, None
    count["streak"] = 0
    count["fired"] += 1
    return count, True, None


def brief(event, limit=300):
    """字條裡放的事件摘要：工具名、參數、退出碼、信或工具結果的開頭。"""
    out = {k: event[k] for k in ("name", "id", "code", "timed_out", "letter", "reason") if k in event}
    if "arguments" in event:
        text = json.dumps(event["arguments"], ensure_ascii=False)
        out["arguments"] = event["arguments"] if len(text) <= limit else text[:limit] + "..."
    if isinstance(event.get("content"), str):
        c = event["content"]
        out["content"] = c if len(c) <= limit else c[:limit] + "..."
    return out


def ctl_seq(agent_stack):
    """agent 控制窗 ctl.json 現在的 seq（沒有或讀不到＝None）。字條記它，why() 拿來認「之後有沒有人再下過 ctl」（Argon A5）。"""
    try:
        with open(os.path.join(agent_stack, "ctl.json"), encoding="utf-8") as f:
            v = json.load(f).get("seq")
    except (OSError, ValueError, AttributeError):
        return None
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def log_path(agent_stack):
    return os.path.join(agent_stack, LOG_DIR, LOG)


def append_log(agent_stack, entry):
    """往 gdb/log.jsonl 加一行（O_APPEND 一次寫完；hook、REPL、將來的觀察者都只往後加，不互蓋）。"""
    path = log_path(agent_stack)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = (json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def read_log(agent_stack):
    """gdb/log.jsonl 全部的行（壞行跳過）；沒有檔＝[]。"""
    try:
        with open(log_path(agent_stack), encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return []
    out = []
    for line in lines:
        try:
            doc = json.loads(line)
        except ValueError:
            continue
        if isinstance(doc, dict):
            out.append(doc)
    return out


def since_resume(entries):
    """最後一筆 resume 之後的字條（stop、pause_failed）。"""
    tail = []
    for e in entries:
        if e.get("kind") == "resume":
            tail = []
        elif e.get("kind") in ("stop", "pause_failed"):
            tail.append(e)
    return tail


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path, doc):
    """先寫暫存再改名（N-05）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = os.path.join(os.path.dirname(path), ".%s.%d.tmp" % (os.path.basename(path), os.getpid()))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
