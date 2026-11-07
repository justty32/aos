"""Read review settings, traverse definition trees, and account for measured costs."""
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sys

import observed
from tool_io import Error


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def settings(path):
    value = read(path)
    if not isinstance(value, dict):
        raise Error('ArgumentsBad', 'ladder.json must be an object')
    ladder = value.get('ladder')
    watch = value.get('watch', {})
    if not isinstance(ladder, list) or not ladder or any(not isinstance(x, str) or not x for x in ladder):
        raise Error('ArgumentsBad', 'ladder must be a nonempty array of endpoint names')
    if len(set(ladder)) != len(ladder):
        raise Error('ArgumentsBad', 'ladder endpoint names must be unique')
    if type(value.get('repeat')) is not int or value['repeat'] < 1:
        raise Error('ArgumentsBad', 'repeat must be a positive integer')
    score = value.get('min_score')
    if type(score) not in (int, float) or not 0 <= score <= 1:
        raise Error('ArgumentsBad', 'min_score must be between 0 and 1')
    if value.get('promote_by', 'self') not in ('self', 'claude'):
        raise Error('ArgumentsBad', 'promote_by must be self or claude')
    if not isinstance(watch, dict):
        raise Error('ArgumentsBad', 'watch must be an object')
    for key in ('window', 'baseline_cases'):
        if type(watch.get(key)) is not int or watch[key] < 1:
            raise Error('ArgumentsBad', 'watch.%s must be a positive integer' % key)
    tolerance = watch.get('tolerance')
    if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or tolerance < 0:
        raise Error('ArgumentsBad', 'watch.tolerance must be finite and nonnegative')
    if not isinstance(watch.get('metric'), str) or not watch['metric'].startswith('/'):
        raise Error('ArgumentsBad', 'watch.metric must be a JSON pointer')
    return value


def unit(cost, size, metric):
    value = cost
    for token in metric[1:].split('/'):
        key = token.replace('~1', '/').replace('~0', '~')
        value = value[int(key)] if isinstance(value, list) else value[key]
    if type(size) not in (int, float) or not math.isfinite(size) or size <= 0:
        raise Error('MeasureBad', 'size_bytes must be positive to calculate unit cost')
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise Error('MeasureBad', 'metric must select a finite nonnegative cost')
    return value / size


def nodes(tree):
    yield tree
    for child in tree.get('children', []):
        yield from nodes(child)


def local(value, defs):
    if not isinstance(value, str) or not value:
        return None
    path = (defs / value).resolve()
    if not path.is_relative_to(defs):
        return None
    relative = path.relative_to(defs).as_posix()
    if relative == '.' or any(part.startswith('.') for part in relative.split('/')):
        return None
    return relative


def dirty(tree, target, defs):
    """Return only the selected node's ancestors and descendants in the call tree."""
    related = set()

    def walk(node, parents):
        name = local(node.get('def'), defs)
        if name == target:
            related.update(x for x in parents if x)
            related.update(local(n.get('def'), defs) for n in nodes(node))
        for child in node.get('children', []):
            walk(child, parents + [name])

    walk(tree, [])
    return sorted(related - {None, target})


def add_cost(costs):
    result = {'token': {'in': 0, 'out': 0, 'cached': 0}, 'counter_calls': 0, 'time_ms': 0}
    for cost in costs:
        for key in result['token']:
            result['token'][key] += cost.get('token', {}).get(key, 0)
        for key in ('counter_calls', 'time_ms', 'counter_usage_missing'):
            if key in cost:
                result[key] = result.get(key, 0) + cost[key]
    return result


def call(name, target, args, tolerated=()):
    code, out, err = observed.call(name, target, json.dumps(args).encode())
    stderr = err.decode(errors='replace')
    if code:
        tail = stderr.strip().splitlines()
        if tail and ': error: ' in tail[-1]:
            tag, _, reason = tail[-1].split(': error: ', 1)[1].partition(' ')
            if tag not in tolerated:
                sys.stderr.write(stderr)
            raise Error(tag, reason)
        sys.stderr.write(stderr)
        raise Error('ToolFailed', '%s exited %d' % (name, code))
    sys.stderr.write(stderr)
    value = json.loads(out)
    if not isinstance(value, dict):
        raise Error('ToolFailed', '%s did not return a JSON object' % name)
    return value


def new_round(reviews):
    instant = datetime.now(timezone.utc)
    while True:
        stamp = instant.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        folder = reviews / stamp.replace(':', '-')
        try:
            folder.mkdir(parents=True)
            return stamp, folder
        except FileExistsError:
            instant += timedelta(milliseconds=1)


def history(reviews):
    return [read(path) for path in sorted(reviews.glob('*/review.json'))]
