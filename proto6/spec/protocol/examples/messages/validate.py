#!/usr/bin/env python3
"""驗證全部協議 schema 與正反例；需要 jsonschema。"""
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

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
                 'kernel-quota-set-payload': 'res-quota',
                 'kernel-usage-output': 'msg-usage-output',
                 'kernel-usage-result': 'msg-command-result',
                 'command-result': 'msg-command-result', 'summary': 'msg-summary',
                 'file-request': 'msg-file-rpc', 'file-error': 'msg-file-rpc',
                 'outbox': 'msg-outbox',
                 'work-cancel-payload': 'msg-cancel-payload',
                 'work-cancel-error': 'msg-file-rpc'}
        return names.get(topic, 'msg-methods')
    raise AssertionError(f'unknown example directory: {group}')


def extra_errors(path, value):
    """schema 表達不了的跨欄位關係；invalid 範例只要 schema 或這裡任一處報錯就算擋下。"""
    errors = []
    if path.parent.name == 'node' and path.name.startswith('tick-record.') and isinstance(value, dict):
        # B-633、P-213：stopped_after 是最後一項；exit 0 時每項都成功；exit 1 時有失敗或被停下。
        tasks = value.get('tasks') or []
        ok = [isinstance(t, dict) and t.get('exit') == 0 and 'signal' not in t for t in tasks]
        if 'stopped_after' in value and (not tasks or tasks[-1].get('id') != value['stopped_after']):
            errors.append('stopped_after is not the last task')
        if value.get('exit') == 0 and not all(ok):
            errors.append('exit 0 but some task failed')
        if value.get('exit') == 1 and 'stopped_after' not in value and all(ok):
            errors.append('exit 1 without failure or stop')
    return errors


def main():
    schemas = {p.stem.removesuffix('.schema'): load(p) for p in SCHEMAS.glob('*.json')}
    # schema 沒有 $id，$ref 是相對檔名（如 ops-attention.schema.json）；以檔名登記。
    registry = Registry().with_resources(
        (n + '.schema.json', Resource.from_contents(b, DRAFT202012))
        for n, b in schemas.items())
    validators = {}
    for name, body in schemas.items():
        Draft202012Validator.check_schema(body)
        validators[name] = Draft202012Validator(body, registry=registry)
    # 每個 $ref（含根入口）都要解得開；既有範例只走部分入口，壞引用會漏掉。
    def refs(node):
        if isinstance(node, dict):
            if isinstance(node.get('$ref'), str):
                yield node['$ref']
            for child in node.values():
                yield from refs(child)
        elif isinstance(node, list):
            for child in node:
                yield from refs(child)
    for name, body in schemas.items():
        resolver = registry.resolver(base_uri=name + '.schema.json')
        for ref in refs(body):
            resolver.lookup(ref)
    counts, failures = Counter(), []
    for path in sorted(EXAMPLES.rglob('*.json')):
        validator = validators[schema_name(path)]
        value = load(path)
        errors = [e.message for e in validator.iter_errors(value)] + extra_errors(path, value)
        expected = path.name.endswith('.valid.json')
        assert expected or path.name.endswith('.invalid.json'), path
        if bool(errors) == expected:
            failures.append(f'{path.relative_to(EXAMPLES)}: expected valid={expected}; '
                            + '; '.join(errors[:2]))
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
            # 第二十批：B-629 範本改成 mq-get 開頭、mq-post／summary／clean 收尾（kernel 12、agent 6）；
            # kernel、agent 範本下一輪才改（T5、T6），過渡期兩種項數都收。
            agent = 'config/agent.json' in files
            assert len(tasks) in ((2, 6) if agent else (9, 12)), path
            seen, claimed = set(), set()
            for task in tasks:
                assert task['id'] not in seen, path
                # P-202：同一 method 只能由一項任務宣告。
                assert not claimed & set(task.get('methods', [])), path
                claimed.update(task.get('methods', []))
                # 第二十批撤 needs 欄（改用 aos-needs，B-621）；舊範例還帶的只當不認得的欄位，
                # 有寫時仍只准指向前面的項，免得過渡期範例自相矛盾。
                assert set(task.get('needs', [])) <= seen, path
                seen.add(task['id'])
                argv = task['argv']
                assert '--node' not in argv, path
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
