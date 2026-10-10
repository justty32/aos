"""MN3：每層需求切片、條件跳層與通用 aos-tool 分段。"""
import copy
import itertools
import json
import re
import subprocess
import sys
from menucase import MenuCase, PACK, TOP, TOOLS, simple, read_json
from aos7_menu import MenuError, after, load, new_state, options, render, step
from aos7_menu_check import brief_sections
from aos7_menu_run import prompt

EXAMPLE = PACK / 'examples/aos-tool'
AUTHOR = TOP / 'packs/author/examples'


def sections(**values):
    return ''.join('=== %s ===\n%s\n' % pair for pair in values.items())


class MenuBrief(MenuCase):
    def pair(self, brief='', names=None):
        obj = simple()
        if names is not None:
            obj['layers']['one']['brief'] = names
        menu = load(obj, TOOLS)
        return menu, new_state(menu, 'test', {'part': 'second'}, brief, 'hash')

    def rejected(self, obj, field):
        with self.assertRaises(MenuError) as got:
            load(obj, TOOLS)
        self.assertEqual(got.exception.code, 2)
        self.assertIn('one', str(got.exception))
        self.assertIn(field, str(got.exception))

    def test_sections_exact_header_newline_trim_and_legacy(self):
        self.assertEqual(brief_sections('=== first ===\n\n甲\n\n=== second ===\n乙\n'),
                         {'first': '甲', 'second': '乙'})
        self.assertEqual(brief_sections('=== empty ===\n\n'), {'empty': ''})
        for text in ('', 'plain\n=== second ===\n乙', '\n=== first ===\n甲',
                     '=== too.long ===\n甲', '=== ' + 'a' * 41 + ' ===\n甲'):
            with self.subTest(text=text):
                self.assertIsNone(brief_sections(text))
        menu, state = self.pair('舊摘要', ['missing'])
        self.assertIn('需求：舊摘要', render(menu, state))

    def test_duplicate_section_names_raise_code_two(self):
        with self.assertRaises(MenuError) as got:
            brief_sections('=== same ===\n甲\n=== same ===\n乙')
        self.assertEqual(got.exception.code, 2)
        brief = self.node / 'brief'
        brief.write_text('=== same ===\n甲\n=== same ===\n乙')
        self.run_menu('--brief', brief, menu=self.fixture(simple()), rc=2)

    def test_render_selection_order_dedup_missing_and_template(self):
        text = sections(first='UNIQUE_FIRST', second='UNIQUE_SECOND', third='UNIQUE_THIRD')
        menu, state = self.pair(text, ['{part}', 'missing', 'first', '{part}'])
        saved = copy.deepcopy(state)
        rendered = render(menu, state)
        self.assertIn('需求：UNIQUE_SECOND\nUNIQUE_FIRST\n', rendered)
        self.assertEqual(rendered.count('UNIQUE_SECOND'), 1)
        self.assertNotIn('UNIQUE_THIRD', rendered)
        self.assertEqual(state, saved)
        menu['layers']['one']['brief'] = ['missing']
        self.assertNotIn('需求：', render(menu, state))
        del menu['layers']['one']['brief']
        self.assertIn('需求：UNIQUE_FIRST\nUNIQUE_SECOND\nUNIQUE_THIRD\n', render(menu, state))

    def test_static_combined_limit_with_literal_and_default_selection(self):
        text = sections(first='甲' * 750, second='乙' * 750)
        for selected in (None, ['first', 'second']):
            with self.subTest(selected=selected):
                obj = simple()
                if selected is not None:
                    obj['layers']['one']['brief'] = selected
                menu = load(obj, TOOLS)
                with self.assertRaisesRegex(MenuError, '層 one.*1501.*1500'):
                    new_state(menu, 'test', {}, text, 'hash')
                brief = self.node / 'brief'
                brief.write_text(text)
                p = self.run_menu('--brief', brief, menu=self.fixture(obj), rc=2)
                self.assertIn('層 one', p.stderr)
        self.pair(text, ['first', 'missing', 'first'])
        self.pair(sections(first='甲' * 1500), ['first'])

    def test_render_template_combined_limit_raises_code_two(self):
        menu, state = self.pair(sections(first='甲' * 750, second='乙' * 750), ['first', '{part}'])
        with self.assertRaisesRegex(MenuError, '層 one.*1501.*1500') as got:
            render(menu, state)
        self.assertEqual(got.exception.code, 2)

    def test_template_overflow_resume_and_status_are_code_two(self):
        obj = simple()
        obj['layers']['one']['brief'] = ['first']
        obj['layers']['one']['options'][0].update(next='two', set={'part': 'second'})
        obj['layers']['two'] = dict(copy.deepcopy(simple()['layers']['one']), brief=['first', '{part}'])
        menu = self.fixture(obj)
        brief = self.node / 'brief'
        brief.write_text(sections(first='甲' * 750, second='乙' * 750))
        reply = self.node / 'reply'
        reply.write_text('選：1')
        self.run_menu('--brief', brief, '--reply', reply, menu=menu, rc=2)
        self.assertEqual(self.state('test')['layer'], 'two')
        self.run_menu('--reply', reply, menu=menu, rc=2)
        self.cli('status', self.node, '--run', 'test', '--prompt', rc=2)

    def test_legacy_section_and_file_size_limits_cli(self):
        # All sections themselves fit; only the 20000-character file ceiling fails.
        oversized = ''.join('=== s%d ===\n%s\n' % (i, '甲' * 1400) for i in range(15))
        for text in ('甲' * 1501, sections(first='甲' * 1501), oversized):
            with self.subTest(length=len(text)):
                brief = self.node / 'brief'
                brief.write_text(text)
                obj = simple()
                obj['layers']['one']['brief'] = ['absent']
                with self.assertRaises(MenuError):
                    new_state(load(obj, TOOLS), 'test', {}, text, 'hash')
                self.run_menu('--brief', brief, menu=self.fixture(obj), rc=2)

    def test_option_brief_conditions_presence_nonempty_and_count(self):
        obj = simple()
        obj['layers']['one']['options'] = [
            {'text': 'always', 'next': 'end'},
            {'text': 'present', 'next': 'end', 'when': 'brief:first'},
            {'text': 'empty', 'next': 'end', 'when': 'brief:empty'},
            {'text': 'missing', 'next': 'end', 'when': 'brief:missing'}]
        menu = load(obj, TOOLS)
        for text, expected in ((sections(first='yes', empty=''), ['always', 'present']),
                               ('plain', ['always']), ('', ['always'])):
            state = new_state(menu, 'test', {}, text, 'hash')
            self.assertEqual([x['text'] for x in options(menu, state)], expected)
        obj['layers']['one']['options'] = obj['layers']['one']['options'][1:]
        menu = load(obj, TOOLS)
        with self.assertRaises(MenuError):
            options(menu, new_state(menu, 'test', {}, '', 'hash'))

    def chain(self):
        obj = simple({'max_bytes': 20})
        obj['layers']['one'].update(when='brief:first', next='two')
        obj['layers']['two'] = dict(copy.deepcopy(obj['layers']['one']), when='brief:second', next='last')
        obj['layers']['last'] = simple()['layers']['one']
        return obj

    def test_layer_start_and_consecutive_skips_do_not_call_ai(self):
        obj = self.chain()
        menu = load(obj, TOOLS)
        for text, expected in ((sections(first='yes'), 'one'), (sections(first='', second='yes'), 'two'), ('plain', 'last')):
            self.assertEqual(new_state(menu, 'test', {}, text, 'hash')['layer'], expected)
        state = new_state(menu, 'test', {}, '', 'hash')
        self.assertEqual(state['layer'], 'last')
        self.assertEqual(state['calls'], [])
        self.run_menu(menu=self.fixture(obj))
        state = self.state('test')
        self.assertEqual([x['layer'] for x in state['calls']], ['last'])
        self.assertFalse(any(x['kind'] == 'ask' and x['layer'] in ('one', 'two')
                             for x in self.logs('test')))

    def test_layer_skip_on_option_next_tool_ok_and_fail_and_write(self):
        obj = self.chain()
        obj['start'] = 'last'
        obj['layers']['last']['options'][0]['next'] = 'one'
        obj['layers']['tool'] = {'do': {'tool': 'check', 'args': {'path': ''}}, 'ok': 'one', 'fail': 'one'}
        obj['layers']['last']['options'][0]['next'] = 'one'
        menu = load(obj, TOOLS)
        state = new_state(menu, 'test', {}, '', 'hash')
        moved, _ = step(menu, state, '選：1')
        self.assertEqual(moved['layer'], 'last')
        for rc in (0, 1):
            state['layer'] = 'tool'
            moved, _ = after(menu, state, {'rc': rc})
            self.assertEqual(moved['layer'], 'last')
        state['layer'] = 'one'
        state['pending'] = {'act': {'write': 'out/reply.txt', 'text': 'ok'}, 'next': 'two'}
        moved, _ = after(menu, state, {'rc': 0})
        self.assertEqual(moved['layer'], 'last')

    def test_layer_skip_cycle_raises_code_two(self):
        obj = self.chain()
        obj['layers']['two']['next'] = 'one'
        with self.assertRaises(MenuError) as got:
            new_state(load(obj, TOOLS), 'test', {}, '', 'hash')
        self.assertEqual(got.exception.code, 2)

    def test_brief_field_type_count_and_ask_only_validation(self):
        for value in ('first', [], [1], ['x'] * 9):
            obj = simple()
            obj['layers']['one']['brief'] = value
            self.rejected(obj, 'brief')
        obj = simple()
        obj['layers']['one'] = {'do': {'tool': 'check', 'args': {'path': ''}}, 'ok': 'end', 'brief': ['first']}
        self.rejected(obj, 'brief')

    def test_layer_when_shape_and_options_validation(self):
        for value in (7, 'new:out/a', 'brief:', 'brief:bad.name'):
            obj = self.chain()
            obj['layers']['one']['when'] = value
            self.rejected(obj, 'when')
        obj = simple()
        obj['layers']['one']['when'] = 'brief:first'
        self.rejected(obj, 'when')
        obj = self.chain()
        del obj['layers']['one']['next']
        self.rejected(obj, 'when')

    def test_unknown_option_when_validation(self):
        for value in ('other:first', 'brief:', 'brief:bad.name'):
            obj = simple()
            obj['layers']['one']['options'][0]['when'] = value
            self.rejected(obj, 'when')


