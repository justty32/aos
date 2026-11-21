"""aos.py.agent - 「agent」這個東西的 Python 那一面：對活的那隻下指令（aos-agent 的薄殼、遙控器 a = agent.attach(名)），加上寫定義的 defs（轉匯出 aos.agent_spec，檔不搬）。

使用者 11-19：「a.xxx這塊，感覺就是aos-agent xxxx」；入口叫 aos.py、遙控器式（thinking/2026-11/19/aos-pylib-1119/07）；
寫定義的名字「改from aos.py.agent import defs。就是說這個defs不只會在agent，其他地方也會有，所以歸到agent下」「就 aos.py.agent.defs 吧」。
遙控器的類別 11-21 從 Agent 改名 Attached，跟寫定義的 defs.Agent 分開（使用者選「改遙控器那個」、「那就Attached」；thinking/2026-11/21/agent遙控器改名-Attached-1121.md）。

    from aos.py import agent
    agent.ctl.ls()                          # $ aos-agent ctl ls          （ctl add／rm／ls／set-def／who 不吃 --target：在模組層叫）
    a = agent.attach("ann", daemon=".stack")
    a.say("hi")                             # $ aos-agent --daemon /abs/.stack --target ann say hi   回信名
    a.listen(timeout_s=20)                  # $ aos-agent ... listen --timeout-s 20
    a.ctl.state(json=True)                  # 解好的 dict
    a.tools.add("lib/my/tools/grep")
    a.bp ...、a.look ...                    # 兩個延伸（斷點、讀 stack 的檔），不是 aos-agent 子指令；第一次用到才載入 aos.gdb
    from aos.py.agent import defs           # 寫定義：defs.Agent、defs.tool、defs.state、defs.fsm、defs.main…（＝aos.agent_spec）
                                            # 遙控器 a 的類別叫 Attached（agent.attach 回的），寫定義的是 defs.Agent

a 底下的名字：aos-agent 的子指令（表從 aos.apps.agent.SUBS 讀，不另抄）就是那條指令；不是的只有 bp、look、name、daemon、stack，其他當場 AttributeError。
attach 只記名字與 daemon（daemon 轉成絕對路徑），不跑指令；a.stack 每次問都跑一條 aos-agent ctl state --json who（不快取）。
daemon 不給＝庫什麼都不加，交給指令自己（$AOS_DAEMON，再沒有 ./.stack）。"""
import importlib
import os

from aos.py import _shell

# 轉匯出：名字 → 模組（要搬位置改這一行；defs 的位置使用者 11-19 定在這裡）
REEXPORT = {"defs": "aos.agent_spec"}
PROG = "aos-agent"
POINTING = ("daemon", "target")
EXTENSIONS = ("bp", "look")


def subcommands():
    """aos-agent 的子指令名（aos.apps.agent.SUBS 那份）。"""
    from aos.apps.agent import SUBS
    return tuple(SUBS)


def say(text, *, target=None, daemon=None, **kw):
    """aos-agent say：回信名（str，交給 listen(letter=...) 等那一封的回答）。模組層與遙控器上是同一支。"""
    out = _shell.Proxy(PROG, pointing=POINTING)
    return str(out.say(text, target=target, daemon=daemon, **kw) or "").strip()


HANDWRITTEN = {"say": say}


def attach(name, daemon=None):
    """一隻 agent 的遙控器：記住名字與 daemon，之後 a.X.Y(...)＝aos-agent --daemon D --target 名 X Y ...。不跑指令。"""
    if not isinstance(name, str) or not name:
        raise _shell.Failed("agent.attach", "give the agent's name (a non-empty string)", code="ArgumentsBad")
    return Attached(name, daemon)


class Attached:
    """遙控器 a（agent.attach 回的；接上＝記住名字與 daemon，不查那隻在不在）：a.<aos-agent 子指令>＝那條指令；a.bp＝斷點、a.look＝讀 stack 的檔；a(*args)＝aos-agent ... ARGS 原樣。"""

    def __init__(self, name, daemon=None):
        self.name = name
        self.daemon = None if daemon is None else os.path.abspath(str(daemon))

    @property
    def _head(self):
        return (["--daemon", self.daemon] if self.daemon else []) + ["--target", self.name]

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in HANDWRITTEN:
            f = HANDWRITTEN[name]
            return lambda *args, **kw: f(*args, target=self.name, daemon=self.daemon, **kw)
        subs = subcommands()
        if _shell.word(name) in subs:
            return _shell.Proxy(PROG, self._head, (name,))
        raise AttributeError("%s: %s is not an aos-agent subcommand (%s) nor %s" % (
            self._repr_name(), name, ", ".join(subs), ", ".join("a." + e for e in EXTENSIONS)))

    def __dir__(self):
        return sorted(set(n.replace("-", "_") for n in subcommands()) | set(EXTENSIONS) | {"name", "daemon", "stack"})

    def __call__(self, *args, **kw):
        return _shell.run(PROG, self._head, (), args, kw)

    def _repr_name(self):
        return "<%s>" % " ".join([PROG] + self._head)

    def __repr__(self):
        return self._repr_name()

    @property
    def bp(self):
        """斷點（延伸，不是 aos-agent 子指令；本體 aos.gdb.Breakpoints，第一次用到才載入）。每次取都是新的（stack 在裡面問一次）。"""
        from aos.gdb import Breakpoints, Target
        return Breakpoints(Target(self.name, self.daemon))

    @property
    def look(self):
        """讀 stack 的檔（延伸：where、history、observed、request、queue、stderr、file；本體 aos.gdb.look.Look）。"""
        from aos.gdb import StackLook
        return StackLook(self.name, self.stack)

    @property
    def stack(self):
        """這隻的 stack（絕對路徑）：每次問都跑 aos-agent ctl state --json who（被 rm 再掛回來也不會讀到舊夾）。"""
        who = (_shell.run(PROG, self._head, ("ctl", "state"), ("who",), {"json": True}) or {}).get("who") or {}
        s = who.get("stack")
        if not isinstance(s, str) or not s:
            raise _shell.Failed("a.stack", "cannot tell where the stack of %s is (aos-agent ctl state who)" % self.name, code="StackMissing")
        return s


def __getattr__(name):
    if name in REEXPORT:
        return importlib.import_module(REEXPORT[name])
    if not name.startswith("_") and _shell.word(name) in subcommands():
        return getattr(_shell.Proxy(PROG, pointing=POINTING), name)
    raise AttributeError("module aos.py.agent has no %s (aos-agent subcommands: %s; attach, say, defs)" % (name, ", ".join(subcommands())))


def __dir__():
    return sorted(set(globals()) | set(REEXPORT) | set(n.replace("-", "_") for n in subcommands()))
