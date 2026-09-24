"""一格接一格的排程者：proto5-2 的池表、帳本第 2 版、只碰有事的 cpu、宣告式 scale。

規範在 proto5-2/spec/（kernel-*.md、protocol.md、handoff.md）；沒寫的照 proto5/spec/kernel/。
這個檔只是匯出層：實作分在 aos_kernel_info／ledger／pools／engine／boot／cpu／health／cli。
"""
import sys

from aos_kernel_info import (
    CLI, CPU_CLI, DEFAULTS, KCPU, KERNEL_POOL, KernelError, CLIUsage, _name, _bad, load_info,
    _parse_info, _validate_info, info_from_config, init, new_state, new_pool, classify, _put, _body_error,
    members, is_member, encode, member_set, cpu_key, split_key, pool_location, work_pools, pool_name_ok,
    error_code,
)
from aos_kernel_ledger import KernelLedger
from aos_kernel_pools import PoolsMixin, envs_digest, template, pool_summary
from aos_kernel_engine import Kernel, tick
from aos_kernel_boot import boot, status, stop
from aos_kernel_cpu import cpu_add, cpu_rm, cpu_ls, pool_rows, kernel_running
from aos_kernel_health import health, agent_marks, agents_health
from aos_kernel_cli import (
    _stderr_hint, _summary, _Parser, _parser, _cli_request, main,
)


if __name__ == "__main__":
    sys.exit(main())
