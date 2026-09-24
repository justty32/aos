"""aos-agent persona show／set／append：人格是信任資料（proto5/notes/2026-09-24-tool-era/catalog.md〈T-persona〉），
模型改不到——模型只能用 persona_propose 工具寄一份提案（走 T-ask 的待辦），人看過同意了才用這支指令真的寫進
prompts/system.json。三個動作都不叫模型、不碰任何牢（persona 檔本來就只有 agent 自己的 runtime 讀，不經工具）。

找人格檔：<家>/info.json 的 "system"（相對＝相對 agent 家）；沒有這個檔或沒寫 system＝<家>/prompts/system.json
（跟 aos_agent_home 的預設一致）。
"""
import json
import os

import aos_home
from aos_agent_home import AgentError

DEFAULT_REL = os.path.join('prompts', 'system.json')


def _system_path(base):
    info_path = os.path.join(base, 'info.json')
    if not os.path.isfile(info_path):
        return os.path.join(base, DEFAULT_REL)
    try:
        info = aos_home.read_json(info_path)
    except (OSError, ValueError) as e:
        raise AgentError('ReadFailed', 'cannot read %s: %s' % (info_path, e)) from e
    rel = info.get('system') if isinstance(info, dict) else None
    if not isinstance(rel, str) or not rel:
        rel = DEFAULT_REL
    return os.path.join(base, rel)


def _read(path):
    if not os.path.isfile(path):
        return ''
    try:
        data = aos_home.read_json(path)
    except (OSError, ValueError) as e:
        raise AgentError('ReadFailed', 'cannot read %s: %s' % (path, e)) from e
    if not isinstance(data, dict) or not isinstance(data.get('content'), str):
        raise AgentError('MessageInvalid', '%s 必須是含字串 content 的物件' % path)
    return data['content']


def show(target, as_json=False):
    path = _system_path(os.path.abspath(target))
    content = _read(path)
    if as_json:
        print(json.dumps({'content': content}, ensure_ascii=False))
    else:
        print(content, end='' if content.endswith('\n') else '\n')
    return 0


def _write(path, content):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    aos_home.write_json(path, {'content': content})


def set_(target, text):
    path = _system_path(os.path.abspath(target))
    _write(path, text)
    print('已寫入 %s（%d 字）' % (path, len(text)))
    return 0


def append(target, text):
    path = _system_path(os.path.abspath(target))
    content = _read(path)
    new = content + ('' if not content or content.endswith('\n') else '\n') + text
    _write(path, new)
    print('已加一行到 %s（現在 %d 字）' % (path, len(new)))
    return 0


def main(target, action, text=None, as_json=False):
    if action == 'show':
        if text is not None:
            raise AgentError('Usage', 'persona show 不收 TEXT')
        return show(target, as_json=as_json)
    if action in ('set', 'append'):
        if as_json:
            raise AgentError('Usage', '--json 只給 persona show')
        if not text:
            raise AgentError('Usage', 'persona %s 要非空的 TEXT' % action)
        return set_(target, text) if action == 'set' else append(target, text)
    raise AgentError('Usage', 'persona 只認 show、set、append，不是 %r' % (action,))
