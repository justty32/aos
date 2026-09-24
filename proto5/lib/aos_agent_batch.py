"""aos-agent.md §5～§7：建批、送件、收回、結清。"""
import os
import shlex
from pathlib import Path
import shutil

import aos_home
import aos_inst
import aos_agent_access
from aos_jail import secret_name
from aos_agent_home import AgentError
from aos_agent_results import act_done, model_message, response_parts, success, think_done
import aos_agent_events as events
from aos_agent_runtime import RESUMED, history_prefix, ledger, report, unique_id

META = {'_type': 'posix', '_version': 1}
# 權限牆擋下的那件，給模型看的話（它讀得懂、不會以為要自己修；細節留給人在 check／status 看）
JAIL_WHY = {
    'EnvUnsafe': '這支工具的設定有安全問題（會把金鑰類環境變數帶進牢裡）',
    'NoBwrap': '這台機器沒有裝關牢要用的 bwrap',
}
JAIL_WHY_ACCESS = '這個 agent 的權限設定（access.json）有問題'


def no_access_fix(base):
    """家裡沒 access.json 時教的那行：只給工具家裡的 workspace（絕對路徑，不怕殼在哪個資料夾）。"""
    ws, home = shlex.quote(os.path.join(str(base), 'workspace')), shlex.quote(str(base))
    return 'mkdir -p %s && aos-agent access set ws %s --cwd --target %s' % (ws, ws, home)


def jail_message(tool, code, base):
    """工具被權限牆擋下時寫進記憶的 tool 訊息。"""
    if code == 'NoAccess':
        return ('工具 %s 沒有執行：這個 agent 還沒設定工具能碰哪些資料夾（沒有 access.json），被 aos 擋下（NoAccess）。'
                '這不是你能修的，也不要改用別的工具繞過；請告訴使用者：「工具 %s 沒有 access.json 不能跑，'
                '請先跑 %s，再叫我一次」。'
                % (tool, tool, no_access_fix(base)))
    why = JAIL_WHY.get(code, JAIL_WHY_ACCESS)
    return ('工具 %s 沒有執行：%s，被 aos 擋下（%s）。這不是你能修的，也不要改用別的工具繞過；'
            '請告訴使用者：「工具 %s 被 aos 權限牆擋下（%s），請跑 aos-agent check --target %s 看細節」。'
            % (tool, why, code, tool, code, base))


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
    # id：批的身分（事件紀錄用；整批都在本地結束、沒有工作名時也有，spec/agent/events.md）
    run.st['batch'] = {'kind': kind, 'id': identity, 'kernel': kernel, 'base_len': len(history),
                       'sent': False, 'calls': calls}
    if kind == 'act':
        # access.md：一批只解一次，同批每件、崩潰重送都用這份快照
        run.st['batch']['access'] = aos_agent_access.snapshot(run.base, run.env, run.info, run.st)
    run.save('state.batch')


def already_posted(kernel, name):
    kernel = Path(kernel)
    if (kernel / 'requests' / (name + '.json')).exists():
        return True
    state = ledger(kernel, missing=True)
    if name in state['procs'] or any(r['name'] == name + '.json' for r in state['replies']):
        return True
    return (kernel / 'responses' / (name + '.json')).exists()


def jail_argv(decoded, access):
    """把解好的 argv 包成 aos-jail（spec/aos-agent/access.md）；_meta.envs 改成 --setenv。"""
    prog = decoded['argv'][0]
    if '/' in prog:
        prog = os.path.join(decoded['cwd'], prog)
    flags = []
    for mount, m in access['mounts'].items():
        flags += ['--mount-ro' if m['ro'] else '--mount', '%s=%s' % (mount, m['path'])]
    if access['cwd'] is not None:
        flags += ['--chdir', access['cwd']]
    flags += ['--net', 'on' if access['net'] else 'off']
    for key, value in decoded['envs'].items():
        if not secret_name(key):            # 敏感名字在寫進 inst 之前就丟（aos-jail 端還有第二層）
            flags += ['--setenv', '%s=%s' % (key, value)]
    # 用跟自己同一份 proto5 的 aos-jail 絕對路徑，不靠 PATH（PATH 可能指到可寫位置的替身）
    return [aos_agent_access.JAIL, *flags, '--', prog, *decoded['argv'][1:]]


