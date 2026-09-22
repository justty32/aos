#!/usr/bin/env python3
"""三顆 kernel CPU 跑 agent / llm CPU / tool CPU；保留 CLI、ls、記憶與 stop 證據。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PROTO = Path(__file__).resolve().parents[1]


def put(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def pgrep(ignore_ancestors=False):
    command = ['pgrep', *(['-A'] if ignore_ancestors else []), '-f', 'aos-']
    result = subprocess.run(command, text=True, capture_output=True)
    return {'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}


def main():
    demo = PROTO / '.build' / ('stage5-demo-%d' % time.time_ns())
    demo.mkdir(parents=True)
    agent, llm, tool, kernel, daemon_home = [demo / n for n in ('A', 'C', 'T', 'K', 'D')]
    env = dict(os.environ, AOS_DAEMON_HOME=str(daemon_home), PYTHONDONTWRITEBYTECODE='1')
    trace = {'demo': str(demo), 'endpoint': 'http://127.0.0.1:1234/v1',
             'model': 'qwen/qwen3-1.7b', 'before_pgrep': pgrep(), 'commands': [], 'snapshots': []}
    daemon = None

    def save():
        put(demo / 'trace.json', trace)

    def invoke(name, *args):
        command = [str(PROTO / 'cli' / name), *map(str, args)]
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
        record = {'command': command, 'exit': result.returncode,
                  'stdout': result.stdout, 'stderr': result.stderr}
        trace['commands'].append(record)
        save()
        if result.returncode:
            raise RuntimeError(str(record))
        return result.stdout

    put(llm / 'info.json', {
        '_metainfo': {'_type': 'llm_cpu', '_version': 1},
        'models': {'small': {'endpoint': trace['endpoint'], 'model': trace['model'],
                             'api_key': None, 'timeout_ms': 120000}}})
    put(tool / 'info.json', {'_metainfo': {'_type': 'tool_cpu', '_version': 1}})
    put(agent / 'info.json', {
        '_metainfo': {'_type': 'llm_agent', '_version': 1},
        'tools': ['tools/now.json'], 'tool_cpu': '../T',
        'engine': {'model': 'small', 'cpu': '../C',
                   'params': {'temperature': 0, 'max_tokens': 1024}}})
    put(agent / 'prompts/system.json', {
        'content': '請用繁體中文簡潔回答。詢問目前時間時必須先使用 now 工具，收到結果後直接回答。'})
    put(agent / 'tools/now.json', [{
        'type': 'function', 'function': {
            'name': 'now', 'description': '查詢台灣目前日期與時間，執行約需兩秒',
            'parameters': {'type': 'object', 'properties': {}, 'required': []}},
        '_run': 'cpu', '_timeout_ms': 10000,
        '_meta': {'argv': ['sh', '-c', 'sleep 2; date "+%Y-%m-%d %H:%M:%S %Z"'],
                  'envs': {'TZ': 'Asia/Taipei'}}}])
    for home, cli in ((agent, 'aos-agent'), (llm, 'aos-llm-cpu'), (tool, 'aos-tool-cpu')):
        put(home / 'inst.json', {'argv': [str(PROTO / 'cli' / cli), str(home)],
                                 'cwd': str(home),
                                 'stderr': {'$opt': 'append', '$val': str(home / 'stderr.log')}})
    try:
        invoke('aos-kernel', 'init', kernel, '--ncpu', 3)
        # Keep the public defaults; this is a real one-second kernel and runner cadence.
        for name, home in (('agent', agent), ('llm', llm), ('tool', tool)):
            invoke('aos-kernel', 'add', kernel, home / 'inst.json', '--name', name)
        with (demo / 'daemon-stderr.log').open('w') as log:
            daemon = subprocess.Popen([str(PROTO / 'cli/aos-daemon')], env=env,
                                      stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 10
        while not (daemon_home / 'state.json').exists():
            if daemon.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('daemon did not start')
            time.sleep(.05)
        invoke('aos-kernel', 'boot', kernel)
        trace['kernel_info'] = json.loads((kernel / 'info.json').read_text())
        trace['daemon_info'] = json.loads((daemon_home / 'info.json').read_text())
        # ls now uses the daemon recorded by boot, even without the shell variable.
        env.pop('AOS_DAEMON_HOME', None)
        put(agent / 'input.json', '現在幾點？用工具查')
        start = time.monotonic()
        last_signature = None
        while time.monotonic() - start < 150:
            state_path = agent / 'state.json'
            state = json.loads(state_path.read_text()) if state_path.exists() else {}
            history_path = agent / 'prompts/history.json'
            history = json.loads(history_path.read_text()) if history_path.exists() else []
            signature = json.dumps([state, len(history)], sort_keys=True)
            if signature != last_signature:
                output = invoke('aos-kernel', 'ls', kernel)
                row = {'seconds': round(time.monotonic() - start, 3),
                       'state': state, 'history_length': len(history), 'ls': output,
                       'runners': {str(p.parent): json.loads(p.read_text())
                                   for p in sorted((daemon_home / 'runners').glob('*/run.json'))}}
                trace['snapshots'].append(row)
                save()
                print(json.dumps(row, ensure_ascii=False), flush=True)
                last_signature = signature
            if (state.get('state') == 'idle' and history and
                    history[-1]['role'] == 'assistant' and
                    any(m['role'] == 'tool' for m in history)):
                if not list((tool / 'done').glob('*.json')) or len(list((llm / 'done').glob('*.json'))) < 2:
                    raise RuntimeError('CPU queues did not complete the round trip')
                trace['history'] = history
                trace['files_ls'] = subprocess.run(
                    ['ls', '-lR', str(demo)], text=True, capture_output=True).stdout
                trace['cpu_done'] = {h.name: len(list((h / 'done').glob('*.json'))) for h in (llm, tool)}
                break
            time.sleep(.2)
        else:
            raise RuntimeError('agent did not finish within 150 seconds')
    finally:
        if daemon is not None:
            if daemon.poll() is None:
                try:
                    invoke('aos-daemon-ctl', '--home', daemon_home, 'stop')
                finally:
                    if daemon.poll() is None:
                        try:
                            daemon.wait(timeout=12)
                        except subprocess.TimeoutExpired:
                            daemon.terminate()
                            daemon.wait(timeout=8)
            trace['daemon_exit'] = daemon.returncode
            if (daemon_home / 'state.json').exists():
                trace['daemon_state_after_stop'] = json.loads((daemon_home / 'state.json').read_text())
            trace['daemon_pidfile_after_stop'] = (daemon_home / 'daemon.pid').exists()
        trace['after_pgrep'] = pgrep()
        trace['after_pgrep_ignoring_ancestors'] = pgrep(ignore_ancestors=True)
        baseline = set(trace['before_pgrep']['stdout'].split())
        trace['new_aos_pids_after_stop'] = sorted(set(trace['after_pgrep']['stdout'].split()) - baseline)
        trace['remaining_demo_processes'] = []
        for pid in trace['after_pgrep']['stdout'].split():
            try:
                argv = Path('/proc') / pid / 'cmdline'
                command = argv.read_bytes().replace(b'\0', b' ').decode('utf-8', 'replace')
            except OSError:
                continue
            if str(demo) in command:
                trace['remaining_demo_processes'].append({'pid': pid, 'command': command})
        save()
        print('TRACE ' + str(demo / 'trace.json'), flush=True)
    if trace['remaining_demo_processes']:
        raise RuntimeError('demo processes remain: ' + str(trace['remaining_demo_processes']))
    print('HISTORY ' + json.dumps(trace['history'], ensure_ascii=False), flush=True)
    print('PGREP ' + json.dumps(trace['after_pgrep'], ensure_ascii=False), flush=True)
    print('PGREP_IGNORE_ANCESTORS ' + json.dumps(trace['after_pgrep_ignoring_ancestors']), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
