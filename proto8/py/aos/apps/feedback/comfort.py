"""Calculate AI comfort from scored feedback and consecutive observed tool calls."""
from pathlib import Path
import statistics

from .storage import KINDS, fail, read_rows


def behavior_counts(key, paths):
    calls = errors = retries = 0
    for path in paths:
        if not Path(path).is_file():
            fail('FileMissing', 'observed ledger does not exist: %s' % path)
        previous = None
        for row in read_rows(Path(path)):
            if row.get('kind') != 'tool':
                continue
            name, definition = row.get('name'), row.get('def')
            matches = name == key or (isinstance(definition, str) and Path(definition).name == key)
            identity = ('def', definition) if definition else ('name', name)
            if matches:
                if type(row.get('code')) is not int:
                    fail('FileBad', '%s: matching tool row needs an integer code' % path)
                calls += 1
                errors += row['code'] != 0
                if previous is not None and previous[0] == identity and previous[1] != 0:
                    retries += 1
            previous = (identity, row.get('code'))
    return calls, errors, retries


def components(rows, behavior):
    ai = {}
    for kind in KINDS:
        scores = [row['score'] for row in rows if row['kind'] == kind and 'score' in row]
        ai[kind] = statistics.mean(scores) if scores else None
    values = [value for value in ai.values() if value is not None]
    val = statistics.mean(values) if values else behavior
    if values and behavior is not None:
        val *= behavior
    return ai, val


def score(key, rows, paths):
    calls, errors, retries = behavior_counts(key, paths)
    behavior = calls / (calls + errors + retries) if calls else None
    ai, val = components(rows, behavior)
    groups = {'family': {}, 'tier': {}}
    for axis in groups:
        buckets = {}
        for row in rows:
            group = row.get('rater', {}).get(axis, 'unknown')
            buckets.setdefault(group, []).append(row)
        for group, members in buckets.items():
            subitems, subtotal = components(members, behavior)
            groups[axis][group] = dict(subitems, val=subtotal)
    return {'key': key, 'feedback': len(rows), 'calls': calls, 'errors': errors,
            'retries': retries, 'comfort': {'ai': ai, 'ai_by': groups,
                                          'user': None, 'val': val}}
