"""wf_fill 的本體：照事實表機械填 {{…}}、刪〔模板說明〕、（選）刪範例區塊與整列都是佔位的表格列。

不叫模型、不猜：對不上事實的佔位原樣留著，列給模型（附原因）。
對得上的規則（寫死，改了要改測試）：
- 佔位的「名字」＝{{ }} 裡去掉例子的那段（「，如…」「，例…」「例：…」「；…」「：…」之後都不算），
  表格列另外用第一格的字當第二個名字（第一格本身沒有佔位時）。
- 名字跟事實表的鍵比：一樣 → 同義詞表（ALIASES）→ 一邊包含另一邊（這層才要至少兩個字）；每一層恰好一個才算，某一層不只一個就整個停（不再拿表格第一格去猜），
  兩個以上＝對不上（列「不只一條事實像它」）。
- 第一格整格是佔位的表格列＝「範本列」（例：INDEX 的 `{{src/ 或主要產出目錄}}`）：整列都不填，
  template_rows="delete" 才整列刪掉。
- 事實值是「今天…」或 "today"：換成今天的日期（照事實表的時區；沒有就用本機）。
- examples="delete"：〔導入判斷〕說是「範例」的——上方表格裡第一格是「（範例）」的列，
  或它底下「下面 N 段」緊接著的 N 個同級小節（不夠 N 個就不動）——連同那段〔導入判斷〕一起刪。
  認不出範圍的〔導入判斷〕不動，列給模型。
"""
import datetime
import json
import os
import re

import _wf

