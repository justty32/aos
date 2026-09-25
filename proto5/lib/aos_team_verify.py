"""驗收員（spec/team/verify.md）：照任務單的 done_when 跑**固定的檢查器**，每條回 過／不過／檢查器壞。

兩種「沒過」分開（2026-09-24 使用者裁）：
- 不過（fail）＝隊員交的東西不合：檔不在、表沒填、殘留還在、lint 沒過…→ 郵差寄修正、扣一次機會；
- 檢查器壞（error）＝沒辦法判：檢查器載不到、跑不完、本身故障、done_when 寫錯（不認得的名字、缺參數、絕對路徑）
  → 整份結果 broken，不扣隊員次數，郵差寄信給人，單子停在 verifying 等人修好再 `aos-team verify ID --again`。

- 只跑這裡登記的檢查器（CHECKS）；不執行專案裡的任何檔，唯一例外是 cmd_ok：
  跑名冊 team.json 的 cmd_ok 白名單裡的一條指令，**關在牢裡**（專案唯讀掛 /work/ws、不上網、清環境），退出碼 0＝過。
- 會執行程式的檢查器（wf_lint_strict 跑快照的 bash＋git、cmd_ok）一律經 aos-jail 關牢；純讀檔的
  （file_exists、table_filled、contains、wf_residue）在牢外讀，靠 realpath 圍在專案裡（第二波 B 隊，見 verify.md〈牢〉）。
- 路徑一律相對專案資料夾（team.json 的 project），解開符號連結後在專案外＝檢查失敗。
- `judge` 條目不歸這裡（審查員判），結果裡不列。
- 郵差把它當 kernel 一次性工作提交（aos-team verify ID --rev R --attempt A --out 檔），結果寫檔、郵差下一輪收；
  人也可以直接跑 `aos-team verify t-0001` 看結果（不改任何檔）。
別隊加檢查器：在 CHECKS 加一行 '名字': '模組:函式'；函式 fn(project: Path, args: dict) → (過了沒, 一句白話)，
隊員交的東西不合丟 NotMet（＝不過），檢查器自己沒辦法判丟 CheckError（＝檢查器壞）。
"""
import argparse
import csv
import importlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from aos_team_format import TeamError, Layout, load_roster, now_iso, project_dir, write_json
import aos_team_task

PASS, FAIL, ERROR = 'pass', 'fail', 'error'
WORDS = {PASS: '過', FAIL: '不過', ERROR: '檢查器壞'}
PROTO = Path(__file__).resolve().parent.parent
JAIL_LINT = PROTO / 'tools' / 'wf' / '_jail_lint'
OUTPUT_TAIL = 600                     # cmd_ok 的輸出最後留幾個字元給修正信
KEEP_BYTES = 64 * 1024                # cmd_ok 讀輸出時牢外最多留多少位元組（邊讀邊丟前面的）

CHECKS = {
    'contains': 'aos_team_verify:check_contains',
    'not_contains': 'aos_team_verify:check_not_contains',
    'wf_residue': 'aos_team_verify:check_wf_residue',
    'wf_lint_strict': 'aos_team_verify:check_wf_lint_strict',
    'last_line_contains': 'aos_team_verify:check_last_line_contains',
    'max_bytes': 'aos_team_verify:check_max_bytes',
}


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


def jail_argv(project, prog_argv, setenv=(), mounts=None):
    """關牢的 argv：專案**唯讀**掛 /work/ws（起點）、不上網、清環境（aos-jail）。沒 bwrap＝CheckError，不退回不關牢。
    mounts：cmd_ok 白名單那條人寫的多掛資料夾（名字 → 路徑），一律唯讀掛 /work/<名>。"""
    import aos_agent_access
    if shutil.which('bwrap') is None:
        raise CheckError('這條要關在牢裡跑，這台找不到 bwrap（bubblewrap）')
    argv = [aos_agent_access.JAIL, '--mount-ro', 'ws=%s' % os.path.realpath(project), '--chdir', 'ws', '--net', 'off']
    for name, path in sorted((mounts or {}).items()):
        if not os.path.isdir(path):
            raise CheckError('cmd_ok 白名單要多掛的 %s（%s）不在或不是資料夾' % (name, path))
        argv += ['--mount-ro', '%s=%s' % (name, os.path.realpath(path))]
    for kv in setenv:
        argv += ['--setenv', kv]
    return argv + ['--', *prog_argv]


def jail_run(project, prog_argv, stdin_text, timeout, setenv=(), mounts=None):
    """關牢跑一支程式，回 CompletedProcess；逾時丟 subprocess.TimeoutExpired。"""
    return subprocess.run(jail_argv(project, prog_argv, setenv, mounts), input=stdin_text, capture_output=True, text=True,
                          timeout=timeout, errors='replace')


