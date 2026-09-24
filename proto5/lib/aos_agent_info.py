"""agent.md 的完整設定與進度讀驗；內容六格重用 aos_agent_home。"""
import copy
import os
from pathlib import Path

from aos_agent_home import AgentError, _read_json, load_llm_view, read_info_doc, resolve_field
from aos_directives import (Context, DirectiveError, Document, is_directive,
                            parse_options, resolve_located)
from aos_home import write_json


def _typed(value, kind, where):
    valid = isinstance(value, str) if kind is str else type(value) is int and value >= 0
    if not valid:
        raise AgentError('FieldTypeMismatch', '%s 型別不合' % where)
    return value


def load(agent_dir, env=None):
    """六格與內容照共用層；補齊排程欄位，工具 _meta 保持原樣。"""
    info = load_llm_view(agent_dir, env=env)
    doc = read_info_doc(info['dir'])
    ctx = Context(doc, base_dir=info['dir'], env=env)
    info['metainfo'] = resolve_field(doc, ctx, ['_metainfo'])
    llm = {'model': info['model'], 'params': info['params']}
    for key, default, kind in [('pool', 'llm', str), ('timeout_ms', 125000, int)]:
        value = resolve_field(doc, ctx, ['llm', key]) if key in doc.root['llm'] else default
        llm[key] = _typed(value, kind, 'llm.' + key)
    info['llm'] = llm
    value = resolve_field(doc, ctx, ['tool_pool']) if 'tool_pool' in doc.root else 'default'
    info['tool_pool'] = _typed(value, str, 'tool_pool')
    # §2 只限頂層與 llm 為字面物件；tick 可以由指示詞取得。
    try:
        loc = resolve_located(doc.root.get('tick', {}), ctx, ['tick'])
        tick = parse_options(loc.value, loc.position, {})[1]
    except DirectiveError as exc:
        raise AgentError(exc.code, exc.msg) from exc
    if not isinstance(tick, dict):
        raise AgentError('FieldTypeMismatch', 'tick 必須解成物件')
    tick = {key: resolve_field(loc.ctx.doc, loc.ctx, loc.position + [key])
            for key in ('pool', 'interval_ms') if key in tick}
    info['tick'] = {'pool': _typed(tick.get('pool', 'default'), str, 'tick.pool'),
                    'interval_ms': (_typed(tick['interval_ms'], int, 'tick.interval_ms')
                                    if 'interval_ms' in tick else None)}
    return info


WAIT_OPTIONS = {name: {'val': 'required'} for name in ('consume', 'exists', 'all')}
FIELDS = ('state', 'errors', 'input', 'waits', 'batch', 'intake', 'consuming', 'sweep')


def require(ok, where):
    if not ok:
        raise AgentError('FieldTypeMismatch', '%s 必須是規定形狀的字面值' % where)


def obj(value, where):
    require(isinstance(value, dict) and not is_directive(value), where)


def natural(value):
    return type(value) is int and value >= 0


def absolute(value):
    return isinstance(value, str) and os.path.isabs(value) and '\0' not in value


def work_name(value):
    return isinstance(value, str) and value not in ('', '.', '..') and '/' not in value and '\0' not in value


def paths(value, where):
    if isinstance(value, str):
        return [value]
    require(isinstance(value, list) and bool(value) and all(isinstance(p, str) for p in value), where)
    return value


def pairs(value, where):
    require(isinstance(value, list), where)
    for item in value:
        obj(item, where)
        require(absolute(item.get('src')) and absolute(item.get('dst')), where)


