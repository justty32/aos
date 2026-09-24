"""proto5/tools/wf/wf_fill（w2a）：照事實表機械填 {{…}}、刪〔模板說明〕、（選）刪範例與範本列。

整包複製進假 agent 家、當子行程跑（跟 test_tools_wf.py 同一套）；另外直接 import _fill 測對名字的規則。
真的用快照 wf_init 導入 heartbeat，再 wf_fill，最後 wf_lint --strict 要 PASS。不叫模型。
"""
import datetime
import json
import os
import shutil
import sys
import unittest

from test_tools_wf import PACK, WfCase, slurp

FACTS = {
    "專案名": "p",
    "專案一句話": "試跑用的空專案",
    "驗證指令（測試／build／lint）": "無",
    "時區": "Asia/Taipei",
    "分支慣例": "直接在 main",
    "語言": "繁中",
    "直接做、不用問": "直接做（改文件、跑唯讀指令）",
    "一定先問": "刪檔、對外送出",
    "回覆風格的例外": "無",
    "佈局": "標準佈局（不用 non-invasive）",
    "flavor": "heartbeat",
    "skills": "不裝",
    "範例區塊（routines／schedule 的範例時機、範例列）": "一律刪掉，不要自己編新的",
    "其他頂層目錄": "沒有（INDEX 佈局表裡的佔位列刪掉）",
    "導入日期": "今天（用工具查日期，照時區）",
}

sys.path.insert(0, PACK)
import _fill  # noqa: E402
sys.path.remove(PACK)


