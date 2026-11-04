"""手動暫停與解除暫停（aos-agent.md §1.4、§1.6）；只投檔、刪檔，不拿 tick 鎖、不寫 state.json。"""
from datetime import datetime
import os
from pathlib import Path

import aos_agent_info
import aos_home
from aos_agent_home import AgentError
from aos_agent_runtime import KERNEL_ENV, PAUSED, RESUMED, kernel_procs, manual_paused
from aos_agent_status import pause_path, waits


def pause(agent_dir):
    """aos-agent.md §1.6：只放一個 paused 檔，不拿 tick 鎖、不寫 state.json。"""
    base = Path(os.path.abspath(agent_dir))
    if not (base / 'info.json').exists():
        raise AgentError('NotAnAgent', '%s 沒有 info.json' % base)
    if manual_paused(base) is not None:
        print('已經暫停了（aos-agent continue --target %s 解除）' % base)
        return 0
    _mark(base, PAUSED)
    print('paused %s（aos-agent continue --target %s 解除）' % (base, base))
    return 0


def _mark(base, name):
    stamp = datetime.now().astimezone().isoformat(timespec='seconds')
    temp = Path(base) / ('.%s.%d.tmp' % (name, os.getpid()))
    temp.write_text('%s at %s\n' % (name, stamp), encoding='utf-8')
    os.rename(temp, Path(base) / name)


def _resume(base, env=None, lines=None):
    """解兩種暫停；回 (手動解了沒, 連敗解了沒, 要印的行)。state 讀驗錯照拋（手動暫停已先解，行已記進 lines）。"""
    lines = [] if lines is None else lines
    manual = False
    try:
        os.unlink(os.path.join(base, PAUSED))
        manual = True
        lines.append('continued: 解除手動暫停')
    except FileNotFoundError:
        pass
    st = aos_agent_info.load_state(base, env=env)
    paths = dict.fromkeys(p for w in waits(base, st) for p in w['paths']
                          if pause_path(base, p, w['consume']))
    for path in paths:
        if os.path.exists(path):
            lines.append('已經 touch 過，等下一格 tick：' + path)
            continue
        # fix-r5：兩階段——先放 resumed 再 touch 門（§1.4）。門沒開之前 tick 不會重問，
        # 所以「成功結清刪 resumed」一定排在這之後，不會被這裡蓋回去（astra 審查）。
        _mark(base, RESUMED)
        try:
            with open(path, 'x'):
                pass
            lines.append('continued: touched ' + path)
        except FileExistsError:
            lines.append('已經 touch 過，等下一格 tick：' + path)
    if paths:
        lines.append('已解除暫停，等下一次成功（aos-agent status --target %s 看）' % base)
    return manual, bool(paths), lines


def resume(agent_dir, env=None):
    base = os.path.abspath(agent_dir)
    if not os.path.exists(os.path.join(base, 'info.json')):
        raise AgentError('NotAnAgent', '%s 沒有 info.json' % base)
    lines = []
    try:
        _resume(base, env, lines)
    except BaseException:
        if lines:
            print('\n'.join(lines))
        raise
    print('\n'.join(lines) if lines else '沒有在暫停')
    return 0


def resume_all(env=None):
    """continue --all（aos-agent.md §1.4）：K 帳本裡登記的 agent 家，暫停中的逐個解。"""
    from aos_agent import _other_home
    env = os.environ if env is None else env
    kernel = env.get(KERNEL_ENV)
    if not isinstance(kernel, str) or not os.path.isabs(kernel):
        raise AgentError('Usage', 'continue --all 要 %s（kernel 家的絕對路徑）' % KERNEL_ENV)
    procs = kernel_procs(kernel)
    homes = []
    for name, proc in procs.items():
        if not name.startswith('agent-') or not isinstance(proc, dict) or proc.get('once'):
            continue
        target = proc.get('target')
        if isinstance(target, str) and Path(target).name == 'tick.json':
            base = str(Path(target).parent)
            if os.path.exists(os.path.join(base, 'info.json')) and not _other_home(Path(base)):
                homes.append((name, base))
    if not homes:
        print('K 帳本裡沒有登記的 agent（%s）' % kernel)
        return 0
    done = skipped = 0
    for name, base in homes:
        try:
            manual, stuck, _ = _resume(base, env)
        except (AgentError, aos_home.HomeError, OSError, ValueError) as exc:
            skipped += 1
            print('%s  %s  跳過：%s' % (name, base, ' '.join(str(exc).split())))
            continue
        what = '、'.join(w for w, on in (('解除手動暫停', manual), ('解除連敗暫停（等下一次成功）', stuck)) if on)
        done += bool(what)
        print('%s  %s  %s' % (name, base, what or '沒在暫停'))
    print('continued %d／%d' % (done, len(homes)))
    return 1 if skipped else 0
