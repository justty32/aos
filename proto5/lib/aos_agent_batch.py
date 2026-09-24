"""aos-agent.md §5～§7：建批、送件、收回、結清。"""
from pathlib import Path

import aos_home
import aos_inst
from aos_agent_home import AgentError
from aos_agent_results import act_done, model_message, think_done
from aos_agent_runtime import RESUMED, history_prefix, ledger, report, unique_id

META = {'_type': 'posix', '_version': 1}


def tool_map(run):
    return {t['function']['name']: t for t in run.info['tools_raw']}


def make_batch(run, kernel):
    kind, history = run.st['state'], run.info['history']
    identity = 'aw-%s-%s' % (run.base.name, unique_id())
    calls = []
    if kind == 'think':
        calls.append({'name': identity + '-0', 'done': None, 'acked': False})
    else:
        known = tool_map(run)
        for i, item in enumerate(history[-1]['tool_calls']):
            tool = item['function']['name']
            found = tool in known
            calls.append({'name': '%s-%d' % (identity, i) if found else None,
                          'tool_call_id': item['id'], 'tool': tool,
                          'done': None if found else {'content': '沒有這個工具：' + tool},
                          'acked': not found})
    run.st['batch'] = {'kind': kind, 'kernel': kernel, 'base_len': len(history),
                       'sent': False, 'calls': calls}
    run.save('state.batch')


def already_posted(kernel, name):
    kernel = Path(kernel)
    if (kernel / 'requests' / (name + '.json')).exists():
        return True
    state = ledger(kernel, missing=True)
    if name in state['procs'] or any(r['name'] == name + '.json' for r in state['replies']):
        return True
    return (kernel / 'responses' / (name + '.json')).exists()


def tool_inst(meta, base, name, env):
    decoded = aos_inst.load_obj(meta, str(base), env=env)
    inst = {'_metainfo': dict(META), 'argv': decoded['argv'], 'cwd': decoded['cwd']}
    if decoded['cwd_mkdir']:
        inst['cwd'] = {'$opt': 'mkdir', '$val': decoded['cwd']}
    if decoded['envs_clear']:
        inst['envs'] = {'$opt': 'clear', '$val': decoded['envs']}
    elif decoded['envs']:
        inst['envs'] = decoded['envs']
    for field in ('stderr', 'exit'):
        stream = decoded[field]
        special = next((key for key in ('inherit', 'merge') if stream.get(key)), None)
        if special:
            inst[field] = {'$opt': special}
        elif stream['path']:
            opts = [key for key in ('append', 'mkdir') if stream[key]]
            inst[field] = {'$opt': opts, '$val': stream['path']} if opts else stream['path']
    inst['stdin'] = str(base / 'work' / (name + '.in'))
    inst['stdout'] = {'$opt': 'mkdir', '$val': str(base / 'work' / (name + '.out'))}
    return inst


def think_inst(base, name):
    return {'_metainfo': dict(META), 'argv': ['aos-llm', 'call', str(base)], 'cwd': str(base),
            'stdout': {'$opt': 'mkdir', '$val': str(base / 'work' / (name + '.out'))},
            'stderr': {'$opt': ['append', 'mkdir'], '$val': str(base / 'log' / 'llm.err')}}


def send(run):
    batch, tools = run.st['batch'], tool_map(run)
    for i, call in enumerate(batch['calls']):
        name = call['name']
        if name is None or call['done'] is not None:
            continue
        path = run.base / 'work' / (name + '.inst.json')
        think = batch['kind'] == 'think'
        tool = tools.get(call.get('tool'))
        if not path.exists():
            if think:
                inst = think_inst(run.base, name)
            else:
                if tool is None:
                    call.update(done={'content': '沒有這個工具：' + call['tool']}, acked=True)
                    continue
                try:
                    inst = tool_inst(tool['_meta'], run.base, name, run.env)
                except aos_inst.InstError as exc:
                    call.update(done={'content': '工具 %s 跑不起來：%s' % (call['tool'], exc)}, acked=True)
                    continue
                history, length = run.info['history'], batch['base_len']
                if length == 0 or len(history) < length:
                    raise AgentError('HistoryChanged', '送工具時原 assistant 已不在')
                source = history[length - 1].get('tool_calls', [])
                if i >= len(source) or source[i]['id'] != call['tool_call_id']:
                    raise AgentError('HistoryChanged', '送工具時 tool_calls 已改變')
                run.text(run.base / 'work' / (name + '.in'), source[i]['function']['arguments'])
            run.write(path, inst, 'work.inst')
        if not already_posted(batch['kernel'], name):
            pool = run.info['llm']['pool'] if think else run.info['tool_pool']
            timeout = run.info['llm']['timeout_ms'] if think else (tool or {}).get('_timeout_ms', 60000)
            run.submit(batch['kernel'], name + '.json', 'add',
                       {'target': str(path), 'name': name, 'once': True, 'pool': pool, 'timeout_ms': timeout})
    batch['sent'] = True
    run.save('state.sent')
    return 0


