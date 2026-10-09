"""只看快照提出候選；不讀檔、不控制程序。"""
from copy import deepcopy


def _key(src):
    if isinstance(src, str):
        return src
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
    recipient = params.get('notify')
    recipient = recipient if isinstance(recipient, str) and recipient else 'you'
    sources = {_key(s): s for s in config.get('sources') or []
               if isinstance(s, dict) and s.get('kind') == 'brain' and _key(s)}
    targets = {_key(t): t for t in config.get('targets') or [] if _key(t)}
    old = rstate if isinstance(rstate, dict) else {}
    if not all(isinstance(old.get(k, {}), dict) for k in ('brains', 'killed')):
        old = {}
    state = {'brains': {k: deepcopy(v) for k, v in old.get('brains', {}).items()
                        if k in sources and _valid(v)},
             'killed': {k: v for k, v in old.get('killed', {}).items()
                        if k in sources and type(v) is int}}
    items = snap.get('items', []) if isinstance(snap, dict) else snap
    items = items if isinstance(items, list) else []
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
            continue
        task, run, ct = item.get('value'), item.get('run'), item.get('completed_tock')
        if not (item.get('read') == 'ok' and type(run) is int and type(ct) is int
                and isinstance(task, dict) and isinstance(task.get('id'), str)
                and type(task.get('step')) is int):
            if previous:
                previous['gap'] = True
            continue
        ident, step = task['id'], task['step']
        if previous is None or (ident, step, run) != (previous['id'], previous['step'], previous['run']):
            state['brains'][key] = dict(id=ident, step=step, run=run, since=ct, last=ct,
                                       notified=False, gap=False)
            continue
        if previous['gap'] or ct < previous['last']:
            previous.update(since=ct, last=ct, gap=False)
            continue
        previous['last'] = ct
        age = ct - previous['since']
        basis = dict(src=key, file=item['file'], run=run, completed_tock=ct,
                     id=ident, step=step, since=previous['since'], age=age)
        if age >= warn and not previous['notified']:
            candidates.append(dict(op='notify', target=recipient, basis=deepcopy(basis),
                text=f"{source['node']} 的 brain：信 {ident} 停在第 {step} 回合，已 {age} 回合沒進展（停在：{task.get('line', '')}）"))
            previous['notified'] = True
        if age >= stop and state['killed'].get(key) != run and key in targets:
            candidates.append(dict(op='kill', target=deepcopy(targets[key]), run=run, basis=deepcopy(basis),
                why=f"信 {ident} 停在第 {step} 回合已 {age} 回合沒進展，殺掉 run {run} 讓 brain 從 task.json 接續"))
            state['killed'][key] = run
    return state, candidates


def noop(ctx, snap, rstate):
    return deepcopy(rstate) if isinstance(rstate, dict) else {}, []


RULES = {'supervise-brain': supervise_brain, 'noop': noop}
