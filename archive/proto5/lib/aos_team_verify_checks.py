"""驗收員的固定檢查器（直接讀專案檔）：結果三態與錯誤、路徑關在專案裡、file_exists、table_filled、contains 類、max_bytes、wf_residue。"""
import csv
import io
import json
import os
from pathlib import Path
import re
import sys


PASS, FAIL, ERROR = 'pass', 'fail', 'error'
WORDS = {PASS: '過', FAIL: '不過', ERROR: '檢查器壞'}
PROTO = Path(__file__).resolve().parent.parent


class CheckError(Exception):
    """檢查器沒辦法判（檢查器不在、跑不完、參數不對、done_when 寫錯）→ 結果是「檢查器壞」，不扣隊員次數。"""


class NotMet(Exception):
    """隊員交的東西不合（檔不在、在專案外、表壞了…）→ 結果是「不過」。"""


# ------------------------------------------------------------------ 路徑 ----

def inside(project, rel):
    """rel 相對 project（絕對路徑、~ 不收）；解開符號連結後要在 project 裡，否則 CheckError。回絕對路徑（不查在不在）。
    這是防手滑：檢查之後、開檔之前有人換連結擋不住（驗收員在牢外跑，這一版的信任前提見 plan.md 第一波）。"""
    if not isinstance(rel, str) or not rel or '\0' in rel:
        raise CheckError('path 要是非空字串')
    if os.path.isabs(rel) or rel.startswith('~'):
        raise CheckError('%s 要寫成相對專案資料夾的路徑' % rel)
    root = os.path.realpath(project)
    full = os.path.realpath(os.path.join(root, rel))
    if full != root and not full.startswith(root.rstrip(os.sep) + os.sep):
        raise NotMet('%s 在專案資料夾外（%s）' % (rel, root))
    return Path(full)


def read_text(project, rel):
    path = inside(project, rel)
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        raise NotMet('%s 不存在' % rel)
    except IsADirectoryError:
        raise NotMet('%s 是資料夾' % rel)
    except (OSError, UnicodeError) as e:
        raise NotMet('讀不到 %s：%s' % (rel, e))


# --------------------------------------------------------------- 檢查器 ----

def check_file_exists(project, item):
    path = inside(project, item['path'])
    if path.exists():
        return True, '%s 在' % item['path']
    return False, '%s 不在' % item['path']


def _empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return value in ([], {})


def _md_tables(text):
    """Markdown 裡的表：[(前面最近的標題, 表頭, [列…])]；列是字串陣列。"""
    tables, heading, lines = [], None, text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#'):
            heading = line.lstrip('#').strip()
        if line.startswith('|') and i + 1 < len(lines) and re.match(r'\s*\|?\s*:?-{2,}', lines[i + 1]):
            header = _cells(line)
            rows, i = [], i + 2
            while i < len(lines) and lines[i].strip().startswith('|'):
                rows.append(_cells(lines[i].strip()))
                i += 1
            tables.append((heading, header, rows))
            continue
        i += 1
    return tables


def _cells(line):
    parts = re.split(r'(?<!\\)\|', line.strip())
    if parts and parts[0].strip() == '':
        parts = parts[1:]
    if parts and parts[-1].strip() == '':
        parts = parts[:-1]
    return [p.strip() for p in parts]


def _columns(item, available):
    """要檢查哪幾欄：欄名要非空、不重複；指定的要在；最後至少一欄（0 欄不能算填滿）。"""
    available = list(available)
    if any(not isinstance(c, str) or not c.strip() for c in available):
        raise NotMet('表頭有空的欄名')
    dup = sorted({c for c in available if available.count(c) > 1})
    want = item.get('columns', item.get('column'))
    if want is None:
        if dup:
            raise NotMet('表頭有重複的欄名：%s' % '、'.join(dup))
        cols = available
    else:
        want = [want] if isinstance(want, str) else want
        if not isinstance(want, list) or not want or not all(isinstance(c, str) and c for c in want):
            raise CheckError('column／columns 要是欄名或欄名陣列')
        missing = [c for c in want if c not in available]
        if missing:
            raise NotMet('找不到欄 %s（有：%s）' % ('、'.join(missing), '、'.join(available) or '無'))
        bad = [c for c in want if c in dup]
        if bad:
            raise NotMet('欄名 %s 在表頭出現不只一次，分不出是哪一欄' % '、'.join(bad))
        cols = list(dict.fromkeys(want))
    if not cols:
        raise NotMet('表沒有欄（0 欄不能算填滿）')
    return cols


