"""Verify public definition discovery, three-axis identity, references and check failures."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / '_entry'


class DefinitionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value) if not isinstance(value, str) else value)

    def definition(self, name, endpoint='terra', tool=None, memory=None):
        path = self.root / name
        self.write(path / 'interfaces.json', {'aos-agent': {'tools': 'tools.json', 'llm': 'llm.json', **({'memory': 'memory/config.json'} if memory is not None else {})}})
        self.write(path / '_metainfo.json', {'summary': 'Example worker', 'lineage': {'from': 'retired/missing'}})
        self.write(path / 'README.md', 'Example worker\n')
        self.write(path / 'system.txt', 'A prompt')
        self.write(path / 'tools.json', {'tools': tool or {}})
        self.write(path / 'llm.json', {'model': endpoint})
        if memory is not None:
            self.write(path / 'memory/config.json', {'base': memory})
        return path

    def call(self, op, **extra):
        env = os.environ.copy()
        env.pop('AOS_STACK', None)
        result = subprocess.run([str(ENTRY)], input=json.dumps({'op': op, 'root': str(self.root), **extra}), text=True, capture_output=True, env=env)
        return result, json.loads(result.stdout) if result.stdout else None

    def test_prompt_ignored_endpoint_distinct_and_non_agent_excluded(self):
        a = self.definition('category/a')
        b = self.definition('category/b')
        self.write(b / 'system.txt', 'Different prompt')
        self.definition('category/c', endpoint='luna')
        self.write(self.root / 'script/interfaces.json', {})
        self.write(self.root / 'script/_metainfo.json', {'summary': 'Script'})
        result, data = self.call('dup')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([g['members'] for g in data['groups']], [['category/a', 'category/b']])
        self.assertEqual(json.loads(data['groups'][0]['key'])['endpoint'], 'terra')

    def test_tools_use_resolved_set_ignore_names_and_env(self):
        shared = self.root / 'shared'
        shared.mkdir()
        (self.root / 'alias').symlink_to(shared, target_is_directory=True)
        self.definition('a', tool={'one': {'path': '../shared', 'env': {'X': 'a'}}})
        self.definition('b', tool={'two': {'path': '../alias', 'env': {'X': 'b'}}, 'repeat': {'path': '../shared'}})
        self.definition('c', tool={'other': {'path': '../different'}})
        _, data = self.call('dup')
        self.assertEqual(data['groups'][0]['members'], ['a', 'b'])

    def test_directive_tool_paths_kept_as_written(self):
        home = {'$env': 'AOS_HOME', '$path': '/lib/base/peek_now_time'}
        self.definition('a', tool={'clock': {'path': home}})
        self.definition('b', tool={'time': {'path': {'$path': '/lib/base/peek_now_time', '$env': 'AOS_HOME'}}})
        self.definition('c', tool={'clock': {'path': {'$env': 'AOS_HOME', '$path': '/lib/base/read'}}})
        result, data = self.call('dup')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([g['members'] for g in data['groups']], [['a', 'b']])
        result, data = self.call('refs', **{'def': 'c'})
        self.assertEqual((result.returncode, data), (0, {'refs': []}))
        self.definition('d', tool={'x': {'path': {'$path': '/x'}}})
        result, data = self.call('check')
        self.assertIn('each tool must declare a path', json.dumps(data))

    def test_memory_paths_and_literal_environment(self):
        self.definition('a', memory='../../kb')
        self.definition('b', memory='../../kb')
        self.definition('c', memory={'$env': 'AOS_WS', '$path': 'kb'})
        self.definition('d', memory={'$path': 'kb', '$env': 'AOS_WS'})
        self.definition('e', memory={'$env': 'AOS_WS', '$path': 'other'})
        _, data = self.call('dup')
        self.assertEqual(sorted(g['members'] for g in data['groups']), [['a', 'b'], ['c', 'd']])

    def test_discovery_stops_at_definition_and_skips_hidden(self):
        self.definition('category/a')
        self.definition('category/a/nested')
        self.definition('.prev/old')
        self.definition('retired/old')
        _, data = self.call('ls', match='WORKER')
        self.assertEqual([x['path'] for x in data['defs']], ['category/a', 'retired/old'])
        _, data = self.call('ls', match='CATEGORY')
        self.assertEqual(len(data['defs']), 1)
        _, data = self.call('ls', match='absent')
        self.assertEqual(data, {'defs': []})

    def test_refs_tool_and_thought_from(self):
        self.definition('target')
        self.definition('direct', tool={'x': {'path': '../target'}})
        self.definition('thought', tool={'x': {'path': '../thought_tool', 'env': {'AOS_THOUGHT_FROM': str(self.root / 'target')}}})
        self.definition('other')
        result, data = self.call('refs', **{'def': 'target'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data, {'refs': ['direct', 'thought']})

    def test_nested_tool_table_paths(self):
        self.definition('target')
        caller = self.definition('caller')
        self.write(caller / 'interfaces.json', {'aos-agent': {'tools': 'cfg/tools.json', 'llm': 'llm.json'}})
        self.write(caller / 'cfg/tools.json', {'tools': {'x': {'path': '../../target'}}})
        _, data = self.call('ls', match='caller')
        self.assertEqual(data['defs'][0]['tools'], ['target'])
        _, data = self.call('refs', **{'def': 'target'})
        self.assertEqual(data['refs'], ['caller'])

    def test_relative_thought_source_uses_workspace(self):
        self.definition('target')
        self.definition('caller', tool={'x': {'path': '../thought_tool', 'env': {'AOS_THOUGHT_FROM': 'target'}}})
        from unittest.mock import patch
        with patch.dict(os.environ, {'AOS_WS': str(self.root)}):
            _, data = self.call('refs', **{'def': 'target'})
        self.assertEqual(data['refs'], ['caller'])

    def test_check_good_does_not_require_existing_lineage(self):
        self.definition('good')
        result, data = self.call('check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data, {'problems': []})

    def test_check_missing_interfaces_json_has_json_stdout(self):
        self.write(self.root / 'bad/_metainfo.json', {'summary': 'Broken'})
        self.write(self.root / 'bad/README.md', 'Broken\n')
        result, data = self.call('check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('defs: error: DefBad', result.stderr)
        self.assertIn('interfaces.json', data['problems'][0]['reason'])

    def test_check_each_required_field(self):
        for field in ('readme', 'summary', 'tools', 'llm', 'memory', 'name'):
            with self.subTest(field=field):
                root = self.root / field
                root.mkdir()
                old = self.root
                self.root = root
                path = self.definition('Bad!' if field == 'name' else 'bad', memory='../../kb')
                if field == 'readme':
                    self.write(path / 'README.md', '\ntext')
                elif field == 'summary':
                    self.write(path / '_metainfo.json', {})
                elif field in ('tools', 'llm', 'memory'):
                    self.write(path / ('memory/config.json' if field == 'memory' else field + '.json'), 'broken')
                result, data = self.call('check')
                self.assertEqual(result.returncode, 1)
                self.assertTrue(data['problems'])
                self.root = old

    def test_metadata_only_definition_is_listed_without_brain(self):
        self.write(self.root / 'script/_metainfo.json', {'summary': 'Script'})
        result, data = self.call('ls')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data['defs'], [{'path': 'script', 'summary': 'Script', 'brain': False}])

    def test_errors_and_empty_tree(self):
        _, data = self.call('dup')
        self.assertEqual(data, {'groups': []})
        for payload, code in (({'op': 'unknown'}, 'CommandUnknown'),
                              ({'op': 'refs'}, 'ArgumentsBad'),
                              ({'op': 'ls', 'root': str(self.root / 'missing')}, 'RootMissing')):
            result = subprocess.run([str(ENTRY)], input=json.dumps({'root': str(self.root), **payload}), text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn(code, result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_default_endpoint_and_help(self):
        self.definition('a', endpoint='')
        _, data = self.call('ls')
        self.assertEqual(data['defs'][0]['endpoint'], '')
        self.definition('b', endpoint='default')
        c = self.definition('c')
        self.write(c / 'llm.json', {})
        _, groups = self.call('dup')
        self.assertEqual([g['members'] for g in groups['groups']], [['b', 'c']])
        result = subprocess.run([str(ENTRY), '--help'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--root', result.stdout)


if __name__ == '__main__':
    unittest.main()
