# Verify every knowledge_check check turns red on a broken fixture tree and green on a clean one.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ENTRY = Path(__file__).resolve().parents[1] / '_entry'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    """.json 檔寫 JSON（字串也是 JSON 字串），其他檔寫原文。"""
    path.write_text(json.dumps(value) if path.suffix == '.json' else value, encoding='utf-8')


class KnowledgeCheckTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name) / 'proto8'
        h, kb = self.home, self.home / 'knowledge'
        write(h / 'lib' / 'packs' / 'p.json', {'tools': {'hammer': {'path': {'$env': 'AOS_HOME', '$path': '/lib/tools/hammer'}}}})
        write(h / 'lib' / 'tools' / 'hammer' / '_tooldef.json', {
            'description': 'Hit things. Details: knowledge_read aos/tools.json#/hammer.',
            'parameters': {'type': 'object', 'properties': {}}, 'errors': ['ArgumentsBad', 'NailMissing']})
        write(h / 'lib' / 'tools' / 'hammer' / 'helper.py', 'DOC = "see aos/tools.json#/hammer"\n')
        write(h / 'cmd' / 'aos-saw' / 'bin' / 'aos-saw', '#!/bin/sh\n')
        write(h / 'impls' / 'aos-drill' / 'CMakeLists.txt', 'add_executable(aos-drill_main src/main.cpp)\n')
        write(kb / '_index.json', {'aos/': {'_description': 'Start here.'}})
        write(kb / 'aos' / '_description.json', 'aos in one page.')
        write(kb / 'aos' / '_index.json', {'tools.json': {'_description': 'Tools.'},
                                          'cli/': {'_description': 'Commands.'}})
        write(kb / 'aos' / 'tools.json', {'_index': {'hammer': {'_description': 'Tool hammer.'}},
                                         'hammer': 'Use hammer. ArgumentsBad, NailMissing. See aos/cli/saw.json.'})
        write(kb / 'aos' / 'cli' / '_index.json', {'saw.json': {'_description': 'Use aos-saw to cut. aos-drill makes holes.'}})
        write(kb / 'aos' / 'cli' / 'saw.json', 'Run aos-saw. Same as {"x"}.')
        self.kb = kb

    def run_check(self, *flags):
        env = dict(os.environ, AOS_HOME=str(self.home))
        env.pop('AOS_WS', None)
        got = subprocess.run([sys.executable, str(ENTRY), '--json', *flags], stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, env=env)
        self.assertIn(got.returncode, (0, 1), got.stderr)
        report = json.loads(got.stdout)
        self.assertEqual(got.returncode, 1 if report['errors'] else 0, got.stderr)
        return report

    def codes(self, *flags):
        report = self.run_check(*flags)
        return {(p['check'], p['code'] or p['where']) for p in report['problems']}

    def test_clean_tree_is_green(self):
        report = self.run_check()
        self.assertEqual(report['errors'], 0, report['problems'])
        self.assertEqual(report['warnings'], 0, report['problems'])

    def test_refs_in_text_ref_directive_and_code(self):
        write(self.kb / 'aos' / 'cli' / 'saw.json', 'See aos/cli/gone.json and aos/tools.json#/nope.')
        write(self.home / 'templates' / 't' / 'x.py', 'P = "aos/missing.json"\n')
        write(self.kb / 'aos' / 'tools.json', {'_index': {'hammer': {'_description': 'Tool hammer.'}},
                                               'hammer': {'$ref': 'cli/none.json'}})
        report = self.run_check('--only', 'refs')
        reasons = sorted(p['reason'] for p in report['problems'])
        self.assertEqual(len(reasons), 4, reasons)
        self.assertTrue(all(p['code'] == 'RefMissing' for p in report['problems']))
        self.assertTrue(any('cli/none.json' in r for r in reasons))
        self.assertTrue(any('aos/missing.json' in r for r in reasons))

    def test_ref_follows_ref_directive(self):
        write(self.kb / 'aos' / 'tools.json', {'_index': {'hammer': {'_description': 'Tool hammer.'}},
                                               'hammer': {'$ref': 'cli/real.json'}})
        write(self.kb / 'aos' / 'cli' / 'real.json', {'k': 'v'})
        write(self.kb / 'aos' / 'cli' / '_index.json', {'saw.json': {'_description': 'Use aos-saw. aos-drill.'},
                                                       'real.json': {'_description': 'Real.'}})
        write(self.kb / 'aos' / 'cli' / 'saw.json', 'See aos/tools.json#/hammer/k. ArgumentsBad NailMissing')
        self.assertEqual(self.run_check('--only', 'refs', '--only', 'index')['errors'], 0)

    def test_skipped_folders_are_not_scanned(self):
        write(self.home / 'lib' / 'tools' / 'hammer' / 'tests' / 'fixture.json', {'p': 'aos/missing.json'})
        write(self.home / 'kernel' / 'thinking' / 'x.py', 'P = "aos/missing.json"\n')
        self.assertEqual(self.run_check('--only', 'refs')['errors'], 0)

    def test_index_missing_entry_and_orphans(self):
        write(self.kb / 'aos' / 'stray.json', 'not listed')
        write(self.kb / 'aos' / '_index.json', {'tools.json': {}, 'cli/': {}, 'gone.json': {}})
        write(self.kb / 'aos' / 'tools.json', {'_index': {'hammer': {}, 'nail': {}}, 'hammer': 'x', 'saw': 'y', '_description': 'ok'})
        got = self.codes('--only', 'index')
        self.assertEqual({c for _, c in got}, {'IndexEntryMissing', 'NodeMissing'})
        where = {p['where'] for p in self.run_check('--only', 'index')['problems']}
        self.assertEqual(where, {'aos/stray.json', 'aos/', 'aos/tools.json#/saw', 'aos/tools.json'})

    def test_index_bad(self):
        write(self.kb / 'aos' / 'cli' / '_index.json', [1, 2])
        self.assertIn(('index', 'IndexBad'), self.codes('--only', 'index'))

    def test_tool_without_details_or_with_broken_details(self):
        td = self.home / 'lib' / 'tools' / 'hammer' / '_tooldef.json'
        write(td, {'description': 'Hit things.', 'parameters': {'type': 'object'}, 'errors': []})
        self.assertEqual(self.codes('--only', 'tools'), {('tools', 'ToolNodeMissing')})
        write(td, {'description': 'Hit. Details: knowledge_read aos/tools.json#/nail.', 'parameters': {'type': 'object'}})
        self.assertEqual(self.codes('--only', 'tools'), {('tools', 'ToolNodeMissing')})
        td.unlink()
        self.assertEqual(self.codes('--only', 'tools'), {('tools', 'ToolDefMissing')})

    def test_new_pack_and_command_are_found_dynamically(self):
        write(self.home / 'lib' / 'packs' / 'q.json', {'tools': {'file': {'path': '../tools/file'}}})
        write(self.home / 'lib' / 'tools' / 'file' / '_tooldef.json', {'description': 'File.', 'parameters': {'type': 'object'}})
        write(self.home / 'cmd' / 'aos-plane' / 'bin' / 'aos-plane', '#!/bin/sh\n')
        report = self.run_check('--only', 'tools', '--only', 'cmds')
        self.assertEqual({(p['code'], p['where']) for p in report['problems']},
                         {('ToolNodeMissing', 'tool file (q.json)'), ('CmdNodeMissing', 'command aos-plane')})

    def test_command_name_must_be_whole_word(self):
        write(self.kb / 'aos' / 'cli' / '_index.json', {'saw.json': {'_description': 'Use aos-sawmill. aos-drill.'}})
        self.assertEqual(self.codes('--only', 'cmds'), {('cmds', 'CmdNodeMissing')})

    def test_impls_are_errors(self):
        write(self.kb / 'aos' / 'cli' / '_index.json', {'saw.json': {'_description': 'Use aos-saw.'}})
        report = self.run_check('--only', 'impls')
        self.assertEqual((report['errors'], report['warnings']), (1, 0))
        self.assertEqual((report['problems'][0]['code'], report['problems'][0]['where']), ('CmdNodeMissing', 'command aos-drill'))

    def test_codes_not_in_knowledge_and_bad_endings(self):
        write(self.home / 'lib' / 'tools' / 'hammer' / '_tooldef.json', {
            'description': 'Details: knowledge_read aos/tools.json#/hammer', 'parameters': {'type': 'object'},
            'errors': ['ArgumentsBad', 'NailMissing', 'HandleBroke', 'Internal']})
        report = self.run_check('--only', 'codes')
        self.assertEqual(report['errors'], 0)
        rows = sorted((p['where'], 'ending' in p['reason']) for p in report['problems'])
        self.assertEqual(rows, [('code HandleBroke', False), ('code HandleBroke', True), ('code Internal', False)])

    def test_residue(self):
        write(self.kb / 'aos' / 'cli' / 'saw.json', 'Run aos-saw.\n\n11-06 note: old. See ../../thinking/x.md. Put XXX here.')
        self.assertEqual({c for _, c in self.codes('--only', 'residue')}, {'DateNoteBad', 'ThinkingRefBad', 'PlaceholderBad'})

    def test_residue_ignores_lookalikes(self):
        write(self.kb / 'aos' / 'cli' / 'saw.json', 'Run aos-saw. Keep XXXL, the 2026-11-06 note and 11-06 notes on file; rethinking it.')
        self.assertEqual(self.run_check('--only', 'residue')['errors'], 0)

    def test_size_warnings_and_limits(self):
        write(self.kb / 'aos' / 'cli' / 'saw.json', 'Run aos-saw. ' + 'x' * 2000)
        report = self.run_check('--only', 'size')
        self.assertEqual((report['errors'], report['warnings']), (0, 1))
        report = self.run_check('--only', 'size', '--max-text-bytes', '5000', '--max-file-bytes', '1500')
        self.assertEqual([p['reason'].split(' is ')[0] for p in report['problems']], ['file'])

    def test_text_output_and_exit_codes(self):
        write(self.kb / 'aos' / 'stray.json', 'x')
        env = dict(os.environ, AOS_HOME=str(self.home))
        got = subprocess.run([sys.executable, str(ENTRY), '--only', 'index'], stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, env=env)
        self.assertEqual(got.returncode, 1)
        lines = got.stdout.splitlines()
        self.assertEqual(lines[0], 'knowledge_check: error: IndexEntryMissing aos/stray.json: not listed in its index')
        self.assertEqual(lines[-1], 'knowledge_check: error: CheckFailed 1 errors, 0 warnings')
        self.assertEqual(got.stderr.strip(), lines[-1])
        (self.kb / 'aos' / 'stray.json').unlink()
        got = subprocess.run([sys.executable, str(ENTRY), '--only', 'index'], stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, env=env)
        self.assertEqual((got.returncode, got.stdout.strip(), got.stderr), (0, 'knowledge_check: total: 0 errors, 0 warnings', ''))

    def test_bad_arguments(self):
        env = dict(os.environ, AOS_HOME=str(self.home))
        for flags, code in [(['--only', 'nope'], 'ArgumentsBad'), (['--root', '/no/such/dir'], 'KnowledgeBad'),
                            (['--home', '/no/such/dir'], 'HomeBad')]:
            got = subprocess.run([sys.executable, str(ENTRY), *flags], stdin=subprocess.DEVNULL,
                                 capture_output=True, text=True, env=env)
            self.assertEqual(got.returncode, 1, flags)
            self.assertIn('knowledge_check: error: %s ' % code, got.stderr)


if __name__ == '__main__':
    unittest.main()