def run_tail(argv, timeout, keep=KEEP_BYTES):
    """跑 argv（stdin 空、stdout＋stderr 併一條），邊讀邊只留最後 keep 位元組（輸出再大牢外記憶體也不漲）。
    回 (退出碼或 None＝逾時被砍, 尾端文字)。逾時砍的是 aos-jail＝bwrap 本身，牢裡的行程跟著死（--die-with-parent）。"""
    import threading
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    buf = bytearray()

    def pump():
        for chunk in iter(lambda: proc.stdout.read(8192), b''):
            buf.extend(chunk)
            if len(buf) > keep:
                del buf[:len(buf) - keep]
    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        code = None
    reader.join(5)
    proc.stdout.close()
    return code, bytes(buf).decode('utf-8', 'replace')


def check_wf_lint_strict(project, args):
    """跑 wf 工具包快照裡的 wf-lint.sh --strict（不是專案裡那份），**關在牢裡**（它會跑 bash 與 git）：
    pass／fail；檢查器本身壞了＝檢查失敗。"""
    wf = _wf()
    try:
        r = jail_run(project, [str(JAIL_LINT)], json.dumps({'strict': True}), wf.LINT_TIMEOUT + 30)
    except subprocess.TimeoutExpired:
        raise CheckError('wf-lint 跑不完（牢裡超過 %d 秒）' % (wf.LINT_TIMEOUT + 30))
    try:
        res = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise CheckError('wf-lint 在牢裡沒回結果（退 %d）：%s' % (r.returncode, (r.stderr or r.stdout)[-300:]))
    if 'error' in res:
        raise CheckError('wf-lint 跑不完：%s' % res.get('message'))
    total = res['total_line'] or '（沒印 TOTAL）'
    if res['status'] == 'error':
        raise CheckError('wf-lint 本身故障（退 %d）：%s' % (res['exit'], total))
    first = '；前幾條：%s' % '／'.join(res['problems'][:3]) if res['problems'] else ''
    return res['status'] == 'pass', ('%s%s' % (total, first))[:600]


def check_cmd_ok(project, item, roster):
    """cmd_ok：跑專案自己的指令（例：測試），關在牢裡；退 0＝過、其他＝不過（附輸出最後一段）、逾時＝不過。
    白名單在名冊 team.json 的 cmd_ok（人寫）；單子上寫的 run 與 timeout_s 要對得上其中一條（開單時郵差驗過，
    這裡再驗一次：人事後拿掉了就不跑＝檢查器壞）。"""
    import aos_team_format
    entry = aos_team_format.cmd_allowed(roster, item)
    if entry is None:
        raise CheckError('指令 %s 不在 team.json 的 cmd_ok 白名單（或 timeout_s 超過白名單的）；人加進白名單再 --again'
                         % json.dumps(item.get('run'), ensure_ascii=False))
    timeout = item.get('timeout_s', entry['timeout_s'])
    shown = ' '.join(item['run'])
    # 先在同一種牢裡確認指令找得到、牢開得起來（這一步只跑 sh 的 command -v，不跑專案的東西）。
    # 之後只看退出碼：不去解析專案程式自己印的 stderr（它能假冒 bwrap 的錯誤訊息；astra w2b M1）
    try:
        probe = jail_run(project, ['sh', '-c', 'command -v -- "$1"', 'sh', item['run'][0]], '', 30,
                         mounts=entry.get('mounts'))
    except subprocess.TimeoutExpired:
        raise CheckError('「%s」：牢開不起來（確認指令在不在的那一步超過 30 秒）' % shown)
    if probe.returncode != 0 or not probe.stdout.strip():
        raise CheckError('「%s」在牢裡跑不起來：找不到指令 %s，或牢開不起來（退 %d）：%s'
                         % (shown, item['run'][0], probe.returncode, (probe.stderr or '').strip()[-300:]))
    code, out = run_tail(jail_argv(project, item['run'], ('PYTHONDONTWRITEBYTECODE=1',), entry.get('mounts')), timeout)
    tail = out.strip()[-OUTPUT_TAIL:]
    if code is None:
        return False, '「%s」跑超過 %d 秒，砍掉了%s' % (shown, timeout, '；最後的輸出：' + tail if tail else '')
    if code == 0:
        return True, '「%s」退 0' % shown
    return False, '「%s」退 %d：%s' % (shown, code, tail)


def checker(name):
    spec = CHECKS.get(name)
    if spec is None:
        raise CheckError('不認得的檢查器 %r（認得：%s）' % (name, '、'.join(sorted(CHECKS))))
    module, func = spec.split(':')
    try:
        return getattr(importlib.import_module(module), func)
    except (ImportError, AttributeError) as e:
        raise CheckError('檢查器 %s 載不到（%s：%s）' % (name, spec, e))


