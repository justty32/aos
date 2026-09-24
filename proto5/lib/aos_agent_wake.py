"""投完輸入後叫醒停著的 agent（2026-09-24 閒置停車；aos-agent tick.md §12、kernel syscall.md 的 wake）。

idle 沒輸入的 agent 退 102＝停車，kernel 要到 park_ms 才再派它。投了話的人（say、talk、郵差）放好輸入檔**之後**
往 K 放一張 `wake` 通知（沒有 id、kernel 不回音），kernel 下一格就把它拉回來。
盡力而為：K 找不到、放不進去都不算錯（崩在「輸入放好、wake 還沒放」之間一樣靠 park_ms 保底）。
"""
import os
from pathlib import Path

import aos_home
import aos_hops
from aos_agent_runtime import KERNEL_ENV, unique_id


def kernel_of(base, env=None):
    """agent 登記在哪個 K：先看 tick.json 記的（它真的登記在那），沒有再看 AOS_KERNEL_HOME。"""
    from aos_agent_status import tick_kernel
    home = tick_kernel(base)
    if home is None:
        env = os.environ if env is None else env
        value = env.get(KERNEL_ENV)
        home = value if isinstance(value, str) and os.path.isabs(value) else None
    return home


def wake(base, env=None):
    """往 K/requests/ 放 `aa-<資料夾名>-wake-<ns>-<pid>.json`；放了回檔名，沒放回 None。"""
    base = Path(os.path.abspath(base))
    home = kernel_of(base, env)
    if home is None or not (Path(home) / 'requests').is_dir():
        return None
    name = 'aa-%s-wake-%s.json' % (base.name, unique_id())
    try:
        aos_home.post_request(home, name, {'jsonrpc': '2.0', 'method': 'wake',
                                           'params': {'name': 'agent-' + base.name}})
    except (aos_home.HomeError, OSError):
        return None
    aos_hops.mark('wake', 'sent', agent=base.name, name=name)
    return name
