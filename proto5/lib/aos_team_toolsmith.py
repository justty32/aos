"""T-toolsmith（第三波 W3-1，catalog E 節；spec/team/toolsmith.md）：成員寫一支工具草稿，郵差在牢裡測，人批了才裝。

- 模型端 tool_draft 工具：{name, description, parameters, code, lang: "py", cases?} → 自己 outbox 的
  tools-staging/<名>/ 放一份給自己看，同時寄一份 kind: tool_draft 申請（整份草稿就在申請裡）。
- 郵差端 on_tool_draft：驗格式 → 用**申請裡的內容**（不是 staging，那裡模型改得到）生一個工具包到
  team/tool-drafts/d-NNNN/<名>/（只有郵差寫；記每個檔的 sha256）→ `aos-agent tools test <包> --json`
  （A 隊的，關在牢裡、每次執行有逾時；整個再包一層總逾時）→
  過了＝開一題「[工具] …」問人；沒過＝退一封 FAILED 給寫的人，附沒過的那幾條，改了再交一次（同名）。
- 人端 aos-team tool approve q-NNNN：只裝最新一版、核對 sha256 → `aos-agent tools add <包> --target <寫的人的家>`
  → 回覆寫的人。不要就 aos-team answer q-NNNN 不要。
- 工具的外殼（`<名>` 程式）是固定的：照 parameters 驗參數（錯＝BadArguments）、叫 draft.py 的 main(args, root)、
  例外一律 PythonError、回傳不是字串就 json.dumps。模型只寫 main 的本體。
不叫模型。沒有 bwrap 就不測（不在主機上直接跑模型寫的程式）。
"""
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import aos_team_ask
from aos_team_format import HUMAN, Layout, TeamError, bad, json_files, load_roster, next_number, now_iso, \
    read_json, write_json

DRAFT_TYPE = 'aos_team_tool_draft'
FIELDS = ('name', 'description', 'parameters', 'code', 'lang', 'cases')
NAME = re.compile(r'[a-z][a-z0-9_]{0,39}\Z')
TYPES = ('string', 'integer', 'number', 'boolean', 'array', 'object')
PROP_KEYS = ('type', 'description', 'enum', 'items', 'minimum', 'maximum')
MAX_CODE, MAX_DESC, MAX_PROPS, MAX_CASES = 20000, 600, 8, 5
TOOL_TIMEOUT_MS = 5000          # 草稿工具每次執行的逾時（寫進工具檔 _timeout_ms；tools test 照它砍）
TEST_TIMEOUT_S = 90             # 整個 tools test 的總逾時（再保險一層，郵差不會卡更久）
REPORT_CHARS = 1500             # 退信裡附的測試結果最多幾個字
PREFIX = '[工具]'
CLI_AGENT = Path(__file__).resolve().parent.parent / 'cli' / 'aos-agent'
BASE_COMMON = Path(__file__).resolve().parent.parent / 'tools' / 'base' / '_common.py'
MARKER = '.toolsmith.json'      # 包裡記「這是 tool_draft 生的、哪一版」；重裝同名時才准 --force


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise TeamError('Usage', '%s\n%s' % (message, self.format_usage().strip()))


def folder(lay):
    return lay.team / 'tool-drafts'


# ------------------------------------------------------------------ 驗 ----

def _bad(where, msg):
    bad(where, msg, 'BadDraft')


