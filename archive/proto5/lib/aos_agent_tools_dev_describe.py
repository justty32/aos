"""`tools wrap-py --describe-with-llm／--describe`：叫模型補描述只寫提案檔，人看過再照提案產包；提案的機械檢查。"""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile

from aos_agent_home import AgentError

from aos_agent_tools_dev_pack import _dump, _shown
from aos_agent_tools_dev_pyread import analyze
from aos_agent_tools_dev_wrappy import _print_rows, _read_py, _wrap_pack


# ------------------------------------------------------------------ wrap-py：模型補描述（第三波 W3-2，spec/aos-agent/tools-llm.md） ----

DESCRIBE_TYPE = 'aos_wrap_py_describe'
DESCRIBE_MAX = 200                                       # 描述、參數說明最多幾個字
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')   # 控制字元（ESC、NUL…）：一律不收（審查 S1）
DESCRIBE_SYSTEM = ('You write short descriptions for Python functions that an AI agent will call as tools. '
                   'Read the code to see what each function really does. Reply with one JSON object only.')


def _needs(result):
    """收了的函式裡缺什麼：{函式: {'description': 缺描述?, 'params': [缺說明的參數]}}（什麼都不缺的不列）。"""
    need = {}
    for fname, sig in result['functions'].items():
        miss = [p['name'] for p in sig['params'] if p['name'] not in sig['docs']]
        if not sig.get('has_doc') or miss:
            need[fname] = {'description': not sig.get('has_doc'), 'params': miss}
    return need


def _clean_text(value):
    return ' '.join(value.split()) if isinstance(value, str) else None


def check_describe(data, result):
    """模型回的（或人改過的）描述 → (收的 {函式: {'description'?, 'params': {}}}, 丟掉的 [(標籤, 原因)])。
    只收已知的函式與參數名；描述非空、≤ 200 字；已有 docstring／說明的不覆蓋。"""
    if not isinstance(data, dict):
        return {}, [('（整份）', '要是 {函式名: {"description", "params"}} 物件')]
    functions, need = result['functions'], _needs(result)
    ok, dropped = {}, []
    for fname, entry in data.items():
        if fname not in functions:
            dropped.append((fname, '不認得的函式（這次收的只有 %s）' % ('、'.join(functions) or '（無）')))
            continue
        if not isinstance(entry, dict):
            dropped.append((fname, '要是 {"description", "params"} 物件'))
            continue
        got = {'params': {}}
        if entry.get('description') is not None:
            text = _clean_text(entry['description'])
            if fname not in need or not need[fname]['description']:
                dropped.append((fname, '已有 docstring，不覆蓋'))
            elif not text:
                dropped.append((fname, '描述是空的或不是字串'))
            elif CONTROL.search(text):
                dropped.append((fname, '描述含控制字元（ESC、NUL…）'))
            elif len(text) > DESCRIBE_MAX:
                dropped.append((fname, '描述 %d 字，超過 %d' % (len(text), DESCRIBE_MAX)))
            else:
                got['description'] = text
        params = entry.get('params') or {}
        if not isinstance(params, dict):
            dropped.append((fname, 'params 要是 {參數: 說明}'))
            params = {}
        known = [p['name'] for p in functions[fname]['params']]
        for pname, ptext in params.items():
            label = '%s.%s' % (fname, pname)
            text = _clean_text(ptext)
            if pname not in known:
                dropped.append((label, '%s 沒有這個參數（有：%s）' % (fname, '、'.join(known) or '（無）')))
            elif pname in functions[fname]['docs']:
                dropped.append((label, '已有說明，不覆蓋'))
            elif not text:
                dropped.append((label, '說明是空的或不是字串'))
            elif CONTROL.search(text):
                dropped.append((label, '說明含控制字元（ESC、NUL…）'))
            elif len(text) > DESCRIBE_MAX:
                dropped.append((label, '說明 %d 字，超過 %d' % (len(text), DESCRIBE_MAX)))
            else:
                got['params'][pname] = text
        if 'description' in got or got['params']:
            ok[fname] = got
    return ok, dropped


def describe_prompt(sources, need):
    """sources＝{函式名: 原始碼}；need＝_needs() 的結果。"""
    lines = []
    for fname, what in need.items():
        want = (['a "description"'] if what['description'] else []) + (
            ['"params" for %s' % ', '.join(what['params'])] if what['params'] else [])
        lines.append('- %s: %s' % (fname, ' and '.join(want)))
    code = '\n\n'.join(sources.get(f) or '' for f in need)
    return ('For the functions below, return {"<function name>": {"description": "<one sentence: what it does and '
            'what it returns>", "params": {"<param>": "<what to pass>"}}}.\n'
            'Only these functions and fields:\n%s\n'
            'Each text: one short sentence, under %d characters. Describe what the code actually does, '
            'not what the name suggests.\n\n```python\n%s\n```' % ('\n'.join(lines), DESCRIBE_MAX, code))


