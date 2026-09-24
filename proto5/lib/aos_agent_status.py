"""日常診斷；只讀狀態，不推進回合。"""
from datetime import datetime
import json
import os
from pathlib import Path
import re

import aos_agent_info
import aos_home
import aos_kernel_health
from aos_agent_home import AgentError
from aos_agent_runtime import KERNEL_ENV, files, kernel_proc, manual_paused, resumed_since

SHORT_LIMIT = 120


def tick_binding(base):
    """tick.json 記的 K：回（原值, 是否 fix-r4 前的舊鍵 AOS_K）；讀不懂＝(None, False)。"""
    try:
        envs = aos_home.read_json(Path(base) / 'tick.json').get('envs', {})
        if KERNEL_ENV in envs:
            return envs[KERNEL_ENV], False
        if 'AOS_K' in envs:
            return envs['AOS_K'], True
    except (aos_home.HomeError, AttributeError, TypeError):
        pass
    return None, False


def tick_kernel(base):
    value = tick_binding(base)[0]
    return value if isinstance(value, str) and os.path.isabs(value) else None


def _iso(stamp):
    return None if stamp is None else datetime.fromtimestamp(stamp).astimezone().isoformat()


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
    home = env.get(KERNEL_ENV)
    if not isinstance(home, str) or not os.path.isabs(home):
        home = tick_kernel(base)
    result = dict(home=home, name='agent-' + Path(base).name, proc=None, note='')
    if home is None:
        result['note'] = '（沒設 %s）' % KERNEL_ENV
        return result
    try:
        found = kernel_proc(home, result['name'])
        result['proc'] = found['proc'] if found else None
        if result['proc'] is None:
            result['note'] = '沒登記（aos-agent start --target %s）' % base
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
    recovering = None
    if k['home'] is not None:
        code, message = aos_kernel_health.health(k['home'])
        if code == 'stopped':
            return dict(code='kernel', message='kernel ' + message)
        if code == 'recovering':
            recovering = message  # fix-r5：會自己好，排在暫停、bad 之後
        elif code != 'ok':
            return dict(code='kernel', message='kernel 家有問題：' + message)
    if unregistered(k):
        return dict(code='unregistered', message='沒登記（aos-agent start --target %s）' % base)
    if data['manual_paused'] and data['paused']:
        return dict(code='manual_paused',
                    message='手動暫停＋連敗暫停（修好原因後 aos-agent continue --target %s）' % base)
    if data['manual_paused']:
        return dict(code='manual_paused', message='手動暫停（aos-agent continue --target %s）' % base)
    if data['paused']:
        return dict(code='paused', message='連敗暫停（aos-agent continue --target %s）' % base)
    if isinstance(k['proc'], dict) and k['proc'].get('status') == 'bad':
        return dict(code='bad', message='kernel 判壞了（看 %s/log/agent.err）' % base)
    if recovering is not None:
        return dict(code='recovering', message=recovering)
    if data['streak'] and not data['state_error']:
        return dict(code='retrying', message='重試中（連敗 %s/3）' % data['streak'])
    if data['resumed']:
        return dict(code='resuming', message='已解除暫停，等下一次成功')
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
        data['last_error'] = lines[-1] if lines else None  # 原文；一般輸出才縮短（fix-r5）
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


def brief(agent_dir, env=None):
    """fix-r5：給 aos-kernel ls 的一句標記 (code, 文字)；沒什麼好標、或不是 agent 家＝None。

    只讀 paused、resumed、state.json（errors 與沒到的門），不讀記憶、不問 kernel、不拿鎖。
    """
    base = os.path.abspath(agent_dir)
    try:
        meta = aos_home.read_json(Path(base) / 'info.json').get('_metainfo')
        kind = meta.get('_type') if isinstance(meta, dict) else None
        if isinstance(kind, str) and kind != 'llm_agent':
            return None
    except (aos_home.HomeError, AttributeError):
        return None
    manual = manual_paused(base) is not None
    try:
        st = aos_agent_info.load_state(base, env=os.environ if env is None else env)
    except (AgentError, OSError, ValueError):
        return ('manual_paused', '手動暫停中') if manual else None
    stuck = any(w['pause'] and not w['arrived'] for w in waits(base, st))
    if manual and stuck:
        return 'both_paused', '手動暫停中＋連敗暫停中'
    if stuck:
        return 'paused', '連敗暫停中'
    if manual:
        return 'manual_paused', '手動暫停中'
    if st['errors']:
        return 'retrying', '重試中（連敗 %s/3）' % st['errors']
    if resumed_since(base) is not None:
        return 'resuming', '已解除暫停，等下一次成功'
    return None


