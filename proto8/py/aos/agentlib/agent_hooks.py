"""agent_hooks - the agent family's hook remote: open once (the definition's hookeds with the stack's copy on top), then one line per point; dropping a letter, a blocked tool's default text and tool_added's list live only here.

Design: proto8/thinking/2026-11/20/aos-hook-plan-1120/04 "agent 一家" (11-20 the user "宣告式＋小函式都做"); since 11-21 (line
top-1121-hooknew, the user's fourth layer) the rules (what blocks, what may change, condition) are the agent family's own
in aos.agentlib.hooks, and the engine aos.hook_run only runs handlers. The list is read again on every fire (an added hook
counts from the next event). Errors go to the fail(code, sentence) given to open: what fail raises goes out as it is; if
fail returns, FailReturned is raised.
Firing programs call this: the cells (templates/agents/agent-fsm and copies), aos-eca-turn, aos-mcp.

API:
    open(def_folder, stack, fail, warn=None) -> remote; def_folder None = an empty remote (no hooks; aos-mcp without --hooks)
    remote.fire(event, data, only=None) -> the result of hooks.fire ({"data", "changed", "blocked", "hook", "text"})
    remote.has(event), remote.names(event, data)
    remote.clock_tick() -> [names run] (hook_clock.clock_tick)
    remote.take_letter(box, sig, content) -> the (maybe changed) content; blocked by before_queue = letters.json records it
                    as dropped (cannot write = a warning), aos-post done (cannot start or exits non-zero = PostFailed),
                    mailbox_warning.txt gets one line (cannot write = WriteFailed), returns None
    remote.guard_tool(name, cid, arguments) -> ("run", arguments: the given object when nobody changed it, else the new one)
                    or ("blocked", the text for the brain: the hook's stdout, empty = "[aos] hook: tool NAME blocked by hook HOOK.")
    remote.announce_tools(tools) -> None: tool_added once for each name new since last time; tools = [(name, path)], or a
                    function returning that, called only when some hook listens to tool_added; cannot record = WriteFailed
    FailReturned    raised when fail() returned; .code
"""
import io
import os

from aos import flags as aos_flags
from aos import ws as aos_ws
from aos.agentlib import hook_clock, hooks

MAILBOX_WARNING = "mailbox_warning.txt"


class FailReturned(RuntimeError):
    """The fail() given to open() returned instead of leaving; raised so a bad result never goes on."""

    def __init__(self, code, sentence):
        super().__init__("%s %s" % (code, sentence))
        self.code = code


def open(def_folder, stack, fail, warn=None):
    """The agent's hook remote; def_folder None = an empty one (no hooks, fire gives the data back)."""
    return AgentHooks(def_folder, stack, fail, warn)


def _write_atomic(path, text):
    tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")   # N-05: temp file, then rename
    with io.open(tmp, "w", encoding="utf-8") as f:                 # io.open: this module's own open is the remote
        f.write(text)
    os.replace(tmp, path)


class AgentHooks:
    """The agent's hook remote (see the module doc)."""

    def __init__(self, def_folder, stack, fail, warn):
        self.def_folder, self.stack = def_folder, stack
        self._fail, self._warn = fail, warn

    def _die(self, code, sentence):
        self._fail(code, sentence)
        raise FailReturned(code, sentence)

    def load(self):
        if self.def_folder is None:
            return {}
        try:
            return hooks.load(self.def_folder, self.stack)
        except hooks.HooksBad as e:
            self._die("HooksBad", str(e))

    def fire(self, event, data, only=None):
        try:
            return hooks.fire(event, data, self.load(), self.stack, warn=self._warn, only=only)
        except hooks.HookFailed as e:
            self._die("HookFailed", str(e))

    def has(self, event):
        return any(e["event"] == event for e in self.load().values())

    def names(self, event, data):
        return [n for n, e in sorted(self.load().items()) if e["event"] == event and hooks.matches(e, data)]

    def clock_tick(self):
        if self.def_folder is None:
            return []
        try:
            return hook_clock.clock_tick(self.def_folder, self.stack, warn=self._warn)
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
