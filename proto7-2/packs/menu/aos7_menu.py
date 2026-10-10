"""選單核心：純函式，不讀檔、不呼叫工具、不改傳入物件。"""
import copy
import secrets
from aos7_menu_check import (BUILTINS, MenuError, check_slot, out_path,
                             parse_reply, require, template, validate, normalize_out, at, expanded_slot,
                             validate_brief, selected_brief, brief_limit, brief_when, BriefError)

SYSTEM = '你在走一份選單。每次只回答這一層。所需資料都在下面，不用找檔案或工具。照回法回，不要多寫別的。'


def load(obj, tools):
    return validate(obj, tools)


def new_state(menu, run, vars, brief, menu_sha):
    validate_brief(menu, brief)
    values = copy.deepcopy(vars)
    values['run'] = run
    state = {'v': 1, 'menu': '', 'menu_sha': menu_sha, 'run': run,
            'layer': menu['start'], 'vars': values, 'brief': brief, 'done': [],
            'tries': 0, 'step': 0, 'calls': [], 'gate_rounds': {},
            'var_owner': {}, 'nonce': secrets.token_hex(8), 'pending': None, 'status': 'walking', 'why': None}
    _move(menu, state, menu['start'])
    return state


def options(menu, state):
    layer = menu['layers'][state['layer']]
    source = layer.get('options')
    done = [normalize_out('out/' + name) for name in state['done']]
    label = '層 ' + state['layer'] + ' '
    if isinstance(source, dict):
        only = [at(label + 'options.only', template, x, state['vars']) for x in source.get('only', [])]
        result = [{'text': name, 'set': {'file': name}, 'next': layer['next']}
                  for name in done if 'only' not in source or name in only]
    elif source is None:
        result = [{'text': '交出這一格', 'next': layer['next']}]
    else:
        complete = None
        if any(o.get('when') in ('required_done', 'required_missing') for o in source):
            required = [normalize_out(at(label + 'required', template, x, state['vars']))
                        for x in menu.get('required', [])]
            complete = all(x in done for x in required)
        result = []
        for option in source:
            when = option.get('when')
            enabled = when is None or (when == 'required_done' and complete) or (when == 'required_missing' and not complete)
            if when and when.startswith('new:'):
                path = at(label + 'options.when', out_path, when[4:], state['vars'])
                enabled = normalize_out(path) not in done
            if when and when.startswith('brief:'):
                enabled = brief_when(when, state.get('brief', ''))
            if enabled:
                result.append(option)
    require(2 <= len(result) + 1 <= 5, label + 'options 含出口要 2～5 個，現在 %s 個' % (len(result) + 1))
    return result


def _tool(layer, state):
    return {'tool': layer['do']['tool'], 'args': {k: at('層 ' + state['layer'] + ' do.args', template, v, state['vars']) for k, v in layer['do'].get('args', {}).items()}}


def view(menu, state):
    if state['status'] == 'done' or state['layer'] == 'end':
        return {'kind': 'done'}
    if state['status'] == 'stuck':
        return {'kind': 'stuck', 'code': state.get('code', 1), 'why': state['why']}
    if state.get('pending') and 'act' in state['pending']:
        return {'kind': 'act', 'act': copy.deepcopy(state['pending']['act'])}
    layer = menu['layers'][state['layer']]
    if 'ask' not in layer:
        if state['gate_rounds'].get(state['layer'], 0) >= layer.get('max_rounds', float('inf')):
            return {'kind': 'stuck', 'code': 1, 'why': '層 ' + state['layer'] + ' max_rounds 輪數到上限。請換 --run 重走'}
        return {'kind': 'act', 'act': _tool(layer, state)}
    options(menu, state)
    previous = state.get('pending') or {}
    count = sum(c['layer'] == state['layer'] for c in state['calls']) + 1
    call_id = previous.get('call_id', 'menu/%s/%s/%s' % (state['run'], state['layer'], count))
    return {'kind': 'ask', 'layer': state['layer'], 'call_id': call_id, 'reminder': state['why'] if state['tries'] else None}


def render(menu, state, shown=None, reminder=None):
    layer = menu['layers'][state['layer']]
    pieces = []
    reminder = reminder or (state['why'] if state['tries'] else None)
    if reminder:
        pieces.append('上一次不行：' + reminder + '。照回法重回一次')
    try:
        brief = at('層 ' + state['layer'] + ' brief', selected_brief, layer, state.get('brief', ''), state['vars'])
    except MenuError as exc:
        raise BriefError(str(exc)) from None
    brief_limit(state['layer'], brief)
    if brief:
        pieces.append('需求：' + brief)
    if state['done']:
        pieces.append('已交：' + '、'.join(state['done']))
    pieces.append(at('層 ' + state['layer'] + ' ask', template, layer['ask'], state['vars']))
    if shown is not None:
        require(len(shown.encode('utf-8')) <= 8192, '層 ' + state['layer'] + ' show 檔案超過 8192 bytes')
        pieces.append('目前的內容：\n' + shown)
    choices = options(menu, state)
    literal = isinstance(layer.get('options'), dict)
    pieces.extend('%s. %s' % (i, o['text'] if literal else at('層 ' + state['layer'] + ' options.text', template, o['text'], state['vars'])) for i, o in enumerate(choices, 1))
    pieces.append('%s. %s' % (len(choices) + 1, at('層 ' + state['layer'] + ' exit.text', template, layer['exit']['text'], state['vars'])))
    pieces.append('回法：第一行 選：N')
    if 'slot' in layer:
        slot = at('層 ' + state['layer'] + ' slot', expanded_slot, layer['slot'], state['vars'])
        pieces.append('第二行起：先寫「格：」，後面（同一行或下一行起）到結尾放全文，原樣、不加 ``` 圍欄，全文後面不要再寫任何字')
        limits = []
        for key, value in slot.items():
            if key == 'max_bytes':
                limits.append('最多 %s bytes' % value)
            elif key == 'max_lines':
                limits.append('最多 %s 行' % value)
            elif key == 'prefix':
                limits.append('第一行以「%s」開頭' % value)
            elif key == 'sections':
                limits.extend('要有一行以「%s」開頭' % section for section in value)
            elif key == 'tool':
                limits.append('會再用工具檢查')
        pieces.append('這格的限制（只是說明，不要抄進格子）：' + '、'.join(limits))
    return '\n'.join(pieces)


