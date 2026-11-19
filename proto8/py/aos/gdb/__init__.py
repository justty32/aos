"""aos.gdb - aos-gdb 的 Python 庫（在 python REPL 裡用）：對一隻已在跑的 agent 下條件觸發器（裝一個 hook）或起一個觀察者（另一支 proc），條件成立就把它停下來；列出／拿掉、看停沒停與為什麼、檢閱 stack、續。

使用者 11-19：「先用python產出一份粗定義，然後進入python repl，用aos-gdb庫，下斷點，然後跑。」斷點＝「特定條件發生時，暫停loop或fsm，
停下來等待檢閱」，「能把他停下來的都可以」，「hook不用動」；第二版：「stop_before_tool不就是在工具開始前停下嗎？丙可以繼續」。
圖紙：thinking/2026-11/19/aos-gdb-1119（乙案）、08-Argon審與採納、aos-gdb-lib-第一版.md、aos-gdb-lib-第二版.md。

兩種停法，由事件決定（不是選項）：
    事件還沒發生（before_tool、before_queue）＝扣住（hold）：hook handler 自己不回，工具還沒跑、信還沒進 history；
        a.resume() 讓那次照原樣跑，a.resume(skip=True) 讓那次工具不跑（腦收到一句「被跳過」）。表上照寫 running（它卡在那一格裡）。
    其他事件（已經發生）＝暫停（pause）：ctl pause，loop 在這一格做完、下一格開頭停住；a.resume()＝ctl resume。
觀察者（丙）：另一支掛在 daemon 表上的 proc，每隔一陣子看目標的檔，成立就 ctl pause 目標（晚一格），字條 by "watch"（aos.gdb.watcher）。

薄殼：每個方法背後是一條 aos 指令（aos-agent …、aos-daemon-ctl …）或讀寫 stack 裡的一個檔；g.echo 為真時先印出那條指令，REPL 和 shell 可以混著用
（觸發器掛在 agent 的 stack、觀察者掛在 daemon 表上，REPL 關了照樣在；停住的那隻用 `aos-agent ctl resume` 也續得了，扣住的也是）。

    import aos.gdb as g
    a = g.attach("ann", daemon=".stack")          # daemon 預設 $AOS_DAEMON
    a.stop_before_tool("write")                   # write 要跑之前扣住：a.resume() 照跑、a.resume(skip=True) 不跑
    a.stop_after_tool("write")                    # write 跑完、腦還沒看到結果就停
    a.stop_on_tool_error()                        # 任何工具回錯（退出碼不是 0、逾時）
    a.stop_when("after_tool", sh="grep -q secret", times=2)       # 自訂條件：一段 shell（事件 JSON 在 stdin，退 0＝算）
    a.stop_when("before_tool", py=lambda ev: ev["arguments"].get("path", "").endswith(".env"))   # 或一個 Python 函式／運算式字串
    a.watch(py=lambda t: len(t.history(0)) > 20)  # 觀察者：另一支 proc 每 0.5 秒看一次，成立就 pause
    a.say("hi"); a.wait_paused(); a.why(); a.where(); a.history(3)
    a.resume(); a.triggers(); a.remove("before_tool_1"); a.clear(); a.watchers(); a.unwatch("w1")

觸發器的檔、字條、扣住檔、條件怎麼判在 aos.gdb.trigger；hook handler 是 lib/tools/agent/gdb_trigger；觀察者在 aos.gdb.watcher 與 lib/tools/agent/gdb_watch。"""
import json
import os
import time

from aos.agentlib import hooks as _hooks
from aos.gdb import trigger, watcher as _watch
from aos.gdb.look import Look, Text, Why, run, sh, Failed  # noqa: F401  （sh、Failed、Text 給 REPL 用）

echo = True                                       # 為真＝每條指令先印一行 "$ ..."（看得到背後是哪條 shell）
HANDLER = {"$env": "AOS_HOME", "$path": "/lib/tools/agent/gdb_trigger"}
NAMED = tuple(e for e, d in _hooks.EVENTS.items() if d["condition"] == "name")   # tool= 能篩的事件（brain_failed 的 name＝錯誤代號）
EVENTS = tuple(e for e in _hooks.EVENTS if e != _hooks.CLOCK_EVENT)               # on_clock 要給間隔，不是「事件發生」，不收
RELEASE_WAIT_S = 10


def attach(name, daemon=None):
    """接上一隻已經掛在 daemon 上的 agent（不改它任何東西）：記住名字、daemon、stack 在哪，確認它的定義宣告了 hooks。"""
    return Agent(name, daemon)


def _daemon(daemon):
    d = daemon or os.environ.get("AOS_DAEMON")
    if not d:
        raise Failed("aos.gdb", "no daemon given and AOS_DAEMON is not set (daemon='.stack')")
    return os.path.abspath(d)