def check_parameters(params, where='tool_draft.parameters'):
    if not isinstance(params, dict) or params.get('type') != 'object':
        _bad(where, '要是 {"type": "object", "properties": {…}, "required": [...]}')
    extra = sorted(set(params) - {'type', 'properties', 'required'})
    if extra:
        _bad(where, '不認得的欄位 %s（可用：type、properties、required）' % '、'.join(extra))
    props = params.get('properties', {})
    if not isinstance(props, dict) or len(props) > MAX_PROPS:
        _bad(where + '.properties', '要是物件，最多 %d 個參數' % MAX_PROPS)
    for k, p in props.items():
        w = '%s.properties.%s' % (where, k)
        if not re.match(r'[A-Za-z_][A-Za-z0-9_]{0,39}\Z', k):
            _bad(w, '參數名只能用英數與底線')
        if not isinstance(p, dict) or p.get('type') not in TYPES:
            _bad(w, 'type 要是 %s 之一' % '／'.join(TYPES))
        more = sorted(set(p) - set(PROP_KEYS))
        if more:
            _bad(w, '不認得的欄位 %s（可用：%s）' % ('、'.join(more), '、'.join(PROP_KEYS)))
        if 'enum' in p and (not isinstance(p['enum'], list) or not p['enum']):
            _bad(w + '.enum', '要是非空陣列')
    req = params.get('required', [])
    if not isinstance(req, list) or any(r not in props for r in req):
        _bad(where + '.required', '要是 properties 裡的參數名陣列')
    return params


def check_code(code, where='tool_draft.code'):
    if not isinstance(code, str) or not code.strip():
        _bad(where, '要是 Python 原始碼字串')
    if len(code) > MAX_CODE:
        _bad(where, '太長（上限 %d 字）' % MAX_CODE)
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        _bad(where, '語法錯（第 %s 行）：%s' % (e.lineno, e.msg))
    mains = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main']
    if not mains or len(mains[0].args.args) != 2:
        _bad(where, '要有頂層的 def main(args, root)：args＝驗過的參數（dict），root＝工作根目錄（牢裡的 /work/ws）')
    return code


def check_cases(cases, props, where='tool_draft.cases'):
    # 至少一條 expect "ok" 的例子：tools test 自動生的正例只看「照契約回話」，程式每次都丟例外也算過
    # （回 PythonError 是合法的錯誤回話），沒有真的例子就測不出它會不會做事。
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        _bad(where, '要是 1～%d 條的陣列，至少一條 expect "ok"（真的叫一次、看輸出）' % MAX_CASES)
    if not any(isinstance(c, dict) and c.get('expect') == 'ok' for c in cases):
        _bad(where, '至少要一條 expect "ok" 的例子（最好帶 contains 對輸出）')
    for i, c in enumerate(cases):
        w = '%s[%d]' % (where, i)
        if not isinstance(c, dict) or not isinstance(c.get('args'), dict) or not isinstance(c.get('expect'), str):
            _bad(w, '要是 {"args": {…}, "expect": "ok" 或錯誤代號, "contains"?: "…", "files"?: {路徑: 內容}}')
        more = sorted(set(c) - {'args', 'expect', 'contains', 'files', 'name'})
        if more:
            _bad(w, '不認得的欄位 %s' % '、'.join(more))
        files = c.get('files', {})
        if not isinstance(files, dict) or not all(isinstance(v, str) for v in files.values()):
            _bad(w + '.files', '要是 {相對路徑: 內容字串}')
        for rel in files:
            if not rel or rel.startswith(('/', '~')) or '..' in rel.split('/'):
                _bad(w + '.files', '路徑要相對工作根目錄、不含 ..：%r' % rel)
    return cases


def check_body(req):
    extra = sorted(set(req) - set(FIELDS) - {'id', 'from', 'kind', 'at'})
    if extra:
        _bad('tool_draft', '不認得的欄位 %s（可用：%s）' % ('、'.join(extra), '、'.join(FIELDS)))
    name = req.get('name')
    if not isinstance(name, str) or not NAME.match(name):
        _bad('tool_draft.name', '名字 %r 只能用小寫英數與底線、英文字母開頭、最長 40' % (name,))
    desc = req.get('description')
    if not isinstance(desc, str) or not desc.strip() or len(desc) > MAX_DESC:
        _bad('tool_draft.description', '要是 1～%d 字的一句話（給模型看，英文、越短越好）' % MAX_DESC)
    if req.get('lang', 'py') != 'py':
        _bad('tool_draft.lang', '這版只收 "py"')
    params = check_parameters(req.get('parameters'))
    check_code(req.get('code'))
    check_cases(req.get('cases'), params.get('properties', {}))
    return req


