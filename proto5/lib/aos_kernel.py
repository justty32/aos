"""一格接一格的排程者：kernel.md 的帳本、出貨箱、syscall 與 boot。

持久決定只寫 state.json；工作與四類出貨先記後放，只有接 tick 鏈先放後記。
目標只記路徑、不讀 inst；交給執行它的 cpu 與 aos-exec 讀驗。
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import aos_client
import aos_daemon
import aos_home
from aos_directives import Context, DirectiveError, Document, parse_options, resolve_located

from aos_kernel_info import (
    CLI, CPU_CLI, DEFAULTS, KernelError, CLIUsage, _name, _bad, load_info,
    _parse_info, _validate_info, init, _idle, new_state, classify, _put, _body_error,
)
from aos_kernel_engine import Kernel, tick
from aos_kernel_boot import boot, status, stop
from aos_kernel_cli import (
    _cpu_options, _stderr_hint, _summary, _Parser, _parser, _cli_request, main,
)


if __name__ == "__main__":
    sys.exit(main())
