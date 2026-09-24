"""日常診斷與解除連敗門；只讀狀態，不推進回合。"""
from datetime import datetime
import json
import os
from pathlib import Path

import aos_agent_info
import aos_home
import aos_kernel_health
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


def unregistered(kernel):
    """帳本讀不到時保持未知，不把暫態讀取失敗當成撤銷登記。"""
    return kernel['home'] is None or (kernel['proc'] is None
                                     and kernel['note'].startswith('沒登記'))


def agent_health(data):
    k, base = data['kernel'], data['dir']
    if k['home'] is not None:
        code, message = aos_kernel_health.health(k['home'])
        if code == 'stopped':
            return dict(code='kernel', message='kernel ' + message)
        if code != 'ok':
            return dict(code='kernel', message='kernel 家有問題：' + message)
    if unregistered(k):
        return dict(code='unregistered', message='沒登記（aos-agent start %s）' % base)
    if data['paused']:
        return dict(code='paused', message='連敗暫停（aos-agent continue %s）' % base)
    if isinstance(k['proc'], dict) and k['proc'].get('status') == 'bad':
        return dict(code='bad', message='kernel 判壞了（看 %s/log/agent.err）' % base)
    if data['info_error'] or data['state_error']:
        return dict(code='config', message='家的設定讀不到（看下面 info／state 行）')
    return dict(code='ok', message='ok')


def error_details(data):
    data.update(current_error=None, last_error_time=None, streak=data['errors'] or 0,
                paused=any(pause_path(data['dir'], p, w['consume']) and not arrived(data['dir'], p)
                           for w in data['waits'] for p in w['paths']))
    if data['paused']:
        data['streak'] = 3
    lines = []
    try:
        with (Path(data['dir']) / 'log/agent.err').open(encoding='utf-8', errors='replace') as log:
            lines = [s.strip() for s in log if s.strip()]
            if lines:
                data['last_error_time'] = datetime.fromtimestamp(os.fstat(log.fileno()).st_mtime).astimezone().isoformat()
        data['last_error'] = lines[-1][:300] if lines else None
    except OSError:
        pass
    stuck = next((i for i in reversed(range(len(lines)))
                  if lines[i].startswith('aos-agent: stuck:')), None)
    if data['streak']:
        candidates = lines[:stuck] if data['paused'] and stuck is not None else lines
        engine = next((s.removeprefix('aos-agent: engine: ')
                       for s in reversed(candidates) if s.startswith('aos-agent: engine: ')), None)
        data['current_error'] = engine or (lines[stuck] if data['paused'] and stuck is not None else None)
    else:
        proc = data['kernel']['proc']
        if isinstance(proc, dict) and (proc.get('fails', 0) > 0 or proc.get('status') == 'bad'):
            data['current_error'] = data['last_error']
    return lines[stuck] if stuck is not None else None


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
    error_details(result)
    result['health'] = agent_health(result)
    return result


def show(data, *, as_json=False, verbose=False):
    if as_json:
        print(json.dumps(data, ensure_ascii=False))
        return
    print('health ' + data['health']['message'])
    print('agent  ' + data['dir'])
    if data['info_error']:
        print('info  bad：' + ' '.join(data['info_error'].split()))
    if data['state_error']:
        print('state bad：' + ' '.join(data['state_error'].split()))
    else:
        print('state  %s  %s' % (data['state'], '連敗暫停中（已連敗 3 次）' if data['paused']
                                  else 'errors %s' % data['errors']))
        b = data['batch']
        print('batch  ' + ('%s  送出 %s／%s  收回 %s%s' %
              (b['kind'], b['sent_n'], b['total'], b['done_n'], '' if b['sent'] else '  送件中') if b else '-'))
        for w in data['waits']:
            for path in w['paths']:
                note = '已到，下一格會開' if arrived(data['dir'], path) else '沒到'
                if pause_path(data['dir'], path, w['consume']):
                    note += '（連敗暫停，aos-agent continue）'
                    if verbose:
                        note += '：touch ' + path
                print('wait   %s %s' % (path, note))
        pending = data['pending_inputs']
        print('input  ' + ('%s 個檔還沒收：%s' % (len(pending), ' '.join(pending)) if pending else '-'))
        if data['intake']:
            print('intake 收到一半（下一格會接著做）')
    current = data['current_error']
    if current and data['paused'] and not verbose and current.startswith('aos-agent: stuck:'):
        current = current.split('touch ', 1)[0] + 'aos-agent continue ' + data['dir']
    print('error  ' + (current or '（無）'))
    if data['paused']:
        print('       已連敗 3 次，等 aos-agent continue ' + data['dir'])
        if verbose:
            detail = dict(data)
            stuck = error_details(detail)
            if stuck:
                print('stuck  ' + stuck)
    elif data['streak']:
        print('       已連敗 %s 次（3 次會暫停）' % data['streak'])
    elif data['last_error'] and not data['current_error']:
        stamp = datetime.fromisoformat(data['last_error_time']).strftime('%m-%d %H:%M:%S')
        print('last-error  %s  %s（已恢復）' % (stamp, data['last_error']))
    k = data['kernel']
    if k['home'] is None:
        print('kernel 從沒 start 過（沒設 AOS_K、也沒 tick.json）；aos-agent start ' + data['dir'])
    elif isinstance(k['proc'], dict):
        p = k['proc']
        print('kernel %s  %s  runs %s  fails %s  %s' %
              (k['name'], p.get('status', '?'), p.get('runs', 0), p.get('fails', 0), k['note']))
    else:
        label = k['home'] if '帳本讀不到' in k['note'] else k['name'] if k['home'] else ''
        print('kernel %s %s' % (label, ' '.join(k['note'].split())))


def status(agent_dir, *, as_json=False, verbose=False, env=None):
    show(collect(agent_dir, env), as_json=as_json, verbose=verbose)
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
