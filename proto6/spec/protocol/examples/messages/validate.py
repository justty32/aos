#!/usr/bin/env python3
"""從任意 cwd 重驗本篇 schema／範例／相對連結；需要 jsonschema。"""
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

EXAMPLES = Path(__file__).resolve().parent
PROTOCOL = EXAMPLES.parent.parent
SCHEMAS = PROTOCOL / 'schemas'


def strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f'duplicate key: {key}')
        value[key] = item
    return value


def load(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=strict_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def main():
    common = SCHEMAS / 'common.schema.json'
    if not common.is_file():
        raise SystemExit('缺 common.schema.json；不能完成跨篇驗證。')
    Draft202012Validator.check_schema(load(common))
    validators = {}
    for path in sorted(SCHEMAS.glob('msg-*.schema.json')):
        body = load(path)
        Draft202012Validator.check_schema(body)
        validators[path.stem.removesuffix('.schema')] = Draft202012Validator(
            body, resolver=RefResolver(base_uri=path.as_uri(), referrer=body))
    count = 0
    for path in sorted(EXAMPLES.glob('*.json')):
        topic = path.name.split('.')[0]
        name = ('msg-methods' if topic in ('agent-send', 'agent-reply', 'kernel-recheck', 'resources-set', 'resources-measure') else
                'msg-resource-result' if topic == 'resources-measured' else
                'msg-accepted' if topic == 'accepted' else
                'msg-summary' if topic == 'summary' else 'msg-file-rpc')
        value = load(path)
        valid = validators[name].is_valid(value)
        expected = path.name.endswith('.valid.json')
        if valid != expected:
            errors = [error.message for error in validators[name].iter_errors(value)]
            raise AssertionError(f'{path.name}: expected {expected}, got {valid}: {errors}')
        count += 1
    first = EXAMPLES / 'agent-send.minimal.valid.json'
    original = first.read_bytes()
    resend = bytes(original)
    conflict = load(first)
    conflict['params']['text'] += ' changed'
    assert original == resend
    assert load(first) != conflict
    assert validators['msg-methods'].is_valid(conflict)
    assert load(first)['id'] == conflict['id'] == load(EXAMPLES / 'accepted.minimal.valid.json')['id']
    destination = Path(load(first)['reply_to']) / 'responses' / (load(first)['id'] + '.json')
    assert str(destination) == '/srv/aos/a/responses/m1.json'
    links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', (PROTOCOL / 'messages.md').read_text())
    checked = 0
    for link in links:
        if '://' in link or link.startswith('#'):
            continue
        assert (PROTOCOL / link.split('#')[0]).exists(), f'broken link: {link}'
        checked += 1
    print(f'PASS: {len(validators)} schemas, {count} examples, {checked} relative links; generated replay/conflict and routing fixtures match.')
    print('使用實體 common.schema.json；不代表 OS 授權、發布原子性與 tick 故障恢復已實作。')


if __name__ == '__main__':
    main()