def _stop(state, why, code=1):
    state.update(status='stuck', why=why, code=code, pending=None)


def _bad(state, why):
    state['pending'] = None
    state['tries'] += 1
    state['why'] = why
    if state['tries'] >= 3:
        _stop(state, '連 3 次回得不像（層 %s）：%s。請換 --run 重走' % (state['layer'], why))


def _move(menu, state, target):
    skipped = 0
    while target != 'end':
        layer = menu['layers'][target]
        if 'when' not in layer or brief_when(layer['when'], state.get('brief', '')):
            break
        skipped += 1
        if skipped > len(menu['layers']):
            raise MenuError('層 ' + target + ' when 連跳超過層數。請改好 next，避免跳過的層繞圈')
        target = layer['next']
    state.update(layer=target, tries=0, why=None, pending=None)
    if target == 'end':
        state['status'] = 'done'


def step(menu, state, reply):
    s = copy.deepcopy(state)
    s['step'] += 1
    s['pending'] = None
    s['fence'] = False
    layer = menu['layers'][s['layer']]
    choices = options(menu, s)
    number, _, _, why = parse_reply(reply)
    if why or number < 1 or number > len(choices) + 1:
        _bad(s, why or '編號不在這層選項裡')
        return s, view(menu, s)
    if number == len(choices) + 1:
        _stop(s, 'AI 選了出口：' + at('層 ' + s['layer'] + ' exit.text', template, layer['exit']['text'], s['vars']) + '。請換 --run 重走')
        return s, view(menu, s)
    text = None
    if 'slot' in layer:
        _, text, s['fence'], why = parse_reply(reply, True)
        why = why or at('層 ' + s['layer'] + ' slot', check_slot, layer['slot'], text, s['vars'])
        if why:
            _bad(s, why)
            return s, view(menu, s)
    option = choices[number - 1]
    literal = isinstance(layer.get('options'), dict)
    values = {k: v if literal else at('層 ' + s['layer'] + ' options.set', template, v, s['vars'])
              for k, v in option.get('set', {}).items()}
    s['vars'].update(values)
    for key in values:
        s['var_owner'].pop(key, None)
    target = option['next']
    act = None
    if 'do' in layer:
        if 'write' in layer['do']:
            act = {'write': at('層 ' + s['layer'] + ' do.write', out_path, layer['do']['write'], s['vars']), 'text': text}
        else:
            act = _tool(layer, s)
    pending = {'act': act, 'next': target} if act else {'next': target}
    if 'tool' in layer.get('slot', {}):
        s['pending'] = {'act': {'check': layer['slot']['tool'], 'text': text}, 'then': pending}
    elif act:
        s['pending'] = pending
        s.update(tries=0, why=None)
    else:
        _move(menu, s, target)
    return s, view(menu, s)


def after(menu, state, result):
    s = copy.deepcopy(state)
    s['step'] += 1
    layer = menu['layers'][s['layer']]
    pending = s.get('pending') or {'act': _tool(layer, s)}
    act = pending['act']
    rc = result.get('rc', 0 if result.get('ok') else 3)
    if rc not in (0, 1):
        return s, {'kind': 'stuck', 'code': 2 if rc == 2 else 3, 'why': result.get('err') or '工具沒有確定完成。照原樣再跑一次會接續'}
    if 'tool' in act or 'check' in act:
        name = act.get('tool', act.get('check'))
        owners = s['var_owner']
        for key in [key for key, owner in owners.items() if owner == name]:
            s['vars'].pop(key, None)
            owners.pop(key)
        for k, value in result.get('out', {}).items():
            if k not in BUILTINS and isinstance(value, (str, int, float, bool)):
                s['vars'][k] = value[:600] + '…' if isinstance(value, str) and len(value) > 600 else value
                owners[k] = name
    if 'check' in act:
        if rc:
            _bad(s, (result.get('err') or '格子檢查沒過').splitlines()[-1][:200])
        else:
            then = pending['then']
            s.update(tries=0, why=None)
            if 'act' in then:
                s['pending'] = then
            else:
                _move(menu, s, then['next'])
    elif 'write' in act:
        if rc:
            return s, {'kind': 'stuck', 'code': 3, 'why': '不確定：寫檔沒有完成。照原樣再跑一次會接續'}
        path = normalize_out(act['write'])
        s['done'] = list(dict.fromkeys(normalize_out('out/' + x) for x in s['done']))
        if path not in s['done']:
            s['done'].append(path)
        _move(menu, s, pending['next'])
    else:
        s['gate_rounds'][s['layer']] = s['gate_rounds'].get(s['layer'], 0) + 1
        target = pending.get('next') if rc == 0 else None
        target = target or layer.get('ok' if rc == 0 else 'fail')
        if target:
            _move(menu, s, target)
        else:
            _stop(s, '層 ' + s['layer'] + ' fail 沒有分支，工具沒過。請換 --run 重走')
    return s, view(menu, s)