def _function_sources(source):
    tree = ast.parse(source)
    return {n.name: ast.get_source_segment(source, n) for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def describe_with_llm(file, only=None, name=None, out=None, force=False, model=None, ask=None):
    """wrap-py --describe-with-llm：缺描述的函式一次打包問模型，寫提案檔 <out>/<PACK>.describe.json；不產包。"""
    import aos_llm_ask
    src, data, source = _read_py(file)
    pack, folder = _wrap_pack(src, name, out)
    result = analyze(source, str(src), only)
    if not result['functions']:
        _print_rows(result)
        raise AgentError('NothingToWrap', '%s 沒有一支函式能包成工具；不問模型' % src)
    need = _needs(result)
    if not need:
        raise AgentError('NothingToDescribe', '收的函式都有 docstring 與參數說明，不用問模型；直接 wrap-py 就好')
    target = folder / (pack + '.describe.json')
    if os.path.lexists(target) and not force:                # 問模型之前先擋，免得白花一次
        raise AgentError('AlreadyExists', '%s 已經在了（要蓋掉加 --force）' % target)
    ask = ask or aos_llm_ask.ask_json
    reply, got = ask(DESCRIBE_SYSTEM, describe_prompt(_function_sources(source), need), alias=model)
    ok, dropped = check_describe(reply, result)
    proposal = {'_type': DESCRIBE_TYPE, '_version': 1, 'source': str(src), 'sha256': hashlib.sha256(data).hexdigest(),
                'generated': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
                'model': got.get('model'), 'alias': got.get('alias'), 'usage': got.get('usage'), 'ms': got.get('ms'),
                'functions': ok, 'dropped': [{'item': a, 'reason': b} for a, b in dropped]}
    write_json_file(target, proposal, force)
    _print_describe(result, ok, dropped)
    print(aos_llm_ask.usage_line(got), file=sys.stderr)
    print('提案寫在 %s（%d 支有提案、%d 條丟掉；還沒產包）' % (target, len(ok), len(dropped)))
    extra = ''.join(' %s %s' % (k, shlex.quote(v)) for k, v in (('--only', ','.join(only) if only else None),
                                                                ('--name', name), ('--out', out)) if v)
    print('看過沒問題（可以先改提案檔；這一步不叫模型）：aos-agent tools wrap-py %s --describe %s%s'
          % (shlex.quote(file), shlex.quote(_shown(target)), extra))
    return 0


def _print_describe(result, ok, dropped):
    """函式｜現在的描述（機械版＝函式名）｜模型提的。"""
    width = max([len(n) for n in result['functions']] + [4])
    print('%-*s  %-30s  %s' % (width, '函式', '現在的描述', '模型提的'))
    for fname, sig in result['functions'].items():
        now = sig['description'] if sig.get('has_doc') else '%s（沒 docstring）' % fname
        new = ok.get(fname, {})
        fallback = '（有 docstring，不改）' if sig.get('has_doc') else '（沒提）'
        print('%-*s  %-30s  %s' % (width, fname, now[:30], new.get('description', fallback)))
        for pname, text in new.get('params', {}).items():
            print('%-*s    參數 %s：%s' % (width, '', pname, text))
    for label, why in dropped:
        print('丟掉  %s（%s）' % (label, why))


def write_json_file(target, value, force):
    """寫一個 JSON 檔（暫存＋rename）；已在要 --force，符號連結或非一般檔一律不蓋。"""
    if os.path.lexists(target) and not force:
        raise AgentError('AlreadyExists', '%s 已經在了（要蓋掉加 --force）' % target)
    if os.path.islink(target) or (os.path.lexists(target) and not target.is_file()):
        raise AgentError('AlreadyExists', '%s 不是一般檔（或是符號連結），--force 也不蓋' % target)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix='.%s.' % target.name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(_dump(value))
        os.replace(tmp, target)
    except BaseException:
        os.unlink(tmp)
        raise


def apply_describe(path, result, sha):
    """wrap-py --describe FILE：照提案補描述（改 result 裡的簽名）。原檔 sha 對不上＝SourceChanged；
    提案有任何一條沒過機械檢查＝DescribeInvalid（人給的就要整份對）。回寫進 wrap.json 的紀錄。"""
    p = Path(os.path.abspath(os.path.expanduser(path)))
    try:
        raw = p.read_bytes()
        data = json.loads(raw.decode('utf-8'))
    except FileNotFoundError:
        raise AgentError('NotFound', '找不到 --describe %s' % p)
    except (OSError, ValueError, UnicodeError) as e:
        raise AgentError('DescribeInvalid', '讀不了 --describe %s：%s' % (p, e))
    if not isinstance(data, dict) or data.get('_type') != DESCRIBE_TYPE or data.get('_version') != 1 \
            or not isinstance(data.get('functions'), dict):
        raise AgentError('DescribeInvalid', '%s 不是 wrap-py 描述提案（要 _type %s、_version 1、functions）'
                         % (p, DESCRIBE_TYPE))
    if data.get('sha256') != sha:
        raise AgentError('SourceChanged', '原檔跟提案記的不一樣了（sha256 %s… ≠ %s…）；重新提案'
                         % (sha[:12], str(data.get('sha256'))[:12]))
    wanted = {k: v for k, v in data['functions'].items() if k in result['functions']}
    skipped = [k for k in data['functions'] if k not in result['functions']]
    ok, dropped = check_describe(wanted, result)
    if dropped:
        raise AgentError('DescribeInvalid', '提案有 %d 條沒過機械檢查：%s' % (
            len(dropped), '；'.join('%s：%s' % d for d in dropped)))
    done = set()
    for fname, entry in ok.items():
        sig = result['functions'][fname]
        if 'description' in entry:
            sig['description'] = entry['description']
            sig['has_doc'] = True
            done.add('%s 沒有 docstring（第一段），描述先用函式名' % fname)
        sig['docs'].update(entry['params'])
        done.update('%s 的參數 %s 沒有說明' % (fname, q) for q in entry['params'])
    result['warnings'] = [w for w in result['warnings'] if w not in done]
    for fname in skipped:
        result['warnings'].append('提案裡的 %s 這次沒包（沒收或沒在 --only 裡），略過' % fname)
    print('照 %s 補了 %d 支的描述' % (p, len(ok)))
    return {'file': str(p), 'sha256': hashlib.sha256(raw).hexdigest(), 'functions': sorted(ok)}
