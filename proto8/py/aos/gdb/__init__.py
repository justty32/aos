"""aos.gdb - aos-gdb 的 Python 庫（在 python REPL 裡用）：接上一隻已在跑的 agent（a.xxx＝aos-agent xxx 的薄殼），斷點全在 a.bp 底下（增刪改查、停、續、為什麼停）。

使用者 11-19：「先用python產出一份粗定義，然後進入python repl，用aos-gdb庫，下斷點，然後跑。」斷點＝「特定條件發生時，暫停loop或fsm，
停下來等待檢閱」，「能把他停下來的都可以」，「hook不用動」；第二版：「stop_before_tool不就是在工具開始前停下嗎？丙可以繼續」。
介面（線 aosgdb-api-1119）：「斷點這塊，我覺得他的架構就是以斷點為核心， 增刪改查。然後a.xxx這塊，感覺就是aos-agent xxxx。……
或者說他應該是a.bp.stop(),a.bp.resume()。對斷點增刪改查，包括以id查詢斷點...」。
圖紙：thinking/2026-11/19/aos-gdb-1119（乙案）、08-Argon審與採納、aos-gdb-lib-第一版.md、aos-gdb-lib-第二版.md（末節＝這次的介面）。

兩層（遙控器在入口 aos.py.agent；這裡是它的延伸 a.bp 與 a.look 的本體）：
    a.xxx＝aos-agent xxx（aos.py 的通用代理）；a.look＝讀 stack 的檔（Look：where、history、observed、request、queue、stderr、file）。
    a.bp＝斷點（class Breakpoints）：增 a.bp.add.<種類>(...)（回斷點物件 Breakpoint）、rm／set／ls／get；控制 resume／step／pause（預設等到停下才回；
    wait=False＝送出就回 Pending，is_done() 問好了沒、cancel() 不等了）；查 why／held／stopped、notes；clear。
控制動作（使用者 11-19「我記得有step into還是啥的，參考那些ide」，選項框選「resume/step 自己等到停」；「不該有這個方法」＝skip 拿掉；
    線 aosgdb-verbs-1119，紀錄 thinking/2026-11/19/aos-gdb-動詞-1119.md）：resume＝繼續跑、等下一次停；step＝走 fsm 一格就停；pause＝現在停（使用者 11-19 選「改 a.bp.pause()」：VS Code 的「停一下」叫 Pause）。
    wait=（使用者 11-20 選項框：加 wait= 的是「暫停 a.bp.pause()」、不等時「回一個可以查的物件。用is_done()」、resume／step「三個都加」；
    只開 wait= 這一個參數，idle_s／report_s／timeout_s 照舊是屬性；線 aos-gdb-wait-1120，紀錄 thinking/2026-11/20/aos-gdb-wait-1120.md）。
建斷點的寫法（使用者 11-19 選項框選「a.bp.add.before_tool("x")」，thinking/2026-11/19/aos-pylib-1119/07 第 3 題；字串式 a.bp.add("before_tool") 不留）：
    a.bp.add.<種類>([主詞], *, 條件, 選項) → Breakpoint。種類＝hook 事件（before_tool、after_tool、before_queue、after_queue、brain_failed、tool_added、
    after_start、after_stop；on_clock 不收）、tool_error、watch；tab 補得出、打錯當場 AttributeError；主詞＝能篩名字的事件才有（工具名，brain_failed 是錯誤代號）。
id（使用者 11-20：「不能純數字，然後搭配id、屬性(hook點種類)嗎？」＝純數字、種類放在屬性；號碼「不重用」；add「回物件、帶屬性」、屬性「每次讀都重新查」）：
    號碼是 int，從 1 起、刪了不再用：計數器在 agent 的 stack（gdb/next_id.json，trigger.take_id）；觀察者從它看的每一隻一起拿，所以每隻的 a.bp 裡都不撞。
    id="mine" 自己取名照留（str，不能全是數字）；rm／set／get／replace 收 Breakpoint、號碼、數字字串或名字；set 也回 Breakpoint（使用者 11-20 選「a.bp.set 也回物件」）。
    磁碟上的名字（hook 名、小格夾、觀察者的 proc 名）號碼補零到 4 位：gdb_0002、gdbw_0012（使用者 11-20 選「斷點號碼檔名補零」）；.id 照舊是 int 2。
斷點兩種，同一套 id：
    觸發器（a.bp.add.before_tool(...) 等事件）：agent 身上一個 hook（gdb_<id>），事件來了判條件。
        事件還沒發生（before_tool、before_queue）＝扣住（hold）：hook handler 自己不回，工具還沒跑；a.bp.resume() 放行、照原樣跑。
        其他事件（已經發生）＝暫停（pause）：ctl pause，loop 在這一格做完、下一格開頭停住；a.bp.resume() 背後是 ctl resume。
    觀察者（a.bp.add.watch(...)）：另一支掛在 daemon 表上的 proc（gdbw_<id>），每隔一陣子看目標的檔，成立就 ctl pause 目標（晚一格）（aos.gdb.watcher）。

每一步背後是一條 aos 指令（aos-agent …、aos-daemon-ctl …）或讀寫 stack 裡的一個檔；aos.py.echo 為真時先在 stderr 印出那條指令（或 "# read 路徑"）
（觸發器掛在 agent 的 stack、觀察者掛在 daemon 表上，REPL 關了照樣在；停住的那隻用 `aos-agent ctl resume` 也續得了，扣住的也是）。

    from aos.py import agent
    a = agent.attach("ann", daemon=".stack")              # a.bp 要知道 daemon：不給＝$AOS_DAEMON
    b = a.bp.add.before_tool("write")                     # write 要跑之前扣住；回斷點物件：b.id == 1、b.kind == "before_tool"
    a.bp.add.after_tool("write")                          # write 跑完、腦還沒看到結果就停
    a.bp.add.tool_error(times=2)                          # 任何工具連續回錯兩次
    a.bp.add.after_tool(sh="grep -q secret || exit 10")   # 自訂條件：一段 shell（事件 JSON 在 stdin，退 0＝算）
    a.bp.add.before_tool(py=lambda ev: ev["arguments"].get("path", "").endswith(".env"))
    a.bp.add.watch(py=lambda t: len(t.history(0)) > 20)   # 觀察者：另一支 proc 每 0.5 秒看一次；.kind == "watch"
    a.say("write a note")
    a.bp.resume()      # 沒停著：不送東西，等到停在斷點才回，印 "stopped at breakpoint 1 (before_tool: write)"
    a.bp.why(); a.look.where(); a.look.history(3); b.fired
    a.bp.step()        # 走一格（那次 write 照跑，這一格做完）又停
    p = a.bp.resume(wait=False)   # 放行就回；p.is_done() 問好了沒，p.wait() 拿到跟等的版本一樣的結果
    a.bp.ls(); a.bp.get(b); a.bp.set(b, enabled=False); a.bp.rm(b); a.bp.clear()
    a.bp.pause()        # 不靠斷點：現在停（等到真的停下才回）

觸發器的檔、字條、扣住檔、條件怎麼判在 aos.gdb.trigger；hook handler 是 lib/tools/agent/gdb_trigger；觀察者在 aos.gdb.watcher 與 lib/tools/agent/gdb_watch。

hook 宣告當參考（使用者 11-21「4.要做，我覺得可以在gdb啓動時給他選項，跟他說可以參考這份宣告，然後再去做一些事情。」；線 top-1121-gdbdecl，
紀錄 thinking/2026-11/21/gdb-參考宣告-1121.md）：aos-gdb --hooks FILE／--def-hooks 載入（本體 aos.gdb.decl，REPL 裡叫 hooks）之後，
種類多了宣告裡有、預設沒有的點（kinds()）；主詞照宣告的 condition／subject（subject_of()）；a.bp.add 時點名或 py 條件讀的欄位不在宣告裡＝一行 warning、照下；
a.bp.event() 照宣告的 input 排停下的那個事件。沒載入任何宣告＝跟以前一樣（種類 KINDS、主詞 SUBJECT）。"""
import inspect
import json
import os
import shutil
import signal
import subprocess
import sys
import time

