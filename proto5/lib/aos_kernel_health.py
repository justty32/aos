"""kernel 的唯讀健康摘要，供 CLI 與 agent 共用（kernel-cli.md 的 ls；其他照 proto5 §6 ls）。

先中先印：缺目錄 → 停機中 → daemon 沒在跑 → kernel cpu 不在 → tick 停住 → 池出錯／池不見了 → 搬池中 → 池少幾顆 → ok。
工作池不逐顆查，只看每池 daemon 的 summary.json（O(池數)）。
"""
import os
from pathlib import Path
import time

import aos_home
from aos_kernel_info import DEFAULTS, KERNEL_POOL, load_info

DIRS = ("requests", "responses", "pools")


def health(home, snapshot=None, info=None, now=None) -> tuple[str, str]:
    """回 (code, 一行中文)，讀驗失敗回 broken，不拋出家／I/O 錯誤。

    snapshot 是 aos_kernel_boot.status(K) 的形狀（pools 每格多 summary、daemon{home, alive}）；沒給就自己讀。
    """
    home = Path(os.path.abspath(home))
    try:
        from aos_kernel_boot import status
        from aos_kernel_cpu import _Alive, pool_rows
        if info is None:
            info = load_info(home)
        boot = "aos-kernel boot --target %s" % home
        check = "aos-kernel check --target %s" % home
        missing = [str(home / name) + '/' for name in DIRS if not (home / name).is_dir()]
        if missing:
            return 'dirs', 'K 家缺目錄：%s（跑 %s）' % ('、'.join(missing), check)
        if snapshot is None:
            snapshot = status(home)
        if snapshot.get('phase') == 'stopped' or not snapshot.get('chain'):
            return 'stopped', '停機中（%s）' % boot
        pools = snapshot.get('pools') or {}
        known = {}
        daemon = snapshot.get('daemon') or {}
        if daemon.get('home'):
            known[daemon['home']] = bool(daemon.get('alive'))
        alive = _Alive(known)
        summaries = {p: e.get('summary') for p, e in pools.items()}
        rows = pool_rows(home, info, {**snapshot, 'pools': pools}, summaries=summaries, alive=alive)
        kernel = rows.get(KERNEL_POOL)
        kdaemon = (kernel or {}).get('daemon') or daemon.get('home')
        if not kdaemon or not alive(kdaemon):
            where = kdaemon or '（kernel 池解不出 daemon 家）'
            return 'daemon', 'daemon 沒在跑：%s（先 aos-daemon boot --target %s；之後 health 還不是 ok 再 %s）' % (
                where, where, boot)
        dead = list(dict.fromkeys(r['daemon'] for r in rows.values()
                                  if r['declared'] and r['daemon'] and not alive(r['daemon'])))
        if dead:
            return 'daemon', 'daemon 沒在跑：%s（先 aos-daemon boot --target %s）' % ('、'.join(dead), dead[0])
        ksum = (kernel or {}).get('summary') or {}
        if kernel is None or not kernel['declared'] or ksum.get('running', 0) == 0:
            return 'cpus', 'kernel cpu 不在（daemon 沒在跑或還在拉；跑 %s）' % boot
        if snapshot.get('phase') == 'running':
            age = (time.time() if now is None else now) - (home / 'state.json').stat().st_mtime
            if age > max(10, 10 * info.get('tick_ms', DEFAULTS['tick_ms']) / 1000):
                return 'stall', 'tick 停住：%d 秒沒前進（跑 %s）' % (age, check)
        work = [r for p, r in rows.items() if p != KERNEL_POOL and r['declared']]
        broken = []
        for r in work:
            if r['error']:
                broken.append('池 %s：%s（%s）' % (r['pool'], r['error'].get('code'), r['error'].get('message') or '-'))
            elif r['gone']:
                broken.append('池 %s：池不見了（跑 %s）' % (r['pool'], boot))
        if broken:
            return 'pools', '；'.join(broken)
        if snapshot.get('phase') != 'running':
            return 'ok', 'ok'   # 停機收尾中：池本來就在縮，不報少顆
        moving = [r for r in work if r['moving']]
        if moving:
            return 'recovering', '；'.join('搬池中：池 %s（舊位置 %s %s 收完才換）' % (r['pool'], r['daemon'], r['dpool'])
                                           for r in moving)
        short = []
        for r in work:
            summary = r['summary']
            if summary is None or not r['sent']:
                continue
            lack = r['sent'] - summary.get('running', 0)
            if lack > 0:
                short.append('池 %s 少 %d 顆（daemon 在補；看 aos-daemon ls --target %s --pool %s）' % (
                    r['pool'], lack, r['daemon'], r['dpool']))
        if short:
            return 'recovering', '；'.join(short)
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
