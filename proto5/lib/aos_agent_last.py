"""讀取記憶中的最後一則 assistant 回話。"""
import json

import aos_agent_info
from aos_agent_home import AgentError


def last(agent_dir, *, as_json=False):
    info = aos_agent_info.load(agent_dir)
    message = next((m for m in reversed(info['history']) if m['role'] == 'assistant'), None)
    if message is None:
        raise AgentError('NotFound', '記憶裡還沒有 assistant 的回話')
    if as_json:
        print(json.dumps(message, ensure_ascii=False))
    elif not message['content'] and message.get('tool_calls'):
        print('(tool_calls: %s)' % ', '.join(c['function']['name'] for c in message['tool_calls']))
    else:
        print(message['content'])
    return 0
