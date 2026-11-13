"""Append command feedback and read its local model classification rules."""
import datetime
import fcntl
import json
import math
import os
from pathlib import Path
import re

import aos_flags

KINDS = ('usage', 'help', 'errors', 'args')


def fail(code, reason):
    raise aos_flags.Error(reason, code)


def directory():
    if 'AOS_FEEDBACK' in os.environ:
        if not os.environ['AOS_FEEDBACK']:
            fail('ArgumentsBad', 'AOS_FEEDBACK must not be empty')
        return Path(os.environ['AOS_FEEDBACK']).absolute()
    for parent in Path(__file__).resolve().parents:
        if parent.name == 'proto8':
            return parent / 'feedback'
    fail('PathMissing', 'cannot find proto8; set AOS_FEEDBACK')


def command_key(command):
    words = command.split()
    if not words:
        fail('ArgumentsBad', 'command must not be empty')
    key = re.sub('[^a-z0-9_-]', '_', os.path.basename(words[0]).lower())
    if not key:
        fail('ArgumentsBad', 'command must have a non-empty basename')
    return key


def key_path(root, key):
    if not re.fullmatch('[a-z0-9_-]+', key):
        fail('ArgumentsBad', 'key must contain only a-z, 0-9, underscore or hyphen')
    return root / (key + '.jsonl')


def score_number(value):
    try:
        score = float(value)
    except (TypeError, ValueError, OverflowError):
        fail('ArgumentsBad', 'score must be a finite number from 0 to 1')
    if isinstance(value, bool) or not math.isfinite(score) or not 0 <= score <= 1:
        fail('ArgumentsBad', 'score must be a finite number from 0 to 1')
    return score


def rater(root, options):
    model = options.get('model', 'unknown')
    family, tier = 'unknown', 'unknown'
    if 'model' in options and ('family' not in options or 'tier' not in options):
        path = root / 'raters.json'
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            data = {'rules': []}
        except (OSError, ValueError) as error:
            fail('FileBad', 'cannot read %s: %s' % (path, error))
        if not isinstance(data, dict) or not isinstance(data.get('rules'), list):
            fail('FileBad', '%s must contain a rules array' % path)
        for rule in data['rules']:
            if not isinstance(rule, dict) or any(not isinstance(rule.get(k), str)
                                                 for k in ('match', 'family', 'tier')):
                fail('FileBad', '%s rules need string match, family and tier' % path)
            if rule['match'].lower() in model.lower():
                family, tier = rule['family'], rule['tier']
                break
    return {'model': model, 'family': options.get('family', family),
            'tier': options.get('tier', tier)}


def cwd_without_home():
    """The working directory, with the home directory prefix written as ~ (records go into git)."""
    cwd = os.getcwd()
    home = os.path.expanduser('~').rstrip('/')
    if home and home != '~' and (cwd == home or cwd.startswith(home + '/')):
        return '~' + cwd[len(home):]
    return cwd


def add(root, arguments, options):
    command, pain = arguments[:2]
    key = command_key(command)
    if not pain.strip():
        fail('ArgumentsBad', 'pain must not be empty')
    kind = options.get('kind', 'other')
    if kind not in (*KINDS, 'other'):
        fail('ArgumentsBad', 'kind must be usage, help, errors, args or other')
    record = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec='milliseconds').replace('+00:00', 'Z'),
        'command': command, 'kind': kind, 'pain': pain}
    if len(arguments) == 3:
        record['suggest'] = arguments[2]
    if 'score' in options:
        record['score'] = score_number(options['score'])
    definition = os.environ.get('AOS_CD')
    record.update(by=options.get('by', Path(definition).name if definition else 'unknown'),
                  rater=rater(root, options), cwd=cwd_without_home())
    path = key_path(root, key)
    root.mkdir(parents=True, exist_ok=True)
    # Each append owns the file until its complete JSON line has been flushed.
    with path.open('a', encoding='utf-8') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
        stream.flush()
    return path, record


def read_rows(path):
    try:
        stream = path.open(encoding='utf-8')
    except FileNotFoundError:
        return []
    records = []
    with stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError('row must be an object')
            except ValueError as error:
                fail('FileBad', '%s:%d: %s' % (path, number, error))
            records.append(record)
    return records


def records(root, key):
    rows = read_rows(key_path(root, key))
    for row in rows:
        if any(not isinstance(row.get(k), str) for k in ('at', 'command', 'kind', 'pain', 'by')):
            fail('FileBad', '%s contains a feedback row with missing string fields' % key)
        if row['kind'] not in (*KINDS, 'other'):
            fail('FileBad', '%s contains an unknown feedback kind' % key)
        if 'score' in row:
            value = row['score']
            if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 1:
                fail('FileBad', '%s contains an invalid score' % key)
        rated = row.get('rater', {})
        if not isinstance(rated, dict) or any(not isinstance(rated.get(k, 'unknown'), str)
                                              for k in ('model', 'family', 'tier')):
            fail('FileBad', '%s contains an invalid rater' % key)
    return rows


def listing(root):
    result = []
    for path in sorted(root.glob('*.jsonl')):
        rows = records(root, path.stem)
        if rows:
            result.append({'key': path.stem, 'feedback': len(rows),
                           'latest': rows[-1]['at']})
    return sorted(result, key=lambda row: (-row['feedback'], row['key']))
