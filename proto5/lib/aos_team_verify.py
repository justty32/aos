"""驗收員（spec/team/verify.md）：照任務單的 done_when 跑**固定的檢查器**，每條回 過／不過／檢查失敗。

- 只跑這裡登記的檢查器（CHECKS）；不執行專案裡的任何檔、沒有「跑任意指令」這種條目。
- 路徑一律相對專案資料夾（team.json 的 project），解開符號連結後在專案外＝檢查失敗。
- `judge` 條目不歸這裡（審查員判），結果裡不列。
- 郵差把它當 kernel 一次性工作提交（aos-team verify ID --rev R --attempt A --out 檔），結果寫檔、郵差下一輪收；
  人也可以直接跑 `aos-team verify t-0001` 看結果（不改任何檔）。
別隊加檢查器：在 CHECKS 加一行 '名字': '模組:函式'；函式 fn(project: Path, args: dict) → (過了沒, 一句白話)，
讀不到檔這種「沒辦法判」的丟 CheckError。
"""
import argparse
import csv
import importlib
import io
import json
import os
from pathlib import Path
import re
import sys

from aos_team_format import TeamError, Layout, load_roster, now_iso, project_dir, write_json
import aos_team_task

PASS, FAIL, ERROR = 'pass', 'fail', 'error'
WORDS = {PASS: '過', FAIL: '不過', ERROR: '檢查失敗'}
PROTO = Path(__file__).resolve().parent.parent

CHECKS = {
    'contains': 'aos_team_verify:check_contains',
    'not_contains': 'aos_team_verify:check_not_contains',
    'wf_residue': 'aos_team_verify:check_wf_residue',
    'wf_lint_strict': 'aos_team_verify:check_wf_lint_strict',
}


class CheckError(Exception):
    """沒辦法判（讀不到檔、參數不對、檢查器不在）→ 結果是「檢查失敗」。"""


# ------------------------------------------------------------------ 路徑 ----

def inside(project, rel):
    """rel 相對 project；解開符號連結後要在 project 裡，否則 CheckError。回絕對路徑（不查在不在）。"""
    if not isinstance(rel, str) or not rel or '\0' in rel:
        raise CheckError('path 要是非空字串')
    root = os.path.realpath(project)
    full = os.path.realpath(os.path.join(root, os.path.expanduser(rel)))
    if full != root and not full.startswith(root.rstrip(os.sep) + os.sep):
        raise CheckError('%s 在專案資料夾外（%s）' % (rel, root))
    return Path(full)


def read_text(project, rel):
    path = inside(project, rel)
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        raise CheckError('%s 不存在' % rel)
    except IsADirectoryError:
        raise CheckError('%s 是資料夾' % rel)
    except (OSError, UnicodeError) as e:
        raise CheckError('讀不到 %s：%s' % (rel, e))


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
    want = item.get('columns', item.get('column'))
    if want is None:
        return list(available)
    want = [want] if isinstance(want, str) else want
    if not isinstance(want, list) or not want or not all(isinstance(c, str) for c in want):
        raise CheckError('column／columns 要是欄名或欄名陣列')
    missing = [c for c in want if c not in available]
    if missing:
        raise CheckError('找不到欄 %s（有：%s）' % ('、'.join(missing), '、'.join(available) or '無'))
    return want


def check_table_filled(project, item):
    """wf-table/1 的 .json、.csv 或 Markdown 表（可給 heading 挑哪一張）：指定欄（沒給＝全部欄）每列都非空。"""
    rel = item['path']
    text = read_text(project, rel)
    if rel.endswith('.json'):
        try:
            data = json.loads(text)
        except ValueError as e:
            raise CheckError('%s 不是合法 JSON：%s' % (rel, e))
        rows = data.get('rows') if isinstance(data, dict) else data
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise CheckError('%s 要是 wf-table/1（{"rows": [物件…]}）或物件陣列' % rel)
        available = data.get('columns') if isinstance(data, dict) and isinstance(data.get('columns'), list) \
            else list(dict.fromkeys(k for r in rows for k in r))
        cols = _columns(item, available)
        cells = [(n, c, r.get(c)) for n, r in enumerate(rows) for c in cols]
    elif rel.endswith('.csv'):
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        cols = _columns(item, reader.fieldnames or [])
        cells = [(n, c, r.get(c)) for n, r in enumerate(rows) for c in cols]
    else:
        tables = _md_tables(text)
        heading = item.get('heading')
        if heading is not None:
            tables = [t for t in tables if t[0] == str(heading).lstrip('#').strip()]
        if not tables:
            raise CheckError('%s 裡找不到%s表格' % (rel, '標題「%s」底下的' % heading if heading else ''))
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
    text = read_text(project, args.get('path'))
    want = args.get('text')
    if not isinstance(want, str) or not want:
        raise CheckError('contains 要 args.text（非空字串）')
    return (want in text), '%s %s「%s」' % (args['path'], '有' if want in text else '沒有', want)