class FillToolTests(WfCase):
    def imported(self):
        self.w('facts.json', json.dumps(FACTS, ensure_ascii=False))
        self.tool('wf_init', {'flavor': ['heartbeat']})

    def snapshot(self):
        return {rel: slurp(os.path.join(self.ws, rel), 'rb') for rel in self.files(self.ws)}

    def test_dry_run_lists_what_is_left_and_writes_nothing(self):
        self.imported()
        before = self.snapshot()
        out = self.tool('wf_fill', {'dry_run': True})
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(out.startswith('(dry run, nothing written) 16 placeholders filled'), out[:120])
        self.assertIn('removed 5 〔模板說明〕 blocks', out)
        self.assertIn('placeholders left (8)', out)
        self.assertIn('INDEX.md:9 {{src/ 或主要產出目錄}} - template row', out)
        self.assertIn('workflows/routines.md:35 {{上班時間，如 09:00}} - no fact for it', out)
        self.assertIn('markers left (3)', out)
        self.assertIn('其他頂層目錄 = 沒有', out)                 # 沒用到的事實照列，模型看得到「刪掉」
        self.assertIn('drop_examples:true', out)

    def test_full_fill_passes_strict_lint_and_done_when(self):
        self.imported()
        out = self.tool('wf_fill', {'drop_examples': True, 'drop_template_rows': True})
        self.assertIn('16 placeholders filled', out)
        self.assertIn('3 example blocks, 2 template rows', out)
        self.assertIn('nothing left; run wf_lint', out)
        self.assertIn('  專案一句話 = 試跑用的空專案 -> AGENTS.md:3, INDEX.md:3', out)   # 填在哪，模型不用再 read 確認
        self.assertTrue(self.tool('wf_residue', {}).startswith('residue total=0 '))
        self.assertTrue(self.tool('wf_lint', {}).startswith('PASS'))
        agents = slurp(self.p('AGENTS.md'))
        self.assertIn('# p — AI agent 專案備忘', agents)
        self.assertIn('p = **試跑用的空專案**', agents)
        self.assertIn('驗證綠燈（無）', agents)
        user = slurp(self.p('workflows', 'common', 'user.md'))
        self.assertIn('| 時區 | Asia/Taipei |', user)
        self.assertIn('| 分支慣例 | 直接在 main |', user)
        self.assertIn('| 語言 | 繁中 |', user)
        self.assertIn('這位使用者的例外：無', user)
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d')
        routines = slurp(self.p('workflows', 'routines.md'))
        self.assertIn('| %s |' % today, routines)
        self.assertNotIn('（範例）', routines)
        self.assertNotIn('### 每天上班', routines)
        self.assertIn('## 時機分區', routines)                   # 標題留著、底下的範例小節拿掉
        self.assertIn('## 間隔登記表', routines)
        self.assertNotIn('（範例）', slurp(self.p('workflows', 'schedule.md')))
        index = slurp(self.p('INDEX.md'))
        self.assertNotIn('{{', index)
        self.assertIn('| `workflows/` |', index)
        # 再跑一次：什麼都不動
        before = self.snapshot()
        again = self.tool('wf_fill', {'drop_examples': True, 'drop_template_rows': True})
        self.assertTrue(again.startswith('0 placeholders filled in 0 files'), again)
        self.assertEqual(self.snapshot(), before)

    def test_values_override_and_without_facts_file(self):
        self.w('a.md', '# {{專案名}}\n日期 {{導入日期，如 2026-08-29}}\n')
        out = self.tool('wf_fill', {'values': {'專案名': 'zed', '導入日期': '2026-01-02'}})
        self.assertIn('2 placeholders filled', out)
        self.assertEqual(slurp(self.p('a.md')), '# zed\n日期 2026-01-02\n')

    def test_errors(self):
        self.w('a.md', '{{x}}\n')
        self.assertEqual(self.tool('wf_fill', {}, code=1)['error'], 'NotFound')          # 沒 facts.json
        self.w('facts.json', '[1]')
        self.assertEqual(self.tool('wf_fill', {}, code=1)['error'], 'BadArguments')
        self.w('facts.json', '{bad')
        self.assertEqual(self.tool('wf_fill', {}, code=1)['error'], 'BadArguments')
        self.assertEqual(self.tool('wf_fill', {'facts': '../../x.json'}, code=1)['error'], 'OutsideRoot')
        self.assertEqual(self.tool('wf_fill', {'path': 'a.md', 'values': {'x': '1'}}, code=1)['error'],
                         'NotADirectory')
        self.assertEqual(self.tool('wf_fill', {'values': 'x'}, code=1)['error'], 'BadArguments')
        self.assertEqual(self.tool('wf_fill', {'drop_examples': 'yes', 'values': {'x': '1'}}, code=1)['error'],
                         'BadArguments')
        self.w('facts.json', '{}')
        self.assertEqual(self.tool('wf_fill', {}, code=1)['error'], 'BadArguments')      # 沒有可用的事實

    def test_busy_when_project_locked(self):
        self.w('facts.json', '{"x": "1"}')
        sys.path.insert(0, PACK)
        try:
            import _wf
        finally:
            sys.path.remove(PACK)
        fd = _wf._lock(self.ws)
        try:
            self.assertEqual(self.tool('wf_fill', {}, code=1)['error'], 'Busy')
        finally:
            os.close(fd)

    def test_import_hints_mention_wf_fill(self):
        self.assertIn('wf_fill', self.tool('wf_doc', {'path': 'IMPORT.md', 'limit': 3}).split('\n\n')[0])
        self.w('facts.json', '{}')
        self.assertIn('wf_fill', self.tool('wf_init', {'flavor': ['heartbeat']}))


