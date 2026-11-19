"""aos.gdb - aos-gdb 的 Python 庫（在 python REPL 裡用）：接上一隻已在跑的 agent（a.xxx＝aos-agent xxx 的薄殼），斷點全在 a.bp 底下（增刪改查、停、續、為什麼停）。

使用者 11-19：「先用python產出一份粗定義，然後進入python repl，用aos-gdb庫，下斷點，然後跑。」斷點＝「特定條件發生時，暫停loop或fsm，
停下來等待檢閱」，「能把他停下來的都可以」，「hook不用動」；第二版：「stop_before_tool不就是在工具開始前停下嗎？丙可以繼續」。
介面（線 aosgdb-api-1119）：「斷點這塊，我覺得他的架構就是以斷點為核心， 增刪改查。然後a.xxx這塊，感覺就是aos-agent xxxx。……
或者說他應該是a.bp.stop(),a.bp.resume()。對斷點增刪改查，包括以id查詢斷點...」。
圖紙：thinking/2026-11/19/aos-gdb-1119（乙案）、08-Argon審與採納、aos-gdb-lib-第一版.md、aos-gdb-lib-第二版.md（末節＝這次的介面）。

兩層：
    a.xxx＝aos-agent xxx（a.say、a.listen、a.ctl、a.state、a.agent）與讀 stack 的檔（a.where、a.history、a.observed、a.file…）；a 上沒有斷點的東西。
    a.bp＝斷點（class Breakpoints）：add／rm／set／ls／get（每個斷點一個 id，str）、stop／resume／skip、why／held／stopped／wait_stopped、notes、clear。
斷點兩種，同一套 id：
    觸發器（a.bp.add("before_tool", ...) 等事件）：agent 身上一個 hook（gdb_<id>），事件來了判條件。
        事件還沒發生（before_tool、before_queue）＝扣住（hold）：hook handler 自己不回，工具還沒跑；a.bp.resume() 照原樣跑、a.bp.skip() 那次工具不跑。
        其他事件（已經發生）＝暫停（pause）：ctl pause，loop 在這一格做完、下一格開頭停住；a.bp.resume()＝ctl resume。
    觀察者（a.bp.add("watch", ...)）：另一支掛在 daemon 表上的 proc（gdbw_<id>），每隔一陣子看目標的檔，成立就 ctl pause 目標（晚一格）（aos.gdb.watcher）。

薄殼：每個方法背後是一條 aos 指令（aos-agent …、aos-daemon-ctl …）或讀寫 stack 裡的一個檔；g.echo 為真時先印出那條指令，REPL 和 shell 可以混著用
（觸發器掛在 agent 的 stack、觀察者掛在 daemon 表上，REPL 關了照樣在；停住的那隻用 `aos-agent ctl resume` 也續得了，扣住的也是）。

    import aos.gdb as g
    a = g.attach("ann", daemon=".stack")                  # daemon 預設 $AOS_DAEMON
    b = a.bp.add("before_tool", tool="write")             # write 要跑之前扣住；回 "before_tool_1"
    a.bp.add("after_tool", tool="write")                  # write 跑完、腦還沒看到結果就停
    a.bp.add("tool_error", times=2)                       # 任何工具連續回錯兩次
    a.bp.add("after_tool", sh="grep -q secret || exit 10")              # 自訂條件：一段 shell（事件 JSON 在 stdin，退 0＝算）
    a.bp.add("before_tool", py=lambda ev: ev["arguments"].get("path", "").endswith(".env"))
    a.bp.add("watch", py=lambda t: len(t.history(0)) > 20)              # 觀察者：另一支 proc 每 0.5 秒看一次；回 "watch_1"
    a.say("hi"); a.bp.wait_stopped(); a.bp.why(); a.where(); a.history(3)
    a.bp.resume()      # 或 a.bp.skip()（扣在工具前：那次不跑）
    a.bp.ls(); a.bp.get(b); a.bp.set(b, enabled=False); a.bp.rm(b); a.bp.clear()
    a.bp.stop(); a.bp.resume()                            # 不靠斷點：現在就停／續

觸發器的檔、字條、扣住檔、條件怎麼判在 aos.gdb.trigger；hook handler 是 lib/tools/agent/gdb_trigger；觀察者在 aos.gdb.watcher 與 lib/tools/agent/gdb_watch。"""
import json
import os
import time

