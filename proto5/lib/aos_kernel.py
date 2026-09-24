"""一格接一格的排程者：proto5-2 的池表、帳本第 2 版、只碰有事的 cpu、宣告式 scale。

規範在 proto5-2/spec/（kernel-*.md、protocol.md、handoff.md）；沒寫的照 proto5/spec/kernel/。
這個檔只是入口＋匯出層：實作分在 aos_kernel_info／ledger／pools／engine／boot／cpu／rows／health／ls／check／cli。
下面只匯出 cli/aos-kernel 與測試真的從這裡拿的名字；其餘請直接 import 各模組。
"""
import sys

from aos_kernel_info import CLI, KernelError, classify, init, load_info, members, new_pool, new_state
from aos_kernel_engine import Kernel, tick
from aos_kernel_boot import boot, status
from aos_kernel_cli import main


if __name__ == "__main__":
    sys.exit(main())
