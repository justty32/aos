"""aos-agent persona show／set／append：人格是信任資料（proto5/notes/2026-09-24-tool-era/catalog.md〈T-persona〉），
模型改不到——模型只能用 persona_propose 工具寄一份提案（走 T-ask 的待辦），人看過同意了才用這支指令真的寫進
prompts/system.json。三個動作都不叫模型、不碰任何牢（persona 檔本來就只有 agent 自己的 runtime 讀，不經工具）。

找人格檔：<家>/info.json 的 "system"（跟 aos-llm、aos-agent 一樣解指示詞——可以是 `{"$env": …}`／`{"$ref": …}`
這種，不能只當字面字串讀；09-24 astra 審查 M4：舊版直接 `info.get('system')`，遇到指示詞物件會誤判成沒設定、
默默退回預設檔，跟 runtime 實際讀的檔不是同一份，寫了也沒用還印成功）；沒有這個檔或沒寫 system＝
<家>/prompts/system.json（跟 aos_agent_home 的預設一致）。
"""
import json
import os

import aos_home
from aos_agent_home import AgentError, read_info_doc, resolve_field
from aos_directives import Context, DirectiveError

DEFAULT_REL = os.path.join('prompts', 'system.json')


def _system_path(base):
    try:
        doc = read_info_doc(base)
    except AgentError as e:
        if e.code == 'NotAnAgent':      # 沒有 info.json：當還沒開過機，用預設路徑（show 印空字串）
            return os.path.join(base, DEFAULT_REL)
        raise
    if 'system' not in doc.root:
        return os.path.join(base, DEFAULT_REL)
    ctx = Context(doc, base_dir=base, env=os.environ)
    try:
        value = resolve_field(doc, ctx, ['system'])
    except (AgentError, DirectiveError) as e:
        raise AgentError('FieldTypeMismatch', 'info.json 的 system 解不開：%s' % e) from e
    if not isinstance(value, str) or not value:
        raise AgentError('FieldTypeMismatch', 'info.json 的 system 解出來必須是非空路徑字串（現在是 %r）' % (value,))
    return os.path.join(base, value)


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
