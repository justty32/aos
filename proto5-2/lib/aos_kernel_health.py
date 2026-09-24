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
        boot = "aos-kernel boot --target %s --daemon-target %s" % (home, daemon_home)
        check = "aos-kernel check --target %s" % home
        missing = [str(home / name) + '/' for name in ('requests', 'responses', 'cpus')
                   if not (home / name).is_dir()]
        if missing:
            return 'dirs', 'K 家缺目錄：%s（跑 %s）' % ('、'.join(missing), check)
        if snapshot.get('phase') == 'stopped' or not snapshot.get('chain'):
            return 'stopped', '停機中（%s）' % boot
        daemon = snapshot.get('daemon')
        alive = daemon['alive'] if daemon is not None else aos_daemon.is_alive(daemon_home)
        if not alive:
            return 'daemon', 'daemon 沒在跑：%s（先 aos-daemon boot --target %s，再 %s）' % (
                daemon_home, daemon_home, boot)
        children = daemon['children'] if daemon is not None else aos_daemon.read_state(daemon_home)['children']
        names = dict.fromkeys([*info['cpus'], *(snapshot.get('cpus') or {})])
        kcpu = snapshot['kernel_cpu']['name']
        if kcpu:
            names[kcpu] = None
        missing = [name for name in names if not children.get(name) or children[name]['state'] == 'missing']
        if missing:
            return 'cpus', 'cpu missing：%s（跑 %s）' % ('、'.join(missing), boot)
        # fix-r5：孩子死了、daemon 等著重拉——不是 ok，但會自己好。
        dead = [name for name in names if children[name]['state'] == 'dead']
        if dead:
            return 'recovering', '恢復中（%s cpu dead，daemon 重拉中）' % '、'.join(dead)
        if snapshot.get('phase') == 'running':
            age = (time.time() if now is None else now) - (home / 'state.json').stat().st_mtime
            if age > max(10, 10 * info.get('tick_ms', DEFAULTS['tick_ms']) / 1000):
                return 'stall', 'tick 停住：%d 秒沒前進（跑 %s）' % (age, check)
        return 'ok', 'ok'
    except (aos_home.HomeError, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        reason = ' '.join(str(exc).splitlines())
        return 'broken', 'kernel 家讀不到：%s（跑 aos-kernel check --target %s）' % (reason, home)


def agent_marks(snapshot):
    """fix-r5：帳本裡每個 agent 的暫停／重試標記 {行程名: (code, 標記)}；讀不到的略過（ls 用）。"""
    from aos_agent_status import brief  # 延後 import：aos_agent_status 也 import 本模組
    marks = {}
    for name, proc in (snapshot.get('procs') or {}).items():
        if not name.startswith('agent-') or not isinstance(proc, dict) or proc.get('once'):
            continue
        target = proc.get('target')
        if not isinstance(target, str) or Path(target).name != 'tick.json':
            continue
        mark = brief(Path(target).parent)
        if mark is not None:
            marks[name] = mark
    return marks


def agents_health(marks):
    """kernel 本身 ok 時，ls 第一行再看 agent：暫停 → 重試中 → 等下一次成功；都沒有回 None。"""
    paused = ['%s（%s）' % (n, '連敗' if code == 'paused' else '手動' if code == 'manual_paused' else '手動＋連敗')
              for n, (code, _) in marks.items() if code in ('paused', 'manual_paused', 'both_paused')]
    if paused:
        return 'agents_paused', 'agent 暫停中：%s（修好原因後 aos-agent continue --all）' % '、'.join(paused)
    retrying = [n + text.removeprefix('重試中') for n, (code, text) in marks.items() if code == 'retrying']
    if retrying:
        return 'retrying', '重試中：' + '、'.join(retrying)
    resuming = [n for n, (code, _) in marks.items() if code == 'resuming']
    if resuming:
        return 'resuming', '已解除暫停，等下一次成功：' + '、'.join(resuming)
    return None
