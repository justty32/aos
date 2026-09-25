"""`tools wrap-py` 的產包零件：run 程式樣板、README、印表、讀原檔與包名檢查（主流程 `wrap_py` 留在 aos_agent_tools_dev）。"""
import os
from pathlib import Path
import re

from aos_agent_home import AgentError
from aos_agent_tools import NAME

from aos_agent_tools_dev_pack import _out_dir, package_files


# ------------------------------------------------------------------ wrap-py：產 ----

WRAP_RUN = r'''#!/usr/bin/env python3
"""aos-agent tools wrap-py 產的 run：run <函式名>，stdin 讀 arguments、照 wrap.json 記下的簽名驗型別，
從 src/ 裡的原檔副本 import 函式來叫。run --check-import 只試 import 一次（tools test 用）。
回傳 str 原樣印；其他 json.dumps；例外＝PythonError（不噴 Traceback）。"""
import sys
sys.dont_write_bytecode = True
import contextlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
from _common import HERE, ToolError, fail, report, run  # noqa: E402

KIND = {'str': 'a string', 'int': 'an integer', 'float': 'a number', 'bool': 'a boolean',
        'list': 'an array', 'dict': 'an object'}


def wrap():
    with open(os.path.join(HERE, 'wrap.json'), encoding='utf-8') as f:
        return json.load(f)


def check(value, spec, where):
    """照型別記號驗一個值；回要傳給函式的值（float 參數收整數時轉成小數）。"""
    t = spec['t']
    if t == 'any':
        return value
    if t == 'optional':
        return None if value is None else check(value, spec['of'], where)
    if t == 'literal':
        for v in spec['values']:
            if type(value) is type(v) and value == v:
                return value
        fail('BadArguments', '%s must be one of %s' % (where, json.dumps(spec['values'], ensure_ascii=False)))
    ok = {'str': lambda v: isinstance(v, str),
          'int': lambda v: isinstance(v, int) and not isinstance(v, bool),
          'float': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
          'bool': lambda v: isinstance(v, bool),
          'list': lambda v: isinstance(v, list),
          'dict': lambda v: isinstance(v, dict)}[t](value)
    if not ok:
        fail('BadArguments', '%s must be %s' % (where, KIND[t]))
    if t == 'float':
        return float(value)
    if t == 'list':
        return [check(v, spec['of'], '%s[%d]' % (where, i)) for i, v in enumerate(value)]
    if t == 'dict':
        return {k: check(v, spec['of'], '%s["%s"]' % (where, k)) for k, v in value.items()}
    return value


def load(info):
    path = os.path.join(HERE, info['copy'])
    name = 'aos_wrapped_' + info['module']
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        with contextlib.redirect_stdout(sys.stderr):     # import 時印的東西不混進結果
            spec.loader.exec_module(module)
    except BaseException as e:  # noqa: B902 —— SystemExit、KeyboardInterrupt 也算 import 失敗
        fail('ImportFailed', 'cannot import %s: %s: %s' % (info['copy'], type(e).__name__, e))
    return module


def main(args, root):
    info = wrap()
    name = sys.argv[1] if len(sys.argv) > 1 else ''
    sig = info['functions'].get(name)
    if sig is None:
        fail('UnknownFunction', 'this package has no function %r' % name)
    known = {p['name'] for p in sig['params']}
    extra = sorted(k for k in args if k not in known)
    if extra:
        fail('BadArguments', 'unknown argument(s): %s' % ', '.join(extra))
    keyword = {}
    for p in sig['params']:
        if p['name'] not in args or (args[p['name']] is None and not p['required']):
            if p['required']:
                fail('BadArguments', 'missing required argument "%s"' % p['name'])
            continue
        value = check(args[p['name']], p['type'], 'argument "%s"' % p['name'])
        keyword[p['name']] = value
    os.chdir(root)                                        # 函式裡的相對路徑從工作根目錄算
    fn = getattr(load(info), name, None)
    if not callable(fn):
        fail('ImportFailed', '%s has no function %s' % (info['copy'], name))
    try:
        with contextlib.redirect_stdout(sys.stderr):     # 函式自己 print 的走 stderr，stdout 只放結果
            result = fn(**keyword)
    except BaseException as e:  # noqa: B902 —— KeyboardInterrupt、SystemExit 也一樣轉成 PythonError，不噴 Traceback
        fail('PythonError', '%s: %s' % (type(e).__name__, e), exception=type(e).__name__)
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as e:
        fail('ResultNotJSON', '%s returned %s, which is not JSON-serializable: %s'
             % (name, type(result).__name__, e))


def check_import():
    try:
        load(wrap())
    except ToolError as e:
        return report(e)
    except Exception as e:
        return report(ToolError('InternalError', '%s: %s' % (type(e).__name__, e)))
    sys.stdout.write('import ok\n')
    return 0


if __name__ == '__main__':
    sys.exit(check_import() if sys.argv[1:] == ['--check-import'] else run(main))
'''