def check_batch(batch):
    if batch is None:
        return
    obj(batch, 'batch')
    kind = batch.get('kind')
    require(kind in ('think', 'act'), 'batch.kind')
    require(absolute(batch.get('kernel')), 'batch.kernel')
    require(natural(batch.get('base_len')), 'batch.base_len')
    require(type(batch.get('sent')) is bool, 'batch.sent')
    calls = batch.get('calls')
    require(isinstance(calls, list), 'batch.calls')
    require(kind != 'think' or len(calls) == 1, 'think.calls')
    for call in calls:
        obj(call, 'call')
        require('name' in call and (call['name'] is None or work_name(call['name'])), 'call.name')
        require(type(call.get('acked')) is bool and 'done' in call, 'call')
        if kind == 'act':
            require(isinstance(call.get('tool_call_id'), str) and isinstance(call.get('tool'), str), 'act.call')
        done = call['done']
        if done is None:
            continue
        obj(done, 'done')
        if kind == 'act':
            require(isinstance(done.get('content'), str), 'done.content')
        else:
            require(done.get('ok') is True or
                    (isinstance(done.get('fail'), str) and type(done.get('count')) is bool), 'think.done')


def check_records(st):
    check_batch(st['batch'])
    intake = st['intake']
    if intake is not None:
        obj(intake, 'intake')
        require(isinstance(intake.get('id'), str) and natural(intake.get('base_len')), 'intake')
        pairs(intake.get('files'), 'intake.files')
    pairs(st['consuming'], 'consuming')
    require(isinstance(st['sweep'], list), 'sweep')
    for item in st['sweep']:
        obj(item, 'sweep[]')
        require(absolute(item.get('kernel')) and work_name(item.get('name')), 'sweep[]')


def read_waits(doc, ctx):
    raw = doc.root.get('waits', [])
    entries = raw if isinstance(raw, list) else [raw]
    decoded = []
    for i, entry in enumerate(entries):
        pos = ['waits', str(i)] if isinstance(raw, list) else ['waits']
        # 整條不能藉 $ref 變出陣列；只有選項的 $val 可以解指示詞。
        if isinstance(entry, dict) and '$opt' not in entry:
            if '$val' in entry:
                raise AgentError('UnknownDirective', 'waits 的 $val 缺少 $opt')
            require(False, 'waits 條目')
        require(isinstance(entry, str) or isinstance(entry, dict), 'waits 條目')
        try:
            names, value, _ = parse_options(entry, pos, WAIT_OPTIONS)
        except DirectiveError as exc:
            raise AgentError(exc.code, exc.msg) from exc
        if isinstance(entry, dict):
            value = resolve_field(doc, ctx, pos + ['$val'])
        decoded.append({'options': names, 'paths': paths(value, 'waits.$val')})
    return copy.deepcopy(entries), decoded


def load_state(agent_dir, env=None):
    base = os.path.abspath(agent_dir)
    path = Path(base) / 'state.json'
    try:
        raw = _read_json(path)
    except AgentError as exc:
        if not isinstance(exc.__cause__, FileNotFoundError):
            raise
        raw = {}
    if not isinstance(raw, dict):
        raise AgentError('NotAnObject', 'state.json 頂層必須是物件')
    obj(raw, 'state.json')
    st = {'state': 'idle', 'errors': 0, 'input': 'input.json', 'waits': [],
          'batch': None, 'intake': None, 'consuming': [], 'sweep': []}
    st.update(copy.deepcopy(raw))
    require(not is_directive(st['state']), 'state')
    if st['state'] not in ('idle', 'think', 'act'):
        raise AgentError('StateInvalid', 'state 只認 idle／think／act')
    require(natural(st['errors']), 'errors')
    check_records(st)
    # 以補預設前的文件求值，$ref 的實體位置不變。
    doc = Document(path, raw)
    ctx = Context(doc, base_dir=base, env=env)
    st['_input_raw'] = copy.deepcopy(st['input'])
    value = resolve_field(doc, ctx, ['input']) if 'input' in raw else 'input.json'
    st['input'] = paths(value, 'input')
    st['waits'], st['_waits'] = read_waits(doc, ctx)
    return st


def write_state(agent_dir, st):
    """同目錄暫存再 rename；內部解好的資料不寫進 state。"""
    raw = {k: v for k, v in st.items() if k not in ('_input_raw', '_waits')}
    raw['input'] = copy.deepcopy(st.get('_input_raw', st['input']))
    waits = st['waits']
    raw['waits'] = copy.deepcopy(waits if isinstance(waits, list) else [waits])
    write_json(Path(agent_dir) / 'state.json', raw)
