"""aos.py.kernel - 「kernel」這個東西的 Python 那一面：寫定義的 defs（轉匯出 aos.kernel_spec，檔不搬）。

使用者 11-20 選項框待裁第 9 題「from aos.py.kernel import defs」（一種東西一個 defs，比照 aos.py.agent.defs）；11-21「編譯的kernel入口那塊可以派」。

    from aos.py.kernel import defs          # defs.Kernel、defs.loop、defs.daemon、defs.main…（＝aos.kernel_spec）
    k = defs.Kernel("Let at most two procs run at once", knobs={"max_running": 2})
    defs.main(k)                            # python3 kernel.py --compile／--dry-run

對活的 kernel 下指令的遙控器還沒有（kernel 站靠信與 aos-daemon-ctl，沒有自己的指令）。"""
import importlib

# 轉匯出：名字 → 模組（要搬位置改這一行）
REEXPORT = {"defs": "aos.kernel_spec"}


def __getattr__(name):
    if name in REEXPORT:
        return importlib.import_module(REEXPORT[name])
    raise AttributeError("module aos.py.kernel has no %s (it has %s)" % (name, ", ".join(REEXPORT)))


def __dir__():
    return sorted(set(globals()) | set(REEXPORT))
