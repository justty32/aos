"""看回話（aos-agent.md §1.5）：--last [N] 印最後 N 則、--wait 等下一則、--follow 一直印。

say --wait 也用這裡的 wait_reply，同一套等法只有一份。印法（輪次標頭、工具呼叫行）在 aos_agent_listen_render。
"""
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time

import aos_agent_info
import aos_agent_listen_render as render
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


def print_lines(lines):
    for line in lines:
        print(line)
    sys.stdout.flush()


def _inputs(base):
    try:
        return aos_agent_info.load_state(base)['input']
    except (AgentError, OSError, ValueError, KeyError):
        return []


def last(agent_dir, *, count=1, calls=None, as_json=False):
    base = Path(os.path.abspath(agent_dir))
    try:
        info = aos_agent_info.load(base)
        history, history_path = info['history'], info['history_path']
    except AgentError as original:
        history_path = base / 'prompts/history.json'
        if not (base / 'info.json').exists():
            raise AgentError('NotAnAgent', '%s 沒有 info.json' % base) from original
        report('warn', 'info.json 讀不了（%s），改讀 prompts/history.json' % original.code)
        try:
            history = _read_json(base / 'prompts/history.json')
            if not isinstance(history, list):
                raise original
        except AgentError:
            raise original
    picked, start, total = render.pick(history, count)
    if not picked:
        raise AgentError('NotFound', '記憶裡還沒有 assistant 的回話')
    message = history[picked[-1]]
    warned = False
    try:
        try:
            data = collect(base)
        except AgentError:
            data = {'waits': waits(base, aos_agent_info.load_state(base)), 'manual_paused': False}
        if data.get('manual_paused'):
            warned = True
            report('warn', '已手動暫停（aos-agent continue --target %s 解除），這則回話可能是舊的' % base)
        closed = [(p, w) for w in data['waits'] for p in w['paths'] if not files(base, p)]
        if closed:
            warned = True
            path, entry = closed[0]
            note = ('連敗暫停中，aos-agent continue --target %s 解除' % base
                    if pause_path(base, path, entry['consume']) else '門關著（在等 %s）' % path)
            report('warn', note + '，這則回話可能是舊的；看 aos-agent status --target %s' % base)
        if not warned:
            _warn_processing(base, data, history, message)
    except (AgentError, OSError, ValueError, KeyError):
        pass
    _report_time(history_path, history, message)
    if total < count:
        report('note', '記憶裡只有 %d 則回話，全印' % total)
    if calls:
        _print_span(history, range(start, len(history)), base, calls, as_json)
    elif as_json or count == 1:
        # 只要一則、不看工具：跟以前一樣只印回話本身（方便 $(…)）；--json 每則一行、不加標頭。
        for i in picked:
            print_message(history[i], as_json=as_json)
    else:
        times = render.round_times(history, base, _inputs(base))
        print_lines(render.render(history, picked, times=times))
    return 0


def _warn_processing(base, data, history, message):
    """fix-r5（§1.5）：這一輪還沒走完就講，免得把中途那句當答案。"""
    busy = (bool(message.get('tool_calls')) or history[-1] is not message
            or data.get('state') not in (None, 'idle')
            or data.get('batch') is not None or data.get('intake') or data.get('pending_inputs'))
    if not busy:
        return
    if message.get('tool_calls'):
        names = ', '.join(c['function']['name'] for c in message['tool_calls'])
        report('warn', '還在處理中（tool_calls: %s）：最後的回話還沒出來；要等就 aos-agent listen --wait --target %s'
               % (names, base))
    else:
        report('warn', '還在處理中（新輸入還沒回）：這則是上一輪的回話；要等就 aos-agent listen --wait --target %s' % base)


def _report_time(history_path, history, message):
    """fix-r5（§1.5）：回話附時間＝記憶檔的修改時間（stderr，stdout 照舊只有回話）。"""
    try:
        stamp = datetime.fromtimestamp(os.stat(history_path).st_mtime).strftime('%m-%d %H:%M:%S')
    except OSError:
        return
    report('time', stamp + ('' if history and history[-1] is message else '（記憶最後更新，這則更早）'))


def _stopped(data, base):
    """等回話時不必再等的（先後照 §1.2）：kernel 家有問題、沒登記、手動暫停、連敗暫停、bad。

    fix-r5 加 kernel 與 bad；恢復中、重試中會自己好，不在這裡。
    """
    if data['health']['code'] == 'kernel':
        return 'kernel', data['health']['message']
    if unregistered(data['kernel']):
        return 'unregistered', '目前沒登記、沒人處理：aos-agent start --target ' + base
    if data['manual_paused']:
        return 'paused', '已手動暫停，continue 後才會處理：aos-agent continue --target ' + base
    if data['paused']:
        return 'stuck', '問模型連敗暫停了，修好後 aos-agent continue --target ' + base
    if data['health']['code'] == 'bad':
        return 'bad', data['health']['message']
    return None


def wait_reply(info, h0, timeout_ms, env=None, *, dropped=None, text=None, as_json=False, calls=None):
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
                if dropped is not None:
                    # say --wait：話已經投了，講清楚別再說一次（aos-agent.md §1.2，fix-r5）。
                    print('已投入，start 後會處理，不要再說一次：aos-agent start --target ' + base
                          if stop[0] == 'unregistered' else
                          '已投入 %s，不要再說一次（照上面的原因修好後會處理）' % dropped)
                show(data)
                return 101
            history = read_history(info['history_path'])
            if ((dropped is None or not dropped.exists()) and not data['state_error']
                    and data['state'] == 'idle' and data['batch'] is None and not data['intake']
                    and len(history) > h0 and history[-1]['role'] == 'assistant'
                    and (text is None or any(m['role'] == 'user' and m['content'] == text
                                             for m in history[h0:-1]))):
                if calls:
                    _print_span(history, range(h0, len(history)), base, calls, as_json)
                else:
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


def _print_span(history, indexes, base, calls, as_json):
    """--show-calls：這段的工具呼叫與結果連同回話一起印（有輪次標頭）；--json 每格一行、user 不印。"""
    if as_json:
        for i in indexes:
            if isinstance(history[i], dict) and history[i].get('role') != 'user':
                print_message(history[i], as_json=True)
        return
    times = render.round_times(history, base, _inputs(base))
    print_lines(render.render(history, indexes, calls=calls, times=times))


def follow(info, *, as_json=False, env=None, calls=None):
    """每多一則 assistant 就印一則，直到 Ctrl-C；不因暫停或沒登記退出。

    --show-calls／--show-calls-full：工具結果（role tool）也即時印，叫工具那則印成呼叫行。
    """
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
                names = render.call_names(history, len(history)) if calls else {}
                for message in history[seen:]:
                    if not isinstance(message, dict):
                        continue
                    if calls and not as_json:
                        print_lines(render.event_lines(message, names, calls))
                    elif message.get('role') == 'assistant' or (calls and message.get('role') == 'tool'):
                        print_message(message, as_json=as_json)
                seen = len(history)
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        return 0


def listen(agent_dir, mode='last', *, count=1, calls=None, timeout_ms=300000, as_json=False, env=None):
    """calls：None＝只看回話、'short'＝--show-calls、'full'＝--show-calls-full。"""
    if mode == 'last':
        return last(agent_dir, count=count, calls=calls, as_json=as_json)
    info = aos_agent_info.load(agent_dir, env=env)
    if mode == 'follow':
        return follow(info, as_json=as_json, env=env, calls=calls)
    return wait_reply(info, len(info['history']), timeout_ms, env, as_json=as_json, calls=calls)
