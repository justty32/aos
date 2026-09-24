"""讀取最後回話；設定壞掉時仍可搶救慣例記憶。"""
import json
import os
from pathlib import Path

import aos_agent_info
from aos_agent_home import AgentError, _read_json
from aos_agent_runtime import files, report
from aos_agent_status import collect, pause_path, waits


def print_message(message, *, as_json=False):
    if as_json:
        print(json.dumps(message, ensure_ascii=False))
    elif not message.get('content') and message.get('tool_calls'):
        print('(tool_calls: %s)' % ', '.join(c['function']['name'] for c in message['tool_calls']))
    else:
        print(message.get('content', ''))


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
            data = {'waits': waits(base, aos_agent_info.load_state(base))}
        closed = [(p, w) for w in data['waits'] for p in w['paths'] if not files(base, p)]
        if closed:
            path, entry = closed[0]
            note = ('連敗暫停中，aos-agent continue 解除' if pause_path(base, path, entry['consume'])
                    else '門關著（在等 %s）' % path)
            report('warn', note + '，這則回話可能是舊的；看 aos-agent status')
    except (AgentError, OSError, ValueError):
        pass
    print_message(message, as_json=as_json)
    return 0
