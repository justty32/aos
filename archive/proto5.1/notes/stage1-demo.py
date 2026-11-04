#!/usr/bin/env python3
"""第 1 段真模型驗證：新建指定 scratchpad，逐次記錄兩支 CLI 的退出碼與狀態。"""
import json
from pathlib import Path
import subprocess


PROTO = Path(__file__).resolve().parents[1]
DEMO = Path('/tmp/claude-1000/-home-guanyu-projs-aos/c15290bb-f956-4ef2-8f96-46acea00faa2/scratchpad/p51-demo')


def put(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def snapshot(agent):
    path = agent / 'state.json'
    state = json.loads(path.read_text()) if path.exists() else {}
    return {'state': state.get('state', 'idle'), 'waits': state.get('waits', []),
            'errors': state.get('errors', 0)}


def main():
    """只對全新的 demo 家建檔，避免重跑時蓋掉前一次可檢視的結果。"""
    DEMO.mkdir(parents=True, exist_ok=False)
    agent, cpu = DEMO / 'A', DEMO / 'C'
    put(cpu / 'info.json', {'_metainfo': {'_type': 'llm_cpu', '_version': 1}})
    put(agent / 'info.json', {
        '_metainfo': {'_type': 'llm_agent', '_version': 1},
        'tools': ['tools/now.json'],
        'engine': {'endpoint': 'http://127.0.0.1:1234/v1', 'model': 'qwen/qwen3-1.7b',
                   'cpu': '../C', 'params': {'temperature': 0, 'max_tokens': 1024}}})
    put(agent / 'prompts/system.json', {'content': '請用繁體中文簡潔回答。詢問目前時間時必須先使用 now 工具，收到結果後直接回答。'})
    put(agent / 'tools/now.json', [{
        'type': 'function', 'function': {'name': 'now', 'description': '查詢台灣目前日期與時間',
                                       'parameters': {'type': 'object', 'properties': {}, 'required': []}},
        '_meta': {'argv': ['date', '+%Y-%m-%d %H:%M:%S %Z'], 'envs': {'TZ': 'Asia/Taipei'}}}])
    put(agent / 'input.json', '現在幾點？用工具查')
    records = []
    for index in range(30):
        target = agent if index % 2 == 0 else cpu
        cli = 'aos-agent' if target == agent else 'aos-llm-cpu'
        before = snapshot(agent)
        result = subprocess.run([str(PROTO / 'cli' / cli), str(target)],
                                text=True, capture_output=True, timeout=180)
        row = {'step': index + 1, 'command': cli + ' ' + target.name, 'exit': result.returncode,
               'before': before, 'after': snapshot(agent), 'stdout': result.stdout, 'stderr': result.stderr}
        records.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        put(DEMO / 'trace.json', records)
        if result.returncode not in (0, 101):
            raise RuntimeError(result.stderr)
        if target == agent and result.returncode == 101 and snapshot(agent)['state'] == 'idle':
            history = json.loads((agent / 'prompts/history.json').read_text())
            if not any(m['role'] == 'tool' for m in history):
                raise RuntimeError('模型沒有真的使用工具')
            if not history or history[-1]['role'] != 'assistant':
                raise RuntimeError('沒有最終 assistant 回話')
            print('REPLY ' + history[-1].get('content', ''), flush=True)
            return
    raise RuntimeError('30 次呼叫仍未完成')


if __name__ == '__main__':
    main()