class MenuAosBrief(MenuCase):
    def build(self, request, rc=0):
        result = subprocess.run([sys.executable, '-B', str(EXAMPLE / 'build.py'), 'brief', str(request)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, rc, result.stdout + result.stderr)
        return result

    def test_all_requests_lossless_bounded_and_minimax_partition(self):
        for name in ('gap', 'runs', 'audit', 'mailcount'):
            with self.subTest(name=name):
                path = AUTHOR / ('aos-tool-' + name) / 'request.json'
                req = read_json(str(path))
                parsed = brief_sections(self.build(path).stdout)
                work = [parsed[k] for k in parsed if re.fullmatch('work[1-4]', k)]
                count = len(work)
                self.assertEqual(count, 1) if name == 'mailcount' else self.assertTrue(2 <= count <= 4)
                original = [line[2:] for part in work for line in part.splitlines()[1:]]
                self.assertEqual(original, req['work'])
                self.assertTrue(all(len(part) <= 1500 for part in parsed.values()))
                for names in (["head", "toc"], ["head", "tools"], ["head", "work1"]):
                    self.assertLessEqual(len('\n'.join(parsed[key] for key in names)), 1500)
                lengths = [len('\n'.join((parsed['head'], parsed['accept'], part))) for part in work]
                self.assertTrue(all(n <= 1500 for n in lengths), lengths)
                # Enumerate contiguous partitions independently: minimal K, then shortest longest part.
                candidates = []
                for k in range(1, count + 1):
                    for cuts in itertools.combinations(range(1, len(req['work'])), k - 1):
                        bounds = (0, *cuts, len(req['work']))
                        pieces = ['工作（第 %d／%d 段，共 %d 段）：\n%s' %
                                  (i + 1, k, k, '\n'.join('- ' + x for x in req['work'][bounds[i]:bounds[i+1]]))
                                  for i in range(k)]
                        sizes = [len('\n'.join((parsed['head'], parsed['accept'], part))) for part in pieces]
                        if max(sizes) <= 1500:
                            candidates.append((k, max(sizes)))
                self.assertEqual((count, max(lengths)), min(candidates))
                for item in (req['task'], req['goal'], *req['scope']['only'], *req['scope']['not'], *req['accept']):
                    self.assertIn(item, '\n'.join(parsed.values()))
                for tool in req['tools']:
                    self.assertIn('- ' + tool['tool'] + '：' + tool['use'], parsed['tools'])
                print('MN3 %s K=%d work chars=%s attached=%s' % (name, count, list(map(len, work)), lengths))

    def test_single_oversized_work_is_rejected(self):
        req = read_json(str(AUTHOR / 'aos-tool-mailcount/request.json'))
        req['work'] = ['不能改寫的超長要求' * 200]
        file = self.node / 'request.json'
        file.write_text(json.dumps(req, ensure_ascii=False))
        result = self.build(file, rc=2)
        self.assertEqual(result.stdout, '')
        self.assertIn('4 段', result.stderr)
        self.assertIn('1500', result.stderr)

    def test_gap_prompts_code_continuation_and_fixpart_second_section(self):
        path = AUTHOR / 'aos-tool-gap/request.json'
        brief = self.build(path).stdout
        parsed = brief_sections(brief)
        first, second = [parsed[key].splitlines()[1][2:] for key in ('work1', 'work2')]
        menu = load(read_json(str(EXAMPLE / 'menu.json')), read_json(str(PACK / 'tools.json')))
        state = new_state(menu, 'gap', {'name': 'gap', 'request': str(path), 'review': 'rules',
                          'file': 'packs/gap/aos7_gap.py', 'issues': 'answer wrong'}, brief, 'hash')
        directory = self.node / 'run'
        file = directory / 'out/packs/gap/aos7_gap.py'
        file.parent.mkdir(parents=True)
        file.write_text('CURRENT_PROGRAM_SENTINEL')
        state['layer'] = 'code'
        text = prompt(menu, state, directory)
        self.assertIn(first, text)
        self.assertNotIn(second, text)
        state['layer'] = 'code2'
        text = prompt(menu, state, directory)
        self.assertIn(second, text)
        self.assertNotIn(first, text)
        self.assertIn('目前的內容：\nCURRENT_PROGRAM_SENTINEL', text)
        state['layer'] = 'fixpart'
        choices = options(menu, state)
        self.assertEqual(len(choices), sum(key.startswith('work') for key in parsed))
        fixed, _ = step(menu, state, '選：2')
        self.assertEqual(fixed['layer'], 'fixcode')
        self.assertEqual(fixed['vars']['part'], 'work2')
        text = prompt(menu, fixed, directory)
        self.assertIn(second, text)
        self.assertNotIn(first, text)
        self.assertIn('CURRENT_PROGRAM_SENTINEL', text)
