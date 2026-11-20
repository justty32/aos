"""agent_hooks - agent 一家的 hook 遙控器：open 一次（定義那份疊 stack 那份），之後每個點一行；丟信三步、工具被攔的預設字、tool_added 那串只在這裡一份。

圖紙：proto8/thinking/2026-11/20/aos-hook-plan-1120/04「agent 一家」（11-20 使用者「宣告式＋小函式都做」）；第 2 刀 2a（庫那一半）。
事件表照舊用 hooks.EVENTS、清單照舊經 hooks.load 讀（第 3 刀才改讀宣告）；跑的那段是 aos.hook_point 的遙控器（再交引擎 hook_run）。
錯一律交給 open 時給的 fail(代號, 一句英文)：fail 自己丟的例外原樣往外走；fail 竟然回來＝丟 hook_point.FailReturned。
格程式（templates/agent-fsm）、aos-eca-turn、aos-mcp 還沒改叫這裡（2b：要等 install 之後，格程式存檔即生效）。從 hooks.py 拆出來只為檔案大小（F10）。

對外：
    open(def_folder, stack, fail, warn=None) -> 遙控器；def_folder None＝沒有 hook 的空遙控器（aos-mcp 沒給 --hooks）
    遙控器.fire(event, data, only=None) -> 引擎的結果（形狀同 hooks.fire）
    遙控器.has(event)、遙控器.names(event, data)
    遙控器.clock_tick() -> [跑了的 hook 名]（同 hooks.clock_tick）
    遙控器.take_letter(box, sig, content) -> 改過的 content；被 before_queue 攔下＝letters.json 記 dropped（寫不成只 warning）、
                    aos-post done（起不來或退非 0＝PostFailed）、mailbox_warning.txt 寫一行（寫不成＝WriteFailed），回 None
    遙控器.guard_tool(name, cid, arguments) -> ("run", arguments：沒人改＝給的那個物件本身、改了＝新的)
                    或 ("blocked", 給腦看的字：hook 的 stdout，空的＝「[aos] hook: tool NAME blocked by hook HOOK.」)
    遙控器.announce_tools(tools) -> None：tool_added，這次比上次多出來的名字一個發一次；tools＝[(name, path)]，
                    或不收參數、回那串的函式（有人掛 tool_added 才叫）；記名單寫不成＝WriteFailed
"""
import io
import os

from aos import flags as aos_flags
from aos import hook_point
from aos import ws as aos_ws
from aos.agentlib import hooks

MAILBOX_WARNING = "mailbox_warning.txt"


def open(def_folder, stack, fail, warn=None):
    """agent 的 hook 遙控器；def_folder None＝空遙控器（沒有 hook，fire 原樣回）。"""
    entries = {} if def_folder is None else (lambda: hooks.load(def_folder, stack))
    return AgentHooks(def_folder, stack, fail, warn,
                      hook_point.open(table=hooks.EVENTS, entries=entries, stack=stack, fail=fail, warn=warn,
                                      check=hooks._check))


def _write_atomic(path, text):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")   # N-05：先寫暫存再改名
    with io.open(tmp, "w", encoding="utf-8") as f:                 # io.open：這個模組自己的 open 是遙控器
        f.write(text)
    os.replace(tmp, path)


class AgentHooks:
    """agent 的 hook 遙控器（見檔頭）。"""

    def __init__(self, def_folder, stack, fail, warn, handle):
        self.def_folder, self.stack = def_folder, stack
        self._fail, self._warn, self._h = fail, warn, handle

    def _die(self, code, sentence):
        hook_point.call_fail(self._fail, code, sentence)

    def fire(self, event, data, only=None):
        return self._h.fire(event, data, only=only)

    def has(self, event):
        return self._h.has(event)

    def names(self, event, data):
        return self._h.names(event, data)

    def clock_tick(self):
        if self.def_folder is None:
            return []
        try:
            return hooks.clock_tick(self.def_folder, self.stack, warn=self._warn)
        except (hooks.HookFailed, hooks.HooksBad) as e:
            self._die(type(e).__name__, str(e))

    def take_letter(self, box, sig, content):
        r = self.fire("before_queue", {"letter": sig, "content": content})
        if not r["blocked"]:
            return r["data"]["content"]
        try:                                     # 回答配對：done 之前記進 dropped；寫不成只提醒（ask 最壞等到逾時）
            aos_ws.letters_drop(self.stack, [sig], "blocked")
        except OSError as e:
            if self._warn:
                self._warn("cannot write %s: %s" % (os.path.join(self.stack, aos_ws.LETTERS), e))
        try:
            code, _ = aos_ws.run_post(["done", box, sig])
        except aos_ws.Error as e:
            self._die(e.code, str(e))
        if code != 0:
            self._die("PostFailed", "aos-post done exited %d" % code)
        path = os.path.join(self.stack, MAILBOX_WARNING)
        try:
            _write_atomic(path, "letter %s dropped by hook %s\n" % (sig, r["hook"]))
        except OSError as e:
            self._die("WriteFailed", "cannot write %s: %s" % (path, e))
        return None

    def guard_tool(self, name, cid, arguments):
        r = self.fire("before_tool", {"name": name, "id": cid, "arguments": arguments})
        if r["blocked"]:
            return "blocked", (r["text"] if r["text"].strip()
                               else aos_flags.aos_note("hook", "tool %s blocked by hook %s." % (name, r["hook"])))
        return "run", r["data"]["arguments"] if "arguments" in r["changed"] else arguments

    def announce_tools(self, tools):
        on = self.has("tool_added")
        listed = (tools() if on else []) if callable(tools) else tools
        try:
            added = hooks.tools_added(self.stack, listed, on)
        except OSError as e:
            self._die("WriteFailed", "cannot write %s: %s" % (os.path.join(self.stack, hooks.SEEN), e))
        for name, where in added:
            self.fire("tool_added", {"name": name, "path": where})
