"""只看快照提出候選；不讀檔、不控制程序。"""
from copy import deepcopy
from pathlib import Path
import shlex

UP = str(Path(__file__).resolve().parents[2] / "modules/up/aos7-up")

def short(value):
    return " ".join(str(value or "").split())[:60]


def _key(src):
    if isinstance(src, dict) and all(isinstance(src.get(k), str) for k in ('node', 'slot')):
        return src['node'] + '/' + src['slot']
    return None


def _valid(state):
    return (isinstance(state, dict) and isinstance(state.get('id'), str)
            and all(type(state.get(k)) is int for k in ('step', 'run', 'since', 'last'))
            and all(type(state.get(k)) is bool for k in ('notified', 'gap')))


def supervise_brain(ctx, snap, rstate):
    """未知不算停滯；只依信、步數與 run 判進度。"""
    config = ctx.get('config') if isinstance(ctx, dict) and isinstance(ctx.get('config'), dict) else {}
    params = ctx.get('rule')
    if not isinstance(params, dict):
        params = next((r for r in config.get('rules') or []
                       if isinstance(r, dict) and r.get('name') == 'supervise-brain'), {})
    def rounds(name, default):
        n = params.get(name)
        return n if type(n) is int and n > 0 else default
    warn, stop = rounds('no_progress_rounds', 6), rounds('kill_after_rounds', 12)
    maximum = rounds('max_kills', 3)
    recipient = params.get('notify')
    recipient = recipient if isinstance(recipient, str) and recipient else 'you'
    sources = {_key(s): s for s in config.get('sources') or []
               if isinstance(s, dict) and s.get('kind') == 'brain' and _key(s)}
    targets = {_key(t): t for t in config.get('targets') or [] if _key(t)}
    old = rstate if isinstance(rstate, dict) else {}
    if not all(isinstance(old.get(k, {}), dict) for k in ('brains', 'killed', 'notified', 'retries', 'gaps')):
        old = {}
    state = {'brains': {k: deepcopy(v) for k, v in old.get('brains', {}).items()
                        if k in sources and _valid(v)},
             'killed': {k: v for k, v in old.get('killed', {}).items()
                        if k in sources and type(v) is int},
             'notified': {k: v for k, v in old.get('notified', {}).items() if k in sources and isinstance(v, str)},
             'gaps': {k: v for k, v in old.get('gaps', {}).items() if k in sources and type(v) is bool},
             'retries': {k: deepcopy(v) for k, v in old.get('retries', {}).items() if k in sources and isinstance(v, dict) and isinstance(v.get('id'), str)
                        and type(v.get('step')) is int and type(v.get('count')) is int and v['count'] >= 0}}
    # 舊版只有 brain 的旗標與 killed：接上時保留已做過的事。
    for key, brain in state['brains'].items():
        if brain['notified']:
            state['notified'].setdefault(key, brain['id'])
        state['retries'].setdefault(key, dict(id=brain['id'], step=brain['step'],
            count=int(key in state['killed'])))
    items = snap if isinstance(snap, list) else []
    found = {}
    for item in items:
        if (isinstance(item, dict) and isinstance(item.get('file'), str)
                and item['file'].rsplit('/', 1)[-1] == 'task.json'):
            found.setdefault(_key(item.get('src')), []).append(item)
    candidates = []
    for key, source in sources.items():
        matches = found.get(key, [])
        # 同來源有多份相互競爭的快照，無法選出一致依據。
        item = matches[0] if len(matches) == 1 else {}
        previous = state['brains'].get(key)
        if item.get('read') == 'absent':
            state['brains'].pop(key, None)
            state['gaps'].pop(key, None)
            continue
        task, run, ct = item.get('value'), item.get('run'), item.get('completed_tock')
        if not (item.get('read') == 'ok' and type(run) is int and type(ct) is int
                and isinstance(task, dict) and isinstance(task.get('id'), str)
                and type(task.get('step')) is int):
            state['gaps'][key] = True
            if previous:
                previous['gap'] = True
            continue
        state['gaps'].pop(key, None)
        ident, step = task['id'], task['step']
        retry = state['retries'].get(key)
        if not retry or (retry.get('id'), retry.get('step')) != (ident, step):
            retry = state['retries'][key] = dict(id=ident, step=step, count=0)
        if state['notified'].get(key) != ident:
            state['notified'].pop(key, None)
        if previous is None or (ident, step, run) != (previous['id'], previous['step'], previous['run']):
            state['brains'][key] = dict(id=ident, step=step, run=run, since=ct, last=ct,
                                       notified=state['notified'].get(key) == ident, gap=False)
            continue
        if previous['gap'] or ct < previous['last']:
            previous.update(since=ct, last=ct, gap=False)
            continue
        previous['last'] = ct
        age = ct - previous['since']
        basis = dict(src=key, file=item['file'], run=run, completed_tock=ct,
                     id=ident, title=short(item.get('title')) or None, step=step, since=previous['since'], age=age)
        title = basis['title'] or f'一封信（{short(ident)[:12]}…）'
        who, line = short(source['node']), short(task.get('line')) or '沒有留下進度文字'
        threshold = stop * 2 ** retry['count']
        if age >= warn and state['notified'].get(key) != ident and retry['count'] < maximum:
            command = 'python3 ' + shlex.quote(UP) + ' status ' + shlex.quote(item.get('node_path') or source['node'])
            body = (f'## 做了什麼\n監督者發現 {who} 在辦你寄的「{title}」時，停在第 {step} 步，'
                    f'已經 {age} 回合（約 {age} 秒，心跳 1 秒一回合時）沒往下走；'
                    f'{who} 最後寫的進度：「{line}」。\n\n'
                    '## 產出（檔案路徑 / commit / 分支）\n沒有產出，這封只是提醒。\n\n'
                    f'## 沒做到、或證據不足的部分\n還不知道為什麼停住；最常見是 {who} 在等 AI 服務回覆。\n\n'
                    '## 需要對方或使用者決定的事\n'
                    f'①先看一下 AI 服務是不是卡住了：`{command}`。\n'
                    f'②什麼都不做也可以：再卡到第 {threshold} 回合，監督者會把 {who} 收掉重來'
                    f'（同一封信同一步最多 {maximum} 次，之後每次等待加倍）；'
                    f'{who} 從這一步接著做、不會重問 AI；{who} 等 AI 太久也會自己回信說卡住。')
            if key not in targets:
                body = body[:body.index('②')] + f'②什麼都不做也可以：監督者會繼續觀察；{who} 等 AI 太久也會自己回信說卡住。'
            candidates.append(dict(op='notify', target=recipient, basis=deepcopy(basis), body=body,
                text=f'{who} 卡住了：「{title}」已 {age} 回合沒進展'))
            state['notified'][key] = ident
            previous['notified'] = True
        if age >= threshold and retry['count'] < maximum and state['killed'].get(key) != run and key in targets:
            candidates.append(dict(op='kill', target=deepcopy(targets[key]), run=run, basis=deepcopy(basis),
                why=f'「{title}」停在第 {step} 步已 {age} 回合沒進展，收掉 run {run} 讓 brain 接續'))
            state['killed'][key] = run
            retry['count'] += 1
    return state, candidates


def noop(ctx, snap, rstate):
    return deepcopy(rstate) if isinstance(rstate, dict) else {}, []


RULES = {'supervise-brain': supervise_brain, 'noop': noop}