def short_error(line, base):
    """一般 status 的舊錯短版（aos-agent.md §1.3）：原文留給 -v／--json。"""
    text = line.removeprefix('aos-agent: ')
    text = re.sub(r'touch \S+ 繼續', '修好原因後 aos-agent continue --target ' + base, text)
    text = re.sub(r'\baw-[^\s/]*?-\d+-\d+(?:-\d+)?', 'aw-…', text)
    if len(text) > SHORT_LIMIT:
        text = text[:SHORT_LIMIT] + '…（-v 看全文）'
    return text


def collect(agent_dir, env=None):
    """各區獨立診斷；只有不是 agent 家才拒絕。"""
    env = os.environ if env is None else env
    base = os.path.abspath(agent_dir)
    result = dict(dir=base, info_error=None, state_error=None, access_error=None, state=None, errors=None,
                  batch=None, waits=[], pending_inputs=[], intake=False, last_error=None,
                  kernel=kernel_status(base, env))
    since = manual_paused(base)
    result.update(manual_paused=since is not None, manual_paused_since=_iso(since))
    since = resumed_since(base)
    result.update(resumed=since is not None, resumed_since=_iso(since))
    info = None
    try:
        info = aos_agent_info.load(base, env=env)
    except (AgentError, OSError) as exc:
        if getattr(exc, 'code', None) == 'NotAnAgent':
            raise
        result['info_error'] = str(exc)
    try:
        import aos_agent_access
        aos_agent_access.load(base, env=env, info=info)
    except (AgentError, OSError) as exc:
        result['access_error'] = str(exc)
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
    if data.get('access_error'):
        print('access bad：%s（下一批工具會跑不起來；aos-agent access ls 看全表）' % ' '.join(data['access_error'].split()))
    if data['state_error']:
        print('state bad：' + ' '.join(data['state_error'].split()))
    else:
        manual = ('  手動暫停中（%s）' % datetime.fromisoformat(data['manual_paused_since']).strftime('%m-%d %H:%M:%S')
                  if data['manual_paused'] else '')
        print('state  %s  %s%s' % (data['state'], '連敗暫停中（已連敗 3 次）' if data['paused']
                                    else 'errors %s' % data['errors'], manual))
        b = data['batch']
        print('batch  ' + ('%s  送出 %s／%s  收回 %s%s' %
              (b['kind'], b['sent_n'], b['total'], b['done_n'], '' if b['sent'] else '  送件中') if b else '-'))
        for w in data['waits']:
            for path in w['paths']:
                note = '已到，下一格會開' if arrived(data['dir'], path) else '沒到'
                if pause_path(data['dir'], path, w['consume']):
                    note += '（連敗暫停，aos-agent continue --target %s）' % data['dir']
                    if verbose:
                        note += '：touch ' + path
                print('wait   %s %s' % (path, note))
        pending = data['pending_inputs']
        print('input  ' + ('%s 個檔還沒收：%s' % (len(pending), ' '.join(pending)) if pending else '-'))
        if data['intake']:
            print('intake 收到一半（下一格會接著做）')
    current = data['current_error']
    if current and data['paused'] and not verbose and current.startswith('aos-agent: stuck:'):
        current = short_error(current, data['dir'])  # 舊格式的 touch 也改寫成 continue
    print('error  ' + (current or '（無）'))
    if data['paused']:
        print('       已連敗 3 次，等 aos-agent continue --target ' + data['dir'])
        if verbose:
            detail = dict(data)
            stuck = error_details(detail)
            if stuck:
                print('stuck  ' + stuck)
    elif data['streak']:
        print('       已連敗 %s 次（3 次會暫停）' % data['streak'])
    elif data['last_error'] and not data['current_error']:
        stamp = datetime.fromisoformat(data['last_error_time']).strftime('%m-%d %H:%M:%S')
        label = '（已解除暫停，等下一次成功）' if data['resumed'] else '（已恢復）'
        text = data['last_error'] if verbose else short_error(data['last_error'], data['dir'])
        print('last-error  %s %s  %s' % (label, stamp, text))
    k = data['kernel']
    if k['home'] is None:
        print('kernel 從沒 start 過（沒設 %s、也沒 tick.json）；aos-agent start --target %s'
              % (KERNEL_ENV, data['dir']))
    elif isinstance(k['proc'], dict):
        p = k['proc']
        status = p.get('status', '?')
        if status == 'queued' and p.get('parked') is True:
            status = 'queued（停車：等回音或輸入，最晚 park_ms 自己醒）'  # 09-24 停車
        print('kernel %s  %s  runs %s  fails %s  %s' %
              (k['name'], status, p.get('runs', 0), p.get('fails', 0), k['note']))
    else:
        label = k['home'] if '帳本讀不到' in k['note'] else k['name'] if k['home'] else ''
        print('kernel %s %s' % (label, ' '.join(k['note'].split())))


def status(agent_dir, *, as_json=False, verbose=False, env=None):
    show(collect(agent_dir, env), as_json=as_json, verbose=verbose)
    return 0
