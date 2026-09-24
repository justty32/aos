"""看回話（aos-agent.md §1.5）：--last 印最後一則、--wait 等下一則、--follow 一直印。

say --wait 也用這裡的 wait_reply，同一套等法只有一份。
"""
import json
import os
from pathlib import Path
import sys
import time

import aos_agent_info
from aos_agent_home import AgentError, _read_json, read_history
from aos_agent_runtime import files, report
from aos_agent_status import collect, pause_path, show, unregistered, waits

POLL_SECONDS = .2


def print_message(message, *, as_json=False):
    if as_json:
        print(json.dumps(message, ensure_ascii=False))
    elif not message.get('content') and message.get('tool_calls'):
        print('(tool_calls: %s)' % ', '.join(c['function']['name'] for c in message['tool_calls']))
    else:
        print(message.get('content', ''))
    sys.stdout.flush()


def last(agent_dir, *, as_json=False):
    base = Path(os.path.abspath(agent_dir))
    try:
        history = aos_agent_info.load(base)['history']
    except AgentError as original:
        if not (base / 'info.json').exists():
            raise AgentError('NotAnAgent', '%s 沒有 info.json' % base) from original
        report('warn', 'info.json 讀不了（%s），改讀 prompts/history.json' % original.code)
        try:
            history = _read_json(base / 'prompts/history.json')
            if not isinstance(history, list):
                raise original
        except AgentError:
            raise original
    message = next((m for m in reversed(history) if isinstance(m, dict) and m.get('role') == 'assistant'), None)
    if message is None:
        raise AgentError('NotFound', '記憶裡還沒有 assistant 的回話')
    try:
        try:
            data = collect(base)
        except AgentError:
            data = {'waits': waits(base, aos_agent_info.load_state(base)), 'manual_paused': False}
        if data.get('manual_paused'):
            report('warn', '已手動暫停（aos-agent continue --target %s 解除），這則回話可能是舊的' % base)
        closed = [(p, w) for w in data['waits'] for p in w['paths'] if not files(base, p)]
        if closed:
            path, entry = closed[0]
            note = ('連敗暫停中，aos-agent continue --target %s 解除' % base
                    if pause_path(base, path, entry['consume']) else '門關著（在等 %s）' % path)
            report('warn', note + '，這則回話可能是舊的；看 aos-agent status --target %s' % base)
    except (AgentError, OSError, ValueError):
        pass
    print_message(message, as_json=as_json)
    return 0


def _stopped(data, base):
    """等回話時不必再等的三種：沒登記、手動暫停、連敗暫停（先後照 §1.2）。"""
    if unregistered(data['kernel']):
        return 'unregistered', '目前沒登記、沒人處理：aos-agent start --target ' + base
    if data['manual_paused']:
        return 'paused', '已手動暫停，continue 後才會處理：aos-agent continue --target ' + base
    if data['paused']:
        return 'stuck', '問模型連敗暫停了，修好後 aos-agent continue --target ' + base
    return None


def wait_reply(info, h0, timeout_ms, env=None, *, dropped=None, text=None, as_json=False):
    """等這一輪走完、第 h0 則以後出現新的 assistant 回話；say --wait 另給投的檔與 TEXT。"""
    base = info['dir']
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        data = None
        try:
            data = collect(base, env)
            stop = _stopped(data, base)
            if stop is not None:
                report(*stop)
                show(data)
                return 101
            history = read_history(info['history_path'])
            if ((dropped is None or not dropped.exists()) and not data['state_error']
                    and data['state'] == 'idle' and data['batch'] is None and not data['intake']
                    and len(history) > h0 and history[-1]['role'] == 'assistant'
                    and (text is None or any(m['role'] == 'user' and m['content'] == text
                                             for m in history[h0:-1]))):
                print_message(history[-1], as_json=as_json)
                return 0
        except (AgentError, OSError, ValueError):
            pass  # 寫到一半或暫時讀不到，留待下一輪。
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            report('Timeout', '等了 %s 秒沒有新回話（aos-agent status --target %s 看卡在哪）'
                   % (_seconds(timeout_ms), base))
            if data is None:
                # 家被移走時仍保留可辨識的診斷，不把逾時改成讀取失敗。
                print('agent  ' + base)
                print('info  bad：診斷暫時讀不到')
            else:
                show(data)
            return 101
        time.sleep(min(POLL_SECONDS, remaining))


def _seconds(timeout_ms):
    value = timeout_ms / 1000
    return int(value) if value == int(value) else value


def follow(info, *, as_json=False, env=None):
    """每多一則 assistant 就印一則，直到 Ctrl-C；不因暫停或沒登記退出。"""
    seen = len(info['history'])
    try:
        while True:
            try:
                history = read_history(info['history_path'])
            except (AgentError, OSError, ValueError):
                history = None  # 寫到一半，下一輪再讀。
            if history is not None:
                if len(history) < seen:
                    seen = len(history)
                for message in history[seen:]:
                    if message.get('role') == 'assistant':
                        print_message(message, as_json=as_json)
                seen = len(history)
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        return 0


def listen(agent_dir, mode='last', *, timeout_ms=300000, as_json=False, env=None):
    if mode == 'last':
        return last(agent_dir, as_json=as_json)
    info = aos_agent_info.load(agent_dir, env=env)
    if mode == 'follow':
        return follow(info, as_json=as_json, env=env)
    return wait_reply(info, len(info['history']), timeout_ms, env, as_json=as_json)
