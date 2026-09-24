"""日常診斷與解除連敗門；只讀狀態，不推進回合。"""
import json
import os
from pathlib import Path

import aos_agent_info
import aos_home
from aos_agent_home import AgentError
from aos_agent_runtime import files, ledger


def tick_kernel(base):
    try:
        raw = aos_home.read_json(Path(base) / 'tick.json')
        value = raw.get('envs', {}).get('AOS_K')
        return value if isinstance(value, str) and os.path.isabs(value) else None
    except (aos_home.HomeError, AttributeError):
        return None


def pause_path(base, path, consume):
    path = Path(path)
    return (consume and path.parent == Path(base) and path.name.startswith('continue-')
            and path.name.endswith('.json'))


def arrived(base, path):
    try:
        return bool(files(base, path))
    except (OSError, ValueError):
        return False


def waits(base, state):
    result = []
    for entry in state['_waits']:
        paths = [os.path.abspath(os.path.join(base, p)) for p in entry['paths']]
        consume = 'consume' in entry['options']
        pause = next((p for p in paths if pause_path(base, p, consume)), None)
        result.append(dict(paths=paths, arrived=all(arrived(base, p) for p in paths),
                           consume=consume, pause=pause is not None, touch=pause))
    return result


def kernel_status(base, env):
    home = env.get('AOS_K')
    if not isinstance(home, str) or not os.path.isabs(home):
        home = tick_kernel(base)
    result = dict(home=home, name='agent-' + Path(base).name, proc=None, note='')
    if home is None:
        result['note'] = '（沒設 AOS_K）'
        return result
    try:
        result['proc'] = ledger(home)['procs'].get(result['name'])
        if result['proc'] is None:
            result['note'] = '沒登記（aos-agent start）'
        elif not isinstance(result['proc'], dict):
            result['note'] = '帳本行程資料形狀不合'
        elif result['proc'].get('status') == 'bad':
            result['note'] = '看 ' + str(Path(base) / 'log/agent.err')
    except (AgentError, aos_home.HomeError, OSError, ValueError) as exc:
        result['note'] = '帳本讀不到（%s）' % exc
    return result


def collect(agent_dir, env=None):
    """各區獨立診斷；只有不是 agent 家才拒絕。"""
    env = os.environ if env is None else env
    base = os.path.abspath(agent_dir)
    result = dict(dir=base, info_error=None, state_error=None, state=None, errors=None,
                  batch=None, waits=[], pending_inputs=[], intake=False, last_error=None,
                  kernel=kernel_status(base, env))
    try:
        aos_agent_info.load(base, env=env)
    except (AgentError, OSError) as exc:
        if getattr(exc, 'code', None) == 'NotAnAgent':
            raise
        result['info_error'] = str(exc)
    try:
        st = aos_agent_info.load_state(base, env=env)
        result.update(state=st['state'], errors=st['errors'], intake=st['intake'] is not None)
        result['waits'] = waits(base, st)
        result['pending_inputs'] = list(dict.fromkeys(p for v in st['input'] for p in files(base, v)))
        batch = st['batch']
        if batch is not None:
            result['batch'] = dict(kind=batch['kind'], sent=batch['sent'], total=len(batch['calls']),
                                  sent_n=sum(c['name'] is not None for c in batch['calls']),
                                  done_n=sum(c['done'] is not None for c in batch['calls']))
    except (AgentError, OSError, ValueError) as exc:
        result['state_error'] = str(exc)
    try:
        lines = (Path(base) / 'log/agent.err').read_text(encoding='utf-8', errors='replace').splitlines()
        result['last_error'] = next((s.strip()[:300] for s in reversed(lines) if s.strip()), None)
    except OSError:
        pass
    return result


def show(data, *, as_json=False):
    if as_json:
        print(json.dumps(data, ensure_ascii=False))
        return
    print('agent  ' + data['dir'])
    if data['info_error']:
        print('info  bad：' + ' '.join(data['info_error'].split()))
    if data['state_error']:
        print('state bad：' + ' '.join(data['state_error'].split()))
    else:
        print('state  %s  errors %s' % (data['state'], data['errors']))
        b = data['batch']
        print('batch  ' + ('%s  送出 %s／%s  收回 %s%s' %
              (b['kind'], b['sent_n'], b['total'], b['done_n'], '' if b['sent'] else '  送件中') if b else '-'))
        for w in data['waits']:
            for path in w['paths']:
                note = '已到，下一格會開' if arrived(data['dir'], path) else '沒到'
                if pause_path(data['dir'], path, w['consume']):
                    note += '（連敗暫停）：touch ' + path
                print('wait   %s %s' % (path, note))
        pending = data['pending_inputs']
        print('input  ' + ('%s 個檔還沒收：%s' % (len(pending), ' '.join(pending)) if pending else '-'))
        if data['intake']:
            print('intake 收到一半（下一格會接著做）')
    print('error  ' + (data['last_error'] or '-'))
    k = data['kernel']
    if isinstance(k['proc'], dict):
        p = k['proc']
        print('kernel %s  %s  runs %s  fails %s  %s' %
              (k['name'], p.get('status', '?'), p.get('runs', 0), p.get('fails', 0), k['note']))
    else:
        label = k['home'] if '帳本讀不到' in k['note'] else k['name'] if k['home'] else ''
        print('kernel %s %s' % (label, ' '.join(k['note'].split())))


def status(agent_dir, *, as_json=False, env=None):
    show(collect(agent_dir, env), as_json=as_json)
    return 0


def resume(agent_dir, env=None):
    base = os.path.abspath(agent_dir)
    st = aos_agent_info.load_state(base, env=env)
    paths = dict.fromkeys(p for w in waits(base, st) for p in w['paths']
                          if pause_path(base, p, w['consume']))
    for path in paths:
        try:
            with open(path, 'x'):
                pass
            print('continued: touched ' + path)
        except FileExistsError:
            print('已經 touch 過，等下一格 tick：' + path)
    if not paths:
        print('沒有在暫停')
    return 0
