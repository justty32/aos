"""aos-agent.md §3、§8：門與輸入共用先記、再搬的消費流程。"""
from pathlib import Path

from aos_agent_home import _read_json, check_message
from aos_agent_runtime import files, unique_id


def archived(paths, identity):
    return [{'src': path, 'dst': str(Path(path).parent / 'done' / ('%s.%s.done' % (Path(path).name, identity)))}
            for path in dict.fromkeys(paths)]


def finish_consuming(run):
    if run.st['consuming']:
        run.move(run.st['consuming'])
        run.st['consuming'] = []
        run.save('state.consumed')


def gate(run):
    remaining, consumed = [], []
    for entry, decoded in zip(run.st['waits'], run.st['_waits']):
        groups = [files(run.base, path) for path in decoded['paths']]
        if not all(groups):
            remaining.append(entry)
        elif 'consume' in decoded['options']:
            consumed.extend(path for group in groups for path in group)
    if len(remaining) != len(run.st['waits']):
        run.st['waits'] = remaining
        run.st['consuming'] = archived(consumed, unique_id())
        run.save('state.gate')
        finish_consuming(run)
    return not remaining


def intake(run):
    st = run.st
    if st['intake'] is None:
        paths = [p for value in st['input'] for p in files(run.base, value)]
        if not paths:
            return 101
        identity = unique_id()
        st['intake'] = {'id': identity, 'base_len': len(run.info['history']),
                        'files': archived(paths, identity)}
        run.save('state.intake')
    record = st['intake']
    run.move(record['files'])
    messages = []
    for pair in record['files']:
        if not Path(pair['dst']).exists():
            continue
        value = _read_json(pair['dst'])
        if isinstance(value, str):
            value = {'role': 'user', 'content': value}
        values = value if isinstance(value, list) else [value]
        for message in values:
            check_message(message)
        messages.extend(values)
    if not messages:
        st['intake'] = None
        run.save('state.intake_empty')
        return 101
    run.history(record['base_len'], messages)
    st.update(state='think', intake=None)
    run.save('state.intake_done')
    return 0
