"""aos.gdb - aos-gdb 的 Python 庫（在 python REPL 裡用）：對一隻已在跑的 agent 下條件觸發器（裝一個 hook：條件成立就 ctl pause 並留字條）、列出／拿掉、看停沒停與為什麼、檢閱 stack、續。

使用者 11-19：「先用python產出一份粗定義，然後進入python repl，用aos-gdb庫，下斷點，然後跑。」斷點＝「特定條件發生時，暫停loop或fsm，
停下來等待檢閱」，條件主要由 hook 承載、「hook不用動」。圖紙：thinking/2026-11/19/aos-gdb-1119（乙案）、08-Argon審與採納、aos-gdb-lib-第一版.md。

薄殼：每個方法背後是一條 aos 指令（aos-agent …）或讀 stack 裡的一個檔；g.echo 為真時先印出那條指令，REPL 和 shell 可以混著用
（觸發器掛在 agent 的 stack，REPL 關了它照樣在；停住的那隻用 `aos-agent ctl resume` 也續得了）。

    import aos.gdb as g
    a = g.attach("ann", daemon=".stack")          # daemon 預設 $AOS_DAEMON
    a.stop_before_tool("write")                   # 某工具要被叫：這一格做完就停（block=True＝那一次不讓它跑）
    a.stop_on_tool_error()                        # 任何工具回錯（退出碼不是 0、逾時）
    a.stop_when("after_tool", sh="grep -q secret", times=2)       # 自訂條件：一段 shell（事件 JSON 在 stdin，退 0＝算）
    a.stop_when("before_tool", py=lambda ev: ev["arguments"].get("path", "").endswith(".env"))   # 或一個 Python 函式／運算式字串
    a.say("hi"); a.wait_paused(); a.why(); a.where(); a.history(3)
    a.resume(); a.triggers(); a.remove("before_tool_1"); a.clear()

觸發器的檔、字條格式、條件怎麼判在 aos.gdb.trigger；hook handler 是 lib/tools/agent/gdb_trigger。丙（外面的觀察者）之後接同一份字條（by "watch"）。"""
import os
import time

from aos.agentlib import hooks as _hooks
from aos.gdb import trigger
from aos.gdb.look import Look, Text, Why, run, sh, Failed  # noqa: F401  （sh、Failed、Text 給 REPL 用）

echo = True                                       # 為真＝每條指令先印一行 "$ ..."（看得到背後是哪條 shell）
HANDLER = {"$env": "AOS_HOME", "$path": "/lib/tools/agent/gdb_trigger"}
NAMED = tuple(e for e, d in _hooks.EVENTS.items() if d["condition"] == "name")   # tool= 能篩的事件（brain_failed 的 name＝錯誤代號）
EVENTS = tuple(e for e in _hooks.EVENTS if e != _hooks.CLOCK_EVENT)               # on_clock 要給間隔，不是「事件發生」，這版不收


def attach(name, daemon=None):
    """接上一隻已經掛在 daemon 上的 agent（不改它任何東西）：記住名字、daemon、stack 在哪，確認它的定義宣告了 hooks。"""
    return Agent(name, daemon)


