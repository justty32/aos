"""kernel 的唯讀健康摘要，供 CLI 與 agent 共用。"""
import os
from pathlib import Path
import time

import aos_daemon
import aos_home
from aos_kernel_info import DEFAULTS, load_info


def health(home, snapshot=None, info=None, now=None) -> tuple[str, str]:
    """回 (code, 一行中文)，讀驗失敗回 broken，不拋出家／I/O 錯誤。"""
    home = Path(os.path.abspath(home))
    try:
        if info is None:
            info = load_info(home)
        if snapshot is None:
            state = aos_home.read_state(home)
            snapshot = {**state, "kernel_cpu": {"name": state.get("kcpu")}}
        daemon_home = os.path.abspath(info.get("daemon") or aos_daemon.daemon_home())
        boot = "aos-kernel boot %s --daemon %s" % (home, daemon_home)
        check = "aos-kernel check %s" % home
        missing = [str(home / name) + '/' for name in ('requests', 'responses', 'cpus')
                   if not (home / name).is_dir()]
        if missing:
            return 'dirs', 'K 家缺目錄：%s（跑 %s）' % ('、'.join(missing), check)
        if snapshot.get('phase') == 'stopped' or not snapshot.get('chain'):
            return 'stopped', '停機中（%s）' % boot
        daemon = snapshot.get('daemon')
        alive = daemon['alive'] if daemon is not None else aos_daemon.is_alive(daemon_home)
        if not alive:
            return 'daemon', 'daemon 沒在跑：%s（先 aos-daemon --home %s，再 %s）' % (
                daemon_home, daemon_home, boot)
        children = daemon['children'] if daemon is not None else aos_daemon.read_state(daemon_home)['children']
        names = dict.fromkeys([*info['cpus'], *(snapshot.get('cpus') or {})])
        kcpu = snapshot['kernel_cpu']['name']
        if kcpu:
            names[kcpu] = None
        missing = [name for name in names if not children.get(name) or children[name]['state'] == 'missing']
        if missing:
            return 'cpus', 'cpu missing：%s（跑 %s）' % ('、'.join(missing), boot)
        if snapshot.get('phase') == 'running':
            age = (time.time() if now is None else now) - (home / 'state.json').stat().st_mtime
            if age > max(10, 10 * info.get('tick_ms', DEFAULTS['tick_ms']) / 1000):
                return 'stall', 'tick 停住：%d 秒沒前進（跑 %s）' % (age, check)
        return 'ok', 'ok'
    except (aos_home.HomeError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        reason = ' '.join(str(exc).splitlines())
        return 'broken', 'kernel 家讀不到：%s（跑 aos-kernel check %s）' % (reason, home)