# ------------------------------------------------------------ 生工具包 ----

SHELL = r'''#!/usr/bin/env python3
"""{name}：成員用 tool_draft 寫的工具（外殼是固定的，aos_team_toolsmith 生；本體在 draft.py 的 main(args, root)）。"""
import json
import sys
sys.dont_write_bytecode = True
from _common import ToolError, fail, run  # noqa: E402

PARAMS = {params}
KINDS = {{'string': str, 'integer': int, 'number': (int, float), 'boolean': bool, 'array': list, 'object': dict}}


def check(args):
    props = PARAMS.get('properties', {{}})
    extra = sorted(set(args) - set(props))
    if extra:
        fail('BadArguments', 'unknown argument(s): %s (allowed: %s)' % (', '.join(extra), ', '.join(props)))
    for k in PARAMS.get('required', []):
        if k not in args or args[k] is None:
            fail('BadArguments', 'missing required argument "%s"' % k)
    for k, v in args.items():
        p = props[k]
        if v is None:
            continue
        want = KINDS[p['type']]
        if not isinstance(v, want) or (isinstance(v, bool) and p['type'] != 'boolean'):
            fail('BadArguments', 'argument "%s" must be %s' % (k, p['type']))
        if 'enum' in p and v not in p['enum']:
            fail('BadArguments', 'argument "%s" must be one of %s' % (k, json.dumps(p['enum'])))


def main(args, root):
    check(args)
    try:
        import draft
        out = draft.main(args, root)
    except ToolError:
        raise
    except BaseException as e:  # noqa: B902  模型寫的程式出什麼錯都照約定回 JSON，不噴 Traceback
        fail('PythonError', '%s: %s' % (type(e).__name__, e))
    if isinstance(out, str):
        return out
    try:
        return json.dumps(out, ensure_ascii=False)
    except (TypeError, ValueError, RecursionError) as e:
        fail('ResultNotJSON', 'main() returned %s, not text or JSON: %s' % (type(out).__name__, e))


if __name__ == '__main__':
    sys.exit(run(main))
'''


def package_files(req):
    """{相對路徑: (bytes, 可執行?)}。"""
    name = req['name']
    params = {'type': 'object', 'properties': req['parameters'].get('properties', {}),
              'required': req['parameters'].get('required', [])}
    tool = [{'type': 'function',
             'function': {'name': name, 'description': req['description'].strip(), 'parameters': params},
             '_meta': {'argv': ['tools/%s/%s' % (name, name)]}, '_timeout_ms': TOOL_TIMEOUT_MS}]
    cases = [dict({'tool': name}, **c) for c in req['cases']]
    dump = lambda v: (json.dumps(v, ensure_ascii=False, indent=2) + '\n').encode('utf-8')   # noqa: E731
    files = {name + '.json': (dump(tool), False),
             name: (SHELL.format(name=name, params=repr(params)).encode('utf-8'), True),
             'draft.py': (req['code'].encode('utf-8'), False),
             '_common.py': (BASE_COMMON.read_bytes(), False),
             'config.json': (dump({'root': 'workspace'}), False)}
    files['cases.json'] = (dump(cases), False)
    return files


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(lay, did, req):
    """team/tool-drafts/<did>/<名>/：先寫暫存資料夾、整包好了才 rename。回 (包資料夾, {檔: sha256})。"""
    d = folder(lay) / did
    pkg = d / req['name']
    files = package_files(req)
    sums = {rel: sha(data) for rel, (data, _) in files.items()}
    if pkg.is_dir():
        return pkg, sums
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / ('.%s.tmp' % req['name'])
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    for rel, (data, exe) in files.items():
        (tmp / rel).write_bytes(data)
        os.chmod(tmp / rel, 0o755 if exe else 0o644)
    os.rename(tmp, pkg)
    return pkg, sums