def acknowledge(run):
    batch, changed = run.st['batch'], False
    for i, call in enumerate(batch['calls']):
        if call['done'] is not None and not call['acked']:
            if call['name'] is not None:
                run.ack(batch['kernel'], call['name'] + '.json', i)
            call['acked'] = True
            changed = True
    if changed:
        run.save('state.acked')
    return changed


def collect(run):
    batch = run.st['batch']
    changed = acknowledge(run)
    if not batch['sent']:
        return send(run)
    fresh, tools = False, tool_map(run)
    kernel = Path(batch['kernel'])
    for call in batch['calls']:
        if call['done'] is not None or call['name'] is None:
            continue
        name = call['name']
        if (kernel / 'requests' / (name + '.json')).exists():
            continue
        path = kernel / 'responses' / (name + '.json')
        if not path.exists():
            continue
        response = aos_home.read_json(path)
        output = run.base / 'work' / (name + '.out')
        if batch['kind'] == 'think':
            call['done'] = think_done(response, output, run.info['llm']['timeout_ms'],
                                      kernel=batch['kernel'], pool=run.info['llm']['pool'])
        else:
            timeout = tools.get(call['tool'], {}).get('_timeout_ms', 60000)
            call['done'] = act_done(response, output, call['tool'], timeout)
        fresh = True
    if fresh:
        run.save('state.done')
        acknowledge(run)
    if all(c['done'] is not None and c['acked'] for c in batch['calls']):
        return settle(run)
    return 0 if changed or fresh else 101


def settle(run):
    st, history = run.st, run.info['history']
    batch = st['batch']
    length, calls, messages = batch['base_len'], batch['calls'], []
    think = batch['kind'] == 'think'
    if think:
        done = calls[0]['done']
        if done.get('ok'):
            messages = [model_message(run.base / 'work' / (calls[0]['name'] + '.out'))]
    else:
        if (not length or len(history) < length or history[length - 1]['role'] != 'assistant'
                or [c['id'] for c in history[length - 1].get('tool_calls', [])]
                != [c['tool_call_id'] for c in calls]):
            raise AgentError('HistoryChanged', '原 assistant 的 tool_calls id 或順序已改變')
        messages = [{'role': 'tool', 'tool_call_id': c['tool_call_id'], 'content': c['done']['content']}
                    for c in calls]
    history_prefix(history, length, messages)
    if messages:
        run.history(length, messages)
    engine, stuck = None, None
    if not think:
        st['state'] = 'think'
    elif done.get('ok'):
        st.update(state='act' if messages[0].get('tool_calls') else 'idle', errors=0)
    else:
        st['state'] = 'think'
        if done['count']:
            engine = done['fail']
            st['errors'] += 1
            if st['errors'] >= 3:
                st['errors'] = 0
                signal = 'continue-%s.json' % calls[0]['name'].rsplit('-', 1)[0]
                st['waits'].append({'$opt': 'consume', '$val': signal})
                stuck = '問模型連敗 3 次，修好原因後 aos-agent continue --target %s' % run.base
    st['sweep'].extend({'kernel': batch['kernel'], 'name': c['name']} for c in calls if c['name'] is not None)
    st['batch'] = None
    run.save('state.settled')
    if think and done.get('ok'):
        # fix-r5（aos-agent.md §7）：真的成功一次，continue 的「等下一次成功」才算完。
        (run.base / RESUMED).unlink(missing_ok=True)
    if engine is not None:
        report('engine', engine)
    if stuck is not None:
        report('stuck', stuck)
    return 0
