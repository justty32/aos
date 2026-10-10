"""MN3 第一段修正：摘要序列化防段頭注入、多行原文與交付限制保真。"""
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
from unittest.mock import patch
from menucase import MenuCase, PACK, TOP, read_json
from aos7_menu import load, new_state
from aos7_menu_check import brief_sections, selected_brief

EXAMPLE = PACK / 'examples/aos-tool'
AUTHOR = TOP / 'packs/author/examples'


class MenuBriefBuilderFix(MenuCase):
    def build(self, req, rc=0):
        request = self.node / 'request.json'
        request.write_text(json.dumps(req, ensure_ascii=False))
        result = subprocess.run([sys.executable, '-B', str(EXAMPLE / 'build.py'),
                                 'brief', str(request)], capture_output=True,
                                text=True, timeout=30)
        self.assertEqual(result.returncode, rc, result.stdout + result.stderr)
        return result

    def request(self, name='mailcount'):
        return read_json(str(AUTHOR / ('aos-tool-' + name) / 'request.json'))

    def test_multiline_work_stays_whole_in_work_section(self):
        req = self.request()
        req['work'] = ['第一條第一行\n第一條第二行', '第二條\n\n末行必須完整保留']
        parsed = brief_sections(self.build(req).stdout)
        self.assertEqual(list(parsed), ['head', 'accept', 'tools', 'work1', 'toc'])
        for item in req['work']:
            self.assertIn(item, parsed['work1'])

    def test_header_shapes_in_all_original_text_fields_are_code_two(self):
        paths = [('work', 1), ('accept', 0), ('task',), ('goal',),
                 ('scope', 'only', 0), ('scope', 'not', 0),
                 ('tools', 0, 'tool'), ('tools', 0, 'use'), ('deliver',)]
        for path in paths:
            for header in ('=== hidden ===', '=== work1 ===', '=== 名 有空白 ==='):
                with self.subTest(path=path, header=header):
                    req = self.request()
                    target = req
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = '原文前半\n' + header + '\n不可遺漏的後半'
                    result = self.build(req, rc=2)
                    number = 2 if path == ('work', 1) else 1
                    self.assertEqual(result.stdout, '')
                    self.assertIn(f'需求第 {number} 條有一行長得像段頭（=== … ===），請改寫那一行',
                                  result.stderr)

    def test_reparsed_output_must_preserve_sections_and_work(self):
        spec = importlib.util.spec_from_file_location('_test_brief_builder', EXAMPLE / 'build.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        req = self.request()
        actual = builder._check_module.brief_sections
        def corrupted(text):
            parsed = actual(text)
            parsed['work1'] = '序列化時遺失原文'
            return parsed
        with patch.object(builder._check_module, 'brief_sections', side_effect=corrupted):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(builder.Problem) as got:
                    builder.brief(req)
        self.assertEqual(got.exception.code, 2)
        self.assertEqual(output.getvalue(), '')

    def test_max_files_and_deliver_preserved_and_all_layer_attachments_bounded(self):
        menu = load(read_json(str(EXAMPLE / 'menu.json')), read_json(str(PACK / 'tools.json')))
        for name in ('gap', 'runs', 'audit', 'mailcount'):
            with self.subTest(name=name):
                req = self.request(name)
                brief = self.build(req).stdout
                parsed = brief_sections(brief)
                self.assertIn(f'（最多 {req["scope"]["max_files"]} 個檔）', parsed['head'])
                self.assertIn('交付：' + req['deliver'], parsed['tools'])
                state = new_state(menu, name, {'name': req['name'], 'request': 'request',
                    'review': 'rules', 'part': 'work1'}, brief, 'hash')
                for layer in menu['layers'].values():
                    if 'ask' in layer:
                        self.assertLessEqual(len(selected_brief(layer, brief, state['vars'])), 1500)

    def test_optional_max_files_and_deliver_are_omitted(self):
        req = self.request()
        del req['scope']['max_files']
        del req['deliver']
        parsed = brief_sections(self.build(req).stdout)
        self.assertNotIn('最多', parsed['head'])
        self.assertNotIn('交付：', parsed['tools'])