def verify_sums(pkg, sums):
    """核對包裡的檔跟記下的 sha256 一樣、沒多沒少、都是一般檔。回不對的清單。"""
    wrong = []
    names = set()
    for p in pkg.iterdir():
        names.add(p.name)
        if p.is_symlink() or not p.is_file():
            wrong.append('%s 不是一般檔' % p.name)
        elif p.name in sums and sha(p.read_bytes()) != sums[p.name]:
            wrong.append('%s 內容變了' % p.name)
    for extra in sorted(names - set(sums)):
        if extra not in ('__pycache__',):
            wrong.append('多了 %s' % extra)
    for miss in sorted(set(sums) - names):
        wrong.append('少了 %s' % miss)
    return wrong


def jail_ok():
    import aos_agent_tools_dev
    return aos_agent_tools_dev.jail_ready()


def run_test(pkg):
    """在牢裡跑 aos-agent tools test <包> --json。回 {'passed', 'total', 'failed', 'rows', 'note'}。"""
    ok, why = jail_ok()
    if not ok:
        raise TeamError('NoJail', '郵差這台機器關不了牢（%s）：模型寫的程式不在主機上直接跑，沒測；請人裝好 bwrap' % why)
    try:
        r = subprocess.run([sys.executable, str(CLI_AGENT), 'tools', 'test', str(pkg), '--json'],
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=TEST_TIMEOUT_S,
                           start_new_session=True, env=dict(os.environ, AOS_TOOLS_REQUIRE_JAIL='1'))
    except subprocess.TimeoutExpired:
        return {'passed': False, 'total': 0, 'failed': 0, 'rows': [],
                'note': '整個測試超過 %d 秒被砍（多半是程式卡住）' % TEST_TIMEOUT_S}
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    try:
        res = json.loads(lines[-1])
        if not isinstance(res, dict) or res.get('_type') != 'aos_agent_tools_test':
            raise ValueError('not a test report')
    except (IndexError, ValueError):
        if 'NoJail' in r.stdout + r.stderr:
            raise TeamError('NoJail', 'tools test 第二次探測關不了牢，拒跑（沒在主機上跑模型寫的程式）；請人檢查 bwrap')
        tail = (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ['（沒輸出）'])[-1]
        return {'passed': False, 'total': 0, 'failed': 0, 'rows': [], 'note': 'tools test 沒跑完：%s' % tail[:300]}
    if not res.get('jail'):
        raise TeamError('NoJail', 'tools test 沒關牢（%s），結果不算' % res.get('jail_note'))
    rows = [{'case': c['case'], 'pass': c['pass'], 'expect': c['expect'], 'got': c['got']}
            for c in res.get('cases', [])]
    return {'passed': res.get('failed') == 0 and bool(rows), 'total': res.get('total', 0),
            'failed': res.get('failed', 0), 'rows': rows, 'tokens': [t['tokens'] for t in res.get('tools', [])],
            'note': None}


def report(test):
    lines = ['%d 條，%d 條沒過' % (test['total'], test['failed'])]
    if test.get('note'):
        lines.append(test['note'])
    for r in test['rows']:
        if not r['pass']:
            lines.append('FAIL %s：期待 %s；得到 %s' % (r['case'], r['expect'], r['got']))
    text = '\n'.join(lines)
    return text if len(text) <= REPORT_CHARS else text[:REPORT_CHARS] + '…'


# ------------------------------------------------------------ 郵差端 ----

def records(lay):
    out = []
    for d in sorted(folder(lay).glob('d-*')) if folder(lay).is_dir() else []:
        p = d / 'draft.json'
        if p.is_file():
            try:
                out.append(read_json(p))
            except TeamError:
                continue
    return out


def latest(lay, member, name):
    mine = [r for r in records(lay) if r['from'] == member and r['name'] == name]
    return max(mine, key=lambda r: r['id']) if mine else None