from aos.agentlib import hooks as _hooks
from aos.gdb import decl, trigger, watcher as _watch
from aos.gdb.handles import Breakpoint, Pending
from aos.gdb.look import Look, Text, Why, bp_id, bp_name, run, Failed  # noqa: F401
from aos.py._shell import Timeout, call, show

HANDLER = {"$env": "AOS_HOME", "$path": "/lib/tools/agent/gdb_trigger"}
NAMED = tuple(e for e, d in _hooks.POINTS.items() if d["field"] == "name")   # 能篩名字的事件（agent 一家自己的規矩；brain_failed 的 name＝錯誤代號）
# 斷點的種類＝agent 身上會發的事件：agent 一家自己發的（on_clock 要給間隔，不是「事件發生」，不收），加上經 aos-hook fire 發的 eca 壓縮兩點與 loop 四點
# （11-21 線 top-1121-hooknew：以前由 aos 自帶的四份宣告合起來算，宣告改成只是參考之後寫在這裡）
EVENTS = (tuple(e for e in _hooks.POINTS if e != _hooks.CLOCK_EVENT)
          + ("before_compact", "after_compact", "after_start", "after_stop", "before_run", "after_run"))
TOOL_ERROR, WATCH = "tool_error", "watch"         # a.bp.add 的種類除了 EVENTS 之外還有這兩個
KINDS = EVENTS + (TOOL_ERROR, WATCH)
SUBJECT = {e: ("code" if e == "brain_failed" else "tool") for e in NAMED + (TOOL_ERROR,)}   # 有主詞的種類 → 主詞的參數名
RELEASE_WAIT_S = 10
POLL_S = 0.05
# HooksMissing 後面補的那一句（使用者 11-19 下午「派線修」，線 aos-bpfix-1119）：agent-python 骨架已帶 hooks={}，這句給拿掉那行的 agent.py、沒寫 hooks 的衍生、手寫的定義
# （寫法 11-20 改成 defs.Agent(..., hooks={})，編譯程式庫第 2 刀 aos-pylib-k2-1120）
HOOKS_FIX = ("to fix it in an agent.py definition: give hooks={} to defs.Agent(...) in agent.py, "
             "and recompile (python3 agent.py --compile)")
_SHARED = {}                                      # (daemon, 名字) → 那一隻的等的設定與自己送出的 pause（a.bp 每次取都是新的）


def kinds():
    """現在 a.bp.add 有的種類：預設的事件、載入的宣告多出來的點（aos.gdb.decl；沒載入＝沒有）、tool_error、watch。"""
    return EVENTS + decl.extra_kinds(EVENTS) + (TOOL_ERROR, WATCH)


def subject_of(kind):
    """種類 → (主詞的參數名, 拿事件的哪個欄位比) 或 None（沒有主詞）。載入的宣告給了 condition 就照它，不然照預設（SUBJECT，欄位 name）。"""
    if kind == WATCH:
        return None                               # 觀察者看檔、不看事件：沒有主詞
    got = decl.subject("after_tool" if kind == TOOL_ERROR else kind)
    if got:
        return got
    return (SUBJECT[kind], "name") if kind in SUBJECT else None


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class _Defer:
    """送指令的那一小段裡先不理 Ctrl-C（記下來，送完再算「不等了」）：指令不會送一半。只在主執行緒有用（signal 的限制）。"""

    def __enter__(self):
        self.hit, self._old = False, None
        try:
            self._old = signal.signal(signal.SIGINT, self._on)
        except ValueError:
            pass
        return self

    def _on(self, signum, frame):
        self.hit = True

    def __exit__(self, *exc):
        if self._old is not None:
            signal.signal(signal.SIGINT, self._old)
        return False


class Target:
    """a.bp 背後的那一隻：名字、daemon（絕對路徑；遙控器沒給＝$AOS_DAEMON）、stack（第一次用到時問一次，這個 a.bp 用到底）。"""

    def __init__(self, name, daemon=None):
        d = daemon or os.environ.get("AOS_DAEMON")
        if not d:
            raise Failed("a.bp", "no daemon: give agent.attach(name, daemon=...) or set AOS_DAEMON", code="DaemonMissing")
        self.name, self.daemon, self._stack = name, os.path.abspath(d), None

    @property
    def stack(self):
        if self._stack is None:
            out = self.agent("ctl", "state", "--json", "who", quiet=True)
            s = (json.loads(out or "{}").get("who") or {}).get("stack")
            if not isinstance(s, str) or not s:
                raise Failed("a.bp", "cannot tell where the stack of %s is (aos-agent ctl state who)" % self.name, code="StackMissing")
            self._stack = s
        return self._stack

    def agent(self, *args, quiet=False, detach=False):
        """aos-agent --daemon D --target NAME ARGS...；回 stdout（Text，可能是空的）。detach＝自己一個 session（終端機的 Ctrl-C 打不到它）。
        HooksMissing（定義沒宣告 hook，斷點掛不上）：錯誤行原樣，後面補一句怎麼修（HOOKS_FIX）。"""
        try:
            return call(["aos-agent", "--daemon", self.daemon, "--target", self.name] + [str(x) for x in args], quiet=quiet, detach=detach)
        except Failed as e:
            if e.code != "HooksMissing" or isinstance(e, Timeout):
                raise
            raise Failed("%s; %s" % (e, HOOKS_FIX), code=e.code, argv=e.argv, exit=e.exit) from None


class StackLook(Look):
    """a.look：一隻 agent 的 stack 裡的檔（只讀，一次一個）。"""

    def __init__(self, name, stack):
        self.name, self.stack = name, stack

    def __repr__(self):
        return "<a.look of %s (stack %s): where, history, observed, request, queue, stderr, file, path>" % (self.name, self.stack)


class Add:
    """a.bp.add：建斷點。a.bp.add.<種類>([主詞], *, sh=, py=, times=1, once=False, id=None, replace=False) 回斷點物件（Breakpoint）；
    watch 另有 every_ms=500、also=()。種類＝KINDS（tab 補得出）；打錯當場 AttributeError；a.bp.add(...) 直接叫＝Failed，說要寫種類。"""

    def __init__(self, bp):
        self._bp = bp
        self._kinds = kinds()                     # 建的那一刻的種類（a.bp 每次取都是新的，所以 hooks.load 之後的下一個 a.bp 就有新的）
        for kind in self._kinds:
            setattr(self, kind, _maker(bp, kind))

    def __getattr__(self, name):
        raise AttributeError("a.bp.add has no kind %s (kinds: %s)" % (name, ", ".join(self.__dict__.get("_kinds", KINDS))))

    def __dir__(self):
        return list(self._kinds)

    def __call__(self, *args, **kw):
        raise Failed("a.bp.add", "say which kind, e.g. a.bp.add.before_tool(\"write\") (kinds: %s)" % ", ".join(self._kinds), code="ArgumentsBad")

    def __repr__(self):
        def mark(k):
            if not decl.current or k == WATCH:
                return ""
            return "" if ("after_tool" if k == TOOL_ERROR else k) in decl.current.points else "   (not declared)"
        head = "a.bp.add.<kind>(...) returns the new breakpoint (b.id is its number, b.kind its kind); kinds:"
        if decl.current:
            head += " (hook declarations loaded: hooks lists them)"
        return "\n".join([head] + ["  %s%s%s" % (k, inspect.signature(getattr(self, k)), mark(k)) for k in self._kinds])


