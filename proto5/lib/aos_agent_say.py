"""原子投遞 user 訊息，選擇性等待新回話（等法共用 aos_agent_listen.wait_reply）。"""
import json
import os
from pathlib import Path
import tempfile
import time

import aos_agent_info
from aos_agent_home import AgentError
from aos_agent_listen import wait_reply
from aos_agent_runtime import manual_paused, report, unique_id
from aos_agent_status import collect, kernel_status, unregistered

INPUT_WAIT_SECONDS = 10
# fix-r5（aos-agent.md §1.2）：話已經投了，再說一次就會進記憶兩次。
UNREGISTERED_NOTE = '已投入，start 後會處理，不要再說一次：aos-agent start --target '


def deliver(base, value, text, *, with_inode=False):
    """原子投遞；with_inode（talk 用）＝多回投出去那個檔的 inode，好認出「原路徑上的是不是我那份」。"""
    target = Path(os.path.abspath(os.path.join(base, value)))
    directory = value.endswith('/') or target.is_dir()
    if directory:
        target.mkdir(parents=True, exist_ok=True)
        target /= 'say-' + unique_id() + '.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                         prefix='.say-', suffix='.json.tmp', delete=False) as out:
            temp = Path(out.name)
            json.dump({'role': 'user', 'content': text}, out, ensure_ascii=False)
        inode = os.stat(temp).st_ino
        if directory:
            os.rename(temp, target)
        else:
            deadline = time.monotonic() + INPUT_WAIT_SECONDS
            while True:
                try:
                    os.link(temp, target)
                    break
                except FileExistsError:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise AgentError('InputBusy', '%s 還沒被收（agent 沒在跑？看 aos-agent status --target %s）' % (target, base))
                    time.sleep(min(.2, remaining))
    finally:
        if temp is not None:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass  # 已經投成功了，清暫存檔失敗不該把投遞報成失敗
    return (target, inode) if with_inode else target


def _warn_paused(base, env):
    """暫停中照收，但講清楚 continue 之後才會處理（aos-agent.md §1.2）。"""
    if manual_paused(base) is not None:
        report('warn', '已暫停，continue 後才會處理：aos-agent continue --target ' + base)
        return
    try:
        if collect(base, env)['paused']:
            report('warn', '連敗暫停中，修好原因後 continue 才會處理：aos-agent continue --target ' + base)
    except (AgentError, OSError, ValueError):
        pass


def say(agent_dir, text, *, wait=False, timeout_ms=300000, env=None):
    if not text:
        raise AgentError('Usage', 'TEXT 不可為空字串')
    info = aos_agent_info.load(agent_dir, env=env)
    state = aos_agent_info.load_state(agent_dir, env=env)
    length = len(info['history'])
    target = deliver(info['dir'], state['input'][0], text)
    if not wait:
        print('said -> ' + str(target))
        if unregistered(kernel_status(info['dir'], os.environ if env is None else env)):
            print(UNREGISTERED_NOTE + info['dir'])
            report('warn', '目前沒登記、沒人處理：aos-agent start --target ' + info['dir'])
        _warn_paused(info['dir'], env)
        return 0
    return wait_reply(info, length, timeout_ms, env, dropped=target, text=text)