PH = re.compile(r'\{\{(.*?)\}\}')
ONE_PH = re.compile(r'\{\{[^{}]*\}\}')
NUM = {'一': 1, '二': 2, '兩': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
BELOW = re.compile(r'下面([一二兩三四五六七八九十]|[0-9]+)段')
NOTE = '〔模板說明〕'
JUDGE = '〔導入判斷〕'
CUTS = ('，如', ',如', '，例', ',例', '例：', '例:', '；', ';', '：', ':')
DROP = re.compile(r'[\s　/／、，,：:；;「」『』…．\.\-_*`|]+')
PAREN = re.compile(r'（[^）]*）|\([^)]*\)')
# 同義詞：左邊是代表名，右邊是正規化後（去空白標點）的寫法。只收 workflows 模板真的出現過的。
ALIASES = {
    '專案名': ('專案名', '專案名稱', 'projectname', 'project'),
    '專案一句話': ('專案一句話', '一句話', '一句話描述', '專案描述', '專案簡介'),
    '驗證指令': ('驗證指令', '測試buildlint指令', '測試指令', 'build指令', 'lint指令'),
    '時區': ('時區', 'timezone', 'tz'),
    '分支慣例': ('分支慣例', '分支', 'branch'),
    '語言': ('語言', '回覆與文件語言'),
    '直接做': ('直接做不用問', '直接做'),
    '一定先問': ('一定先問', '先問'),
    '回覆風格例外': ('回覆風格', '回覆風格的例外', '回覆風格例外'),
    '導入日期': ('導入日期', '今天日期'),
}
_CANON = {v: k for k, vs in ALIASES.items() for v in vs}


class FillError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


# ------------------------------------------------------------------ 名字 ----

def norm(s, drop_paren=False):
    s = s.strip().lower()
    if drop_paren:
        s = PAREN.sub('', s)
    return DROP.sub('', s)


def label(inner):
    """{{ }} 裡的字 → 名字（去掉例子）。"""
    cut = len(inner)
    for c in CUTS:
        i = inner.find(c)
        if i != -1:
            cut = min(cut, i)
    return inner[:cut].strip()


def _canon(n):
    return _CANON.get(n)


def match(name, facts):
    """回 (事實鍵, None) 或 (None, 原因)。facts：{鍵: 值}。"""
    n = norm(name, drop_paren=True)
    if not n:
        return None, None
    keys = list(facts)
    # 兩個字的下限只給「包含」那層；完全一樣的一個字也算（astra M10）
    levels = (
        lambda k: norm(k, True) == n or norm(k) == norm(name),
        lambda k: _canon(n) is not None and _canon(norm(k, True)) == _canon(n),
        lambda k: len(norm(k, True)) >= 2 and len(n) >= 2 and (norm(k, True) in n or n in norm(k, True)),
    )
    for test in levels:
        hit = [k for k in keys if test(k)]
        if len(hit) == 1:
            return hit[0], None
        if len(hit) > 1:
            return None, 'more than one fact looks like it: %s' % ', '.join(hit)
    return None, None


# ------------------------------------------------------------------ 事實 ----

def load_facts(path, extra):
    """事實檔（JSON 物件）＋ values 疊上去 → {鍵: 字串}；不是字串的值轉成字串，物件略過（列進 skipped）。"""
    facts, skipped = {}, []
    if path is not None:
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
        except OSError as e:
            raise FillError('NotFound' if isinstance(e, FileNotFoundError) else 'ReadFailed',
                            'cannot read facts file %s: %s' % (os.path.basename(path), e.strerror or e))
        except ValueError as e:
            raise FillError('BadArguments', 'facts file is not valid JSON: %s' % e)
        if not isinstance(data, dict):
            raise FillError('BadArguments', 'facts file must be a JSON object {"fact": "value", ...}')
        facts.update(data)
    facts.update(extra or {})
    out = {}
    for k, v in facts.items():
        if isinstance(v, bool) or isinstance(v, dict) or v is None:
            skipped.append(k)
            continue
        if isinstance(v, list):
            if not all(isinstance(x, (str, int, float)) for x in v):
                skipped.append(k)
                continue
            v = '、'.join(str(x) for x in v)
        out[str(k)] = str(v)
    return out, skipped


def today_value(facts, now=None):
    tz = None
    key, _ = match('時區', facts)
    if key:
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(facts[key].split()[0].strip('（(').strip())
        except Exception:
            tz = None
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return (now.astimezone(tz) if tz else now.astimezone()).strftime('%Y-%m-%d')


def value_of(facts, key, now=None):
    v = facts[key].strip()
    if v.startswith('今天') or v.lower() == 'today':
        return today_value(facts, now)
    return v


# ------------------------------------------------------------------ 表格 ----

def cells(line):
    s = line.strip()
    if not s.startswith('|'):
        return None
    parts = s.strip('|').split('|')
    return [p.strip() for p in parts]


def is_template_row(line):
    c = cells(line)
    if not c:
        return False
    first = c[0].strip('`').strip()
    return bool(first) and ONE_PH.fullmatch(first) is not None     # 恰好一個佔位、外面沒別的字（astra M9）


def row_label(line):
    c = cells(line)
    if not c or PH.search(c[0]):
        return None
    lab = c[0].replace('*', '').strip()
    return lab or None


# ------------------------------------------------------------------ 區塊 ----

def _quote_block(lines, i):
    """lines[i] 是 '> ' 開頭：回這段引用的結束（不含）。"""
    j = i + 1
    while j < len(lines) and lines[j].lstrip().startswith('>'):
        j += 1
    return j


def _drop(lines, start, end):
    """刪 [start, end)，兩邊都是空行就多刪一個空行，不留雙空行。"""
    del lines[start:end]
    if 0 < start < len(lines) and not lines[start].strip() and not lines[start - 1].strip():
        del lines[start]


def drop_notes(lines):
    n, i = 0, 0
    while i < len(lines):
        if lines[i].lstrip().startswith('> ' + NOTE) or lines[i].lstrip().startswith('>' + NOTE):
            _drop(lines, i, _quote_block(lines, i))
            n += 1
            continue
        i += 1
    return n


def _heading_level(line):
    m = re.match(r'(#{1,6})\s', line)
    return len(m.group(1)) if m else None


def drop_examples(lines):
    """〔導入判斷〕講範例的：刪範例列或範例小節＋那段判斷。回 (刪了幾段, [(第幾行, 認不出的判斷)])。"""
    n, i = 0, 0
    while i < len(lines):
        s = lines[i].lstrip()
        if not (s.startswith('> ' + JUDGE) or s.startswith('>' + JUDGE)):
            i += 1
            continue
        end = _quote_block(lines, i)
        text = ''.join(lines[i:end])
        if '範例' not in text:
            i = end
            continue
        # 1) 上方表格的（範例）列
        k = i - 1
        while k >= 0 and not lines[k].strip():
            k -= 1
        rows = []
        while k >= 0 and lines[k].lstrip().startswith('|'):
            c = cells(lines[k])
            if c and c[0].startswith('（範例）'):
                rows.append(k)
            k -= 1
        if rows:
            _drop(lines, i, end)
            for r in sorted(rows, reverse=True):
                del lines[r]
            n += 1
            i = min(rows)
            continue
        # 2) 底下「下面 N 段」：緊接著的 N 個同級小節（小節裡更深的標題算它的）。
        #    沒寫段數、或小節不夠 N 個（中途碰到更高級標題）就不動（astra M8：不能一路刪到下一個 ##）
        k = end
        while k < len(lines) and not lines[k].strip():
            k += 1
        above = next((_heading_level(lines[h]) for h in range(i - 1, -1, -1) if _heading_level(lines[h])), None)
        sub = _heading_level(lines[k]) if k < len(lines) else None
        m = BELOW.search(text)
        want = (NUM.get(m.group(1)) or int(m.group(1))) if m else 0
        if want and sub and above and sub > above:
            stop, seen = k, 0
            while stop < len(lines):
                lv = _heading_level(lines[stop])
                if lv is not None and lv < sub:
                    break
                if lv == sub:
                    if seen == want:
                        break
                    seen += 1
                stop += 1
            if seen == want:
                _drop(lines, i, stop)
                n += 1
                continue
        i = end
    return n


# ------------------------------------------------------------------ 主體 ----

def fill_file(text, facts, used, reasons, *, notes, examples, template_rows, now=None):
    """一個檔：回 (新內容, 統計)。used：{事實鍵: [填在第幾行…]}（會加）；reasons：{佔位原文: 原因}（會加）。"""
    lines = text.split('\n')
    stat = {'filled': 0, 'notes': 0, 'examples': 0, 'rows': 0}
    if notes:
        stat['notes'] = drop_notes(lines)
    if examples:
        stat['examples'] = drop_examples(lines)
    if template_rows:
        keep = []
        for line in lines:
            if is_template_row(line):
                stat['rows'] += 1
                continue
            keep.append(line)
        lines = keep
    for idx, line in enumerate(lines):
        if '{{' not in line:
            continue
        if is_template_row(line):
            for m in PH.finditer(line):
                reasons.setdefault(m.group(0), 'template row (first cell is a placeholder); '
                                               'drop_template_rows:true deletes the whole row')
            continue
        rl = row_label(line)

        def repl(m):
            inner = m.group(1)
            why = None
            for name in (label(inner).rstrip('…').strip(), rl):
                if not name:
                    continue
                key, why2 = match(name, facts)
                if key:
                    used.setdefault(key, []).append(idx + 1)
                    stat['filled'] += 1
                    return value_of(facts, key, now)
                if why2:            # 不只一條事實像它：停，不拿第一格去猜（astra M10）
                    why = why2
                    break
            reasons.setdefault(m.group(0), why or 'no fact for it')
            return m.group(0)
        lines[idx] = PH.sub(repl, line)
    return '\n'.join(lines), stat


def scan(project_dir):
    """跟 wf_residue 同一套走法（跳過 .git、staging、backup、符號連結）：回 [(相對路徑, 絕對路徑)]。"""
    out = []
    for dp, dns, fns in os.walk(project_dir):
        dns[:] = sorted(d for d in dns if not _wf._skip_dir(d))
        for fn in sorted(fns):
            full = os.path.join(dp, fn)
            if fn.endswith('.md') and not os.path.islink(full):
                out.append((os.path.relpath(full, project_dir), full))
    return out


def fill(project_dir, facts, *, notes=True, examples=False, template_rows=False, dry_run=False,
         write=None, now=None):
    """整個專案。write(full, 內容, 相對路徑)：寫檔的函式（工具給 _common.write_atomic 包一層）。
    回 {'total': 統計, 'files': {相對路徑: 統計}, 'used': {事實鍵: ['檔:行'…]}, 'reasons': {佔位: 原因},
        'texts': {相對路徑: 新內容}（每個 .md 都有，給 leftovers 重掃）}。"""
    used, reasons, changed, texts = {}, {}, {}, {}
    total = {'filled': 0, 'notes': 0, 'examples': 0, 'rows': 0}
    for relp, full in scan(project_dir):
        with open(full, encoding='utf-8', errors='replace') as f:
            text = f.read()
        texts[relp] = text
        if '{{' not in text and NOTE not in text and JUDGE not in text:
            continue
        mine = {}
        new, st = fill_file(text, facts, mine, reasons, notes=notes, examples=examples,
                            template_rows=template_rows, now=now)
        for k, rows in mine.items():
            used.setdefault(k, []).extend('%s:%d' % (relp, n) for n in rows)
        for k in total:
            total[k] += st[k]
        if new != text:
            changed[relp] = st
            texts[relp] = new
            if not dry_run:
                write(full, new, relp)
    return {'total': total, 'files': changed, 'used': used, 'reasons': reasons, 'texts': texts}


def leftovers(texts, reasons):
    """填完的內容重掃：回 ([(相對路徑, 行, 佔位, 原因)], [(相對路徑, 行, 〔…〕那行開頭)])。"""
    left, marks = [], []
    for relp, text in sorted(texts.items()):
        for i, line in enumerate(text.split('\n'), 1):
            for m in PH.finditer(line):
                left.append((relp, i, m.group(0), reasons.get(m.group(0), 'no fact for it')))
            for mark in (JUDGE, NOTE):
                if mark in line:
                    marks.append((relp, i, ' '.join(line.strip().lstrip('>').split())[:70]))
    return left, marks