def _maker(bp, kind):
    """a.bp.add.<kind> 這一支：參數照種類（有主詞的才有位置參數；watch 多 every_ms、also）。"""
    P = inspect.Parameter
    params = []
    sub = subject_of(kind)
    subject = sub[0] if sub else None
    if subject:
        params.append(P(subject, P.POSITIONAL_OR_KEYWORD, default=None))
    params += [P("sh", P.KEYWORD_ONLY, default=None), P("py", P.KEYWORD_ONLY, default=None),
               P("times", P.KEYWORD_ONLY, default=1), P("once", P.KEYWORD_ONLY, default=False)]
    if kind == WATCH:
        params += [P("every_ms", P.KEYWORD_ONLY, default=500), P("also", P.KEYWORD_ONLY, default=())]
    params += [P("id", P.KEYWORD_ONLY, default=None), P("replace", P.KEYWORD_ONLY, default=False)]
    sig = inspect.Signature(params)

    def add(*args, **kw):
        try:
            got = sig.bind(*args, **kw)
        except TypeError as e:
            raise Failed("a.bp.add.%s" % kind, str(e), code="ArgumentsBad") from None
        got.apply_defaults()
        v = dict(got.arguments)
        return bp._add(kind, tool=v.pop(subject) if subject else None, name=v.pop("id"), **v)

    add.__name__ = add.__qualname__ = kind
    add.__signature__ = sig
    said = (decl.current.get(kind) or {}).get("description") if kind not in _KIND_DOC else None
    add.__doc__ = (_KIND_DOC.get(kind) or ("觸發器：事件 %s 來了（%s）。%s" % (
        kind, "扣住" if trigger.how(kind) == "hold" else "那一格做完暫停", "宣告說：%s" % said if isinstance(said, str) else ""))) + _COMMON_DOC
    return add


_KIND_DOC = {
    "before_tool": "觸發器：工具要跑之前扣住（工具還沒跑；a.bp.resume()／a.bp.step() 放行、照跑）。tool＝只算這個（或這些）工具。",
    "before_queue": "觸發器：一封信要收進來之前扣住（a.bp.resume() 照收）。",
    "after_tool": "觸發器：工具跑完、腦還沒看到結果時停（那一格做完暫停）。tool＝只算這個（或這些）工具。",
    "tool_error": "觸發器：工具跑完而且回錯（退出碼不是 0 或逾時）就停（after_tool 的一種）。tool＝只算這個（或這些）工具。",
    "brain_failed": "觸發器：問腦失敗時停。code＝只算這個（或這些）錯誤代號。",
    "tool_added": "觸發器：加了工具時停。tool＝只算這個（或這些）工具。",
    "watch": "觀察者：另一支 proc 每 every_ms 看一次目標的檔（also＝順便也看這些 agent，同一個 daemon），條件成立就暫停（晚一格）。一定要給 sh 或 py。",
}
_COMMON_DOC = """
條件：不給＝事件來了就算；sh＝一段 shell（觸發器：事件 JSON 在 stdin；觀察者：cwd＝目標 stack；退 0＝算、10＝不算、其他＝條件壞了）；
py＝觸發器是 f(ev)／運算式字串（變數 ev），觀察者是 f(t)／運算式字串（變數 t，t.mem 跨圈留著）。
times＝連續幾次才算；once＝只停一次；id＝自己取名（str，不能全是數字；不給＝下一個號碼，刪了也不再用）；
replace＝同 id 已有就換掉（id＝已有的號碼或斷點物件也行）。回斷點物件：.id、.kind 與 a.bp.get 的每一欄，每次讀都重新查。"""