class _WatchEnv(dict):
    """解 _meta 時記下 $env 讀了哪些名字（含查無的）。"""

    def __init__(self, env):
        super().__init__(env)
        self.read = []

    def __contains__(self, key):
        self.read.append(key)
        return super().__contains__(key)

    def __getitem__(self, key):
        self.read.append(key)
        return super().__getitem__(key)


def _env_cells(value, pos, out):
    """_meta 字面上每個 {"$env": 名} 的位置（envs.FOO、argv.1、envs.X.$fmt.k…）。"""
    if isinstance(value, dict):
        if isinstance(value.get('$env'), str):
            out.setdefault(value['$env'], []).append('.'.join(pos) or '（整份 _meta）')
        for k, v in value.items():
            _env_cells(v, pos + [str(k)], out)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _env_cells(v, pos + [str(i)], out)


def secret_env_reads(meta, base, env):
    """關牢的工具 _meta 用 $env 讀了哪些敏感名字：[(名字, 位置)]。送件與 check 共用這一個判定。

    真的照解析器走一遍（經 $ref／$fmt 讀到的也算），位置從 _meta 字面上找；找不到＝經 $ref 讀的。
    """
    watch = _WatchEnv(os.environ if env is None else env)
    try:
        aos_inst.load_obj(meta, str(base), env=watch)
    except aos_inst.InstError:
        pass
    cells = {}
    _env_cells(meta, [], cells)
    names = sorted({k for k in watch.read if isinstance(k, str) and secret_name(k)})
    return [(n, '、'.join(cells.get(n, ['（經 $ref 讀到，_meta 字面上沒有）']))) for n in names]


def env_unsafe_detail(reads):
    return '；'.join('_meta 的 %s 用 $env 讀了 %s' % (where, name) for name, where in reads) + \
        '（名字像金鑰或 AOS_*，關牢的工具不給）'


def tool_inst(meta, base, name, env, access=None):
    if access is not None:
        # 關牢的工具：_meta 任何一格用 $env 讀敏感名字（AOS_*、像金鑰的、SSH_AUTH_SOCK）＝整件不跑，
        # 不論解出來放到哪個名字或 argv（值一寫進 inst 就落盤了）。
        reads = secret_env_reads(meta, base, env)
        if reads:
            raise aos_inst.InstError('EnvUnsafe', env_unsafe_detail(reads))
    decoded = aos_inst.load_obj(meta, str(base), env=env)
    inst = {'_metainfo': dict(META), 'argv': decoded['argv'], 'cwd': decoded['cwd']}
    if decoded['cwd_mkdir']:
        inst['cwd'] = {'$opt': 'mkdir', '$val': decoded['cwd']}
    if decoded['envs_clear']:
        inst['envs'] = {'$opt': 'clear', '$val': decoded['envs']}
    elif decoded['envs']:
        inst['envs'] = decoded['envs']
    if access is not None:
        inst['argv'] = jail_argv(decoded, access)
        inst.pop('envs', None)
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
    # AOS_LLM_BATCH：aos-llm call 記 log/usage.jsonl 時帶的批 id（spec/agent/events.md）
    return {'_metainfo': dict(META), 'argv': ['aos-llm', 'call', str(base)], 'cwd': str(base),
            'envs': {'AOS_LLM_BATCH': name.rsplit('-', 1)[0]},
            'stdout': {'$opt': 'mkdir', '$val': str(base / 'work' / (name + '.out'))},
            'stderr': {'$opt': ['append', 'mkdir'], '$val': str(base / 'log' / 'llm.err')}}


