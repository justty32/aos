"""aos.gdb.trigger - 條件觸發器的共用零件：觸發器檔（trigger.json）長什麼樣、條件怎麼判、連續幾次才算、停的時候留的字條（gdb/log.jsonl）與停在事件前的「扣住」檔（gdb/hold.json）、斷點號碼的計數器（gdb/next_id.json）；REPL 那邊（aos.gdb）、hook handler（gdb_trigger）與觀察者（gdb_watch）都用這份。

圖紙：proto8/thinking/2026-11/19/aos-gdb-1119（乙案）、08-Argon審與採納、aos-gdb-lib-第一版.md、aos-gdb-lib-第二版.md。使用者 11-19：斷點＝「特定條件發生時，
暫停loop或fsm，停下來等待檢閱」，條件主要由 hook 承載、「hook不用動」；第二版：「stop_before_tool不就是在工具開始前停下嗎？」。
所以這裡不改 hook 機制：觸發器就是一個普通 hook，handler 是同一支 gdb_trigger，它讀自己小格（$AOS_STACK＝<agent stack>/hookeds/<名>/）裡的
trigger.json 判條件，成立時照事件分兩種停法（how）：
    hold   before_tool、before_queue（事件還沒發生、hook 是同步跑的）：handler 自己不回、等人放行——工具還沒跑、信還沒進 history；
           放行＝那次照原樣跑（「放行但那次工具不跑」使用者 11-19 說「不該有這個方法」，線 aosgdb-verbs-1119 拿掉）。agent 這段時間卡在那一格裡，表上照寫 running。
    pause  其他事件（事件已經發生）：叫 `aos-agent ctl pause --no-wait`，loop 在這一格做完、下一格開頭停住。

檔：
    <agent stack>/hookeds/<hook 名>/trigger.json   設定（REPL 寫、handler 讀）：
        {"kind": "always" | "tool_error" | "sh" | "py", "event": 事件, "how": "hold" | "pause"（由事件定）, "tools": [工具名] 或 null,
         "times": N, "once": bool, "agent": 表上的名字, "daemon": daemon stack 的絕對路徑或 null, "sh": 字串,
         "field": tools 比事件的哪個欄位（沒有＝"name"；aos-gdb 載入的 hook 宣告給了別的 condition 才寫，線 top-1121-gdbdecl）,
         "py": {"code": base64 marshal, "defaults": [..], "source": 字串或 null, "python": "3.12"} 或 {"expr": 字串}, "about": 一句英文}
    <agent stack>/hookeds/<hook 名>/hit.json     最近一次成立的那個事件（整份，handler 成立時寫；a.bp.event() 讀）。
    <agent stack>/hookeds/<hook 名>/count.json   handler 記的數：{"seen", "streak", "fired", "last_error", "pending"}；
                                                 pending＝正在扣住、還沒放行的那一次（工具呼叫 id 或信名）：扣住時 agent 被重起（sleep、
                                                 daemon 重起）＝那次沒跑，重跑同一個 id 時直接再扣住（不再判條件、不算新的一次、once 也照扣）。
    <agent stack>/gdb/log.jsonl                  字條（只往後加）：{"kind": "stop" | "pause_failed" | "hold_ended" | "resume", "at", "by", "trigger", ...}；
                                                 by＝誰寫的（"hook"＝觸發器、"repl"＝aos.gdb、"ctl"＝在 shell 下 ctl resume 放行的、"watch"＝觀察者）。
    <agent stack>/gdb/hold.json                  正在扣住時才有：{"token", "pid", "trigger", "event", "key", "detail", "ctl_seq", ...}；
                                                 pid 不在了＝過時（is_held 會查）。
    <agent stack>/gdb/release.json               放行單：{"token": 同 hold.json}（那一次照原樣跑）。
    <agent stack>/gdb/next_id.json               斷點號碼的計數器：{"next": N}＝下一個號碼（使用者 11-20「不重用」：刪了也不再拿來用；
                                                 觸發器從自己這隻拿，觀察者從它看的每一隻一起拿，見 take_id）；鎖檔 gdb/next_id.lock。
條件：always＝事件來了就算；tool_error＝after_tool 的 code 不是 0 或逾時（看 agent-fsm 交給 hook 的 code／timed_out，不猜內容）；
    sh＝`sh -c 字串`、事件 JSON 在 stdin、stdout 丟掉，退 0＝算、退 10＝不算、其他＝條件壞了；
    py＝函式 f(event)（REPL 的 def／lambda，marshal 帶過去）或運算式字串（變數 ev），回真值＝算；看得到 json、re、os 與內建。
tools：有給就只算這些工具的事件（比事件的 field 欄，預設 name）；其他工具的事件＝條件不成立（連續次數歸零：「連續 N 次」是連著的 N 個同類事件，Argon A6）。
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
HOLD_EVENTS = ("before_tool", "before_queue")   # 事件還沒發生、hook 同步跑：扣住（hold）
SPEC = "trigger.json"
COUNT = "count.json"
HIT = "hit.json"                                 # 最近一次成立的事件（a.bp.event() 讀）
LOG_DIR = "gdb"
LOG = "log.jsonl"
HOLD = "hold.json"
RELEASE = "release.json"
NEXT = "next_id.json"                            # 斷點號碼計數器（gdb/ 底下）
NEXT_LOCK = "next_id.lock"
PREFIX = "gdb_"                                  # 觸發器的 hook 名一律以此開頭（ls 時認得出是誰裝的）
NO = 10                                          # sh 條件：10＝查了不算（N-43）
SH_TIMEOUT_S = 20                                # sh 條件自己的上限；pause 型 hook 的 timeout_ms 給得比它大
MODULES = {"json": json, "re": re, "os": os}     # py 條件看得到的模組（其餘只有內建）


class Bad(ValueError):
    """觸發器設定不對、或條件自己壞了（句子英文、不含觸發器名）。"""


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")


def how(event):
    """這個事件的觸發器怎麼停：hold（事件還沒發生，扣住）或 pause（事件已經發生，下一格開頭停）。"""
    return "hold" if event in HOLD_EVENTS else "pause"


def key_of(event):
    """扣住的是哪一次：before_tool＝工具呼叫 id、before_queue＝信名；沒有＝None。"""
    v = event.get("id") if event.get("event") == "before_tool" else event.get("letter")
    return v if isinstance(v, str) and v else None


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


def pack_py(cond, var="ev", what="the event"):
    """REPL 給的 py 條件 → 設定檔的 py 欄。cond＝函式（def／lambda）或運算式字串（變數 var：觸發器是 ev、觀察者是 t）。
    用到外層變數、REPL 裡別的名字、預設值不是 JSON 的＝當場丟 Bad（Argon A7：下斷點那一刻就說，不等跑到一半）。"""
    if isinstance(cond, str):
        try:
            code = compile(cond, "<condition>", "eval")
        except SyntaxError as e:
            raise Bad("py expression does not parse: %s" % e) from None
        bad = [n for n in _unknown_globals(code) if n != var]
        if bad:
            raise Bad("py expression uses names it will not have: %s (it sees %s, json, re, os and builtins)" % (", ".join(bad), var))
        return {"expr": cond, "var": var}
    if not isinstance(cond, types.FunctionType):
        raise Bad("py must be a function (def or lambda) taking %s, or an expression string using %s" % (what, var))
    code = cond.__code__
    if code.co_freevars:
        raise Bad("the function uses outer variables (%s); pass them as defaults (lambda %s, x=x: ...), it runs in another process"
                  % (", ".join(code.co_freevars), var))
    defaults = list(cond.__defaults__ or ())
    if code.co_argcount < 1 or code.co_argcount - len(defaults) != 1:
        raise Bad("the function must take %s as its one argument without a default (more arguments need defaults)" % what)
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
    """設定檔的 py 欄 → 只收一個參數的函式；Python 版本不同或解不開丟 Bad。"""
    env = dict(MODULES, __builtins__=__builtins__)
    if "expr" in py:
        try:
            code = compile(py["expr"], "<condition>", "eval")
        except SyntaxError as e:
            raise Bad("py expression does not parse: %s" % e) from None
        var = py.get("var") or "ev"
        return lambda v: eval(code, dict(env, **{var: v}))
    have = "%d.%d" % sys.version_info[:2]
    if py.get("python") != have:
        raise Bad("the function was packed by Python %s, this is Python %s (add it again from this Python)" % (py.get("python"), have))
    try:
        code = marshal.loads(base64.b64decode(py["code"]))
    except (KeyError, ValueError, TypeError, EOFError) as e:
        raise Bad("cannot unpack the function: %s" % e) from None
    return types.FunctionType(code, env, "condition", tuple(py.get("defaults") or ()))


def call_py(fn, arg):
    """跑使用者的 py 條件：print 改印到 stderr（不進 hook 的 stdout，Argon A1）；什麼錯都算條件壞了（丟 Bad）。"""
    out = sys.stdout
    sys.stdout = sys.stderr
    try:
        return bool(fn(arg))
    except Exception as e:
        raise Bad("the py condition raised %s: %s" % (type(e).__name__, e)) from None
    finally:
        sys.stdout = out


def validate(spec):
    """trigger.json 的形狀；不對丟 Bad。"""
    if not isinstance(spec, dict):
        raise Bad("%s must be a JSON object" % SPEC)
    if spec.get("kind") not in KINDS:
        raise Bad("kind must be one of %s" % ", ".join(KINDS))
    if not isinstance(spec.get("event"), str):
        raise Bad("event must be a hook event name")
    if spec.get("how") != how(spec["event"]):
        raise Bad("how must be %s for event %s" % (how(spec["event"]), spec["event"]))
    times = spec.get("times", 1)
    if not isinstance(times, int) or isinstance(times, bool) or times < 1:
        raise Bad("times must be a whole number >= 1")
    tools = spec.get("tools")
    if tools is not None and not (isinstance(tools, list) and tools and all(isinstance(t, str) and t for t in tools)):
        raise Bad("tools must be null or a non-empty list of tool names")
    if "field" in spec and not (isinstance(spec["field"], str) and spec["field"]):
        raise Bad("field must be the name of the event field tools are matched against")
    if not (isinstance(spec.get("agent"), str) and spec["agent"]):
        raise Bad("agent must be the agent's name on the daemon table")
    if spec["kind"] == "sh" and not (isinstance(spec.get("sh"), str) and spec["sh"].strip()):
        raise Bad("kind sh needs a non-empty sh string")
    if spec["kind"] == "py" and not (isinstance(spec.get("py"), dict) and ("expr" in spec["py"] or "code" in spec["py"])):
        raise Bad("kind py needs py with code or expr")
    if spec["kind"] == "tool_error" and spec["event"] != "after_tool":
        raise Bad("kind tool_error only works on event after_tool")


def run_sh(command, stdin_text, cwd=None, env=None):
    """sh 條件：退 0＝True、10＝False、其他＝丟 Bad。stdout 丟掉。"""
    try:
        r = subprocess.run(["sh", "-c", command], input=stdin_text.encode("utf-8"), cwd=cwd, env=env,
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


def check(spec, event):
    """條件對這次事件成不成立 → True／False；條件自己壞了丟 Bad（句子說為什麼）。"""
    tools = spec.get("tools")
    if tools is not None and event.get(spec.get("field") or "name") not in tools:
        return False
    kind = spec["kind"]
    if kind == "always":
        return True
    if kind == "tool_error":
        return bool(event.get("timed_out")) or event.get("code") not in (0, None)
    if kind == "sh":
        return run_sh(spec["sh"], json.dumps(event, ensure_ascii=False))
    return call_py(unpack_py(spec["py"]), event)


def step(spec, count, event):
    """記一次事件、判條件、算連續次數。回 (新的 count, 這次該不該停, 條件壞了的句子或 None)。不碰檔。
    once 停過一次之後什麼都不做；停了就把連續次數歸零（續了之後要再連續 times 次才再停）。
    扣住被打斷的那一次（count 的 pending）由 handler 自己先認，不經這裡。"""
    count = dict({"seen": 0, "streak": 0, "fired": 0, "last_error": None, "pending": None}, **(count or {}))
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


def brief(event, limit=300, field=None):
    """字條裡放的事件摘要：工具名、參數、退出碼、信或工具結果的開頭；field＝觸發器比主詞的欄位（宣告給的，不是 name 時）也放。"""
    out = {k: event[k] for k in ("name", "id", "code", "timed_out", "letter", "reason") if k in event}
    if field and field in event and field not in out:
        text = json.dumps(event[field], ensure_ascii=False)
        out[field] = event[field] if len(text) <= limit else text[:limit] + "..."
    if "arguments" in event:
        text = json.dumps(event["arguments"], ensure_ascii=False)
        out["arguments"] = event["arguments"] if len(text) <= limit else text[:limit] + "..."
    if isinstance(event.get("content"), str):
        c = event["content"]
        out["content"] = c if len(c) <= limit else c[:limit] + "..."
    return out


def ctl_doc(agent_stack):
    """agent 控制窗 ctl.json 現在的 (seq, cmd)；讀不到＝(None, None)。"""
    try:
        with open(os.path.join(agent_stack, "ctl.json"), encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None, None
    if not isinstance(doc, dict):
        return None, None
    v = doc.get("seq")
    return (v if isinstance(v, int) and not isinstance(v, bool) else None), doc.get("cmd")


def ctl_seq(agent_stack):
    """agent 控制窗 ctl.json 現在的 seq（沒有或讀不到＝None）。字條記它，why() 拿來認「之後有沒有人再下過 ctl」（Argon A5）。"""
    return ctl_doc(agent_stack)[0]


def ctl_unapplied(agent_stack):
    """ctl.json 裡還沒被 loop 套用的 pause／stop（seq 比 state_flux.json 的 ctl_seq 新）→ (seq, cmd)；沒有＝None（Argon A5、A7）。"""
    seq, cmd = ctl_doc(agent_stack)
    if seq is None or cmd not in ("pause", "stop"):
        return None
    try:
        applied = (read_json(os.path.join(agent_stack, "state_flux.json"), {}) or {}).get("ctl_seq")
    except (OSError, ValueError):
        applied = None
    if isinstance(applied, int) and not isinstance(applied, bool) and applied >= seq:
        return None
    return seq, cmd


def log_path(agent_stack):
    return os.path.join(agent_stack, LOG_DIR, LOG)


def append_log(agent_stack, entry):
    """往 gdb/log.jsonl 加一行（O_APPEND 一次寫完；hook、REPL、觀察者都只往後加，不互蓋）。"""
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
    """最後一筆 resume 之後的字條（stop、pause_failed、hold_ended）。"""
    tail = []
    for e in entries:
        if e.get("kind") == "resume":
            tail = []
        elif e.get("kind") in ("stop", "pause_failed", "hold_ended"):
            tail.append(e)
    return tail


def alive(pid):
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_hold(agent_stack):
    """正在扣住的那一次（gdb/hold.json，handler 還活著才算）；沒有或過時＝None。"""
    try:
        doc = read_json(os.path.join(agent_stack, LOG_DIR, HOLD))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or not alive(doc.get("pid")):
        return None
    return doc


def write_release(agent_stack, token):
    """放行單：handler 看到 token 對得上就放行（那一次照原樣跑）。"""
    write_json(os.path.join(agent_stack, LOG_DIR, RELEASE), {"token": token})


class _Locked:
    """依序鎖住這幾個 stack 的 gdb/next_id.lock（排過序，兩個 REPL 同時下斷點不會互卡）。"""

    def __init__(self, stacks):
        self.stacks = sorted(set(os.path.abspath(s) for s in stacks))

    def __enter__(self):
        import fcntl
        self.fds = []
        for s in self.stacks:
            os.makedirs(os.path.join(s, LOG_DIR), exist_ok=True)
            fd = os.open(os.path.join(s, LOG_DIR, NEXT_LOCK), os.O_RDWR | os.O_CREAT, 0o644)
            self.fds.append(fd)
            fcntl.flock(fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        for fd in self.fds:
            os.close(fd)                         # 關檔＝放鎖
        return False


def _next(stack):
    v = (read_json(os.path.join(stack, LOG_DIR, NEXT), {}) or {}).get("next")
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 1 else 1


def take_id(stacks, at_least=1):
    """拿一個新的斷點號碼：n＝at_least 與這幾個 stack 計數器的最大值，每個計數器都推到 n+1（之後誰都不會再拿到 n）。回 n（int）。"""
    with _Locked(stacks) as lk:
        n = max([at_least] + [_next(s) for s in lk.stacks])
        for s in lk.stacks:
            write_json(os.path.join(s, LOG_DIR, NEXT), {"next": n + 1})
    return n


def give_back(stacks, n):
    """下斷點失敗時把號碼 n 還回去：計數器還停在 n+1（之後沒人再拿過）的才改回 n；有人拿過就不動（那就跳過 n，照樣不重用）。"""
    with _Locked(stacks) as lk:
        for s in lk.stacks:
            if _next(s) == n + 1:
                write_json(os.path.join(s, LOG_DIR, NEXT), {"next": n})


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