class Breakpoints:
    """a.bp：以斷點為核心——增 add.<種類>(...)（回 Breakpoint）、刪 rm、改 set、查 ls／get（收 Breakpoint 或 id：號碼 int、數字字串、自己取的名字）；
    控制 resume（繼續跑）、step（走一格）、pause（現在停），只收 wait=：預設等到停下才回、回停在哪；wait=False＝送出就回 Pending（is_done()、wait()、cancel()）；
    查 why（停在哪、為什麼）／held（扣住的那一次）／stopped（停著沒）；字條 notes；全拿掉 clear。
    等的設定（屬性，不是參數）：idle_s＝閒著多久算「不會停了」、report_s＝每幾秒印一行現況（0＝不印）、timeout_s＝最多等幾秒（None＝不限）。
    a.bp 每次取都是新的物件，所以設定與「自己送出的 pause」記在模組裡、以 (daemon, 名字) 為鍵：同一隻的每個 a.bp 共用。"""

    DEFAULTS = {"idle_s": 1.0, "report_s": 10, "timeout_s": None}

    def __init__(self, target):
        self._a = target
        self.add = Add(self)
        self._s = _SHARED.setdefault((target.daemon, target.name), {"mine": set()})
        self._mine = self._s["mine"]              # 自己（step／pause）送出的 pause 的 seq：認得出「這是我送的」

    def _setting(name, check, what):
        def get(self):
            return self._s.get(name, Breakpoints.DEFAULTS[name])

        def put(self, v):
            if not check(v):
                raise Failed("a.bp.%s" % name, "must be %s" % what, code="ArgumentsBad")
            self._s[name] = v
        return property(get, put, doc=what)

    idle_s = _setting("idle_s", lambda v: _num(v) and v > 0, "a number of seconds > 0: idle this long with no stop = return 'did not stop'")
    report_s = _setting("report_s", lambda v: _num(v) and v >= 0, "a number of seconds >= 0: one line on stderr this often while waiting (0 = never)")
    timeout_s = _setting("timeout_s", lambda v: v is None or (_num(v) and v > 0), "None or a number of seconds > 0: wait at most this long, then Timeout")
    del _setting

    def __repr__(self):
        rows = self.ls(quiet=True)
        head = "<a.bp of %s: %d breakpoint(s); add.<kind>(...) / rm / set / ls / get, resume / step / pause, why / held / stopped>" % (self._a.name, len(rows))
        return "\n".join([head] + ["  %s  %s%s  %s%s" % (r["id"], r["kind"], "" if r["enabled"] else " (disabled)", r["about"],
                                                         "  <- stopped here" if r["here"] else "")
                                   for r in rows])

    # ---- 增（a.bp.add.<種類> 叫這一支）----
    def _add(self, on, tool=None, sh=None, py=None, times=1, once=False, name=None, replace=False, every_ms=500, also=()):
        a = self._a
        ks = kinds()
        if on not in ks:
            raise Failed("bp.add", "kind must be one of %s" % ", ".join(ks))
        name = None if name is None else _norm(name)
        if isinstance(name, int) and name not in self._ids(watchers_on_daemon=True):
            raise Failed("bp.add", "there is no breakpoint %d to replace; numbers are given out in order and never used again "
                                   "(leave id= out for a new one, or give a name such as id=\"mine\")" % name)
        if on == WATCH:
            if tool:
                raise Failed("bp.add", "tool= does not work on watch (a watcher looks at files, not at one event)")
            if name is not None and name in self._trigger_ids():
                raise Failed("bp.add", "%s already has a trigger breakpoint %s (a.bp.rm it first)" % (a.name, name))
            return Breakpoint(self, _watch.add(a.daemon, [a.name] + list(also), sh=sh, py=py, times=times, once=once, every_ms=every_ms,
                                               name=name, replace=replace, echo=True))
        if also or every_ms != 500:
            raise Failed("bp.add", "also= and every_ms= only work on watch")
        error = on == TOOL_ERROR
        event = "after_tool" if error else on
        tools = [tool] if isinstance(tool, str) else (list(tool) if tool else None)
        sub = subject_of(on)
        if tools and not sub:
            raise Failed("bp.add", "a first argument only works on %s (event %s has no name to match)"
                         % (", ".join(k for k in ks if subject_of(k)), event))
        if sum(bool(x) for x in (sh, py is not None, error)) > 1:
            raise Failed("bp.add", "give one condition: sh or py (tool_error is a condition already)")
        spec = {"kind": "sh" if sh else "py" if py is not None else "tool_error" if error else "always",
                "event": event, "how": trigger.how(event), "tools": tools, "times": times, "once": bool(once),
                "agent": a.name, "daemon": a.daemon}
        if sub and sub[1] != "name":
            spec["field"] = sub[1]                # 宣告的 condition 不是 name：gdb_trigger 拿這個欄位比主詞
        if sh:
            spec["sh"] = sh
        if py is not None:
            try:
                spec["py"] = trigger.pack_py(py)
            except trigger.Bad as e:
                raise Failed("bp.add", str(e)) from None
        spec["about"] = _about(spec)
        try:
            trigger.validate(spec)
        except trigger.Bad as e:
            raise Failed("bp", str(e)) from None
        for line in decl.warnings(on, event, py=py):   # 宣告只是參考：對不上只提醒，照下
            sys.stderr.write("a.bp.add.%s: warning: %s\n" % (on, line))
            sys.stderr.flush()
        have = self._ids(watchers_on_daemon=True)
        short = name
        if short in have and not replace:
            raise Failed("bp.add", "%s already has a breakpoint %s (replace=True to replace it)" % (a.name, short))
        if short is not None and short not in self._trigger_ids() and short in have:
            raise Failed("bp.add", "%s is a watcher on this daemon (a.bp.rm it first)" % short)
        if short is None:                        # 新號碼：躲開這個 daemon 上觀察者用的號碼（觀察者那邊也會推這隻的計數器）
            short = trigger.take_id([a.stack], 1 + max((i for i in have if isinstance(i, int)), default=0))
        cell = self._cell(short)
        undo = _Undo(self._a.stack, cell, (trigger.SPEC, trigger.COUNT))
        try:
            self._write_spec(short, spec)
            trigger.write_json(os.path.join(cell, trigger.COUNT), {})      # 重下＝重新數
            self._install(short, spec, replace=True)
        except BaseException as e:
            # 裝不上（HooksMissing 等）＝什麼都不留：新建的小格整個拿掉、號碼還回去（id 不被吃掉）、重下的放回原本的設定與計數（線 aos-bpfix-1119）。
            # Ctrl-C 這類打斷：hook 已經裝上了就留著（它是一個真的斷點），沒裝上才收回。
            if isinstance(e, Failed) or not self._installed(short):
                undo()
                if name is None:
                    trigger.give_back([a.stack], short)
            raise
        return Breakpoint(self, short)

    # ---- 刪 ----
    def rm(self, id):
        """拿掉一個斷點（收 Breakpoint 或 id）。觸發器：aos-agent hook rm gdb_ID（小格裡的設定與計數留著給人看，標成 removed）；正扣在它上面的那一次不受影響，
        照樣等 a.bp.resume()／a.bp.step()。觀察者：aos-daemon-ctl rm gdbw_ID（先停、等行程退出、再從表上拿掉；它也看別隻的話別隻也不看了）。
        號碼不再拿來用（之後 add 拿下一個）。"""
        kind, id = self._kind(id)
        if kind == WATCH:
            out = _watch.rm(self._a.daemon, id, echo=True)
            end = time.monotonic() + RELEASE_WAIT_S   # rm 是寄信給 daemon；等表上真的沒了才回（ls／get 才不會還看到它）
            while any(w["name"] == id for w in _watch.ls(self._a.daemon)):
                if time.monotonic() > end:
                    raise Timeout("bp.rm", "watcher %s is still on the daemon table after %d s" % (id, RELEASE_WAIT_S), code="Timeout")
                time.sleep(0.1)
            return out
        spec = self._spec(id)
        out = (self._a.agent("hook", "rm", _hook(id)) if id in self._hooked()
               else Text("breakpoint %s was disabled; marked removed\n" % id))
        spec["removed"] = True
        self._write_spec(id, spec)
        return out

    def clear(self):
        """拿掉這隻身上的全部斷點（觸發器與看著它的觀察者；不碰別的 hook）。"""
        for r in self.ls(quiet=True):
            self.rm(r["id"])

    # ---- 改 ----
    def set(self, id, enabled=None, times=None, once=None):
        """改一個斷點（收 Breakpoint 或 id）：enabled（停用＝觸發器把 hook 拿下、設定留著；觀察者 aos-daemon-ctl stop。啟用＝裝回去／start）、times、once。
        改了 times／once 計數照留（停過幾次不歸零）。條件、事件、tool、every_ms、看誰改不了：同一個 id 重下 a.bp.add.<種類>(..., id=ID, replace=True)。
        回斷點物件（Breakpoint，跟 a.bp.add 回的同一種：屬性每次讀都重新查；要一份當下的 dict 用 a.bp.get(id)）。"""
        kind, id = self._kind(id)
        if times is not None and (not isinstance(times, int) or isinstance(times, bool) or times < 1):
            raise Failed("bp.set", "times must be a whole number >= 1")
        a = self._a
        if kind == WATCH:
            path = os.path.join(_watch.stack_dir(a.daemon, _watch.proc_of(id)), _watch.SPEC)
            spec = trigger.read_json(path, {}) or {}
            if times is not None:
                spec["times"] = times
            if once is not None:
                spec["once"] = bool(once)
            if enabled is not None:
                spec["enabled"] = bool(enabled)   # 表上的 phase 要等 daemon 收下信才變；enabled 以這裡記的為準
            spec["about"] = _watch.about(spec)
            trigger.write_json(path, spec)       # gdb_watch 每圈重讀 watch.json
            if enabled is not None:
                run(["aos-daemon-ctl", "--daemon", a.daemon, "start" if enabled else "stop", _watch.proc_of(id)], echo=True)
            return Breakpoint(self, id)
        spec = self._spec(id)
        if times is not None:
            spec["times"] = times
        if once is not None:
            spec["once"] = bool(once)
        spec["about"] = _about(spec)
        try:
            trigger.validate(spec)
        except trigger.Bad as e:
            raise Failed("bp.set", str(e)) from None
        hooked = self._hooked()
        undo = _Undo(a.stack, self._cell(id), (trigger.SPEC,))
        trigger.write_json(os.path.join(self._cell(id), trigger.SPEC), spec)   # handler 每次事件重讀 trigger.json
        on = id in hooked if enabled is None else bool(enabled)
        try:
            if on:
                self._install(id, spec, replace=True)  # times 變了 hook 的 condition 也跟著變（Argon A6），一律重裝
            elif id in hooked:
                a.agent("hook", "rm", _hook(id))
        except Failed:
            undo()                                 # 裝不上／拿不下＝設定放回原本的，不留改一半的（線 aos-bpfix-1119）
            raise
        return Breakpoint(self, id)

    # ---- 查 ----
    def ls(self, quiet=False):
        """這隻身上的全部斷點（號碼小的在前、自己取名的在後），一個一列：id、kind（種類：before_tool、tool_error…，觀察者是 watch）、how（hold／pause）、
        about、enabled、times、once、seen（看過幾次）、fired（停過幾次）、spent（once 用掉了）、last_error（條件最後一次壞掉的原因）、here（現在是不是停在它這裡）。"""
        here, hooked = self._here(), self._hooked(quiet=quiet)
        out = [self._trigger_row(i, here, hooked) for i in self._trigger_ids()]
        out += [self._watch_row(w, here) for w in _watch.ls(self._a.daemon) if self._a.name in (w.get("targets") or [])]
        return sorted(out, key=lambda r: _order(r["id"]))

    def get(self, id):
        """查一個斷點（收 Breakpoint 或 id）：ls 那一列，加上定義（sh／py 原文、tools）；觀察者另有 targets、every_ms、表上的 phase／pid、每個目標的數。"""
        kind, id = self._kind(id)
        if kind == WATCH:
            w = [w for w in _watch.ls(self._a.daemon) if w["name"] == id][0]
            row = self._watch_row(w, self._here())
            spec = trigger.read_json(os.path.join(_watch.stack_dir(self._a.daemon, _watch.proc_of(id)), _watch.SPEC), {}) or {}
            row.update(targets=w.get("targets"), every_ms=w.get("every_ms"), phase=w.get("phase"), pid=w.get("pid"),
                       per_target=w.get("per_target"), condition=_condition(spec))
            return row
        row = self._trigger_row(id, self._here(), self._hooked())
        spec = self._spec(id)
        row.update(tools=spec.get("tools"), condition=_condition(spec))
        return row

    # ---- 控制：resume、step、pause（預設等到停下才回：使用者 11-19 選「resume/step 自己等到停」；
    #      wait=False＝送出就回 Pending：使用者 11-20「回一個可以查的物件。用is_done()」「三個都加」）----
    def resume(self, wait=True):
        """繼續跑，等到下一次停下才回（像 gdb 的 continue）。回的是 why() 那份，第一行說停在哪（"stopped at breakpoint 1 (before_tool: write)"）。
        扣在斷點上：放行那一次（照原樣跑）；暫停著：aos-agent ctl resume；沒停著（例如剛 a.say 完）：什麼都不送，直接等它停。
        它不會停時不卡死：閒著（stage idle、信箱與 cur 都空、沒有在途的 pause）連續 a.bp.idle_s 秒＝回 "did not stop: idle"；
        行程不在＝回 "did not stop: not running"；等的時候每 a.bp.report_s 秒在 stderr 印一行現況；a.bp.timeout_s 有給才會逾時（丟 Timeout）。
        Ctrl-C＝只是不等了：agent 照跑、什麼都不留（先前 a.bp.step() 送出還沒套用的 pause 一併收回），回一句說明。
        wait=False：放行／ctl resume 送出就回 Pending，等的那段在背景跑；p.is_done() 問好了沒，p.wait() 回跟 wait=True 一樣的東西，
        p.cancel() 不等了（只是不等：送出的放行／resume／pause 不收回，跟 Ctrl-C 不同）。"""
        _check_wait(wait, "resume")
        h, sig0 = self.held(), self._sig()
        with _Defer() as d:
            if h is not None:
                self._release(h, "bp.resume")
            elif self._paused():
                self._resume_cmd()
        return self._finish("resume", wait, sig0, d.hit)

    def step(self, wait=True):
        """只走一格就再停（一格＝fsm 的一格：idle、think、wait、act 之一跑一次；wait 等腦時是 wait 一格接一格），等到停下才回（wait=False 見 resume）。
        暫停著：ctl resume，loop 一套用就馬上 ctl pause --no-wait（這一格做完、下一格開頭停）；
        扣在 before_tool 上：先 ctl pause --no-wait 再放行（那次工具照跑，這一格做完才停）；
        沒停著：ctl pause --no-wait（跑到這一格做完就停）。這一格裡又碰到別的斷點＝停在那裡（回的第一行說是哪個）。
        Ctrl-C＝不等了，這次送的 pause 收回（aos-agent ctl resume），agent 照跑。"""
        _check_wait(wait, "step")
        a = self._a
        h, sig0 = self.held(), self._sig()
        with _Defer() as d:
            if h is not None:
                pend = trigger.ctl_unapplied(a.stack)
                if pend and pend[1] == "pause":
                    own = pend[0]                    # 已經有一個還沒套用的 pause（先前的 step 或別人）：放行後這一格做完就停，不再多送
                else:
                    own = self._pause_cmd()
                self._release(h, "bp.step")
            elif self._paused():
                own = self._resume_then_pause()
            else:
                own = self._pause_cmd()
        return self._finish("step", wait, sig0, d.hit, own=own)

    def pause(self, wait=True):
        """現在停（不靠斷點）：aos-agent ctl pause --no-wait（這一格做完、下一格開頭停住），等到真的停下才回，回的跟 resume() 一樣（第一行說停在哪）。
        已經停著（暫停或扣在斷點上）＝什麼都不送，回現在停在哪。Ctrl-C＝不等了，但 pause 已經送出：這一格做完它就停。
        wait=False：pause 送出就回 Pending（已經停著＝回一個已經好了的）；見 resume。"""
        _check_wait(wait, "pause")
        if self.stopped():
            r = self._result("stopped", "already " + self._stopped_head(self.why()))
            return r if wait else Pending("a.bp.pause(wait=False)", self._a.name, value=r)
        sig0 = self._sig()
        with _Defer() as d:
            own = self._pause_cmd()
        return self._finish("pause", wait, sig0, d.hit, own=own)

    def _finish(self, what, wait, sig0, hit, own=None):
        """送完指令之後：wait＝在這裡等到停（_wait）；不等＝同一段等在背景執行緒跑（不印定期那一行），回 Pending。"""
        if wait:
            return self._wait(sig0, what, hit, own=own)
        return Pending("a.bp.%s(wait=False)" % what, self._a.name,
                       run=lambda cancel: self._wait(sig0, what, False, own=own, report=False, cancel=cancel))

    # ---- 停在哪、為什麼 ----
    def held(self):
        """扣在斷點上的那一次（gdb/hold.json，handler 還活著才算；其中 trigger 是 hook 名 gdb_<id>）；沒有＝None。"""
        return trigger.read_hold(self._a.stack)

    def stopped(self):
        """停著等檢閱沒：ctl pause 已套用（state.json 的 paused），或扣在斷點上（held）。"""
        st = trigger.read_json(os.path.join(self._a.stack, "state.json"), {}) or {}
        return st.get("paused") is True or self.held() is not None

    def why(self):
        """為什麼停：上一次 resume（經 aos.gdb，或在 shell 下 ctl resume 放行的）之後的字條（觸發器與觀察者的），
        加上現在是不是停著、扣在哪、字條是不是這一次的、扣住之後有沒有人下 ctl pause／stop。"""
        stack = self._a.stack
        notes = trigger.since_resume(trigger.read_log(stack))
        h = self.held()
        st = trigger.read_json(os.path.join(stack, "state.json"), {}) or {}
        paused = st.get("paused") is True or h is not None
        seq, cmd = trigger.ctl_doc(stack)
        last = notes[-1] if notes else None
        current = h is not None or bool(paused and last and last.get("ctl_seq") is not None and last.get("ctl_seq") == seq)
        pending = trigger.ctl_unapplied(stack) if h is not None else None
        return Why(self._a.name, paused, current, notes, held=h, pending=pending)

    def notes(self):
        """gdb/log.jsonl 全部（字條與 resume 紀錄，舊的在前）。"""
        return trigger.read_log(self._a.stack)

    def event(self):
        """停在觸發器上時，它成立的那個事件（小格的 hit.json，gdb_trigger 成立時寫的整份事件），照載入的 hook 宣告排好：宣告的欄位照順序、
        帶說明，沒宣告的另列（aos-gdb --hooks；沒載入＝照事件原本的順序）。不是停在觸發器上（沒停、觀察者、a.bp.pause()、step）＝一句說明。"""
        w = self.why()
        id = w.breakpoint
        if id is None:
            return Text("%s is not stopped at a breakpoint (a.bp.why() says where it is)\n" % self._a.name)
        path = os.path.join(self._cell(id), trigger.HIT)
        ev = trigger.read_json(path, None)
        if not isinstance(ev, dict):
            return Text("breakpoint %s has no saved event (a watcher has none; %s is not there)\n" % (id, path))
        show("# read %s" % path)
        return Text(decl.layout(ev, ev.get("event") or "?", " at breakpoint %s (%s)" % (id, _hook(id))) + "\n")

    # ---- 內部 ----
    def _cell(self, id):
        return os.path.join(self._a.stack, _hooks.CELLS, _hook(id))

    def _spec(self, id):
        spec = trigger.read_json(os.path.join(self._cell(id), trigger.SPEC), None)
        if not isinstance(spec, dict) or spec.get("removed"):
            raise Failed("bp", "%s has no breakpoint %s (a.bp.ls() lists them)" % (self._a.name, id), code="BreakpointMissing")
        return spec

    def _write_spec(self, id, spec):
        spec["about"] = _about(spec)
        try:
            trigger.validate(spec)
        except trigger.Bad as e:
            raise Failed("bp", str(e)) from None
        trigger.write_json(os.path.join(self._cell(id), trigger.SPEC), spec)

    def _hooked(self, quiet=True):
        """裝著的 gdb_ hook 的 id（啟用中的觸發器）。"""
        rows = json.loads(self._a.agent("hook", "ls", "--json", quiet=quiet))
        return {bp_id(r["name"]) for r in rows if r.get("name", "").startswith(trigger.PREFIX) and r["name"] != trigger.PREFIX}

    def _installed(self, id):
        """gdb_<id> 這個 hook 裝著沒（問不到＝當沒裝）。"""
        try:
            return id in self._hooked()
        except Failed:
            return False

    def _trigger_ids(self):
        """有設定、沒標 removed 的觸發器 id（啟用與停用的都算）。"""
        cells = os.path.join(self._a.stack, _hooks.CELLS)
        try:
            names = os.listdir(cells)
        except FileNotFoundError:
            return set()
        out = set()
        for n in names:
            if not n.startswith(trigger.PREFIX) or n == trigger.PREFIX:
                continue
            spec = trigger.read_json(os.path.join(cells, n, trigger.SPEC), None)
            if isinstance(spec, dict) and not spec.get("removed"):
                out.add(bp_id(n))
        return out

    def _ids(self, watchers_on_daemon=False):
        ids = self._trigger_ids()
        for w in _watch.ls(self._a.daemon):
            if watchers_on_daemon or self._a.name in (w.get("targets") or []):
                ids.add(w["name"])
        return ids

    def _kind(self, id):
        """Breakpoint／id → ("trigger" 或 "watch", 整好的 id)；這隻身上沒有＝Failed（code BreakpointMissing）。"""
        id = _norm(id)
        if id in self._trigger_ids():
            return "trigger", id
        if any(w["name"] == id and self._a.name in (w.get("targets") or []) for w in _watch.ls(self._a.daemon)):
            return WATCH, id
        raise Failed("bp", "%s has no breakpoint %s (a.bp.ls() lists them)" % (self._a.name, id), code="BreakpointMissing")

    def _install(self, id, spec, replace):
        # hold：不限時（等人放行）；pause：有上限。handler（gdb_trigger）stdout 什麼都不印、自己的錯只 warning 退 0（11-21 起 hook 沒有
        # intercept／on_error 這兩個選項，「不讀回話」「失敗不擋 agent」改由 handler 自己保證；「放行但那次工具不跑」使用者 11-19 說「不該有這個方法」）。
        how, tools = spec["how"], spec.get("tools")
        limit = 0 if how == "hold" else 40000 if spec["kind"] in ("sh", "py") else 15000
        args = ["hook", "add", "--event", spec["event"], "--name", _hook(id), "--path-json", json.dumps(HANDLER),
                "--timeout-ms", limit]
        if tools and spec.get("times", 1) == 1 and spec["event"] in NAMED and spec.get("field", "name") == "name":
            # 只篩工具名、不數連續時才交給 hook 的 condition 省行程（Argon A6）；只有 agent 一家自己的點會照 condition 篩
            for t in tools:
                args += ["--condition", t]
        if replace:
            args.append("--replace")
        self._a.agent(*args)

    def _here(self):
        """現在停在哪個斷點的 id（扣住的那個，或暫停著且最後一張字條是這次的）；不是停在斷點上＝None。"""
        return self.why().breakpoint

    def _trigger_row(self, id, here, hooked):
        cell = self._cell(id)
        spec = trigger.read_json(os.path.join(cell, trigger.SPEC), {}) or {}
        count = trigger.read_json(os.path.join(cell, trigger.COUNT), {}) or {}
        return {"id": id, "kind": _kind_of(spec), "how": spec.get("how"), "about": spec.get("about"),
                "enabled": id in hooked, "times": spec.get("times", 1), "once": spec.get("once", False),
                "seen": count.get("seen", 0), "streak": count.get("streak", 0), "fired": count.get("fired", 0),
                "spent": bool(spec.get("once") and count.get("fired")), "last_error": count.get("last_error"), "here": here == id}

    def _watch_row(self, w, here):
        mine = (w.get("per_target") or {}).get(self._a.name) or {}
        spec = trigger.read_json(os.path.join(_watch.stack_dir(self._a.daemon, _watch.proc_of(w["name"])), _watch.SPEC), {}) or {}
        return {"id": w["name"], "kind": WATCH, "how": "pause", "about": w.get("about"),
                "enabled": spec.get("enabled", True), "times": spec.get("times", 1), "once": spec.get("once", False),
                "seen": mine.get("seen", 0), "streak": mine.get("streak", 0), "fired": mine.get("fired", 0),
                "spent": bool(spec.get("once") and mine.get("fired")), "last_error": mine.get("last_error"), "here": here == w["name"]}

    def _release(self, h, what):
        """寫放行單（gdb/release.json，token 同 hold.json）、等 handler 收到（扣住結束）；那一次照原樣跑。"""
        a = self._a
        show("$ release %s (writes %s)" % (h.get("trigger"), os.path.join(a.stack, trigger.LOG_DIR, trigger.RELEASE)))
        trigger.write_release(a.stack, h["token"])
        end = time.monotonic() + RELEASE_WAIT_S
        while time.monotonic() < end:
            now = self.held()
            if now is None or now.get("token") != h["token"]:
                break
            time.sleep(0.05)
        else:
            raise Timeout(what, "the hold did not end within %d s (is %s still running?)" % (RELEASE_WAIT_S, a.name), code="Timeout")
        # 字條由 handler 自己寫（resume 或 hold_ended，帶 token；Argon A2）：沒看到 resume＝它不是被這張放行單放的
        mine = [n for n in trigger.read_log(a.stack) if n.get("token") == h["token"] and n.get("kind") in ("resume", "hold_ended")]
        if not mine or mine[-1]["kind"] != "resume":
            why = mine[-1].get("why") if mine else "no note from the trigger"
            raise Failed(what, "the hold ended without this release (%s); the call did not go on" % why)
        try:
            os.remove(os.path.join(a.stack, trigger.LOG_DIR, trigger.RELEASE))
        except FileNotFoundError:
            pass

    def _state(self):
        return trigger.read_json(os.path.join(self._a.stack, "state.json"), {}) or {}

    def _paused(self):
        return self._state().get("paused") is True

    def _applied(self):
        """loop 最後套用的 ctl seq（state_flux.json）。"""
        v = (trigger.read_json(os.path.join(self._a.stack, "state_flux.json"), {}) or {}).get("ctl_seq")
        return v if isinstance(v, int) and not isinstance(v, bool) else None

    def _sig(self):
        """現在停的「是哪一次」：(扣住的 token, 暫停著沒, 套用到的 ctl seq)。跟開始時不一樣而且停著＝新的一次停。"""
        h = self.held()
        return (h.get("token") if h else None, self._paused(), self._applied())

    def _pause_cmd(self):
        """aos-agent ctl pause --no-wait（自己一個 session：Ctrl-C 不會打斷它）；回它寫的 seq，記進 _mine。"""
        a = self._a
        a.agent("ctl", "pause", "--no-wait", detach=True)
        seq, cmd = trigger.ctl_doc(a.stack)
        if cmd == "pause" and seq is not None:
            self._mine.add(seq)
        return seq

    def _resume_cmd(self):
        """aos-agent ctl resume（等套用），字條記一筆 resume（why() 從這之後算）。"""
        a = self._a
        a.agent("ctl", "resume", detach=True)
        trigger.append_log(a.stack, {"kind": "resume", "at": trigger.now(), "by": "repl"})

    def _resume_then_pause(self):
        """step 從暫停起：ctl resume 一被 loop 套用（state_flux 的 ctl_seq 追上它）就馬上 ctl pause --no-wait，
        這一格做完、下一格開頭停。ctl 窗只放得下一道指令，兩道不能一起寫，所以只能這樣接力；空檔約是 pause 那條指令起來的時間（實測約 0.04 秒）。"""
        a = self._a
        before, _ = trigger.ctl_doc(a.stack)
        argv = ["aos-agent", "--daemon", a.daemon, "--target", a.name, "ctl", "resume"]
        show("$ " + " ".join(argv))
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                             start_new_session=True)
        end = time.monotonic() + RELEASE_WAIT_S
        seq = None
        while time.monotonic() < end:
            s, cmd = trigger.ctl_doc(a.stack)
            if seq is None and cmd == "resume" and s is not None and (before is None or s > before):
                seq = s
            if seq is not None and (self._applied() or -1) >= seq:
                break
            if p.poll() is not None:
                break
            time.sleep(0.005)
        own = self._pause_cmd()
        _, err = p.communicate()
        if p.returncode:
            lines = [x for x in (err or "").splitlines() if x.strip()]
            raise Failed(lines[-1] if lines else "aos-agent: ctl resume exited %d" % p.returncode, argv=argv, exit=p.returncode)
        trigger.append_log(a.stack, {"kind": "resume", "at": trigger.now(), "by": "repl", "for": "step"})
        return own

    def _body(self):
        """不是停著時它在做什麼：gone（行程不在）、idle（stage idle、信箱 new 與 cur 都空、沒有還沒套用的 pause）、busy。"""
        st = self._state()
        if not trigger.alive(st.get("pid")):
            return "gone"
        if trigger.ctl_unapplied(self._a.stack):
            return "busy"
        stack = self._a.stack
        try:
            with open(os.path.join(stack, "stage.txt"), encoding="utf-8") as f:
                stage = f.read().strip()
        except OSError:
            return "busy"                          # 沒有 stage.txt（例如 eca 身）：認不出閒著，只靠定期那一行與 timeout_s
        if stage != "idle":
            return "busy"
        for box in ("new", "cur"):
            try:
                if any(not n.startswith(".") for n in os.listdir(os.path.join(stack, "queue", box))):
                    return "busy"
            except FileNotFoundError:
                pass
        return "idle"

    def _wait(self, sig0, what, hit, own=None, report=True, cancel=None):
        """resume／step／pause 共用的等：停著而且跟開始時不是同一次＝停了；閒著或行程不在連續 idle_s 秒＝沒停；Ctrl-C＝不等了。report＝印定期那一行。
        cancel（Pending 的 threading.Event）設了＝不等了（outcome cancelled）：只是不再等，送出的東西一樣都不收回（step 送的 pause 照留）。"""
        a = self._a
        start = last = time.monotonic()
        quiet = None
        try:
            if hit:
                raise KeyboardInterrupt
            while True:
                if self.stopped():
                    sig = self._sig()
                    if sig != sig0:
                        if (what == "resume" and sig[0] is None and sig[1] and sig[2] in self._mine
                                and trigger.ctl_doc(a.stack)[0] == sig[2]):
                            # 先前 a.bp.step() 扣在別的斷點時送出的 pause，現在才套用：不是這次要的停，收回、接著等
                            self._mine.discard(sig[2])
                            self._resume_cmd()
                            sig0 = self._sig()
                            continue
                        return self._stopped(what, own)
                if cancel is not None and cancel.is_set():
                    return self._result("cancelled", "stopped waiting (cancel()); nothing is taken back: what a.bp.%s() sent stays sent" % what)
                now = time.monotonic()
                body = self._body()
                if body in ("idle", "gone"):
                    quiet = quiet if quiet and quiet[0] == body else (body, now)
                    if now - quiet[1] >= self.idle_s:
                        return self._result(body, None)
                else:
                    quiet = None
                if self.timeout_s is not None and now - start >= self.timeout_s:
                    self._take_back(what)
                    raise Timeout("a.bp.%s" % what, "%s did not stop in %g s (a.bp.timeout_s); it goes on as it was" % (a.name, self.timeout_s),
                                  code="Timeout")
                if report and self.report_s and now - last >= self.report_s:
                    last = now
                    sys.stderr.write("# a.bp.%s: still waiting for %s to stop (%d s): %s; Ctrl-C stops waiting, %s goes on\n"
                                     % (what, a.name, now - start, self._doing(), a.name))
                    sys.stderr.flush()
                time.sleep(POLL_S)
        except KeyboardInterrupt:
            if self.stopped() and self._sig() != sig0:
                return self._stopped(what, own)
            took = self._take_back(what)
            if what == "pause":
                tail = "; the pause is sent already: %s stops when this step ends" % a.name
            else:
                tail = "; the pause a.bp.step() sent is taken back" if took else ""
            return self._result("interrupted", "stopped waiting (Ctrl-C); %s goes on as it was%s" % (a.name, tail))

    def _take_back(self, what):
        """不等了（Ctrl-C、逾時）時收回自己送出、還沒套用的 pause（pause 不收：要停是使用者要的）。回收回了沒。"""
        if what == "pause":
            return False
        pend = trigger.ctl_unapplied(self._a.stack)
        if not pend or pend[1] != "pause" or pend[0] not in self._mine or self.held() is not None:
            return False
        argv = ["aos-agent", "--daemon", self._a.daemon, "--target", self._a.name, "ctl", "resume"]
        show("$ " + " ".join(argv) + "   (in the background: takes back the pause)")
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self._mine.discard(pend[0])
        return True

    def _doing(self):
        """定期那一行：在哪一格、信箱幾封。"""
        stack = self._a.stack
        try:
            with open(os.path.join(stack, "stage.txt"), encoding="utf-8") as f:
                stage = f.read().strip() or "?"
        except OSError:
            stage = "?"
        try:
            n = len([x for x in os.listdir(os.path.join(stack, "queue", "new")) if not x.startswith(".")])
        except FileNotFoundError:
            n = 0
        return "at %s, %d letter(s) queued" % (stage, n)

    def _stopped(self, what, own):
        """停了：自己送的 pause 停下的（step／pause）留一張字條（by step／pause，帶那個 seq），回 why() 加上第一行。"""
        a = self._a
        if own is not None and self.held() is None and self._applied() == own and trigger.ctl_doc(a.stack)[0] == own:
            trigger.append_log(a.stack, {"kind": "stop", "at": trigger.now(), "by": what if what in ("step", "pause") else "repl",
                                         "trigger": None, "ctl_seq": own,
                                         "about": "a.bp.step(): one step" if what == "step" else "a.bp.pause()",
                                         "detail": {"stage": self._stage()}})
            self._mine.discard(own)
        w = self.why()
        return self._result("stopped", self._stopped_head(w), w)

    def _stage(self):
        try:
            with open(os.path.join(self._a.stack, "stage.txt"), encoding="utf-8") as f:
                return f.read().strip() or None
        except OSError:
            return None

    def _stopped_head(self, w):
        """第一行：停在哪。"""
        if w.held:
            d = w.held.get("detail", {})
            return "stopped at breakpoint %s (%s: %s)" % (w.breakpoint, self._label(w.breakpoint, w.held),
                                                          d.get(self._field(w.breakpoint)) or d.get("name") or d.get("letter")
                                                          or w.held.get("event"))
        last = w.notes[-1] if w.notes else {}
        stage = self._stage() or "?"
        if w.breakpoint is not None:
            d = last.get("detail", {})
            return "stopped at breakpoint %s (%s: %s), before %s" % (
                w.breakpoint, self._label(w.breakpoint, last),
                d.get(self._field(w.breakpoint)) or d.get("name") or d.get("code") or d.get("letter") or d.get("target")
                or last.get("event"), stage)
        if w.current and last.get("by") == "step":
            return "stopped after one step, before %s" % stage
        if w.current and last.get("by") == "pause":
            return "stopped before %s (a.bp.pause())" % stage
        return "stopped before %s (paused, not by a breakpoint)" % stage

    def _label(self, id, note):
        """第一行括號裡的種類：觀察者＝watch；觸發器讀它小格的設定（拿掉了也讀得到），讀不到＝字條上的事件。"""
        if note.get("by") == "watch":
            return WATCH
        spec = trigger.read_json(os.path.join(self._cell(id), trigger.SPEC), None)
        return _kind_of(spec) if isinstance(spec, dict) else note.get("event")

    def _field(self, id):
        """觸發器比主詞用的欄位（宣告給的、不是 name 才記在 trigger.json 的 field）；沒有＝None。"""
        spec = trigger.read_json(os.path.join(self._cell(id), trigger.SPEC), None)
        return spec.get("field") if isinstance(spec, dict) else None

    def _result(self, outcome, head, w=None):
        """resume／step／pause 回的東西：why() 那份，outcome＝stopped／idle／gone／interrupted，第一行 head。"""
        a = self._a
        w = w or self.why()
        if head is None:
            head = {"idle": "%s did not stop: it is idle (nothing queued, no step running); give it work (a.say(...)) and a.bp.resume() waits again" % a.name,
                    "gone": "%s did not stop: it is not running (its loop process is gone: stopped, asleep, or removed); aos-agent ctl state says why" % a.name}[outcome]
        w.outcome, w.head = outcome, head
        return w