def run_item(project, item, roster=None):
    kind = item['kind']
    if kind == 'cmd_ok':
        return check_cmd_ok(project, item, roster or {})
    if kind == 'file_exists':
        return check_file_exists(project, item)
    if kind == 'table_filled':
        return check_table_filled(project, item)
    if kind == 'check':
        return checker(item['name'])(project, _args(item))
    raise CheckError('不認得的條目種類 %r' % kind)


def run_items(project, done_when, roster=None):
    """每條機械條目一筆 {i, kind, result, pass, why}；judge 不列。"""
    out = []
    for i, item in enumerate(done_when):
        if item.get('kind') == aos_team_task.JUDGE:
            continue
        try:
            ok, why = run_item(project, item, roster)
            result = PASS if ok else FAIL
        except NotMet as e:
            result, why = FAIL, str(e)
        except CheckError as e:
            result, why = ERROR, str(e)
        except Exception as e:   # 檢查器自己的 bug：算這一條檢查器壞，不讓整份驗收崩掉
            result, why = ERROR, '%s: %s' % (type(e).__name__, e)
        out.append({'i': i, 'kind': kind_label(item), 'result': result, 'pass': result == PASS, 'why': why})
    return out


def kind_label(item):
    return 'check:%s' % item['name'] if item['kind'] == 'check' else item['kind']


def verify(team_dir, tid, rev=None, attempt=None, roster=None):
    """跑一張單的機械條目，回 {task, rev, attempt, pass, broken, results, at}。只讀，不改任何檔。
    pass＝每條都過；broken＝有一條以上檢查器壞（這時 pass 一定是 false，但不算隊員沒過）。"""
    lay = Layout(team_dir)
    roster = roster or load_roster(team_dir)
    t = aos_team_task.load(lay, tid)
    project = project_dir(team_dir, roster)
    if not project.is_dir():
        raise TeamError('NotFound', '專案資料夾 %s 不在（team.json 的 project）' % project)
    results = run_items(project, t['done_when'], roster)
    return {'task': t['id'], 'rev': t['rev'] if rev is None else rev,
            'attempt': t['attempt'] if attempt is None else attempt,
            'pass': all(r['pass'] for r in results), 'broken': any(r['result'] == ERROR for r in results),
            'results': results, 'at': now_iso(roster.get('tz'))}


def render(res, ticket=None):
    ok = sum(1 for r in res['results'] if r['pass'])
    word = '過' if res['pass'] else ('檢查器壞了（不算隊員沒過）' if res.get('broken') else '不過')
    head = '%s rev%d 第 %d 次 驗收：%s（%d/%d 條過）' % (res['task'], res['rev'], res['attempt'], word, ok,
                                                  len(res['results']))
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
    p.add_argument('--again', action='store_true',
                   help='檢查器修好了：請郵差對這張單（停在 verifying 的）重交一次驗收（寄申請，不在這裡跑）')
    args = p.parse_args(argv)
    if args.again:
        return request_again(team_dir, args.task)
    res = verify(team_dir, args.task, args.rev, args.attempt)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        write_json(out, res)
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(render(res, aos_team_task.load(Layout(team_dir), args.task)))
    if res['broken']:
        sys.stderr.write('aos-team: CheckerBroken: %s 有檢查器壞了（不是隊員沒過）\n' % args.task)
        return 1
    if not res['pass']:
        sys.stderr.write('aos-team: NotPassed: %s 驗收沒過\n' % args.task)
        return 1
    return 0


def request_again(team_dir, tid):
    """人：檢查器修好了 → 往 team/outbox/human/ 放一份 reverify 申請，郵差下一輪重交驗收。"""
    from aos_team_format import HUMAN, new_id, write_new
    lay = Layout(team_dir)
    roster = load_roster(team_dir)
    t = aos_team_task.load(lay, tid)
    if t['status'] != 'verifying':
        raise TeamError('NotVerifying', '%s 現在是 %s，不是停在 verifying（只有等驗收的單能重交）' % (tid, t['status']))
    req = {'id': new_id(HUMAN), 'from': HUMAN, 'kind': 'reverify', 'at': now_iso(roster.get('tz')), 'task': tid}
    box = lay.outbox(HUMAN)
    box.mkdir(parents=True, exist_ok=True)
    write_new(box / (req['id'] + '.json'), req)
    print('已交給郵差：%s 重交驗收（rev%d 第 %d 次；不算新的一次交件）' % (tid, t['rev'], t['attempt']))
    return 0
