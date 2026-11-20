"""aos.py.breakpoint - 斷點（延伸）：bp.attach("ann") 回的跟 a.bp 同一種（aos.gdb.Breakpoints，檔不搬）。用 from aos.py import breakpoint as bp，別用原名（會蓋掉內建的 breakpoint()）。

    from aos.py import breakpoint as bp
    b = bp.attach("ann", daemon=".stack")
    i = b.add.before_tool("write")          # 回斷點物件：i.id == 1、i.kind == "before_tool"
    b.resume(); b.why(); b.step(); b.rm(i)  # resume／step／pause 預設等到停下才回；wait=False＝送出就回，is_done() 問好了沒
建斷點寫法 a.bp.add.<種類>(...)：使用者 11-19 選項框（thinking/2026-11/19/aos-pylib-1119/07 第 3 題）。"""
from aos.gdb import Breakpoints, KINDS  # noqa: F401（對外的名字）


def attach(name, daemon=None):
    """那一隻的斷點（＝agent.attach(name, daemon).bp）。"""
    from aos.py import agent
    return agent.attach(name, daemon).bp