class _Undo:
    """下斷點之前記下小格的原狀，裝不上時 undo() 放回去：小格（或它上面那層 hookeds/）原本不在＝整夾拿掉；原本在＝names 這幾個檔放回原本的內容
    （原本沒有的刪掉）。只動這次會寫的那一夾，不碰別的。"""

    def __init__(self, stack, cell, names):
        self.top = None                                   # 這次會新建的最上層那一夾（在 stack 之下）；None＝小格已經在
        p = os.path.abspath(cell)
        stack = os.path.abspath(stack)
        while p != stack and os.path.dirname(p) != p and not os.path.exists(p):
            self.top, p = p, os.path.dirname(p)
        self.files = {}
        if self.top is None:
            for n in names:
                path = os.path.join(cell, n)
                try:
                    with open(path, "rb") as f:
                        self.files[path] = f.read()
                except FileNotFoundError:
                    self.files[path] = None

    def __call__(self):
        if self.top is not None:
            shutil.rmtree(self.top, ignore_errors=True)
            return
        for path, data in self.files.items():
            if data is None:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
            else:
                tmp = "%s.%d.undo" % (path, os.getpid())
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, path)


def _condition(spec):
    if spec.get("kind") == "sh":
        return {"sh": spec.get("sh")}
    if spec.get("kind") == "py":
        return {"py": spec.get("py")}
    return {"kind": spec.get("kind")}


