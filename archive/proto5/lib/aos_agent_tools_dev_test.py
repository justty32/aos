"""`tools test` 的案例與判定：自動生案例（正例／型別錯／缺參數）、讀 cases.json、判過不過、整套跑與印表（入口 `test` 留在 aos_agent_tools_dev：測試換掉那裡的 jail_ready／Runner）。"""
import json
import os
from pathlib import Path
import sys

from aos_agent_home import AgentError

from aos_agent_tools_dev_pack import BASE_COMMON
from aos_agent_tools_dev_run import _tokens


TOKEN_LIMIT = 300                                        # axes.md 資源軸：工具描述 < 300 token＝5 分
TAIL = 200                                               # FAIL 時「得到什麼」最多印幾個字


def error_code(out):
    """最後一行（非空）是 {"ok": false, "error": 代號, …} 就回代號，否則 None。"""
    lines = [l for l in out.splitlines() if l.strip()]
    if not lines:
        return None
    try:
        obj = json.loads(lines[-1])
    except ValueError:
        return None
    if isinstance(obj, dict) and obj.get('ok') is False and isinstance(obj.get('error'), str):
        return obj['error']
    return None


def _cut(text):
    text = ' '.join(text.split())
    return text if len(text) <= TAIL else text[:TAIL] + '…'


def got(res):
    if res.spawn_error:
        return res.spawn_error
    if res.timed_out:
        return '逾時被砍（%d 毫秒）%s' % (res.ms, '；' + res.stuck if res.stuck else '')
    lines = [l for l in res.out.splitlines() if l.strip()]
    last = lines[-1] if lines else '（stdout 空的）'
    text = '退 %s，最後一行：%s' % (res.code, _cut(last))
    if res.code not in (0, 1) or (res.code == 1 and error_code(res.out) is None):
        err = [l for l in res.err.splitlines() if l.strip()]
        if err:
            text += '；stderr 最後一行：%s' % _cut(err[-1])
    if res.dropped:
        text += '（輸出太多，前面丟了 %d 位元組）' % res.dropped
    if res.stuck:
        text += '；' + res.stuck
    return text


def judge(res, expect, contains=None):
    """expect：'contract'（正例：照契約回話就算過）、'ok'（退 0）或錯誤代號。回 (過?, 期待的白話)。"""
    want = {'contract': '照契約回話（退 0，或退 1 且最後一行 JSON 錯誤、代號不是 InternalError／BadArguments）',
            'ok': '成功（退 0）'}.get(expect, '錯誤 %s（退 1，最後一行 JSON）' % expect)
    if contains:
        want += '，輸出含 %r' % contains
    if res.spawn_error or res.timed_out or 'Traceback (most recent call last)' in res.out:
        return False, want
    code = error_code(res.out)
    if expect == 'contract':
        ok = res.code == 0 or (res.code == 1 and code is not None and code not in ('InternalError', 'BadArguments'))
    elif expect == 'ok':
        ok = res.code == 0
    else:
        ok = res.code == 1 and code == expect
    if ok and contains and contains not in res.out:
        ok = False
    return ok, want