def check_table_filled(project, item):
    """wf-table/1 的 .json、.csv 或 Markdown 表（可給 heading 挑哪一張）：指定欄（沒給＝全部欄）每列都非空。"""
    rel = item['path']
    want = item.get('columns', item.get('column'))           # 條目寫錯（欄的寫法）：先驗，不看交付物
    if want is not None:
        want = [want] if isinstance(want, str) else want
        if not isinstance(want, list) or not want or not all(isinstance(c, str) and c for c in want):
            raise CheckError('column／columns 要是欄名或欄名陣列')
    if item.get('heading') is not None and not isinstance(item['heading'], str):
        raise CheckError('heading 要是字串')
    text = read_text(project, rel)
    if rel.endswith('.json'):
        try:
            data = json.loads(text)
        except ValueError as e:
            raise NotMet('%s 不是合法 JSON：%s' % (rel, e))
        if isinstance(data, dict):
            if data.get('contract') != 'wf-table/1':
                raise NotMet('%s 的 contract 要是 wf-table/1（收到 %r）' % (rel, data.get('contract')))
            rows, available = data.get('rows'), data.get('columns')
            if not isinstance(available, list):
                raise NotMet('%s 缺 columns（wf-table/1 的欄位順序）' % rel)
        else:
            rows = data
            available = list(dict.fromkeys(k for r in rows for k in r)) if isinstance(rows, list) and \
                all(isinstance(r, dict) for r in rows) else []
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise NotMet('%s 要是 wf-table/1（{"contract", "columns", "rows": [物件…]}）或物件陣列' % rel)
        cols = _columns(item, available)
        cells = [(n, c, r.get(c)) for n, r in enumerate(rows) for c in cols]
    elif rel.endswith('.csv'):
        table = list(csv.reader(io.StringIO(text)))
        if not table:
            raise NotMet('%s 是空的（連表頭都沒有）' % rel)
        header, rows = table[0], table[1:]
        cols = _columns(item, header)
        idx = {c: header.index(c) for c in cols}
        cells = [(n, c, r[idx[c]] if idx[c] < len(r) else '') for n, r in enumerate(rows) for c in cols]
    else:
        tables = _md_tables(text)
        heading = item.get('heading')
        if heading is not None:
            tables = [t for t in tables if t[0] == str(heading).lstrip('#').strip()]
        if not tables:
            raise NotMet('%s 裡找不到%s表格' % (rel, '標題「%s」底下的' % heading if heading else ''))
        _, header, rows = tables[0]
        cols = _columns(item, header)
        idx = {c: header.index(c) for c in cols}
        cells = [(n, c, r[idx[c]] if idx[c] < len(r) else '') for n, r in enumerate(rows) for c in cols]
    if not rows:
        return False, '%s 的表是空的（0 列）' % rel
    empty = [(n, c) for n, c, v in cells if _empty(v)]
    if empty:
        shown = '、'.join('第 %d 列 %s' % (n + 1, c) for n, c in empty[:5])
        return False, '%s 有 %d 格空的：%s%s' % (rel, len(empty), shown, '…' if len(empty) > 5 else '')
    return True, '%s %d 列 × %d 欄都填了' % (rel, len(rows), len(cols))


def _args(item):
    args = item.get('args') or {}
    if not isinstance(args, dict):
        raise CheckError('args 要是物件')
    return args


def check_contains(project, args):
    want = args.get('text')
    if not isinstance(want, str) or not want:
        raise CheckError('contains 要 args.text（非空字串）')      # 條目寫錯：先驗，不看交付物
    if not isinstance(args.get('path'), str) or not args['path']:
        raise CheckError('contains 要 args.path（非空字串）')
    text = read_text(project, args['path'])
    return (want in text), '%s %s「%s」' % (args['path'], '有' if want in text else '沒有', want)


