#!/usr/bin/env python3
"""驗證全部協議 schema 與正反例；需要 jsonschema。"""
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from record_rules import record_errors

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
    if group == 'tick':
        # 第九批（2026-10-01）紀錄拆檔：tick-record.* 是展開後的完整紀錄，tick-record-file.* 是 record.json 本體
        return {'tasks': 'tick-tasks', 'tick-record': 'tick-record', 'inst': 'inst',
                'tick-record-file': 'tick-record#/$defs/RecordFile'}[topic]
    if group == 'daemon':
        if topic in ('ctl_request', 'ctl_reply'):     # P-121 控制模組：請求與回應分開驗
            return 'daemon-ctl#/$defs/' + ('Request' if topic == 'ctl_request' else 'Reply')
        if topic in ('mq_request', 'mq_reply'):       # P-125 訊息模組：同上
            return 'daemon-mq#/$defs/' + ('Request' if topic == 'mq_request' else 'Reply')
        return {'core-config': 'daemon-core-config',     # P-120
                'module-state': 'daemon-module-state'}[topic]   # P-123
    raise AssertionError(f'unknown example directory: {group}')


def extra_errors(path, value):
    """schema 表達不了的跨欄位關係；invalid 範例只要 schema 或這裡任一處報錯就算擋下。"""
    errors = []
    if path.parent.name == 'tick' and path.name.startswith('tick-record.'):
        errors += record_errors(value)     # 跟 tests/_tick_util.py 共用（record_rules.py）
    # P-120「頂層沒有 interval_ms 時每一項必填」已由 daemon-core-config 的 if／then 表達，不再另查。
    if path.parent.name == 'daemon' and path.name.startswith('core-config.') and isinstance(value, dict):
        # 第二十五批（P-125）：每項的 mq 只能寫 modules.mq 有的門名（掛了訊息模組時）
        doors = (value.get('modules') or {}).get('mq')
        if isinstance(doors, dict):
            for entry in (value.get('insts') or {}).values():
                subs = entry.get('mq') if isinstance(entry, dict) else None
                if isinstance(subs, list) and any(isinstance(d, str) and d not in doors for d in subs):
                    errors.append('item mq names a door not in modules.mq')
    return errors


# 第二十五批（2026-10-02）取代的訊息模組舊範例：舊裁定紀錄（notes/verdicts）還連著，檔留著、不再驗，
# 也不再是現行範例（現行看 P-125）。
SUPERSEDED = {
    'mq_reply.broadcast-none.valid.json', 'mq_reply.message-extra.invalid.json',
    'mq_reply.message-no-from-socket.invalid.json', 'mq_request.peek-from-string.invalid.json',
    'mq_request.peek-from.valid.json', 'mq_request.send-from-socket-number.invalid.json',
    'mq_request.take-from-empty.invalid.json', 'mq_request.take-from-number.invalid.json',
    'mq_request.take-from.valid.json',
}


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
        if path.parent.name == 'daemon' and path.name in SUPERSEDED:
            continue
        name = schema_name(path)
        if name not in validators:     # 「schema#/指標」：只驗那份 schema 裡的某個 $defs
            validators[name] = Draft202012Validator(
                {'$ref': name.replace('#', '.schema.json#', 1)}, registry=registry)
        validator = validators[name]
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
    print(f'PASS: {len(schemas)} schemas, {sum(counts.values())} examples; '
          + ', '.join(f'{k}={v}' for k, v in sorted(counts.items())))


if __name__ == '__main__':
    main()
