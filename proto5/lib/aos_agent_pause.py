"""手動暫停與解除暫停（aos-agent.md §1.4、§1.6）；只投檔、刪檔，不拿 tick 鎖、不寫 state.json。"""
from datetime import datetime
import os
from pathlib import Path

import aos_agent_info
from aos_agent_home import AgentError
from aos_agent_runtime import PAUSED, manual_paused
from aos_agent_status import pause_path, waits


def pause(agent_dir):
    """aos-agent.md §1.6：只放一個 paused 檔，不拿 tick 鎖、不寫 state.json。"""
    base = Path(os.path.abspath(agent_dir))
    if not (base / 'info.json').exists():
        raise AgentError('NotAnAgent', '%s 沒有 info.json' % base)
    if manual_paused(base) is not None:
        print('已經暫停了（aos-agent continue --target %s 解除）' % base)
        return 0
    stamp = datetime.now().astimezone().isoformat(timespec='seconds')
    temp = base / ('.%s.%d.tmp' % (PAUSED, os.getpid()))
    temp.write_text('paused at %s\n' % stamp, encoding='utf-8')
    os.rename(temp, base / PAUSED)
    print('paused %s（aos-agent continue --target %s 解除）' % (base, base))
    return 0


def resume(agent_dir, env=None):
    base = os.path.abspath(agent_dir)
    if not os.path.exists(os.path.join(base, 'info.json')):
        raise AgentError('NotAnAgent', '%s 沒有 info.json' % base)
    manual = False
    try:
        os.unlink(os.path.join(base, PAUSED))
        manual = True
        print('continued: 解除手動暫停')
    except FileNotFoundError:
        pass
    st = aos_agent_info.load_state(base, env=env)
    paths = dict.fromkeys(p for w in waits(base, st) for p in w['paths']
                          if pause_path(base, p, w['consume']))
    for path in paths:
        try:
            with open(path, 'x'):
                pass
            print('continued: touched ' + path)
        except FileExistsError:
            print('已經 touch 過，等下一格 tick：' + path)
    if not paths and not manual:
        print('沒有在暫停')
    return 0