def check_not_contains(project, args):
    ok, _ = check_contains(project, args)
    return (not ok), '%s %s「%s」' % (args['path'], '還有' if ok else '沒有', args['text'])


def check_last_line_contains(project, args):
    """最後一個非空行有這段字（09-25 arknights 隊加：詞條最後一行要是「詳見：…」）。"""
    want = args.get('text')
    if not isinstance(want, str) or not want:
        raise CheckError('last_line_contains 要 args.text（非空字串）')
    if not isinstance(args.get('path'), str) or not args['path']:
        raise CheckError('last_line_contains 要 args.path（非空字串）')
    lines = [line for line in read_text(project, args['path']).splitlines() if line.strip()]
    if not lines:
        raise NotMet('%s 是空的' % args['path'])
    last = lines[-1].strip()
    short = last if len(last) <= 60 else last[:60] + '…'
    return (want in last), '%s 最後一行%s「%s」（是：%s）' % (args['path'], '有' if want in last else '沒有', want, short)


def check_max_bytes(project, args):
    """path 是檔：它不超過 bytes 位元組；是資料夾：底下每個檔（往下找、不跟符號連結）都不超過。
    missing_ok＝true 時 path 不在也算過（「超了才拆的子資料夾」這種可有可無的）。09-25 arknights 隊加（證據檔 <5KB）。"""
    limit = args.get('bytes')
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise CheckError('max_bytes 要 args.bytes（正整數）')
    if not isinstance(args.get('path'), str) or not args['path']:
        raise CheckError('max_bytes 要 args.path（非空字串）')
    missing_ok = args.get('missing_ok', False)
    if not isinstance(missing_ok, bool):
        raise CheckError('max_bytes 的 args.missing_ok 要是 true／false')
    rel = args['path']
    path = inside(project, rel)
    if not path.exists():
        if missing_ok:
            return True, '%s 不在（可有可無）' % rel
        raise NotMet('%s 不存在' % rel)
    if path.is_dir():
        files = []
        for dirpath, dirnames, filenames in os.walk(path):     # os.walk 預設不跟符號連結進資料夾
            files.extend(Path(dirpath) / name for name in filenames)
    else:
        files = [path]
    over = []
    for f in sorted(files):
        if f.is_symlink():
            continue
        size = f.stat().st_size
        if size > limit:
            over.append('%s %d' % (os.path.relpath(f, os.path.realpath(project)), size))
    if over:
        return False, '%s 有 %d 個檔超過 %d 位元組：%s' % (rel, len(over), limit, '、'.join(over[:5]))
    return True, '%s 共 %d 個檔都不超過 %d 位元組' % (rel, len(files), limit)


def _wf():
    """第 3 隊 wf 工具包的 Python 介面（tools/wf/_wf.py：只跑包裡自帶的 workflows 快照）。"""
    path = str(PROTO / 'tools' / 'wf')
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        import _wf
    except ImportError as e:
        raise CheckError('wf 工具包載不到（%s/_wf.py）：%s' % (path, e))
    return _wf


def check_wf_residue(project, args):
    """專案裡所有 .md 的三種導入殘留（照 workflows IMPORT.md 的 grep）；讀不到的檔另列、不當成 0。"""
    res = _wf().residue(str(project))
    c = res['counts']
    where = '、'.join('%s:%d' % (f, n) for f, n, _ in res['hits'][:3]) + ('…' if len(res['hits']) > 3 else '')
    text = '{{ %d、〔導入判斷〕 %d、〔模板說明〕 %d%s' % (c['{{'], c['〔導入判斷〕'], c['〔模板說明〕'],
                                                  '（%s）' % where if where else '')
    if res['unreadable']:
        raise NotMet('讀不到 %d 個 .md（%s），不能當成 0；%s'
                         % (len(res['unreadable']), '、'.join(f for f, _ in res['unreadable'][:5]), text))
    return res['total'] == 0, text