def watch(targets, daemon=None, sh=None, py=None, times=1, once=False, every_ms=500, name=None, replace=False):
    """起一個觀察者：另一支 proc（daemon 表上的 gdbw_<名>），每 every_ms 看一次每個目標，條件成立（連續 times 次）就 ctl pause 那個目標、留字條。
    py＝函式 f(t) 或運算式字串（變數 t）：t 是目標的檢閱物件（t.history()、t.observed()、t.where()、t.file()…），t.mem 是跨圈留著的 dict；
    sh＝一段 shell（cwd＝目標 stack，環境有 GDB_TARGET、GDB_STACK；退 0＝算、10＝不算）。回觀察者的短名。"""
    return _watch.add(_daemon(daemon), targets, sh=sh, py=py, times=times, once=once, every_ms=every_ms, name=name, replace=replace, echo=echo)


def watchers(daemon=None):
    """這個 daemon 上的觀察者（表上的 phase、看誰、條件、每個目標停過幾次、條件最後一次壞掉的原因）。"""
    return _watch.ls(_daemon(daemon))


def unwatch(name, daemon=None):
    """拿掉一個觀察者（aos-daemon-ctl rm gdbw_NAME：先停、等行程退出，再從表上拿掉）。"""
    return _watch.rm(_daemon(daemon), name, echo=echo)


