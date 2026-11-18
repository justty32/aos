# Fold publicly declared observation ledgers into call trees and aggregate costs.
import json
from pathlib import Path
from statistics import median


def empty_cost():
    return {'token': {'in': 0, 'out': 0, 'cached': 0},
            'counter_calls': 0, 'time_ms': 0}


def add_costs(costs):
    result = empty_cost()
    for cost in costs:
        for key in result['token']:
            result['token'][key] += cost.get('token', {}).get(key, 0)
        for key in ('counter_calls', 'time_ms', 'counter_usage_missing'):
            if key in cost:
                result[key] = result.get(key, 0) + cost[key]
    return result


def _records(stack):
    interface = stack / 'interfaces.json'
    if not interface.exists():
        return []
    interfaces = json.loads(interface.read_text())
    if not isinstance(interfaces, dict):
        raise ValueError('interfaces.json must be an object')
    declaration = interfaces.get('aos-observed', {})
    filename = declaration.get('file') if isinstance(declaration, dict) else None
    if not isinstance(filename, str) or not filename:
        return []
    records = [json.loads(line) for line in (stack / filename).read_text().splitlines()
               if line.strip()]
    if any(not isinstance(record, dict) for record in records):
        raise ValueError('observation records must be objects')
    return records


def fold(stack, defs, target=None, elapsed_ms=None):
    """Return a call tree and total cost, reading only declared public accounts."""
    defs = Path(defs).resolve()
    visited = set()

    def display(value):
        if value is None:
            return None
        path = Path(value)
        path = (defs / path).resolve() if not path.is_absolute() else path.resolve()
        try:
            return path.relative_to(defs).as_posix()
        except ValueError:
            return str(path)

    def walk(location, definition=None, elapsed=None, calls=1, root=False):
        location = Path(location).resolve()
        if location in visited:
            return None
        visited.add(location)
        records = _records(location)
        own = next((r for r in records if r.get('kind') == 'self'), {})
        node = {'def': display(definition or own.get('def')), 'kind': 'script',
                'counter_calls': calls, 'in_bytes': 0,
                'cost': empty_cost(), 'children': [], 'prompt_tokens_median': None}
        cost = node['cost']
        thinks = [r for r in records if r.get('kind') == 'think']
        prompts = [usage['prompt_tokens'] for r in thinks
                   if isinstance(usage := r.get('usage'), dict)
                   and type(usage.get('prompt_tokens')) in (int, float)]
        if prompts:
            node['prompt_tokens_median'] = median(prompts)
        if thinks:
            node['kind'] = 'agent'
            endpoints = list(dict.fromkeys(r['endpoint'] for r in thinks if 'endpoint' in r))
            if endpoints:
                node['endpoint'] = endpoints[0] if len(endpoints) == 1 else endpoints
        for record in thinks:
            cost['counter_calls'] += 1
            usage = record.get('usage')
            if usage is None:
                cost['counter_usage_missing'] = cost.get('counter_usage_missing', 0) + 1
            else:
                cost['token']['in'] += usage.get('prompt_tokens', 0)
                cost['token']['out'] += usage.get('completion_tokens', 0)
                cost['token']['cached'] += (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 0)
        groups = {}
        for record in records:
            if record.get('kind') != 'tool':
                continue
            key = (record.get('name'), record.get('def'), record.get('stack'))
            groups.setdefault(key, []).append(record)
        for (_, definition, relative), group in groups.items():
            duration = sum(r.get('elapsed_ms', 0) for r in group)
            child = walk(location / relative, definition, duration, len(group)) if relative else None
            if child is None:
                child = {'def': display(definition), 'kind': 'script',
                         'counter_calls': len(group), 'cost': empty_cost(), 'children': [],
                         'prompt_tokens_median': None}
                child['cost']['time_ms'] = duration
            child['in_bytes'] = sum(r.get('in_bytes', 0) for r in group)
            for record in group:
                if record.get('child'):
                    nested = walk(location / record['child'])
                    if nested is not None:
                        child['children'].append(nested)
            node['children'].append(child)
        if node['kind'] == 'script' and node['children'] and (root or elapsed is None):
            cost['time_ms'] = sum(c['cost']['time_ms'] for c in node['children'])
        elif elapsed is not None:
            cost['time_ms'] = elapsed
        else:
            cost['time_ms'] = sum(r.get('elapsed_ms', 0) for r in records
                                  if r.get('kind') in ('think', 'cmd'))
            cost['time_ms'] += sum(c['cost']['time_ms'] for c in node['children'])
        return node

    tree = walk(stack, target, elapsed_ms, root=True)

    def costs(node):
        yield node['cost']
        for child in node['children']:
            yield from costs(child)

    total = add_costs(costs(tree))
    total['time_ms'] = tree['cost']['time_ms']
    return tree, total