def jail_problem(access, tool, env):
    """這支要關牢但關不起來 → 錯誤代號（照 send §5.3 記成沒執行）；不用關或關得起來＝None。

    沒 access 檔（快照 None）＝NoAccess：有工具的家一定要有表，不關牢就不送（09-24 使用者裁決 4）。
    """
    if tool.get('_jail', True) is False:
        return None
    if access is None:
        return 'NoAccess'
    if 'error' in access:
        return access['error'].split(':', 1)[0]            # 代號；細節在 status／check
    if shutil.which('bwrap', path=env.get('PATH', os.defpath)) is None:
        return 'NoBwrap'
    return None


def send(run):
    batch, tools = run.st['batch'], tool_map(run)
    access = batch.get('access')
    for i, call in enumerate(batch['calls']):
        name = call['name']
        if name is None or call['done'] is not None:
            continue
        path = run.base / 'work' / (name + '.inst.json')
        think = batch['kind'] == 'think'
        tool = tools.get(call.get('tool'))
        posted = already_posted(batch['kernel'], name)
        if not think and tool is not None and not posted:
            # inst 已在（崩在寫 inst 與送出之間、或舊版寫的未包牢 inst）也要先過這關，不能因檔在就略過（astra r2 #1）
            problem = jail_problem(access, tool, run.env)
            if problem is not None:
                call.update(done={'content': jail_message(call['tool'], problem, run.base)}, acked=True)
                if problem == 'NoAccess':
                    report('NoAccess', '工具 %s 沒送：家裡沒有 access.json（有工具的家要先設定工具能碰哪些資料夾）；'
                           '跑：%s' % (call['tool'], no_access_fix(run.base)))
                continue
        if not path.exists():
            if think:
                inst = think_inst(run.base, name)
            else:
                if tool is None:
                    call.update(done={'content': '沒有這個工具：' + call['tool']}, acked=True)
                    continue
                jailed = access if tool.get('_jail', True) is not False else None
                try:
                    inst = tool_inst(tool['_meta'], run.base, name, run.env, access=jailed)
                except aos_inst.InstError as exc:
                    content = (jail_message(call['tool'], exc.code, run.base) if exc.code == 'EnvUnsafe'
                               else '工具 %s 跑不起來：%s' % (call['tool'], exc))
                    call.update(done={'content': content}, acked=True)
                    continue
                history, length = run.info['history'], batch['base_len']
                if length == 0 or len(history) < length:
                    raise AgentError('HistoryChanged', '送工具時原 assistant 已不在')
                source = history[length - 1].get('tool_calls', [])
                if i >= len(source) or source[i]['id'] != call['tool_call_id']:
                    raise AgentError('HistoryChanged', '送工具時 tool_calls 已改變')
                run.text(run.base / 'work' / (name + '.in'), source[i]['function']['arguments'])
            run.write(path, inst, 'work.inst')
        if not posted:
            pool = run.info['llm']['pool'] if think else run.info['tool_pool']
            timeout = run.info['llm']['timeout_ms'] if think else (tool or {}).get('_timeout_ms', 60000)
            run.submit(batch['kernel'], name + '.json', 'add',
                       {'target': str(path), 'name': name, 'once': True, 'pool': pool, 'timeout_ms': timeout})
    batch['sent'] = True
    events.batch_start(run)  # 至少一次：在提交 sent 之前記（spec/agent/events.md）
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
        _measure(call, response)
        fresh = True
    if fresh:
        run.save('state.done')
        acknowledge(run)
    if all(c['done'] is not None and c['acked'] for c in batch['calls']):
        return settle(run)
    return 0 if changed or fresh else 101


def _measure(call, response):
    """事件紀錄用（spec/agent/events.md）：kernel 回音的 ms（經過時間，不是 cpu 秒）、這件成不成。"""
    try:
        result, _ = response_parts(response)
    except AgentError:
        result = None
    call['ms'] = result['ms'] if result is not None and type(result.get('ms')) is int else None
    call['ok'] = result is not None and success(result)


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
    events.batch_end(run, messages)  # 至少一次：在提交結清之前記
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