def on_tool_draft(lay, roster, req):
    """kind=tool_draft（郵差叫）。冪等：同一份申請回同一份動作（測試只跑一次，結果記在 draft.json）。"""
    for rec in records(lay):
        if rec.get('request') == req['id']:
            return copy.deepcopy(rec.get('effects', []))
    check_body(req)
    member = req['from']
    top = folder(lay)
    top.mkdir(parents=True, exist_ok=True)
    did = next_number_dir(top, 'd-')
    pkg, sums = build(lay, did, req)
    test = run_test(pkg)
    now = now_iso(roster.get('tz'))
    rec = {'_metainfo': {'_type': DRAFT_TYPE, '_version': 1}, 'id': did, 'request': req['id'], 'from': member,
           'name': req['name'], 'description': req['description'].strip(), 'at': now, 'sha256': sums,
           'test': {k: test[k] for k in ('passed', 'total', 'failed', 'note')}, 'q': None, 'effects': []}
    for old in records(lay):                      # 同一個人同名的舊草稿還在等人批：題目收掉（只裝最新一版）
        if old['from'] == member and old['name'] == req['name'] and old.get('q'):
            try:
                q = aos_team_ask.load(lay, old['q'])
            except TeamError:
                continue
            if q['status'] == 'open':
                q.update(status='cancelled', answer='（有新版 %s，這版不裝）' % did, answered_at=now)
                write_json(lay.question(q['id']), q, indent=2)
    if test['passed']:
        qid = next_number(lay.wait_user, 'q-')
        rel = 'team/tool-drafts/%s/%s/draft.py' % (did, req['name'])
        ask = {'id': req['id'] + '.q', 'from': member, 'kind': 'ask', 'at': now, 'reply_to': None,
               'options': ['批准', '不要'], 'tag': 'tool',
               'question': '%s 寫了一支工具 %s：%s。牢裡測試 %d 條全過。程式在 %s（先看過）。'
                           '要裝給 %s 就跑 aos-team tool approve %s；不要就 aos-team answer %s 不要'
                           % (member, req['name'], req['description'].strip(), test['total'], rel, member,
                              qid, qid)}
        rec['effects'] = aos_team_ask.on_ask(lay, roster, ask)
        rec['q'] = next(x['id'] for x in aos_team_ask.all_questions(lay) if x.get('request') == ask['id'])
    else:
        rec['effects'] = [{'do': 'letter', 'to': member, 'status': 'FAILED', 'reply_to': req['id'], 'rev': None,
                           'text': 'tool_draft %s（%s）牢裡測試沒過：%s\n改好再用 tool_draft 交一次（同名）。'
                                   % (req['name'], did, report(test))}]
    write_json(pkg.parent / 'draft.json', rec, indent=2)
    return copy.deepcopy(rec['effects'])


def next_number_dir(top, prefix):
    n = 0
    for p in top.iterdir():
        m = re.match(re.escape(prefix) + r'([0-9]+)\Z', p.name)
        if m:
            n = max(n, int(m.group(1)))
    return '%s%04d' % (prefix, n + 1)


# ------------------------------------------------------------------ 人端 ----

def find(lay, ref):
    for rec in records(lay):
        if ref in (rec['id'], rec.get('q')):
            return rec
    raise TeamError('NotFound', '沒有工具草稿 %s（用 d-NNNN 或它的題號 q-NNNN；aos-team tool ls 看）' % ref)


def state(lay, rec):
    if not rec['test']['passed']:
        return 'failed', None
    try:
        q = aos_team_ask.load(lay, rec['q'])
    except TeamError:
        return 'cancelled', None
    if q['status'] == 'open':
        return 'pending', q
    if q['status'] == 'answered':
        import aos_team_spawn
        return ('approved' if aos_team_spawn._approves(q.get('answer')) else 'denied'), q
    return 'cancelled', q