WRAP_FIXED = ('run', 'wrap.json', '_common.py', 'config.json', 'README.md')
STATUS = {'ok': '收', 'reject': '拒收', 'skip': '跳過'}
STATUS_COL = {'ok': '收  ', 'reject': '拒收', 'skip': '跳過'}   # 中文字佔兩格，對齊用


def _pack_name(stem):
    name = re.sub(r'[^A-Za-z0-9_-]', '_', stem)
    if not name or not NAME.match(name):
        name = '_' + name
    return name


def _wrap_readme(pack, src_name, result, path):
    ok = [r for r in result['rows'] if r[1] == 'ok']
    other = [r for r in result['rows'] if r[1] != 'ok']
    lines = ['# %s — 從 %s 包出來的工具包' % (pack, src_name), '',
             '`aos-agent tools wrap-py` 用 `ast` 靜態讀原檔（沒有 import、沒有執行）產的。原檔副本在 `src/%s`，'
             '`wrap.json` 記了原檔路徑、sha256、每支的簽名與拒收表。' % src_name, '',
             '## 收了哪些', '', '| 工具 | 參數（* 必填） | 描述 |', '|---|---|---|']
    for name, _, _, _ in ok:
        sig = result['functions'][name]
        params = '、'.join(p['name'] + ('*' if p['required'] else '') for p in sig['params']) or '（無）'
        lines.append('| `%s` | %s | %s |' % (name, params, sig['description'].replace('|', '\\|')))
    lines += ['', '## 拒收／跳過', '']
    if other:
        lines += ['| 函式 | 行 | 為什麼 |', '|---|---|---|']
        lines += ['| `%s` | %d | %s：%s |' % (n, line, STATUS[s], why.replace('|', '\\|')) for n, s, why, line in other]
    else:
        lines.append('（沒有）')
    lines += ['', '## 怎麼跑', '',
              '`run <函式名>`：stdin 讀 arguments JSON，照記下的簽名驗型別（多給、少給必填、型別不對＝`BadArguments`），'
              '從 `src/` 的副本 import 函式來叫。回傳字串原樣印，其他 `json.dumps`（不能＝`ResultNotJSON`）；'
              '函式丟例外＝`PythonError`（附例外類別與訊息，不噴 Traceback）；import 失敗＝`ImportFailed`。'
              '函式裡的相對路徑從工作根目錄算（關牢時是牢裡的起點 `/work/ws` 之類）；函式自己 `print` 的走 stderr。', '',
              '## 關牢', '',
              '工具檔沒寫 `_jail`＝預設關牢。這個包**不需要任何額外掛載**：裝進有 `access.json` 的家，就關在牢裡跑，'
              '程式與原檔副本在牢裡的 `/opt/tool`（唯讀），函式碰得到的檔只有 `access.json` 掛進 `/work` 的資料夾。'
              '原檔 import 的套件要在牢裡的 `python3`（主機的 `/usr` 唯讀掛進去）找得到；裝在家目錄的套件（`pip --user`、venv）牢裡看不到。', '',
              '## 試、裝', '', '```sh',
              'aos-agent tools test %s            # 先試 import 一次，再跑自動案例' % path,
              'aos-agent tools add %s --target 家' % path, '```',
              '', '原檔改了要重包：`aos-agent tools wrap-py <原檔> --force`（副本不會自己跟著變）。', '']
    return '\n'.join(lines)


def _print_rows(result):
    width = max([len(r[0]) for r in result['rows']] + [4])
    for name, status, why, line in result['rows']:
        tail = '' if status == 'ok' else '（%s）' % why
        print('%s  %-*s  第 %d 行%s' % (STATUS_COL[status], width, name, line, tail))
    for w in result['warnings']:
        print('警告：' + w)


def _read_py(file):
    src = Path(os.path.abspath(os.path.expanduser(file)))
    try:
        data = src.read_bytes()
    except FileNotFoundError:
        raise AgentError('NotFound', '找不到 %s' % src)
    except OSError as e:
        raise AgentError('ReadFailed', '讀不到 %s：%s' % (src, e.strerror or e))
    try:
        source = data.decode('utf-8')
    except UnicodeDecodeError:
        raise AgentError('ReadFailed', '%s 不是 UTF-8 文字檔' % src)
    return src, data, source


def _wrap_pack(src, name, out):
    pack = name if name is not None else _pack_name(src.stem)
    if not NAME.match(pack):
        raise AgentError('BadName', '工具包名字 %r 只能用英數、底線、連字號（不能以 . 或 - 開頭）' % pack)
    folder = _out_dir(out)
    package_files(pack, [(pack + '.json', '', False)] + [(f, '', False) for f in WRAP_FIXED])  # 先擋撞名（wrap、config）
    return pack, folder