def _about(spec):
    who = " or ".join(spec["tools"]) if spec.get("tools") else None
    what = {"before_tool": "tool %s is about to run" % (who or "any"), "after_tool": "tool %s finished" % (who or "any"),
            "before_queue": "a letter is about to be taken in", "brain_failed": "the brain failed%s" % (" with %s" % who if who else ""),
            "tool_added": "tool %s was added" % (who or "any")}.get(
        spec["event"], "event %s%s" % (spec["event"], " with %s %s" % (spec.get("field") or "name", who) if who else ""))
    cond = {"always": "", "tool_error": " with an error (exit code not 0, or timed out)",
            "sh": " and sh `%s` exits 0" % spec.get("sh"),
            "py": " and the py condition is true"}[spec["kind"]]
    times = " (%d times in a row)" % spec["times"] if spec.get("times", 1) > 1 else ""
    return what + cond + times + (", once" if spec.get("once") else "")


def _norm(id):
    """使用者給的斷點（Breakpoint、號碼、數字字串、自己取的名字）→ id：號碼＝int，名字＝str；認不得＝Failed。"""
    if isinstance(id, Breakpoint):
        return id.id
    if isinstance(id, int) and not isinstance(id, bool) and id >= 1:
        return id
    if isinstance(id, str) and id and "/" not in id and not id.startswith(".") and id.strip() == id:
        return int(id) if id.isascii() and id.isdigit() else id
    raise Failed("bp", "a breakpoint is what a.bp.add.<kind>(...) returned, its number (such as 3), or a name you gave it with id=; "
                       "got %r (a.bp.ls() lists them)" % (id,), code="ArgumentsBad")


def _order(id):
    """ls 的順序：號碼由小到大，自己取名的排在後面。"""
    return (1, 0, id) if isinstance(id, str) else (0, id, "")


def _hook(id):
    """斷點 id → 觸發器的 hook 名（也是小格夾名）gdb_<id>：號碼補零到 4 位（gdb_0002，使用者 11-20 選「斷點號碼檔名補零」），名字原樣。"""
    return trigger.PREFIX + bp_name(id)


def _kind_of(spec):
    """觸發器設定 → 種類（a.bp.add 的那個名字）：tool_error，否則就是事件名。"""
    return TOOL_ERROR if spec.get("kind") == "tool_error" else spec.get("event")


def _check_wait(wait, what):
    if not isinstance(wait, bool):
        raise Failed("a.bp.%s" % what, "wait must be True (wait until it stops) or False (return at once with something to ask is_done())",
                     code="ArgumentsBad")
