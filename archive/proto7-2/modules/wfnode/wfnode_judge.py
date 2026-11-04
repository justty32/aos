"""依 aos node 的已知事實處理特定導入判斷；未知段落保持原文。"""
import os
import re

from wfnode_state import atomic_write


BLOCK = re.compile(r'(?m)^>[^\n]*(?:\n>[^\n]*)*\n?')
SECTIONS = re.compile(r'(?m)^## .*(?:\n(?!## )[^\n]*)*\n?')
ROUTINES = '''已抽到 [../routines.json](../routines.json)（0 列）；由 routines 包（`aos7-routines add --every`）寫，到期由 aos tick 判。

- name：唯一名稱
- every：正整數加 r/s/m/h/d
- inst：要跑的目標路徑
- last_round：上次回合
- last_time：上次 ISO 本地時間
- last_code：結束碼或 running
'''
SCHEDULE = '''已抽到 [../schedule.json](../schedule.json)（0 列）；由 routines 包（`aos7-routines add --at`）寫。

- name：唯一名稱
- at：含日期的 ISO 絕對時刻
- inst：要跑的目標路徑
- claimed：認領時間，本包寫
'''
RULES = {
    'testing.md': [
        ('## 測試分類',
         '> 〔導入判斷〕部分測試需要特殊環境（本機資產、外部服務、實機）→ 在驗證表補列，並在下方寫明離線可跑的子集（例：以標籤 `RequiresXxx` 區分，離線跑 `Category!=RequiresXxx`）。同步：`workflows/dev-env.md` 的「跨機 / 離線差異」表、`workflows/feature-dev/README.md` 的驗證步驟。',
         'block', ''),
    ],
    'dev-env.md': [
        ('## 跨機 / 離線差異',
         '> 〔導入判斷〕只有單一開發環境、沒有離線／CI 差異 → 刪掉本節與上表。同步：`workflows/testing.md` 三欄表的「誰跑」欄（全部由 agent 跑）、`WAIT_USER.md` 裡因環境而卡的條目。',
         'delete', ''),
    ],
    'schedule.md': [
        ('## 一次性時刻表（live）',
         '> 〔導入判斷〕上列只是**格式範例** → 刪掉該列，留空表等第一次登記填。同步：無，本表只被上面第 2 步掃。',
         'replace', SCHEDULE),
    ],
    'routines.md': [
        ('## 時機分區（live 清單',
         '> 〔導入判斷〕下面三段是**範例時機** → 換成自己的時機（沒有固定時機的專案就只留「間隔登記表」）。同步：無，本區只被上面第 2 步對照。',
         'delete', ''),
        ('## 間隔登記表（live）',
         '> 〔導入判斷〕第二列只是**純提醒型的格式範例** → 換成自己的項目或刪掉該列。同步：無。',
         'replace', ROUTINES),
    ],
}

def resolve(wfroot) -> list[str]:
    """完整引用段符合且整節沒有未知判斷才處理；回傳處理位置。"""
    handled = []
    removed_timing = False
    for filename, rules in RULES.items():
        path = wfroot / 'workflows' / filename
        if not path.is_file():
            continue
        original = path.read_text(encoding='utf-8')

        def section(match):
            nonlocal removed_timing
            text = match[0]
            title = text.split('\n', 1)[0]
            for heading, expected, action, body in rules:
                if not title.startswith(heading):
                    continue
                blocks = list(BLOCK.finditer(text))
                decisions = [b for b in blocks if '〔導入判斷〕' in b[0]]
                known = [b for b in decisions if b[0].strip() == expected]
                if not known or len(known) != len(decisions):
                    continue
                handled.append(f'workflows/{filename}：{title[3:]}')
                if action == 'block':
                    return BLOCK.sub(lambda b: '' if b[0].strip() == expected else b[0], text)
                if action == 'delete':
                    removed_timing |= filename == 'routines.md'
                    return ''
                return title + '\n\n' + body + '\n'
            return text

        result = SECTIONS.sub(section, original)
        if filename == 'routines.md' and removed_timing:
            # 模板流程也必須跟著資料表走，不再宣稱有固定時機 live 表。
            replacements = {
                '- **登記**：下面「時機分區」或「間隔登記表」多一列，**執行者**與**內容**兩欄非空。':
                    '- **登記**：[routines.json](../routines.json) 多一列，name、every、inst 非空。',
                '2. 固定時機（上班、下班前、會議前）→ 寫進「時機分區」；每 N 天型 → 寫進「間隔登記表」（「上次執行」先填今天，純提醒型填 `—`）。':
                    '2. 用 `aos7-routines add --every` 寫入 [routines.json](../routines.json)。',
                '2. **對照清單**：現在落在哪個時機分區、哪些間隔項距「上次執行」已超過週期。':
                    '2. 到期由 aos tick 判，對照 [routines.json](../routines.json) 的執行證據。',
            }
            result = ''.join(replacements.get(line.removesuffix('\n'),
                                             line.removesuffix('\n')) +
                             ('\n' if line.endswith('\n') else '')
                             for line in result.splitlines(keepends=True))
        if result != original:
            atomic_write(path, result)
    if removed_timing:
        for path in wfroot.rglob('*.md'):
            original = path.read_text(encoding='utf-8')
            # 只換空路徑或 routines.md 的目的地；全形括號屬於錨點文字。
            destination = os.path.relpath(wfroot / 'routines.json', path.parent)
            result = re.sub(r'\]\((?:[^\s()#]*routines\.md)?#時機分區[^\n)]*\)',
                            lambda _: '](' + destination + ')', original)
            if result != original:
                atomic_write(path, result)
    return handled
