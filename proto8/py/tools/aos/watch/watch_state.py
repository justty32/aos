"""Maintain promotion windows and invoke rollback through observed tool calls."""
import json
import math
import os
from pathlib import Path
import re
import tempfile

import observed
from tool_io import Error

ROLLBACK = Path(__file__).resolve().parent.parent / 'rollback'
FIELDS = ('target', 'defs', 'round', 'promoted_at', 'metric', 'baseline', 'window', 'tolerance')


def _number(value, label, code, positive=False):
    try:
        finite = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or value < 0 or positive and value == 0:
        raise Error(code, '%s must be a finite %s number' % (
            label, 'positive' if positive else 'non-negative'))
    return value


def _string(value, label, code, empty=False):
    if not isinstance(value, str) or '\0' in value or not empty and not value:
        raise Error(code, '%s must be a %sstring' % (label, '' if empty else 'nonempty '))
    return value


def _pointer(value, code):
    _string(value, 'metric', code, empty=True)
    if value and (not value.startswith('/') or re.search(r'~(?![01])', value)):
        raise Error(code, 'metric must be a JSON pointer')


def _window(item, code):
    if not isinstance(item, dict):
        raise Error(code, 'each watch window must be an object')
    for key in ('target', 'defs', 'promoted_at'):
        _string(item.get(key), key, code)
    if not Path(item['defs']).is_absolute():
        raise Error(code, 'defs must be an absolute path')
    if isinstance(item.get('round'), bool) or not isinstance(item.get('round'), (str, int)):
        raise Error(code, 'round must be a string or integer')
    _pointer(item.get('metric'), code)
    for key in ('baseline', 'tolerance'):
        _number(item.get(key), key, code)
    if type(item.get('window')) is not int or item['window'] < 1:
        raise Error(code, 'window must be a positive integer')
    samples = item.get('samples')
    if not isinstance(samples, list):
        raise Error(code, 'samples must be an array')
    for sample in samples:
        if not isinstance(sample, dict) or type(sample.get('pass')) is not bool:
            raise Error(code, 'each sample must be an object with a boolean pass')
        _string(sample.get('case'), 'sample case', code)
        _number(sample.get('unit_cost'), 'sample unit_cost', code)


def _load(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {'watch': []}
    except (ValueError, UnicodeError) as error:
        raise Error('FileBad', 'invalid watch JSON: %s' % error) from None
    except OSError as error:
        raise Error('ReadFailed', str(error)) from None
    if not isinstance(data, dict) or not isinstance(data.get('watch'), list):
        raise Error('FileBad', 'watch file must contain a watch array')
    for item in data['watch']:
        if not isinstance(item, dict) or item.get('state') not in ('watching', 'kept', 'rolled_back'):
            raise Error('FileBad', 'each watch window must have a valid state')
        _string(item.get('target'), 'target', 'FileBad')
        if item['state'] == 'watching':
            _window(item, 'FileBad')
    return data


def _save(path, data):
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name + '-', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, allow_nan=False)
            stream.write('\n')
        os.replace(temporary, path)
    except (OSError, ValueError) as error:
        raise Error('WriteFailed', str(error)) from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _unit_cost(measure, metric):
    try:
        value = measure['cost']
        for part in metric[1:].split('/') if metric else ():
            key = part.replace('~1', '/').replace('~0', '~')
            if isinstance(value, list):
                if not re.fullmatch(r'0|[1-9][0-9]*', key):
                    raise ValueError('invalid array index')
                value = value[int(key)]
            else:
                value = value[key]
        cost = _number(value, 'metric cost', 'MeasureBad')
        size = _number(measure['size_bytes'], 'measure.size_bytes', 'MeasureBad', positive=True)
        return _number(cost / size, 'unit cost', 'MeasureBad')
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as error:
        raise Error('MeasureBad', 'cannot calculate unit cost at %s: %s' % (metric, error)) from None


def _rollback(item):
    try:
        code, _, stderr = observed.call('rollback', ROLLBACK, json.dumps({
            'defs': item['defs'], 'target': item['target']}).encode('utf-8'))
    except OSError as error:
        return 'RollbackFailed %s' % error
    if code == 0:
        return None
    lines = stderr.decode('utf-8', errors='replace').strip().splitlines()
    match = re.search(r': error: (\S+) (.*)', lines[-1]) if lines else None
    return '%s %s [exit code %d]' % (match.group(1), match.group(2), code) if match else (
        'RollbackFailed rollback failed [exit code %d]' % code)


def _feed(data, args):
    case = _string(args.get('case'), 'case', 'ArgumentsBad')
    measure = args.get('measure')
    if (not isinstance(measure, dict) or not isinstance(measure.get('check'), dict)
            or type(measure['check'].get('pass')) is not bool):
        raise Error('MeasureBad', 'measure.check.pass must be a boolean')
    active = [item for item in data['watch'] if item['state'] == 'watching']
    costs = [_unit_cost(measure, item['metric']) for item in active]
    changes = []
    for item, cost in zip(active, costs):
        item['samples'].append({'case': case, 'unit_cost': cost, 'pass': measure['check']['pass']})
        reason, rollback = 'Waiting for more cases.', False
        if any(not sample['pass'] for sample in item['samples']):
            reason, rollback = 'A quality gate failed.', True
        elif len(item['samples']) >= item['window']:
            average = sum(sample['unit_cost'] / item['window']
                          for sample in item['samples'][:item['window']])
            rollback = average > item['baseline'] * (1 + item['tolerance'])
            reason = 'Mean unit cost exceeds tolerance.' if rollback else 'Mean unit cost is within tolerance.'
            if not rollback:
                item['state'] = 'kept'
        change = {'target': item['target'], 'state': item['state'], 'reason': reason}
        if rollback:
            error = _rollback(item)
            if error:
                change['error'] = error
            else:
                item['state'] = change['state'] = 'rolled_back'
        changes.append(change)
    return changes


def run(args):
    """Open or feed windows, saving the resulting watch document atomically."""
    op = args.get('op')
    if op not in ('open', 'feed'):
        raise Error('ArgumentsBad', 'op must be open or feed')
    path = Path(_string(args.get('watch'), 'watch', 'ArgumentsBad'))
    if not path.is_absolute():
        raise Error('PathBad', 'watch must be an absolute path')
    data = _load(path)
    if op == 'open':
        item = {key: args.get(key) for key in FIELDS}
        item.update(samples=[], state='watching')
        _window(item, 'ArgumentsBad')
        data['watch'].append(item)
        changes = [{'target': item['target'], 'state': 'watching', 'reason': 'Opened a promotion window.'}]
    else:
        changes = _feed(data, args)
    if op == 'open' or data['watch']:
        _save(path, data)
    return {'changes': changes}
