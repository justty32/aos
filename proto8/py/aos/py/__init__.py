"""aos.py - aos 給人用的 Python 入口（from aos.py import …）：這個夾裡的＝公開的，夾外的 aos.*＝內部零件。

使用者 11-19 裁定（thinking/2026-11/19/aos-pylib-1119/07）：入口叫 aos.py、遙控器式 a = agent.attach("ann")、建斷點 a.bp.add.before_tool("x")、
讀 stack 的檔收進 a.look；寫定義的叫 defs、放在 aos.py.agent.defs（「就 aos.py.agent.defs 吧」）。

    from aos.py import agent, daemon_ctl, std     # agent＝aos-agent 的薄殼與遙控器、daemon_ctl＝aos-daemon-ctl 的薄殼、std＝隨 aos 發的庫
    from aos.py.agent import defs                 # 寫定義（＝aos.agent_spec，檔不搬）
    from aos.py.kernel import defs                # 寫 kernel 的定義（＝aos.kernel_spec；11-20 使用者待裁第 9 題「from aos.py.kernel import defs」）
    from aos.py import fn                         # 函數當工具／hook：@fn.tool、@fn.hook("事件")、fn.main(函數)（11-20 使用者選「新名字 fn」）
    from aos.py import breakpoint as bp           # 斷點（bp.attach("ann") 回的跟 a.bp 同一種；不要用原名 breakpoint，會蓋掉內建的）
    from aos.py import Failed, Timeout, Text, sh  # 唯一的例外、等太久、REPL 裡印得像 shell 的字串、順手打 shell
    import aos.py; aos.py.echo = True             # 每條指令先在 stderr 印 "$ ..."（庫預設關；aos-gdb 打開）

模組名規則：指令 aos-X-Y ↔ aos.py.X_Y。這裡什麼都不先載入：用到哪個名字才 import 那個模組（寫定義那邊不會載入跑指令的東西，反之亦然）。"""
import importlib

from aos.py._shell import Failed, Timeout, Text, sh  # noqa: F401（對外的名字）

echo = False

# 轉匯出：名字 → (模組, 屬性或 None)；要搬位置改這幾行
REEXPORT = {"std": ("aos.agent_spec_lib", "std")}
SUBMODULES = ("agent", "kernel", "daemon_ctl", "breakpoint", "fn")


def __getattr__(name):
    if name in REEXPORT:
        mod, attr = REEXPORT[name]
        m = importlib.import_module(mod)
        return getattr(m, attr) if attr else m
    if name in SUBMODULES:
        return importlib.import_module("aos.py." + name)
    raise AttributeError("module aos.py has no %s (%s)" % (name, ", ".join(SUBMODULES + tuple(REEXPORT) + ("Failed", "Timeout", "Text", "sh", "echo"))))


def __dir__():
    return sorted(set(globals()) | set(REEXPORT) | set(SUBMODULES))