def sample(prop):
    """照 JSON Schema 給一個合法的樣本值；不認得的型別回 (False, None)。"""
    if not isinstance(prop, dict):
        return False, None
    if isinstance(prop.get('enum'), list) and prop['enum']:
        return True, prop['enum'][0]
    kind = prop.get('type')
    if isinstance(kind, list):
        kind = next((k for k in kind if k != 'null'), None)
    if kind == 'string':
        return True, 'x'
    if kind == 'integer':
        lo, hi = prop.get('minimum'), prop.get('maximum')
        if isinstance(lo, (int, float)) and not isinstance(lo, bool):
            return True, int(-(-lo // 1))
        return True, 1 if not isinstance(hi, (int, float)) or hi >= 1 else int(hi // 1)
    if kind == 'number':
        lo, hi = prop.get('minimum'), prop.get('maximum')
        if isinstance(lo, (int, float)) and not isinstance(lo, bool) and lo > 1.5:
            return True, lo
        if isinstance(hi, (int, float)) and not isinstance(hi, bool) and hi < 1.5:
            return True, hi
        return True, 1.5
    if kind == 'boolean':
        return True, True
    if kind == 'array':
        return True, []
    if kind == 'object':
        return True, {}
    return False, None


WRONG = {'string': 123, 'integer': 'x', 'number': 'x', 'boolean': 'x', 'array': 'x', 'object': 'x'}


def auto_cases(tool):
    """從 parameters 生案例：[(案例名, arguments 的 JSON 字串, 期待)]。"""
    params = tool['function'].get('parameters') or {}
    props = params.get('properties') if isinstance(params.get('properties'), dict) else {}
    required = [r for r in params.get('required') or [] if isinstance(r, str)]
    base, strings = {}, 0
    for name in required:
        ok, value = sample(props.get(name, {}))
        if value == 'x' and not (isinstance(props.get(name), dict) and 'enum' in props[name]):
            strings += 1                                  # 每個字串參數給不同的值（edit 的 old／new 一樣會被拒）
            value = 'x' if strings == 1 else 'x%d' % strings
        base[name] = value if ok else 'x'
    cases = [('ok', json.dumps(base, ensure_ascii=False), 'contract')]
    for name, prop in props.items():
        kind = prop.get('type') if isinstance(prop, dict) else None
        if isinstance(kind, list):
            kind = next((k for k in kind if k != 'null'), None)
        if kind in WRONG:
            args = dict(base, **{name: WRONG[kind]})
            cases.append(('type:' + name, json.dumps(args, ensure_ascii=False), 'BadArguments'))
    for name in required:
        args = {k: v for k, v in base.items() if k != name}
        cases.append(('missing:' + name, json.dumps(args, ensure_ascii=False), 'BadArguments'))
    cases.append(('not-object', '[]', 'BadArguments'))
    return cases


def load_cases(path, names):
    """固定案例檔：JSON 陣列，每條 {tool, args, expect, contains?, name?, files?}。壞了＝CasesInvalid。"""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise AgentError('NotFound', '找不到案例檔 %s' % path)
    except (OSError, ValueError, UnicodeError) as e:
        raise AgentError('CasesInvalid', '讀不了案例檔 %s：%s' % (path, e))
    if not isinstance(data, list):
        raise AgentError('CasesInvalid', '%s 頂層要是陣列' % path)
    out = []
    for i, c in enumerate(data):
        where = '%s 第 %d 條' % (path, i)
        if not isinstance(c, dict) or not isinstance(c.get('tool'), str) or 'args' not in c \
                or not isinstance(c.get('expect'), str) or not c['expect']:
            raise AgentError('CasesInvalid', '%s：要是物件，有 tool（字串）、args、expect（"ok" 或錯誤代號）' % where)
        if c['tool'] not in names:
            raise AgentError('CasesInvalid', '%s：包裡沒有工具 %s（有：%s）' % (where, c['tool'], '、'.join(names)))
        if 'contains' in c and not isinstance(c['contains'], str):
            raise AgentError('CasesInvalid', '%s：contains 要是字串' % where)
        files = c.get('files', {})
        if not isinstance(files, dict) or not all(isinstance(v, str) for v in files.values()):
            raise AgentError('CasesInvalid', '%s：files 要是 {相對路徑: 內容字串}' % where)
        for rel in files:
            parts = Path(rel).parts
            if not rel or os.path.isabs(rel) or '..' in parts:
                raise AgentError('CasesInvalid', '%s：files 的路徑要是工作根目錄底下的相對路徑：%r' % (where, rel))
        name = c.get('name') if isinstance(c.get('name'), str) and c.get('name') else 'case%d' % i
        out.append({'tool': c['tool'], 'name': name, 'stdin': json.dumps(c['args'], ensure_ascii=False),
                    'expect': c['expect'], 'contains': c.get('contains'), 'files': files})
    return out


def _common_drift(folder):
    mine = folder / '_common.py'
    if mine.is_file() and mine.read_bytes() != BASE_COMMON.read_bytes():
        return '_common.py 跟 proto5/tools/base/_common.py 不一樣（要跟著 base 更新就複製一份過來）'
    return None


REQUIRE_JAIL_ENV = 'AOS_TOOLS_REQUIRE_JAIL'   # =1：tools test 關不了牢就拒跑，不退回主機直接跑


def _single(runner, tool, args, jail, note, as_json):
    res = runner.run(tool, args)
    if as_json:
        print(json.dumps({'_type': 'aos_agent_tools_run', '_version': 1, 'tool': tool['function']['name'],
                          'jail': jail, 'jail_note': note, 'exit_code': res.code, 'ms': res.ms,
                          'timed_out': res.timed_out, 'error': res.spawn_error or res.stuck,
                          'dropped': res.dropped, 'stdout': res.out, 'stderr': res.err}, ensure_ascii=False))
    else:
        sys.stdout.write(res.out)
        sys.stdout.flush()
        sys.stderr.write(res.err)
        extra = ''.join(x for x in ('，逾時被砍' if res.timed_out else '',
                                    '，前面丟了 %d 位元組輸出' % res.dropped if res.dropped else '',
                                    '；' + res.stuck if res.stuck else ''))
        sys.stderr.write('（%s：%s，%d 毫秒%s）\n' % (tool['function']['name'],
                                                   '退出碼 %s' % res.code if res.spawn_error is None else res.spawn_error,
                                                   res.ms, extra))
    return 0 if res.code == 0 and not res.timed_out else 1


def _suite(runner, name, folder, tools, cases, jail, note, as_json):
    warnings, rows, sizes = [], [], []
    drift = _common_drift(folder)
    if drift:
        warnings.append(drift)
    for t in tools:
        n = _tokens(t)
        sizes.append({'name': t['function']['name'], 'tokens': n, 'over': n > TOKEN_LIMIT})
    if not as_json:                                       # 表頭先印（跑任何工具之前），每條跑完就印
        print('包 %s（%s）：%d 支工具；%s' % (name, folder, len(tools),
                                         '關在牢裡跑（aos-jail，拋棄式 workspace 掛成 /work/ws，net off）' if jail
                                         else '在拋棄式的假 agent 家裡跑（沒關牢）'))
        for size in sizes:
            print('描述  %s  約 %d token%s' % (size['name'], size['tokens'],
                                           '（超過 %d，資源軸扣分：描述再短一點）' % TOKEN_LIMIT if size['over'] else ''))
        for w in warnings:
            print('警告：' + w)
        sys.stdout.flush()

    def add(row):
        rows.append(row)
        if not as_json:
            print('%s  %s  %s  (%d ms)' % ('PASS' if row['pass'] else 'FAIL', row['tool'], row['case'], row['ms']))
            if not row['pass']:
                print('      期待 %s；得到 %s' % (row['expect'], row['got']))
            sys.stdout.flush()

    def record(tool_name, case, res, expect, contains=None):
        ok, want = judge(res, expect, contains)
        add({'tool': tool_name, 'case': case, 'pass': ok, 'ms': res.ms, 'expect': want,
             'got': got(res), 'exit_code': res.code})

    if (folder / 'wrap.json').is_file():                  # wrap-py 產的：先試 import 一次原檔副本
        probe = {'type': 'function', 'function': {'name': name},
                 '_meta': {'argv': ['tools/%s/run' % name, '--check-import']}}
        record(name, 'import', runner.run(probe, ''), 'ok')
    runnable = []
    for t in tools:
        tname = t['function']['name']
        problem = runner.program(t)
        add({'tool': tname, 'case': 'program', 'pass': problem is None, 'ms': 0,
             'expect': '程式在、有執行位', 'got': problem or '', 'exit_code': None})
        if problem is None:
            runnable.append(t)
    for t in runnable:
        for case, stdin, expect in auto_cases(t):
            record(t['function']['name'], case, runner.run(t, stdin), expect)
    by_name = {t['function']['name']: t for t in runnable}
    for c in cases or []:
        if c['tool'] not in by_name:
            continue
        try:
            for rel, content in c['files'].items():
                runner.write_file(rel, content)
        except OSError as e:
            add({'tool': c['tool'], 'case': c['name'], 'pass': False, 'ms': 0,
                 'expect': '先把 files 寫進 workspace',
                 'got': '寫不進去（路徑經過符號連結、硬連結，或不是資料夾）：%s' % (e.strerror or e),
                 'exit_code': None})
            continue
        record(c['tool'], c['name'], runner.run(by_name[c['tool']], c['stdin']), c['expect'], c['contains'])
    failed = sum(1 for r in rows if not r['pass'])
    if as_json:
        print(json.dumps({'_type': 'aos_agent_tools_test', '_version': 1, 'package': name, 'dir': str(folder),
                          'jail': jail, 'jail_note': note, 'warnings': warnings, 'tools': sizes,
                          'cases': rows, 'total': len(rows), 'failed': failed}, ensure_ascii=False))
        return 1 if failed else 0
    print('%d 條，%d 條沒過' % (len(rows), failed))
    return 1 if failed else 0
