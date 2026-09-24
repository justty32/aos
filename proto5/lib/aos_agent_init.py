"""建立單一內建預設的 agent 家，最後才發佈身分檔。"""
import os
from pathlib import Path

import aos_home
from aos_agent_home import AgentError


def init(agent_dir, force=False):
    base = Path(os.path.abspath(agent_dir))
    if os.path.lexists(base / 'info.json'):
        raise AgentError('AlreadyExists', '%s 已經是 agent 家（拒絕覆蓋）' % (base / 'info.json'))
    # fix-r5（aos-agent.md §1.1）：非空、又不是 agent 家的資料夾，要 --force 才生。
    if not force and base.is_dir():
        names = sorted(p.name for p in base.iterdir())
        if names:
            shown = '、'.join(names[:5]) + ('…等 %d 個' % len(names) if len(names) > 5 else '')
            raise AgentError('NotEmpty', '%s 不是空資料夾，也不是 agent 家（已有 %s）；確定要生在這裡就加 --force'
                             % (base, shown))
    for name in ('prompts', 'tools', 'input', 'log'):
        (base / name).mkdir(parents=True, exist_ok=True)
    aos_home.write_json(base / 'prompts/system.json',
                        {'content': '你是繁體中文助理，回答簡短。要知道現在時間就呼叫 date 工具。'})
    aos_home.write_json(base / 'tools/date.json', [{
        'type': 'function', 'function': {'name': 'date', 'description': '取得現在的本機日期與時間',
                                       'parameters': {'type': 'object', 'properties': {}}},
        '_meta': {'argv': ['date', '+%Y-%m-%d %H:%M:%S']}}])
    aos_home.write_json(base / 'state.json', {'input': 'input'})
    aos_home.write_json(base / 'info.json', {
        '_metainfo': {'_type': 'llm_agent', '_version': 1}, 'system': 'prompts/system.json',
        'history': 'prompts/history.json', 'tools': ['tools'],
        'llm': {'model': 'default', 'pool': 'llm', 'timeout_ms': 125000},
        'tool_pool': 'default', 'tick': {'pool': 'default', 'interval_ms': 1000}})
    print('initialized ' + str(base))
    print('llm.model 是代號 "default"：llm.json（kernel 的 llm cpu 用 AOS_LLM_CONFIG 指的那份，'
          '見 proto5/README.md 第 2 段）要有 default 這個代號')
    return 0
