#!/usr/bin/env python3
"""驗證全部協議 schema 與正反例；需要 jsonschema。"""
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

EXAMPLES = Path(__file__).resolve().parent.parent
SCHEMAS = EXAMPLES.parent / 'schemas'


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate key: {key}')
        result[key] = value
    return result


def load(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=strict_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def schema_name(path):
    group, topic = path.parent.name, path.name.split('.')[0]
    if group in ('agent-tasks', 'kernel-tasks'):
        return topic
    if group == 'node':
        return 'node-' + topic
    if group == 'ops':
        return 'ops-' + topic
    if group == 'resources':
        return 'res-' + topic
    if group == 'daemon':
        if topic.startswith('helper_'):
            return 'daemon-helper'
        return {'config': 'daemon-config', 'state': 'daemon-state',
                'runner_report': 'daemon-runner-report',
                'launch-error': 'daemon-launch-error'}.get(topic, 'daemon-rpc')
    if group == 'work':
        return 'work-result' if topic.endswith('-response') else topic
    if group == 'messages':
        names = {'agent-say-payload': 'msg-say-payload',
                 'agent-reply-receive-payload': 'agent-reply',
                 'kernel-quota-set-payload': 'res-quota',
                 'kernel-usage-output': 'msg-usage-output',
                 'kernel-usage-result': 'msg-command-result',
                 'command-result': 'msg-command-result', 'summary': 'msg-summary',
                 'file-request': 'msg-file-rpc', 'file-error': 'msg-file-rpc',
                 'outbox': 'msg-outbox'}
        return names.get(topic, 'msg-methods')
    raise AssertionError(f'unknown example directory: {group}')


def main():
    schemas = {p.stem.removesuffix('.schema'): load(p) for p in SCHEMAS.glob('*.json')}
    validators = {}
    for name, body in schemas.items():
        Draft202012Validator.check_schema(body)
        validators[name] = Draft202012Validator(
            body, resolver=RefResolver(
                base_uri=(SCHEMAS / (name + '.schema.json')).as_uri(), referrer=body))
    counts, failures = Counter(), []
    for path in sorted(EXAMPLES.rglob('*.json')):
        validator = validators[schema_name(path)]
        errors = list(validator.iter_errors(load(path)))
        expected = path.name.endswith('.valid.json')
        assert expected or path.name.endswith('.invalid.json'), path
        if bool(errors) == expected:
            failures.append(f'{path.relative_to(EXAMPLES)}: expected valid={expected}; '
                            + '; '.join(error.message for error in errors[:2]))
        counts[path.parent.name] += 1
    if failures:
        raise AssertionError('\n'.join(failures))
    # All literal file requests must target the command named by method. Schema
    # cannot resolve inst directives, check an OS allowlist, or read stdin files.
    for path in sorted(EXAMPLES.rglob('*.valid.json')):
        value = load(path)
        result = value.get('result', {})
        if path.parent.name in ('messages', 'work') and 'attempt_id' in result:
            assert result['job_id'] == result['attempt_id'] == value['id'], path
            for stream in ('stdout', 'stderr'):
                output = result.get(stream)
                if output and output['path'].startswith('/srv/aos/shared/'):
                    matches = list(EXAMPLES.rglob(Path(output['path']).name))
                    assert len(matches) == 1, (path, output['path'])
                    assert output['bytes'] == matches[0].stat().st_size, path
        files = value.get('files', {})
        if '.aos/tasks.json' in files:
            tasks = files['.aos/tasks.json']['tasks']
            assert len(tasks) == (1 if 'config/agent.json' in files else 9), path
            seen = set()
            for task in tasks:
                assert task['id'] not in seen, path
                assert set(task.get('needs', [])) <= seen, path
                seen.add(task['id'])
                argv = task['argv']
                assert argv[argv.index('--node') + 1] == value['node_id'], path
        if 'reply_to' not in value or 'method' not in value:
            continue
        argv = value['params'].get('argv')
        if isinstance(argv, list) and all(isinstance(x, str) for x in argv):
            words = ['aos'] + value['method'].split('.')
            assert argv[:len(words)] == words, path
        stdin = value['params'].get('stdin')
        if isinstance(stdin, str):
            matches = list(EXAMPLES.rglob(Path(stdin).name))
            assert len(matches) == 1, (path, stdin)
            assert '.valid.' in matches[0].name, path
    print(f'PASS: {len(schemas)} schemas, {sum(counts.values())} examples; '
          + ', '.join(f'{k}={v}' for k, v in sorted(counts.items())))
    print('已驗字面 method/argv 與 stdin 範例連結；指示詞展開、權限及 tick 恢復仍須實作驗證。')


if __name__ == '__main__':
    main()
