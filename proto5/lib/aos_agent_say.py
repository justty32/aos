"""原子投遞 user 訊息，選擇性等待新回話。"""
import json
import os
from pathlib import Path
import tempfile
import time

import aos_agent_info
from aos_agent_home import AgentError, read_history
from aos_agent_last import print_message
from aos_agent_runtime import report, unique_id
from aos_agent_status import collect, kernel_status, show, unregistered

INPUT_WAIT_SECONDS = 10


def deliver(base, value, text):
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
                        raise AgentError('InputBusy', '%s 還沒被收（agent 沒在跑？看 aos-agent status）' % target)
                    time.sleep(min(.2, remaining))
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    return target


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
            report('warn', '目前沒登記、沒人處理：aos-agent start ' + info['dir'])
        return 0
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        data = None
        try:
            data = collect(agent_dir, env)
            if unregistered(data['kernel']):
                report('unregistered', '目前沒登記、沒人處理：aos-agent start ' + info['dir'])
                show(data)
                return 101
            if data['paused']:
                report('stuck', '問模型連敗暫停了，修好後 aos-agent continue ' + info['dir'])
                show(data)
                return 101
            history = read_history(info['history_path'])
            if (not target.exists() and not data['state_error'] and data['state'] == 'idle'
                    and data['batch'] is None and not data['intake'] and history
                    and history[-1]['role'] == 'assistant'
                    and any(m['role'] == 'user' and m['content'] == text for m in history[length:-1])):
                print_message(history[-1])
                return 0
        except (AgentError, OSError, ValueError):
            pass  # 寫到一半或暫時讀不到，留待下一輪。
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            report('Timeout', '等了 %s ms 還沒等到回話' % timeout_ms)
            if data is None:
                # 家被移走時仍保留可辨識的診斷，不把逾時改成讀取失敗。
                print('agent  ' + info['dir'])
                print('info  bad：診斷暫時讀不到')
            else:
                show(data)
            return 101
        time.sleep(min(.2, remaining))
