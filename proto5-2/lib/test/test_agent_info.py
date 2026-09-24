"""新版 agent info／state 的純讀驗契約；不啟動任何行程。"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import aos_agent_info as info
from aos_agent_home import AgentError


class AgentInfoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.raw = {'_metainfo': {'_type': 'llm_agent', '_version': 1}, 'llm': {'model': 'small'}}
        self.put('info.json', self.raw)

    def put(self, name, value):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def bad(self, code, reader):
        with self.assertRaises(AgentError) as caught:
            reader(self.base)
        self.assertEqual(code, caught.exception.code)

    def test_six_shared_fields(self):
        value = info.load(self.base)
        self.assertEqual(value['system'], '')
        self.assertEqual(value['history'], [])
        self.assertEqual(value['tools_raw'], [])
        self.assertEqual(value['llm']['model'], 'small')
        self.assertEqual(value['llm']['params'], {})

    def test_meta_not_resolved(self):
        meta = {'argv': [{'$env': 'UNSET'}]}
        self.raw['tools'] = ['tools.json']
        self.put('info.json', self.raw)
        self.put('tools.json', [{'type': 'function', 'function': {'name': 't'}, '_meta': meta}])
        self.assertEqual(info.load(self.base)['tools_raw'][0]['_meta'], meta)

    def test_tick_reference_with_relative_pointer(self):
        self.raw.update(tick={'$ref': 'tick-options.json'})
        self.put('tick-options.json', {'pool': {'$ref': '', '$at': '../other'}, 'other': 'p', 'interval_ms': 0})
        self.put('info.json', self.raw)
        self.assertEqual(info.load(self.base)['tick'], {'pool': 'p', 'interval_ms': 0})

    def test_info_env(self):
        self.raw['llm']['pool'] = {'$env': 'POOL'}
        self.put('info.json', self.raw)
        self.assertEqual(info.load(self.base, {'POOL': 'x'})['llm']['pool'], 'x')

    def test_input_directive(self):
        self.put('state.json', {'input': {'$env': 'INPUT'}})
        st = info.load_state(self.base, {'INPUT': 'in/a.json'})
        self.assertEqual(st['input'], ['in/a.json'])
        self.assertEqual(st['_input_raw'], {'$env': 'INPUT'})

    def test_input_reference_array(self):
        self.put('state.json', {'input': {'$ref': '', '$at': '/paths'}, 'paths': ['a', 'b']})
        self.assertEqual(info.load_state(self.base)['input'], ['a', 'b'])

    def test_wait_single_string(self):
        self.put('state.json', {'waits': 'signal'})
        self.assertEqual(info.load_state(self.base)['waits'], ['signal'])

    def test_wait_array(self):
        self.put('state.json', {'waits': ['a', 'b']})
        self.assertEqual([x['paths'] for x in info.load_state(self.base)['_waits']], [['a'], ['b']])

    def test_wait_option_value_reference(self):
        self.put('state.json', {'p': ['a', 'b'], 'waits': {'$opt': ['consume', 'exists', 'all'],
                                                        '$val': {'$ref': '', '$at': '/p'}}})
        st = info.load_state(self.base)
        self.assertEqual(st['_waits'][0]['paths'], ['a', 'b'])
        self.assertEqual(st['_waits'][0]['options'], {'consume', 'exists', 'all'})

    def test_write_preserves_input_and_wait_shapes(self):
        raw = {'input': {'$env': 'INPUT'}, 'waits': {'$opt': 'consume', '$val': {'$env': 'SIGNAL'}},
               'unknown': {'$env': 'DO_NOT_RESOLVE'}}
        self.put('state.json', raw)
        st = info.load_state(self.base, {'INPUT': 'x', 'SIGNAL': 'go'})
        st['errors'] = 2
        info.write_state(self.base, st)
        out = json.loads((self.base / 'state.json').read_text())
        self.assertEqual(out['input'], raw['input'])
        self.assertEqual(out['waits'], [raw['waits']])
        self.assertEqual(out['unknown'], raw['unknown'])
        self.assertEqual(out['errors'], 2)
        self.assertFalse(list(self.base.glob('*.tmp')))
        self.assertNotIn('_waits', out)

    def test_valid_records(self):
        pair = {'src': str(self.base / 'x'), 'dst': str(self.base / 'x.id.done')}
        batch = {'kind': 'think', 'kernel': '/K', 'base_len': 0, 'sent': False,
                 'calls': [{'name': 'B-0', 'done': {'fail': 'x', 'count': False}, 'acked': True}]}
        self.put('state.json', {'batch': batch, 'intake': {'id': 'id', 'base_len': 0, 'files': [pair]},
                                'consuming': [pair], 'sweep': [{'kernel': '/K', 'name': 'B-0'}]})
        self.assertEqual(info.load_state(self.base)['batch'], batch)

    def test_valid_act_done(self):
        batch = {'kind': 'act', 'kernel': '/K', 'base_len': 1, 'sent': True,
                 'calls': [{'name': None, 'tool': 'x', 'tool_call_id': 'c',
                            'done': {'content': '無'}, 'acked': True}]}
        self.put('state.json', {'batch': batch})
        self.assertEqual(info.load_state(self.base)['batch'], batch)

    def test_state_bad_json(self):
        (self.base / 'state.json').write_text('{')
        self.bad('JsonSyntax', info.load_state)

    def test_state_nonobject(self):
        self.put('state.json', [])
        self.bad('NotAnObject', info.load_state)


# 每格是獨立 unittest，避免 subTest 掩蓋驗收條數；每條都驗可觀察契約。
def info_case(path, value, expected=None, error=None, omit=False):
    def test(self):
        raw = copy.deepcopy(self.raw)
        parent = raw
        for key in path[:-1]:
            parent = parent.setdefault(key, {})
        if not omit:
            parent[path[-1]] = value
        self.put('info.json', raw)
        if error:
            self.bad(error, info.load)
        else:
            result = info.load(self.base)
            for key in path:
                result = result[key]
            self.assertEqual(result, expected)
    return test


for path, default in [(('llm', 'pool'), 'llm'), (('llm', 'timeout_ms'), 125000),
                      (('tool_pool',), 'default'), (('tick', 'pool'), 'default'),
                      (('tick', 'interval_ms'), None)]:
    label = '_'.join(path)
    setattr(AgentInfoTests, 'test_default_' + label, info_case(path, None, default, omit=True))
    for i, wrong in enumerate(([None, 7, {}] if isinstance(default, str) else [None, True, -1, '10'])):
        setattr(AgentInfoTests, 'test_type_%s_%d' % (label, i),
                info_case(path, wrong, error='FieldTypeMismatch'))
for name, path, value, error in [
        ('llm_literal', ('llm',), {'$ref': 'x'}, 'FieldTypeMismatch'),
        ('llm_null', ('llm',), None, 'FieldTypeMismatch'),
        ('tick_null', ('tick',), None, 'FieldTypeMismatch'),
        ('pool_options', ('llm', 'pool'), {'$opt': 'clear'}, 'UnknownOption'),
        ('tick_options', ('tick',), {'$opt': 'clear'}, 'UnknownOption')]:
    setattr(AgentInfoTests, 'test_' + name, info_case(path, value, error=error))


def state_case(raw, code=None, key=None, expected=None):
    def test(self):
        if raw is not None:
            self.put('state.json', raw)
        if code:
            self.bad(code, info.load_state)
        else:
            self.assertEqual(info.load_state(self.base)[key], expected)
    return test


for key, expected in [('state', 'idle'), ('errors', 0), ('input', ['input.json']), ('waits', []),
                      ('batch', None), ('intake', None), ('consuming', []), ('sweep', [])]:
    setattr(AgentInfoTests, 'test_state_default_' + key, state_case(None, key=key, expected=expected))
for key, wrong in [('state', 'wait'), ('state', None), ('errors', True), ('errors', -1),
                   ('input', []), ('input', [3]), ('input', None), ('waits', None),
                   ('batch', []), ('intake', []), ('consuming', {}), ('sweep', {})]:
    label = '%s_%s' % (key, str(wrong).replace(' ', ''))
    setattr(AgentInfoTests, 'test_state_type_' + label,
            state_case({key: wrong}, 'StateInvalid' if key == 'state' else 'FieldTypeMismatch'))
for key in ('state', 'errors', 'batch', 'intake', 'consuming', 'sweep'):
    setattr(AgentInfoTests, 'test_state_literal_' + key,
            state_case({key: {'$ref': 'x.json'}}, 'FieldTypeMismatch'))
for name, value, code in [
        ('missing_opt', {'$val': 'a'}, 'UnknownDirective'),
        ('unknown_opt', {'$opt': 'any', '$val': 'a'}, 'UnknownOption'),
        ('duplicate', {'$opt': ['consume', 'consume'], '$val': 'a'}, 'UnknownOption'),
        ('unknown_in_array', [{'$opt': 'mtime', '$val': 'a'}], 'UnknownOption'),
        ('bad_value', {'$opt': 'all', '$val': []}, 'FieldTypeMismatch'),
        ('missing_value', {'$opt': 'consume'}, 'OptionConflict'),
        ('bad_option_type', {'$opt': 1, '$val': 'a'}, 'DirectiveValueTypeMismatch'),
        ('literal_list', {'$ref': 'x.json'}, 'FieldTypeMismatch')]:
    setattr(AgentInfoTests, 'test_wait_' + name, state_case({'waits': value}, code))


def record_case(field, value):
    def test(self):
        batch = {'kind': 'think', 'kernel': '/K', 'base_len': 0, 'sent': False,
                 'calls': [{'name': 'B-0', 'done': None, 'acked': False}]}
        parent = batch
        for token in field[:-1]:
            parent = parent[token]
        parent[field[-1]] = value
        self.put('state.json', {'batch': batch})
        self.bad('FieldTypeMismatch', info.load_state)
    return test


for i, (field, value) in enumerate([
        (['kind'], 'idle'), (['kernel'], 'relative'), (['base_len'], True),
        (['sent'], 1), (['calls'], []), (['calls'], {}), (['calls', 0, 'name'], 3),
        (['calls', 0, 'acked'], 0), (['calls', 0, 'done'], {'ok': 1}),
        (['calls', 0, 'done'], {'fail': 'x', 'count': 1}),
        (['calls', 0, 'done'], {'$ref': 'x'}), (['calls', 0, 'name'], '../bad')]):
    setattr(AgentInfoTests, 'test_batch_shape_%02d' % i, record_case(field, value))
for label, raw in [
        ('intake_id', {'intake': {'id': 1, 'base_len': 0, 'files': []}}),
        ('intake_length', {'intake': {'id': 'x', 'base_len': -1, 'files': []}}),
        ('intake_files', {'intake': {'id': 'x', 'base_len': 0, 'files': {}}}),
        ('consuming_paths', {'consuming': [{'src': 'relative', 'dst': '/abs'}]}),
        ('consuming_literal', {'consuming': [{'$ref': 'x'}]}),
        ('sweep_paths', {'sweep': [{'kernel': 'relative', 'name': 'n'}]}),
        ('sweep_literal', {'sweep': [{'$ref': 'x'}]}),
        ('top_literal', {'$ref': 'x'})]:
    setattr(AgentInfoTests, 'test_record_' + label, state_case(raw, 'FieldTypeMismatch'))


if __name__ == '__main__':
    unittest.main()
