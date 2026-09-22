#!/usr/bin/env python3
"""第 2 段：真模型＋sleep 2/date CPU 工具，保留每次 CLI 的退出碼、門與狀態。"""
import argparse
import json
from pathlib import Path
import subprocess
import time


PROTO = Path(__file__).resolve().parents[1]


def put(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def snapshot(agent):
    path = agent / 'state.json'
    state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    return {key: state.get(key, default) for key, default in
            (('state', 'idle'), ('waits', []), ('errors', 0))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dir', nargs='?', type=Path,
                        default=PROTO / '.build' / ('stage2-demo-%d' % time.time_ns()))
    demo = parser.parse_args().dir.resolve()
    demo.mkdir(parents=True, exist_ok=False)
    agent, llm, tool = demo / 'A', demo / 'C', demo / 'T'
    put(llm / 'info.json', {'_metainfo': {'_type': 'llm_cpu', '_version': 1}})
    put(tool / 'info.json', {'_metainfo': {'_type': 'tool_cpu', '_version': 1}})
    put(agent / 'info.json', {
        '_metainfo': {'_type': 'llm_agent', '_version': 1},
        'tools': ['tools/now.json'], 'tool_cpu': '../T',
        'engine': {'endpoint': 'http://127.0.0.1:1234/v1', 'model': 'qwen/qwen3-1.7b',
                   'cpu': '../C', 'params': {'temperature': 0, 'max_tokens': 1024}}})
    put(agent / 'prompts/system.json', {
        'content': '請用繁體中文簡潔回答。詢問目前時間時必須先使用 now 工具，收到結果後直接回答。'})
    put(agent / 'tools/now.json', [{
        'type': 'function', 'function': {
            'name': 'now', 'description': '查詢台灣目前日期與時間，執行約需兩秒',
            'parameters': {'type': 'object', 'properties': {}, 'required': []}},
        '_run': 'cpu', '_timeout_ms': 10000,
        '_meta': {'argv': ['sh', '-c', 'sleep 2; date "+%Y-%m-%d %H:%M:%S %Z"'],
                  'envs': {'TZ': 'Asia/Taipei'}}}])
    put(agent / 'input.json', '現在幾點？用工具查')
    records = []

    def invoke(cli, target):
        before = snapshot(agent)
        started = time.monotonic()
        result = subprocess.run([str(PROTO / 'cli' / cli), str(target)],
                                text=True, capture_output=True, timeout=180)
        row = {'step': len(records) + 1, 'command': cli + ' ' + target.name,
               'exit': result.returncode, 'seconds': round(time.monotonic() - started, 3),
               'before': before, 'after': snapshot(agent),
               'stdout': result.stdout, 'stderr': result.stderr}
        records.append(row)
        put(demo / 'trace.json', records)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        if result.returncode not in (0, 101):
            raise RuntimeError(result.stderr)
        return row

    print('DEMO ' + str(demo), flush=True)
    for _ in range(20):
        row = invoke('aos-agent', agent)
        if row['exit'] == 101 and row['after']['state'] == 'idle':
            history = json.loads((agent / 'prompts/history.json').read_text(encoding='utf-8'))
            if not any(m['role'] == 'tool' for m in history) or history[-1]['role'] != 'assistant':
                raise RuntimeError('缺少工具結果或最終回覆')
            if not list((tool / 'done').glob('*.json')):
                raise RuntimeError('工具沒有真的經過 tool cpu')
            print('REPLY ' + history[-1].get('content', ''), flush=True)
            return
        if row['after']['waits'] and not row['before']['waits']:
            probe = invoke('aos-agent', agent)
            if probe['exit'] != 101 or probe['before'] != probe['after']:
                raise RuntimeError('結果未到時沒有留在原地等')
        invoke('aos-llm-cpu', llm)
        invoke('aos-tool-cpu', tool)
    raise RuntimeError('20 輪仍未完成')


if __name__ == '__main__':
    main()
