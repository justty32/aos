"""aos-agent check（advice-r1，aos-agent.md §1.7）：從 aos-kernel check --agent 搬來的啟動前唯讀檢查。

K 不用人給：AOS_KERNEL_HOME（start 用的那個），沒設就用 tick.json 記的（上次 start 寫的）。
先整段跑 kernel 那份檢查，再查這個 agent 家；不問模型（--probe 才打 endpoint）、不拿鎖、不寫檔。
"""
import os

import aos_kernel_check
from aos_agent_runtime import KERNEL_ENV
from aos_agent_status import tick_binding


def find_kernel(base, env):
    """回 (K 或 None, 來源, 額外 bad 訊息或 None)。"""
    raw = tick_binding(base)[0]
    bound = raw if isinstance(raw, str) and os.path.isabs(raw) else None
    value = env.get(KERNEL_ENV)
    if value:
        if not os.path.isabs(value):
            return None, KERNEL_ENV, '%s 不是絕對路徑：%s（start 也會拒絕）' % (KERNEL_ENV, value)
        if raw is not None and raw != value:  # 跟 start 一樣逐字比（aos_agent._tick_inst）
            return value, KERNEL_ENV, ('%s 是 %s，但 tick.json 綁在 %s；start 會拒絕（KernelMismatch），'
                                       '要換 K 就先 aos-agent stop 再刪 tick.json' % (KERNEL_ENV, value, raw))
        return value, KERNEL_ENV, None
    if bound is not None:
        return bound, 'tick.json', None
    return None, None, ('找不到 K：沒設 %s，也沒有 tick.json（沒 start 過）；'
                        'export %s=<kernel 家的絕對路徑> 再跑' % (KERNEL_ENV, KERNEL_ENV))


def check(agent_dir, probe=False, env=None):
    env = os.environ if env is None else env
    base = os.path.abspath(agent_dir)
    checks = aos_kernel_check.Checks()
    home, source, problem = find_kernel(base, env)
    if home is not None:
        checks.report('ok', 'kernel', 'K＝%s（取自 %s）' % (home, source))
    if problem is not None:
        checks.report('bad', 'kernel', problem)
    pools, models, tool_env = None, set(), dict(env)
    if home is not None:
        pools, models, tool_env = aos_kernel_check.kernel_checks(
            checks, home, note='（K＝%s，取自 %s）' % (home, source), recorded_daemon=True)
    checks.agent(base, pools, models, tool_env)
    return aos_kernel_check.finish(checks, probe, then='aos-agent start')