from aos.agentlib import hooks as _hooks
from aos.gdb import trigger, watcher as _watch
from aos.gdb.look import Look, Text, Why, bp_id, run, sh, Failed  # noqa: F401  （sh、Failed、Text 給 REPL 用）

echo = True                                       # 為真＝每條指令先印一行 "$ ..."（看得到背後是哪條 shell）
HANDLER = {"$env": "AOS_HOME", "$path": "/lib/tools/agent/gdb_trigger"}
NAMED = tuple(e for e, d in _hooks.EVENTS.items() if d["condition"] == "name")   # tool= 能篩的事件（brain_failed 的 name＝錯誤代號）
EVENTS = tuple(e for e in _hooks.EVENTS if e != _hooks.CLOCK_EVENT)               # on_clock 要給間隔，不是「事件發生」，不收
TOOL_ERROR, WATCH = "tool_error", "watch"         # a.bp.add 的 on 除了 EVENTS 之外收這兩個
ONS = EVENTS + (TOOL_ERROR, WATCH)
RELEASE_WAIT_S = 10


def attach(name, daemon=None):
    """接上一隻已經掛在 daemon 上的 agent（不改它任何東西）：記住名字、daemon、stack 在哪，確認它的定義宣告了 hooks。"""
    return Agent(name, daemon)


def _daemon(daemon):
    d = daemon or os.environ.get("AOS_DAEMON")
    if not d:
        raise Failed("aos.gdb", "no daemon given and AOS_DAEMON is not set (daemon='.stack')")
    return os.path.abspath(d)


class Agent(Look):
    """a.xxx＝aos-agent --daemon D --target NAME xxx 的薄殼，加上讀 stack 的檔（Look）；斷點在 a.bp。"""

    def __init__(self, name, daemon=None):
        self.name, self.daemon = name, _daemon(daemon)
        who = self._json(["ctl", "state", "--json", "who"]).get("who", {})
        stack = who.get("stack")
        if not isinstance(stack, str) or not stack:
            raise Failed("attach", "cannot tell where the stack of %s is (aos-agent ctl state who)" % name)
        self.stack = stack
        self.agent("hook", "ls", quiet=True)      # 定義沒宣告 hooks＝這裡就說 HooksMissing（Argon A2）
        self.bp = Breakpoints(self)

    def __repr__(self):
        return "<aos.gdb agent %s (stack %s); breakpoints: a.bp>" % (self.name, self.stack)

    def agent(self, *args, quiet=False):
        """aos-agent --daemon D --target NAME ARGS...；回 stdout（Text）。退非 0 丟 Failed（帶它最後一行錯誤）。"""
        return run(["aos-agent", "--daemon", self.daemon, "--target", self.name] + [str(x) for x in args], echo=echo and not quiet)

    def _json(self, args):
        return json.loads(self.agent(*args, quiet=True))

    def say(self, text):
        """aos-agent say；回信名（str，交給 listen(letter=...) 等那一封的回答）。"""
        return Text(self.agent("say", text).strip())

    def listen(self, timeout_s=20, letter=None):
        """aos-agent listen：等它的回答；letter＝say 回的信名：等那一封的。"""
        return self.agent("listen", "--timeout-s", timeout_s, *(["--letter", str(letter).strip()] if letter else []))

    def ctl(self, *args):
        """aos-agent ctl ARGS...（例 a.ctl("pause")、a.ctl("where")）。停在斷點的事用 a.bp（a.bp.stop()／a.bp.resume() 會留字條）。"""
        return self.agent("ctl", *args)