class MatchRuleTests(unittest.TestCase):
    def fill(self, text, facts, **kw):
        used, reasons = {}, {}
        now = datetime.datetime(2026, 3, 1, 20, 0, tzinfo=datetime.timezone.utc)
        new, st = _fill.fill_file(text, facts, used, reasons, notes=kw.get('notes', True),
                                  examples=kw.get('examples', False), template_rows=kw.get('rows', False), now=now)
        return new, st, used, reasons

    def test_label_drops_examples(self):
        self.assertEqual(_fill.label('時區，如 Asia/Taipei'), '時區')
        self.assertEqual(_fill.label('例：Asia/Taipei'), '')
        self.assertEqual(_fill.label('一句話：這專案是什麼、產出什麼'), '一句話')
        self.assertEqual(_fill.label('一句話；有導航 index 就連過去'), '一句話')
        self.assertEqual(_fill.label('src/ 或主要產出目錄'), 'src/ 或主要產出目錄')

    def test_exact_alias_contains_and_row_label(self):
        facts = {'專案一句話': 'A', '驗證指令（測試／build／lint）': 'make', '語言': '繁中', '時區': 'UTC'}
        new, st, used, _ = self.fill('x {{一句話描述}} {{測試 / build / lint 指令}}\n'
                                     '| 語言 | {{回覆與文件語言，例：繁中}} |\n| 時區 | {{例：Asia/Taipei}} |\n', facts)
        self.assertEqual(new, 'x A make\n| 語言 | 繁中 |\n| 時區 | UTC |\n')
        self.assertEqual(st['filled'], 4)
        self.assertEqual(set(used), set(facts))

    def test_ambiguous_is_not_filled(self):
        facts = {'上班時間': '9', '下班時間': '17'}
        new, st, _, reasons = self.fill('{{時間}}\n', facts)
        self.assertEqual(new, '{{時間}}\n')
        self.assertIn('more than one fact', reasons['{{時間}}'])

    def test_template_row_never_filled_even_if_a_fact_matches(self):
        facts = {'其他頂層目錄': '沒有'}
        text = '| `{{其他頂層目錄…}}` | {{…}} |\n'
        new, st, _, reasons = self.fill(text, facts)
        self.assertEqual(new, text)
        self.assertIn('template row', reasons['{{其他頂層目錄…}}'])
        new, st, _, _ = self.fill(text, facts, rows=True)
        self.assertEqual((new, st['rows']), ('', 1))

    def test_today_uses_fact_timezone(self):
        facts = {'時區': 'Asia/Taipei', '導入日期': '今天（照時區）'}
        new, _, _, _ = self.fill('{{導入日期，如 2026-08-29}}', facts)
        self.assertEqual(new, '2026-03-02')                    # UTC 20:00 = 台北隔天 04:00
        new, _, _, _ = self.fill('{{導入日期}}', {'導入日期': 'today', '時區': 'UTC'})
        self.assertEqual(new, '2026-03-01')

    def test_notes_blocks_removed_without_double_blank(self):
        text = 'a\n\n> 〔模板說明〕說明\n> 第二行\n\nb\n'
        new, st, _, _ = self.fill(text, {'x': '1'})
        self.assertEqual((new, st['notes']), ('a\n\nb\n', 1))
        new, st, _, _ = self.fill(text, {'x': '1'}, notes=False)
        self.assertEqual(new, text)

    def test_examples_only_recognised_shapes(self):
        text = ('## 表\n\n| a | b |\n|---|---|\n| 真的 | 1 |\n| （範例）假的 | 2 |\n\n'
                '> 〔導入判斷〕上列只是**格式範例** → 刪掉該列。\n\n'
                '## 區\n\n> 〔導入判斷〕下面兩段是**範例** → 換成自己的。\n\n### 一\n- x\n\n### 二\n- y\n\n'
                '## 下一節\n\n> 〔導入判斷〕要不要保留 → 看專案。\n\n'
                '> 〔導入判斷〕這是範例但認不出範圍\n')
        new, st, _, _ = self.fill(text, {'x': '1'}, examples=True)
        self.assertEqual(st['examples'], 2)
        self.assertIn('| 真的 | 1 |', new)
        self.assertNotIn('（範例）', new)
        self.assertNotIn('### 一', new)
        self.assertIn('## 區\n\n## 下一節', new)
        self.assertIn('〔導入判斷〕要不要保留', new)            # 不是範例：不動
        self.assertIn('〔導入判斷〕這是範例但認不出範圍', new)    # 認不出範圍：不動

    def test_load_facts_non_text(self):
        facts, skipped = _fill.load_facts(None, {'a': ['x', 'y'], 'b': {'c': 1}, 'd': True, 'e': 3})
        self.assertEqual(facts, {'a': 'x、y', 'e': '3'})
        self.assertEqual(sorted(skipped), ['b', 'd'])


if __name__ == '__main__':
    unittest.main()