class Agent(Look):
    def __init__(self, name, daemon=None):
        self.name, self.daemon = name, _daemon(daemon)
        who = self._json(["ctl", "state", "--json", "who"]).get("who", {})
        stack = who.get("stack")
        if not isinstance(stack, str) or not stack:
            raise Failed("attach", "cannot tell where the stack of %s is (aos-agent ctl state who)" % name)
        self.stack = stack
        self.agent("hook", "ls", quiet=True)      # 定義沒宣告 hooks＝這裡就說 HooksMissing（Argon A2）

    def __repr__(self):
        return "<aos.gdb agent %s (stack %s)>" % (self.name, self.stack)

    # ---- 指令 ----
    def agent(self, *args, quiet=False):
        """aos-agent --daemon D --target NAME ARGS...；回 stdout（Text）。退非 0 丟 Failed（帶它最後一行錯誤）。"""
        return run(["aos-agent", "--daemon", self.daemon, "--target", self.name] + [str(x) for x in args], echo=echo and not quiet)

    def _json(self, args):
        return json.loads(self.agent(*args, quiet=True))

    def say(self, text):
        """aos-agent say；回信名（Text，交給 listen(letter=...) 等那一封的回答）。"""
        return self.agent("say", text)

    def listen(self, timeout_s=20, letter=None):
        """等它的回答（aos-agent listen）；letter＝say 回的信名：等那一封的。"""
        return self.agent("listen", "--timeout-s", timeout_s, *(["--letter", str(letter).strip()] if letter else []))

    def pause(self):
        return self.agent("ctl", "pause")

    def resume(self, skip=False, text=None):
        """續。扣在斷點上：放行那一次——照原樣跑（預設），或 skip=True 不跑（before_tool 才行；text＝給腦的那句，不給用預設）；
        等 handler 收到放行才回（字條的 resume 由 handler 寫）。暫停著：aos-agent ctl resume，字條記一筆 resume（why() 從這之後算）。"""
        h = self.held()
        if h is None:
            if skip:
                raise Failed("resume", "%s is not held before a tool; skip=True only works there (a pause comes after the event happened)" % self.name)
            out = self.agent("ctl", "resume")
            trigger.append_log(self.stack, {"kind": "resume", "at": trigger.now(), "by": "repl"})
            return out
        if skip and not h.get("skippable"):
            raise Failed("resume", "%s is held at %s, which cannot be skipped (skipping would drop it); a.resume() lets it go on" % (self.name, h.get("event")))
        go = "skip" if skip else "run"
        pending = self.why().pending                # 扣著時又來的 ctl pause／stop：放行後這一格做完就套用（Argon A10）
        if echo:
            print("$ release %s: %s (writes %s)" % (h.get("trigger"), go, os.path.join(self.stack, trigger.LOG_DIR, trigger.RELEASE)))
        trigger.write_release(self.stack, h["token"], go, text)
        end = time.monotonic() + RELEASE_WAIT_S
        while time.monotonic() < end:
            now = self.held()
            if now is None or now.get("token") != h["token"]:
                break
            time.sleep(0.05)
        else:
            raise Failed("resume", "the hold did not end within %d s (is %s still running?)" % (RELEASE_WAIT_S, self.name))
        # 字條由 handler 自己寫（resume 或 hold_ended，帶 token；Argon A2）：沒看到 resume＝它不是被這張放行單放的
        mine = [n for n in trigger.read_log(self.stack) if n.get("token") == h["token"] and n.get("kind") in ("resume", "hold_ended")]
        if not mine or mine[-1]["kind"] != "resume":
            why = mine[-1].get("why") if mine else "no note from the trigger"
            raise Failed("resume", "the hold ended without this release (%s); the call did not go on" % why)
        try:
            os.remove(os.path.join(self.stack, trigger.LOG_DIR, trigger.RELEASE))
        except FileNotFoundError:
            pass
        d = h.get("detail", {})
        tail = "; then it %ss: ctl %s (seq %s) came while held" % (pending[1], pending[1], pending[0]) if pending else ""
        return Text("%s: %s %s (by %s)%s\n" % (self.name, "skipped tool" if go == "skip" else "released; going on with",
                                              d.get("name") or d.get("letter") or h.get("event"), mine[-1].get("by"), tail))

    # ---- 觸發器 ----
    def stop_before_tool(self, tool=None, **kw):
        """某工具（不給＝任何工具）要跑之前就停：扣住，工具還沒跑。a.resume()＝那次照原樣跑，a.resume(skip=True)＝那次不跑。"""
        return self.stop_when("before_tool", tool=tool, **kw)

    def stop_after_tool(self, tool=None, **kw):
        """某工具（不給＝任何工具）跑完就停：發 ctl pause，act 這一格做完才套用——結果已進 history、腦還沒看到（停在下一格 think 開頭）；
        腦一次叫好幾個工具時，同一格後面的工具照跑（Argon A10）。"""
        return self.stop_when("after_tool", tool=tool, **kw)

    def stop_on_tool_error(self, tool=None, **kw):
        """工具回錯（退出碼不是 0、或逾時）就停，同 stop_after_tool 停的位置；不給 tool＝任何工具，後來才加的也算。"""
        return self.stop_when("after_tool", tool=tool, error=True, **kw)

    def stop_on_brain_failed(self, code=None, **kw):
        """問腦失敗（brain_failed；code＝錯誤代號如 BrainFailed、BudgetMissing，不給＝都算）就停（那一格做完）。"""
        return self.stop_when("brain_failed", tool=code, **kw)

    def stop_when(self, event, tool=None, sh=None, py=None, error=False, times=1, once=False, name=None, replace=False):
        """在 event 發生、條件成立（連續 times 次）時把它停下來。before_tool、before_queue＝事件之前扣住；其他事件＝那一格做完暫停。
        條件：不給＝事件來了就算；error＝工具回錯（after_tool）；sh＝一段 shell（事件 JSON 在 stdin，退 0＝算、退 10＝不算）；
        py＝函式 f(event) 或運算式字串（變數 ev）。tool＝只算這個（或這些）工具；once＝只停一次。回觸發器名（不含 gdb_ 前綴）。"""
        if event not in EVENTS:
            raise Failed("stop_when", "event must be one of %s" % ", ".join(EVENTS))
        tools = [tool] if isinstance(tool, str) else (list(tool) if tool else None)
        if tools and event not in NAMED:
            raise Failed("stop_when", "tool= only works on %s (event %s has no tool name)" % (", ".join(NAMED), event))
        if sum(bool(x) for x in (sh, py is not None, error)) > 1:
            raise Failed("stop_when", "give one condition: sh, py or error")
        if error and event != "after_tool":
            raise Failed("stop_when", "error=True only works on after_tool")
        how = trigger.how(event)
        spec = {"kind": "sh" if sh else "py" if py is not None else "tool_error" if error else "always",
                "event": event, "how": how, "tools": tools, "times": times, "once": bool(once),
                "agent": self.name, "daemon": self.daemon}
        if sh:
            spec["sh"] = sh
        if py is not None:
            try:
                spec["py"] = trigger.pack_py(py)
            except trigger.Bad as e:
                raise Failed("stop_when", str(e)) from None
        spec["about"] = _about(spec)
        try:
            trigger.validate(spec)
        except trigger.Bad as e:
            raise Failed("stop_when", str(e)) from None
        have = {t["name"] for t in self.triggers(quiet=True)}
        short = name or _free(event, have)
        hook = trigger.PREFIX + short
        if short in have and not replace:
            raise Failed("stop_when", "%s already has a trigger named %s (replace=True to replace it)" % (self.name, short))
        cell = os.path.join(self.stack, _hooks.CELLS, hook)
        trigger.write_json(os.path.join(cell, trigger.SPEC), spec)
        trigger.write_json(os.path.join(cell, trigger.COUNT), {})      # 重下＝重新數
        # hold：不限時（等人放行）、讀回話（skip 的退 10 才擋得下；handler 平常什麼都不印）；
        # pause：有上限、不讀回話（handler 印了什麼都不會變成 hook 失敗，Argon A1）。兩種都 on_error continue。
        limit = 0 if how == "hold" else 40000 if spec["kind"] in ("sh", "py") else 15000
        args = ["hook", "add", "--event", event, "--name", hook, "--path-json", json.dumps(HANDLER),
                "--on-error", "continue", "--timeout-ms", limit]
        if tools and times == 1:                  # 只篩工具名、不數連續時才交給 hook 的 condition 省行程（Argon A6）
            for t in tools:
                args += ["--condition", t]
        if how == "pause":
            args.append("--no-intercept")
        if replace:
            args.append("--replace")
        self.agent(*args)
        return short

    def triggers(self, quiet=False):
        """這隻身上 aos.gdb 裝的觸發器：名字、事件、怎麼停（hold／pause）、說明、連續幾次、看過幾次事件、停過幾次、條件最後一次壞掉的原因。"""
        rows = json.loads(self.agent("hook", "ls", "--json", quiet=quiet))
        out = []
        for r in rows:
            n = r.get("name", "")
            if not n.startswith(trigger.PREFIX):
                continue
            cell = os.path.join(self.stack, _hooks.CELLS, n)
            spec = trigger.read_json(os.path.join(cell, trigger.SPEC), {}) or {}
            count = trigger.read_json(os.path.join(cell, trigger.COUNT), {}) or {}
            out.append({"name": n[len(trigger.PREFIX):], "event": r.get("event"), "how": spec.get("how"), "about": spec.get("about"),
                        "times": spec.get("times", 1), "once": spec.get("once", False),
                        "seen": count.get("seen", 0), "streak": count.get("streak", 0), "fired": count.get("fired", 0),
                        "spent": bool(spec.get("once") and count.get("fired")), "last_error": count.get("last_error")})
        return out

    def remove(self, name):
        """拿掉一個觸發器（aos-agent hook rm gdb_NAME；小格裡的設定與計數留著給人看）。正扣在它上面的那一次不受影響，照樣等 a.resume()。"""
        return self.agent("hook", "rm", trigger.PREFIX + name)

    def clear(self):
        """拿掉 aos.gdb 裝的全部觸發器（不碰別的 hook）。"""
        for t in self.triggers(quiet=True):
            self.remove(t["name"])

    # ---- 觀察者（看這一隻；also＝順便也看別隻，同一個 daemon）----
    def watch(self, sh=None, py=None, also=(), **kw):
        """起一個看這隻（與 also 裡別隻）的觀察者；參數同 aos.gdb.watch()。回觀察者的短名。"""
        return watch([self.name] + list(also), daemon=self.daemon, sh=sh, py=py, **kw)

    def watchers(self):
        """看著這隻的觀察者。"""
        return [w for w in watchers(self.daemon) if self.name in (w.get("targets") or [])]

    def unwatch(self, name):
        return unwatch(name, daemon=self.daemon)

    # ---- 停了沒、為什麼 ----
    def held(self):
        """扣在斷點上的那一次（gdb/hold.json，handler 還活著才算）；沒有＝None。"""
        return trigger.read_hold(self.stack)

    def is_paused(self):
        """停著等檢閱沒：ctl pause 已套用（state.json 的 paused），或扣在斷點上（held）。"""
        st = trigger.read_json(os.path.join(self.stack, "state.json"), {}) or {}
        return st.get("paused") is True or self.held() is not None

    def wait_paused(self, timeout_s=30, every_s=0.1):
        """等到它真的停住（暫停已套用或已扣住；不是看字條，Argon A4）。逾時丟 TimeoutError。"""
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            if self.is_paused():
                return True
            time.sleep(every_s)
        raise TimeoutError("%s did not pause in %g s" % (self.name, timeout_s))

    def why(self):
        """為什麼停：上一次 resume（經 aos.gdb，或在 shell 下 ctl resume 放行的）之後的字條（觸發器與觀察者的），
        加上現在是不是停著、扣在哪、字條是不是這一次的、扣住之後有沒有人下 ctl pause／stop。"""
        notes = trigger.since_resume(trigger.read_log(self.stack))
        h = self.held()
        st = trigger.read_json(os.path.join(self.stack, "state.json"), {}) or {}
        paused = st.get("paused") is True or h is not None
        seq, cmd = trigger.ctl_doc(self.stack)
        last = notes[-1] if notes else None
        current = h is not None or bool(paused and last and last.get("ctl_seq") is not None and last.get("ctl_seq") == seq)
        pending = trigger.ctl_unapplied(self.stack) if h is not None else None
        return Why(self.name, paused, current, notes, held=h, pending=pending)


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


def _free(event, have):
    i = 1
    while "%s_%d" % (event, i) in have:
        i += 1
    return "%s_%d" % (event, i)