class Breakpoints:
    """a.bp：以斷點為核心——增 add、刪 rm、改 set、查 ls／get（都以 id，str）；停 stop、續 resume、跳過 skip；
    停在哪、為什麼 why／held、停了沒 stopped、等到停下來 wait_stopped；字條 notes；全拿掉 clear。"""

    def __init__(self, agent):
        self._a = agent

    def __repr__(self):
        rows = self.ls(quiet=True)
        head = "<a.bp of %s: %d breakpoint(s); add / rm / set / ls / get, stop / resume / skip, why / wait_stopped>" % (self._a.name, len(rows))
        return "\n".join([head] + ["  %s%s  %s%s" % (r["id"], "" if r["enabled"] else " (disabled)", r["about"], "  <- stopped here" if r["here"] else "")
                                   for r in rows])

    # ---- 增 ----
    def add(self, on, tool=None, sh=None, py=None, times=1, once=False, name=None, replace=False, every_ms=500, also=()):
        """下一個斷點，回它的 id（str，例 "before_tool_1"、"watch_1"；name＝自己取）。on＝什麼時候判：
          hook 事件（before_tool、after_tool、before_queue、brain_failed、tool_added…）：觸發器，before_tool／before_queue＝扣住（事件還沒發生），其他＝那一格做完暫停；
          "tool_error"＝after_tool 且工具回錯（退出碼不是 0 或逾時）；
          "watch"＝觀察者：另一支 proc 每 every_ms 看一次（also＝順便也看這些 agent，同一個 daemon），成立就暫停（晚一格）。
        條件：不給＝事件來了就算（watch 一定要給）；sh＝一段 shell（觸發器：事件 JSON 在 stdin；觀察者：cwd＝目標 stack；退 0＝算、10＝不算、其他＝條件壞了）；
        py＝觸發器是 f(ev)／運算式字串（變數 ev），觀察者是 f(t)／運算式字串（變數 t，t.mem 跨圈留著）。
        tool＝只算這個（或這些）工具（brain_failed 是錯誤代號）；times＝連續幾次才算；once＝只停一次；replace＝同 id 已有就換掉。"""
        a = self._a
        if on not in ONS:
            raise Failed("bp.add", "on must be one of %s" % ", ".join(ONS))
        name = None if name is None else str(name)
        if on == WATCH:
            if tool:
                raise Failed("bp.add", "tool= does not work on watch (a watcher looks at files, not at one event)")
            have = self._ids(watchers_on_daemon=True)
            short = name or _free(WATCH, have)
            if short in self._trigger_ids():
                raise Failed("bp.add", "%s already has a trigger breakpoint %s (a.bp.rm it first)" % (a.name, short))
            return str(_watch.add(a.daemon, [a.name] + list(also), sh=sh, py=py, times=times, once=once, every_ms=every_ms,
                                  name=short, replace=replace, echo=echo))
        if also or every_ms != 500:
            raise Failed("bp.add", "also= and every_ms= only work on watch")
        error = on == TOOL_ERROR
        event = "after_tool" if error else on
        tools = [tool] if isinstance(tool, str) else (list(tool) if tool else None)
        if tools and event not in NAMED:
            raise Failed("bp.add", "tool= only works on %s (event %s has no tool name)" % (", ".join(NAMED + (TOOL_ERROR,)), event))
        if sum(bool(x) for x in (sh, py is not None, error)) > 1:
            raise Failed("bp.add", "give one condition: sh or py (tool_error is a condition already)")
        spec = {"kind": "sh" if sh else "py" if py is not None else "tool_error" if error else "always",
                "event": event, "how": trigger.how(event), "tools": tools, "times": times, "once": bool(once),
                "agent": a.name, "daemon": a.daemon}
        if sh:
            spec["sh"] = sh
        if py is not None:
            try:
                spec["py"] = trigger.pack_py(py)
            except trigger.Bad as e:
                raise Failed("bp.add", str(e)) from None
        have = self._ids(watchers_on_daemon=True)
        short = name or _free(on, have)
        if short in have and not replace:
            raise Failed("bp.add", "%s already has a breakpoint %s (replace=True to replace it)" % (a.name, short))
        if short not in self._trigger_ids() and short in have:
            raise Failed("bp.add", "%s is a watcher on this daemon (a.bp.rm it first)" % short)
        cell = self._cell(short)
        self._write_spec(short, spec)
        trigger.write_json(os.path.join(cell, trigger.COUNT), {})      # 重下＝重新數
        self._install(short, spec, replace=True)
        return short

    # ---- 刪 ----
    def rm(self, id):
        """拿掉一個斷點。觸發器：aos-agent hook rm gdb_ID（小格裡的設定與計數留著給人看，標成 removed）；正扣在它上面的那一次不受影響，
        照樣等 a.bp.resume()／a.bp.skip()。觀察者：aos-daemon-ctl rm gdbw_ID（先停、等行程退出、再從表上拿掉；它也看別隻的話別隻也不看了）。"""
        kind = self._kind(id)
        if kind == WATCH:
            out = _watch.rm(self._a.daemon, id, echo=echo)
            end = time.monotonic() + RELEASE_WAIT_S   # rm 是寄信給 daemon；等表上真的沒了才回（ls／get 才不會還看到它）
            while any(w["name"] == id for w in _watch.ls(self._a.daemon)):
                if time.monotonic() > end:
                    raise Failed("bp.rm", "watcher %s is still on the daemon table after %d s" % (id, RELEASE_WAIT_S))
                time.sleep(0.1)
            return out
        spec = self._spec(id)
        out = self._a.agent("hook", "rm", trigger.PREFIX + id) if id in self._hooked() else Text("%s was disabled; marked removed\n" % id)
        spec["removed"] = True
        self._write_spec(id, spec)
        return out

    def clear(self):
        """拿掉這隻身上的全部斷點（觸發器與看著它的觀察者；不碰別的 hook）。"""
        for r in self.ls(quiet=True):
            self.rm(r["id"])

    # ---- 改 ----
    def set(self, id, enabled=None, times=None, once=None):
        """改一個斷點：enabled（停用＝觸發器把 hook 拿下、設定留著；觀察者 aos-daemon-ctl stop。啟用＝裝回去／start）、times、once。
        改了 times／once 計數照留（停過幾次不歸零）。條件、事件、tool、every_ms、看誰改不了：同一個 id 重下 a.bp.add(..., name=ID, replace=True)。回改完的 get(id)。"""
        kind = self._kind(id)
        if times is not None and (not isinstance(times, int) or isinstance(times, bool) or times < 1):
            raise Failed("bp.set", "times must be a whole number >= 1")
        a = self._a
        if kind == WATCH:
            path = os.path.join(_watch.stack_dir(a.daemon, _watch.PREFIX + id), _watch.SPEC)
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
                run(["aos-daemon-ctl", "--daemon", a.daemon, "start" if enabled else "stop", _watch.PREFIX + id], echo=echo)
            return self.get(id)
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
        trigger.write_json(os.path.join(self._cell(id), trigger.SPEC), spec)   # handler 每次事件重讀 trigger.json
        on = id in self._hooked() if enabled is None else bool(enabled)
        if on:
            self._install(id, spec, replace=True)  # times 變了 hook 的 condition 也跟著變（Argon A6），一律重裝
        elif id in self._hooked():
            a.agent("hook", "rm", trigger.PREFIX + id)
        return self.get(id)

    # ---- 查 ----
    def ls(self, quiet=False):
        """這隻身上的全部斷點，一個一列：id、kind（trigger／watch）、on、how（hold／pause）、about、enabled、times、once、
        seen（看過幾次）、fired（停過幾次）、spent（once 用掉了）、last_error（條件最後一次壞掉的原因）、here（現在是不是停在它這裡）。"""
        here, hooked = self._here(), self._hooked(quiet=quiet)
        out = [self._trigger_row(i, here, hooked) for i in sorted(self._trigger_ids())]
        out += [self._watch_row(w, here) for w in _watch.ls(self._a.daemon) if self._a.name in (w.get("targets") or [])]
        return out

    def get(self, id):
        """以 id 查一個斷點：ls 那一列，加上定義（sh／py 原文、tools）；觀察者另有 targets、every_ms、表上的 phase／pid、每個目標的數。"""
        if self._kind(id) == WATCH:
            w = [w for w in _watch.ls(self._a.daemon) if w["name"] == id][0]
            row = self._watch_row(w, self._here())
            spec = trigger.read_json(os.path.join(_watch.stack_dir(self._a.daemon, _watch.PREFIX + id), _watch.SPEC), {}) or {}
            row.update(targets=w.get("targets"), every_ms=w.get("every_ms"), phase=w.get("phase"), pid=w.get("pid"),
                       per_target=w.get("per_target"), condition=_condition(spec))
            return row
        row = self._trigger_row(id, self._here(), self._hooked())
        spec = self._spec(id)
        row.update(tools=spec.get("tools"), condition=_condition(spec))
        return row

    # ---- 停、續、跳過 ----
    def stop(self):
        """現在就停（不靠斷點）：aos-agent ctl pause（loop 這一格做完、下一格開頭停住，最多等 5 秒套用），回那條指令的一行結果。
        已經扣在斷點上＝已經停著，不再送 pause（送了會在放行後再停一次），回一行說明。"""
        a = self._a
        h = self.held()
        if h is not None:
            return Text("%s is already held at breakpoint %s; nothing sent; a.bp.resume() lets it go on\n" % (a.name, bp_id(h.get("trigger"))))
        return a.agent("ctl", "pause")

    def resume(self):
        """續（跟 a.bp.stop() 一對，不收參數）。扣在斷點上：放行那一次、照原樣跑，等 handler 收到放行才回（字條的 resume 由 handler 寫）；
        暫停著：aos-agent ctl resume，字條記一筆 resume（why() 從這之後算）。要放行但那次工具不跑用 a.bp.skip()。"""
        a = self._a
        h = self.held()
        if h is None:
            out = a.agent("ctl", "resume")
            trigger.append_log(a.stack, {"kind": "resume", "at": trigger.now(), "by": "repl"})
            return out
        return self._release(h, "run", None, "bp.resume")

    def skip(self, text=None):
        """放行扣在 before_tool 斷點上的那一次，但那次工具不跑：腦收到一句「被跳過」（text＝給腦的那句，不給用預設）。
        只有扣在工具之前才行（暫停是事件已經發生之後，沒東西可跳）；等 handler 收到放行才回。"""
        a = self._a
        h = self.held()
        if h is None:
            raise Failed("bp.skip", "%s is not held before a tool; a.bp.skip() only works there (a pause comes after the event happened; a.bp.resume() goes on)" % a.name)
        if not h.get("skippable"):
            raise Failed("bp.skip", "%s is held at %s, which cannot be skipped (skipping would drop it); a.bp.resume() lets it go on" % (a.name, h.get("event")))
        return self._release(h, "skip", text, "bp.skip")

    # ---- 停在哪、為什麼 ----
    def held(self):
        """扣在斷點上的那一次（gdb/hold.json，handler 還活著才算；其中 trigger 是 hook 名 gdb_<id>）；沒有＝None。"""
        return trigger.read_hold(self._a.stack)

    def stopped(self):
        """停著等檢閱沒：ctl pause 已套用（state.json 的 paused），或扣在斷點上（held）。"""
        st = trigger.read_json(os.path.join(self._a.stack, "state.json"), {}) or {}
        return st.get("paused") is True or self.held() is not None

    def wait_stopped(self, timeout_s=30, every_s=0.1):
        """等到它真的停住（暫停已套用或已扣住；不是看字條，Argon A4）。回 True；逾時丟 TimeoutError。"""
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            if self.stopped():
                return True
            time.sleep(every_s)
        raise TimeoutError("%s did not stop in %g s" % (self._a.name, timeout_s))

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

    # ---- 內部 ----
    def _cell(self, id):
        return os.path.join(self._a.stack, _hooks.CELLS, trigger.PREFIX + id)

    def _spec(self, id):
        spec = trigger.read_json(os.path.join(self._cell(id), trigger.SPEC), None)
        if not isinstance(spec, dict) or spec.get("removed"):
            raise Failed("bp", "%s has no breakpoint %s (a.bp.ls() lists them)" % (self._a.name, id))
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
        return {r["name"][len(trigger.PREFIX):] for r in rows if r.get("name", "").startswith(trigger.PREFIX)}

    def _trigger_ids(self):
        """有設定、沒標 removed 的觸發器 id（啟用與停用的都算）。"""
        cells = os.path.join(self._a.stack, _hooks.CELLS)
        try:
            names = os.listdir(cells)
        except FileNotFoundError:
            return set()
        out = set()
        for n in names:
            if not n.startswith(trigger.PREFIX):
                continue
            spec = trigger.read_json(os.path.join(cells, n, trigger.SPEC), None)
            if isinstance(spec, dict) and not spec.get("removed"):
                out.add(n[len(trigger.PREFIX):])
        return out

    def _ids(self, watchers_on_daemon=False):
        ids = self._trigger_ids()
        for w in _watch.ls(self._a.daemon):
            if watchers_on_daemon or self._a.name in (w.get("targets") or []):
                ids.add(w["name"])
        return ids

    def _kind(self, id):
        if not isinstance(id, str) or not id:
            raise Failed("bp", "a breakpoint id is a string such as before_tool_1 (a.bp.ls() lists them)")
        if id in self._trigger_ids():
            return "trigger"
        if any(w["name"] == id and self._a.name in (w.get("targets") or []) for w in _watch.ls(self._a.daemon)):
            return WATCH
        raise Failed("bp", "%s has no breakpoint %s (a.bp.ls() lists them)" % (self._a.name, id))

    def _install(self, id, spec, replace):
        # hold：不限時（等人放行）、讀回話（skip 的退 10 才擋得下；handler 平常什麼都不印）；
        # pause：有上限、不讀回話（handler 印了什麼都不會變成 hook 失敗，Argon A1）。兩種都 on_error continue。
        how, tools = spec["how"], spec.get("tools")
        limit = 0 if how == "hold" else 40000 if spec["kind"] in ("sh", "py") else 15000
        args = ["hook", "add", "--event", spec["event"], "--name", trigger.PREFIX + id, "--path-json", json.dumps(HANDLER),
                "--on-error", "continue", "--timeout-ms", limit]
        if tools and spec.get("times", 1) == 1:   # 只篩工具名、不數連續時才交給 hook 的 condition 省行程（Argon A6）
            for t in tools:
                args += ["--condition", t]
        if how == "pause":
            args.append("--no-intercept")
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
        on = TOOL_ERROR if spec.get("kind") == "tool_error" else spec.get("event")
        return {"id": id, "kind": "trigger", "on": on, "how": spec.get("how"), "about": spec.get("about"),
                "enabled": id in hooked, "times": spec.get("times", 1), "once": spec.get("once", False),
                "seen": count.get("seen", 0), "streak": count.get("streak", 0), "fired": count.get("fired", 0),
                "spent": bool(spec.get("once") and count.get("fired")), "last_error": count.get("last_error"), "here": here == id}

    def _watch_row(self, w, here):
        mine = (w.get("per_target") or {}).get(self._a.name) or {}
        spec = trigger.read_json(os.path.join(_watch.stack_dir(self._a.daemon, _watch.PREFIX + w["name"]), _watch.SPEC), {}) or {}
        return {"id": w["name"], "kind": WATCH, "on": WATCH, "how": "pause", "about": w.get("about"),
                "enabled": spec.get("enabled", True), "times": spec.get("times", 1), "once": spec.get("once", False),
                "seen": mine.get("seen", 0), "streak": mine.get("streak", 0), "fired": mine.get("fired", 0),
                "spent": bool(spec.get("once") and mine.get("fired")), "last_error": mine.get("last_error"), "here": here == w["name"]}

    def _release(self, h, go, text, what):
        """寫放行單、等 handler 收到；go＝run（照跑）或 skip（不跑）。"""
        a = self._a
        pending = self.why().pending                # 扣著時又來的 ctl pause／stop：放行後這一格做完就套用（Argon A10）
        if echo:
            print("$ release %s: %s (writes %s)" % (h.get("trigger"), go, os.path.join(a.stack, trigger.LOG_DIR, trigger.RELEASE)))
        trigger.write_release(a.stack, h["token"], go, text)
        end = time.monotonic() + RELEASE_WAIT_S
        while time.monotonic() < end:
            now = self.held()
            if now is None or now.get("token") != h["token"]:
                break
            time.sleep(0.05)
        else:
            raise Failed(what, "the hold did not end within %d s (is %s still running?)" % (RELEASE_WAIT_S, a.name))
        # 字條由 handler 自己寫（resume 或 hold_ended，帶 token；Argon A2）：沒看到 resume＝它不是被這張放行單放的
        mine = [n for n in trigger.read_log(a.stack) if n.get("token") == h["token"] and n.get("kind") in ("resume", "hold_ended")]
        if not mine or mine[-1]["kind"] != "resume":
            why = mine[-1].get("why") if mine else "no note from the trigger"
            raise Failed(what, "the hold ended without this release (%s); the call did not go on" % why)
        try:
            os.remove(os.path.join(a.stack, trigger.LOG_DIR, trigger.RELEASE))
        except FileNotFoundError:
            pass
        d = h.get("detail", {})
        tail = "; then it %ss: ctl %s (seq %s) came while held" % (pending[1], pending[1], pending[0]) if pending else ""
        return Text("%s: %s %s (by %s)%s\n" % (a.name, "skipped tool" if go == "skip" else "released; going on with",
                                              d.get("name") or d.get("letter") or h.get("event"), mine[-1].get("by"), tail))


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
            "tool_added": "tool %s was added" % (who or "any")}.get(spec["event"], "event %s" % spec["event"])
    cond = {"always": "", "tool_error": " with an error (exit code not 0, or timed out)",
            "sh": " and sh `%s` exits 0" % spec.get("sh"),
            "py": " and the py condition is true"}[spec["kind"]]
    times = " (%d times in a row)" % spec["times"] if spec.get("times", 1) > 1 else ""
    return what + cond + times + (", once" if spec.get("once") else "")


def _free(on, have):
    i = 1
    while "%s_%d" % (on, i) in have:
        i += 1
    return "%s_%d" % (on, i)