class Agent(Look):
    def __init__(self, name, daemon=None):
        d = daemon or os.environ.get("AOS_DAEMON")
        if not d:
            raise Failed("attach", "no daemon given and AOS_DAEMON is not set (attach(name, daemon='.stack'))")
        self.name, self.daemon = name, os.path.abspath(d)
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
        import json
        return json.loads(self.agent(*args, quiet=True))

    def say(self, text):
        return self.agent("say", text)

    def listen(self, timeout_s=20):
        """等它下一個回答（aos-agent listen）。"""
        return self.agent("listen", "--timeout-s", timeout_s)

    def pause(self):
        return self.agent("ctl", "pause")

    def resume(self):
        """aos-agent ctl resume，成功後在字條加一筆 resume（why() 從這之後算）。"""
        out = self.agent("ctl", "resume")
        trigger.append_log(self.stack, {"kind": "resume", "at": trigger.now(), "by": "repl"})
        return out

    # ---- 觸發器 ----
    def stop_before_tool(self, tool=None, **kw):
        """某工具（不給＝任何工具）要被叫的時候停。停在這一格做完：那次工具照跑，除非 block=True（那一次不跑，腦收到被擋）。"""
        return self.stop_when("before_tool", tool=tool, **kw)

    def stop_on_tool_error(self, tool=None, **kw):
        """工具回錯（退出碼不是 0、或逾時）就停；不給 tool＝任何工具，後來才加的也算。"""
        return self.stop_when("after_tool", tool=tool, error=True, **kw)

    def stop_on_brain_failed(self, code=None, **kw):
        """問腦失敗（brain_failed；code＝錯誤代號如 BrainFailed、BudgetMissing，不給＝都算）就停。"""
        return self.stop_when("brain_failed", tool=code, **kw)

    def stop_when(self, event, tool=None, sh=None, py=None, error=False, times=1, once=False, block=False, name=None, replace=False):
        """在 event 發生、條件成立（連續 times 次）時把它停下來。條件：不給＝事件來了就算；error＝工具回錯（after_tool）；
        sh＝一段 shell（事件 JSON 在 stdin，退 0＝算、退 10＝不算）；py＝函式 f(event) 或運算式字串（變數 ev）。
        tool＝只算這個（或這些）工具；once＝只停一次；block＝before_tool 停的那一次不讓工具跑。回觸發器名（不含 gdb_ 前綴）。"""
        if event not in EVENTS:
            raise Failed("stop_when", "event must be one of %s" % ", ".join(EVENTS))
        tools = [tool] if isinstance(tool, str) else (list(tool) if tool else None)
        if tools and event not in NAMED:
            raise Failed("stop_when", "tool= only works on %s (event %s has no tool name)" % (", ".join(NAMED), event))
        if sum(bool(x) for x in (sh, py is not None, error)) > 1:
            raise Failed("stop_when", "give one condition: sh, py or error")
        if error and event != "after_tool":
            raise Failed("stop_when", "error=True only works on after_tool")
        if block and event != "before_tool":
            raise Failed("stop_when", "block=True only works on before_tool")
        spec = {"kind": "sh" if sh else "py" if py is not None else "tool_error" if error else "always",
                "event": event, "tools": tools, "times": times, "once": bool(once), "block": bool(block),
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
        args = ["hook", "add", "--event", event, "--name", hook, "--path-json", _json_text(HANDLER),
                "--on-error", "continue", "--timeout-ms", 40000 if spec["kind"] in ("sh", "py") else 15000]
        if tools and times == 1:                  # 只篩工具名、不數連續時才交給 hook 的 condition 省行程（Argon A6）
            for t in tools:
                args += ["--condition", t]
        if not block:
            args.append("--no-intercept")          # 不讀回話：handler 印了什麼都不會變成 hook 失敗（Argon A1）
        if replace:
            args.append("--replace")
        self.agent(*args)
        return short

    def triggers(self, quiet=False):
        """這隻身上 aos.gdb 裝的觸發器：名字、事件、說明、連續幾次、看過幾次事件、停過幾次、條件最後一次壞掉的原因。"""
        import json
        rows = json.loads(self.agent("hook", "ls", "--json", quiet=quiet))
        out = []
        for r in rows:
            n = r.get("name", "")
            if not n.startswith(trigger.PREFIX):
                continue
            cell = os.path.join(self.stack, _hooks.CELLS, n)
            spec = trigger.read_json(os.path.join(cell, trigger.SPEC), {}) or {}
            count = trigger.read_json(os.path.join(cell, trigger.COUNT), {}) or {}
            out.append({"name": n[len(trigger.PREFIX):], "event": r.get("event"), "about": spec.get("about"),
                        "times": spec.get("times", 1), "once": spec.get("once", False), "block": spec.get("block", False),
                        "seen": count.get("seen", 0), "streak": count.get("streak", 0), "fired": count.get("fired", 0),
                        "spent": bool(spec.get("once") and count.get("fired")), "last_error": count.get("last_error")})
        return out

    def remove(self, name):
        """拿掉一個觸發器（aos-agent hook rm gdb_NAME；小格裡的設定與計數留著給人看）。"""
        return self.agent("hook", "rm", trigger.PREFIX + name)

    def clear(self):
        """拿掉 aos.gdb 裝的全部觸發器（不碰別的 hook）。"""
        for t in self.triggers(quiet=True):
            self.remove(t["name"])

    # ---- 停了沒、為什麼 ----
    def is_paused(self):
        """讀 stack 的 state.json：loop 停在兩格之間了沒（ctl pause 已經套用）。"""
        st = trigger.read_json(os.path.join(self.stack, "state.json"), {}) or {}
        return st.get("paused") is True

    def wait_paused(self, timeout_s=30, every_s=0.2):
        """等到 loop 真的停住（state.json 的 paused；不是看字條，Argon A4）。逾時丟 TimeoutError。"""
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            if self.is_paused():
                return True
            time.sleep(every_s)
        raise TimeoutError("%s did not pause in %g s" % (self.name, timeout_s))

    def why(self):
        """為什麼停：上一次 resume（經 aos.gdb）之後觸發器留的字條，加上現在是不是停著、字條是不是這一次的。"""
        notes = trigger.since_resume(trigger.read_log(self.stack))
        paused = self.is_paused()
        seq = trigger.ctl_seq(self.stack)
        last = notes[-1] if notes else None
        current = bool(paused and last and last.get("ctl_seq") is not None and last.get("ctl_seq") == seq)
        return Why(self.name, paused, current, notes)


def _about(spec):
    who = " or ".join(spec["tools"]) if spec.get("tools") else None
    what = {"before_tool": "tool %s is about to run" % (who or "any"), "after_tool": "tool %s finished" % (who or "any"),
            "brain_failed": "the brain failed%s" % (" with %s" % who if who else ""),
            "tool_added": "tool %s was added" % (who or "any")}.get(spec["event"], "event %s" % spec["event"])
    cond = {"always": "", "tool_error": " with an error (exit code not 0, or timed out)",
            "sh": " and sh `%s` exits 0" % spec.get("sh"),
            "py": " and the py condition is true"}[spec["kind"]]
    times = " (%d times in a row)" % spec["times"] if spec.get("times", 1) > 1 else ""
    return what + cond + times + (", once" if spec.get("once") else "") + (", blocking that call" if spec.get("block") else "")


def _free(event, have):
    i = 1
    while "%s_%d" % (event, i) in have:
        i += 1
    return "%s_%d" % (event, i)


def _json_text(v):
    import json
    return json.dumps(v, ensure_ascii=False)