def check_not_contains(project, args):
    ok, _ = check_contains(project, args)
    return (not ok), '%s %s「%s」' % (args['path'], '還有' if ok else '沒有', args['text'])


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
        raise CheckError('讀不到 %d 個 .md（%s），不能當成 0；%s'
                         % (len(res['unreadable']), '、'.join(f for f, _ in res['unreadable'][:5]), text))
    return res['total'] == 0, text


def check_wf_lint_strict(project, args):
    """跑 wf 工具包快照裡的 wf-lint.sh --strict（不是專案裡那份）：pass／fail；檢查器本身壞了＝檢查失敗。"""
    wf = _wf()
    try:
        res = wf.lint(str(project), strict=True)
    except wf.WfError as e:
        raise CheckError('wf-lint 跑不完：%s' % e.message)
    total = res['total_line'] or '（沒印 TOTAL）'
    if res['status'] == 'error':
        raise CheckError('wf-lint 本身故障（退 %d）：%s' % (res['exit'], total))
    first = '；前幾條：%s' % '／'.join(res['problems'][:3]) if res['problems'] else ''
    return res['status'] == 'pass', ('%s%s' % (total, first))[:600]


def checker(name):
    spec = CHECKS.get(name)
    if spec is None:
        raise CheckError('不認得的檢查器 %r（認得：%s）' % (name, '、'.join(sorted(CHECKS))))
    module, func = spec.split(':')
    try:
        return getattr(importlib.import_module(module), func)
    except (ImportError, AttributeError) as e:
        raise CheckError('檢查器 %s 載不到（%s：%s）' % (name, spec, e))


def run_item(project, item):
    kind = item['kind']
    if kind == 'file_exists':
        return check_file_exists(project, item)
    if kind == 'table_filled':
        return check_table_filled(project, item)
    if kind == 'check':
        return checker(item['name'])(project, _args(item))
    raise CheckError('不認得的條目種類 %r' % kind)


def run_items(project, done_when):
    """每條機械條目一筆 {i, kind, result, pass, why}；judge 不列。"""
    out = []
    for i, item in enumerate(done_when):
        if item.get('kind') == aos_team_task.JUDGE:
            continue
        try:
            ok, why = run_item(project, item)
            result = PASS if ok else FAIL
        except CheckError as e:
            result, why = ERROR, str(e)
        except Exception as e:   # 檢查器自己的 bug 也只算這一條檢查失敗，不讓整份驗收崩掉
            result, why = ERROR, '%s: %s' % (type(e).__name__, e)
        out.append({'i': i, 'kind': kind_label(item), 'result': result, 'pass': result == PASS, 'why': why})
    return out


def kind_label(item):
    return 'check:%s' % item['name'] if item['kind'] == 'check' else item['kind']


def verify(team_dir, tid, rev=None, attempt=None, roster=None):
    """跑一張單的機械條目，回 {task, rev, attempt, pass, results, at}。只讀，不改任何檔。"""
    lay = Layout(team_dir)
    roster = roster or load_roster(team_dir)
    t = aos_team_task.load(lay, tid)
    project = project_dir(team_dir, roster)
    if not project.is_dir():
        raise TeamError('NotFound', '專案資料夾 %s 不在（team.json 的 project）' % project)
    results = run_items(project, t['done_when'])
    return {'task': t['id'], 'rev': t['rev'] if rev is None else rev,
            'attempt': t['attempt'] if attempt is None else attempt,
            'pass': all(r['pass'] for r in results), 'results': results, 'at': now_iso(roster.get('tz'))}


def render(res, ticket=None):
    ok = sum(1 for r in res['results'] if r['pass'])
    head = '%s rev%d 第 %d 次 驗收：%s（%d/%d 條過）' % (res['task'], res['rev'], res['attempt'],
                                                  '過' if res['pass'] else '不過', ok, len(res['results']))
    lines = [head]
    for r in res['results']:
        lines.append('  %-4s %d. %s：%s' % (WORDS[r['result']], r['i'], r['kind'], r['why']))
    if ticket is not None:
        for i, it in enumerate(ticket['done_when']):
            if it['kind'] == aos_team_task.JUDGE:
                lines.append('  略過 %d. （審查員判）%s' % (i, it['text']))
    return '\n'.join(lines)


def cmd_verify(team_dir, argv):
    p = argparse.ArgumentParser(prog='aos-team verify', description='對一張單跑固定檢查器（只讀）；全過退 0，沒過退 1')
    p.add_argument('task', help='任務單號，例 t-0001')
    p.add_argument('--rev', type=int, help='（郵差用）這次驗收是哪個 rev')
    p.add_argument('--attempt', type=int, help='（郵差用）第幾次交件')
    p.add_argument('--json', action='store_true', help='印一行 JSON')
    p.add_argument('--out', help='（郵差用）結果另寫進這個檔（暫存檔＋rename）')
    args = p.parse_args(argv)
    res = verify(team_dir, args.task, args.rev, args.attempt)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        write_json(out, res)
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(render(res, aos_team_task.load(Layout(team_dir), args.task)))
    if not res['pass']:
        sys.stderr.write('aos-team: NotPassed: %s 驗收沒過\n' % args.task)
        return 1
    return 0