def approve(team_dir, ref):
    import aos_agent_tools
    import aos_team_spawn
    from aos_agent_home import AgentError
    lay = Layout(team_dir)
    roster = load_roster(team_dir)
    rec = find(lay, ref)
    st, q = state(lay, rec)
    if st == 'failed':
        raise TeamError('NotPassed', '%s 測試沒過，不能裝' % rec['id'])
    if st in ('denied', 'cancelled'):
        raise TeamError('Closed', '%s 已經%s（%s）' % (rec['q'], '被你拒絕' if st == 'denied' else '取消',
                                                   (q or {}).get('answer')))
    new = latest(lay, rec['from'], rec['name'])
    if new['id'] != rec['id']:
        raise TeamError('Superseded', '%s 不是最新一版（最新是 %s）；只裝最新的' % (rec['id'], new['id']))
    if rec['from'] not in roster['members']:
        raise TeamError('NotFound', '%s 不在名冊裡了' % rec['from'])
    pkg = folder(lay) / rec['id'] / rec['name']
    wrong = verify_sums(pkg, rec['sha256'])
    if wrong:
        raise TeamError('Tampered', '%s 跟測試時不一樣：%s；不裝' % (pkg, '、'.join(wrong)))
    home = lay.member(rec['from'])
    installed = home / 'tools' / rec['name']
    force = (installed / MARKER).is_file()        # 只有 tool_draft 裝過的同名包能蓋，別的同名包一律不動
    staged = folder(lay) / rec['id'] / ('.install-%s' % rec['name'])
    shutil.rmtree(staged, ignore_errors=True)
    staged.mkdir()
    dest = staged / rec['name']
    shutil.copytree(pkg, dest, symlinks=True)
    write_json(dest / MARKER, {'draft': rec['id'], 'q': rec['q'], 'sha256': rec['sha256']}, indent=2)
    try:
        aos_agent_tools.add(str(home), str(dest), force=force)
    except AgentError as e:
        raise TeamError(e.code, 'aos-agent tools add 失敗：%s' % e.msg)
    finally:
        shutil.rmtree(staged, ignore_errors=True)
    text = '批准：工具 %s（%s）已經裝進你的工具表，下一輪起可以直接叫 %s' % (rec['name'], rec['id'], rec['name'])
    print(aos_team_spawn.notify(lay, roster, rec, q, text))
    return 0


def describe(lay, rec):
    st, _ = state(lay, rec)
    words = {'failed': '測試沒過', 'pending': '等你批', 'approved': '你答了批准、還沒裝（aos-team tool approve %s）' % rec['q'],
             'denied': '你不要', 'cancelled': '收掉了（有新版或題目不見）'}
    new = latest(lay, rec['from'], rec['name'])
    word = '已裝' if _installed(lay, rec) else words[st]
    return '%s  %s  %s 的 %s  測試 %d/%d  %s%s' % (rec['id'], rec.get('q') or '-', rec['from'], rec['name'],
                                               rec['test']['total'] - rec['test']['failed'], rec['test']['total'],
                                               word, '' if new['id'] == rec['id'] else '（舊版）')


def _installed(lay, rec):
    mark = lay.member(rec['from']) / 'tools' / rec['name'] / MARKER
    try:
        return read_json(mark).get('draft') == rec['id']
    except TeamError:
        return False


def cmd_tool(team_dir, argv):
    ap = Parser(prog='aos-team tool', description='tool ls：成員寫的工具草稿與測試結果；'
                'tool approve q-NNNN：批准（核對、aos-agent tools add 到寫的人的家、回覆它）')
    sub = ap.add_subparsers(dest='op', required=True)
    ls = sub.add_parser('ls')
    ls.add_argument('--json', action='store_true')
    ok = sub.add_parser('approve')
    ok.add_argument('ref', help='q-NNNN 或 d-NNNN')
    args = ap.parse_args(argv)
    lay = Layout(team_dir)
    load_roster(team_dir)
    if args.op == 'approve':
        return approve(team_dir, args.ref)
    rows = records(lay)
    if args.json:
        print(json.dumps([dict(r, state=state(lay, r)[0]) for r in rows], ensure_ascii=False, indent=2))
    elif not rows:
        print('沒有工具草稿')
    else:
        for r in rows:
            print(describe(lay, r))
    return 0
