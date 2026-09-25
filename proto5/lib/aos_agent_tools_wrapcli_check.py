"""`tools wrap-cli` 參數表的機械檢查（模型回的、人改過的都走這條），以及 --describe-with-llm 的提示與叫模型。"""
import math
import re

from aos_agent_home import AgentError

from aos_agent_tools_wrapcli_const import (
    CONTROL, FLAG, HELP_MAX, KINDS, LLM_CAP, MAX_NARGS, PARAM_NAME, SKIP_FLAGS
)


# ------------------------------------------------------------------ 參數表的機械檢查（模型回的、人改過的都走這條） ----

def _in_text(flag, evidence):
    return re.search(r'(?<![\w-])%s(?![\w-])' % re.escape(flag), evidence) is not None


def _line_of(flag, evidence):
    for i, line in enumerate(evidence.split('\n')):
        if _in_text(flag, line):
            return i + 1
    return None


def _joiner(flag, evidence):
    return '=' if re.search(r'(?<![\w-])%s\[?=' % re.escape(flag), evidence) else ' '


def check_params(raw, evidence):
    """參數表逐格驗 → (收的 [參數], 丟掉的 [(標籤, 原因)])。旗標要在原文逐字出現、型別只准那幾種、名字合法。"""
    if not isinstance(raw, list):
        return [], [('params', 'params 要是陣列')]
    ok, dropped, names, flags_seen = [], [], set(), set()
    variable = None                                       # 前面可變長度（選填或陣列）的位置參數
    for i, p in enumerate(raw):
        label = '第 %d 格' % (i + 1)
        if not isinstance(p, dict):
            dropped.append((label, '不是物件'))
            continue
        name = p.get('name')
        label = '%s（%s）' % (label, name) if isinstance(name, str) else label
        why = _check_one(p, evidence, names, flags_seen)
        is_var = p.get('kind') == 'positional' and (not p.get('required') or p.get('array'))
        if not why and is_var and variable:
            why = ('前面已有可變長度的位置參數 %s（選填或陣列），再一個就分不清值給誰（跳過前面的也會被配錯）'
                   % variable)
        if why:
            dropped.append((label, why))
            continue
        kind = p['kind']
        q = {'name': name, 'flags': list(p.get('flags') or []), 'kind': kind,
             'type': {'flag': 'boolean', 'count': 'integer'}.get(kind, p.get('type')),
             'array': bool(p.get('array')), 'required': bool(p.get('required')),
             'help': ' '.join(str(p.get('help') or '').split())[:HELP_MAX]}
        if p.get('choices'):
            q['choices'] = list(p['choices'])
        if kind == 'option':
            longs = [f for f in q['flags'] if f.startswith('--')]
            q['joiner'] = p.get('joiner') if p.get('joiner') in ('=', ' ') else (
                _joiner(longs[0], evidence) if longs else ' ')
        if q['array'] and kind == 'option':
            q['multi'] = p.get('multi') if p.get('multi') in ('repeat', 'once') else 'repeat'
        if 'default' in p and (p['default'] is None or isinstance(p['default'], (str, int, float, bool))):
            q['default'] = p['default']
        line = p.get('line') if isinstance(p.get('line'), int) and not isinstance(p.get('line'), bool) else None
        q['line'] = line if line is not None else (_line_of(q['flags'][0], evidence) if q['flags'] else None)
        if p.get('nargs') is not None:
            q['nargs'] = p['nargs']
        if is_var:
            variable = name
        names.add(name)
        flags_seen.update(q['flags'])
        ok.append(q)
    return ok, dropped


def _check_one(p, evidence, names, flags_seen):
    name, kind, flags = p.get('name'), p.get('kind'), p.get('flags', [])
    if not isinstance(name, str) or not PARAM_NAME.match(name):
        return '名字 %r 不合法（英數底線、不以數字開頭、≤ 64 字）' % (name,)
    if name in names:
        return '名字 %s 重複' % name
    if kind not in KINDS:
        return 'kind %r 不認得（只收 %s）' % (kind, '、'.join(KINDS))
    if flags is None:
        flags = []
    if not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
        return 'flags 要是字串陣列'
    if kind == 'positional' and flags:
        return '位置參數不能有旗標'
    if kind != 'positional' and not flags:
        return '%s 至少要一個旗標' % kind
    for f in flags:
        if not FLAG.match(f):
            return '旗標 %r 寫法不對（- 或 -- 開頭，不含 = 與空白）' % f
        if f in SKIP_FLAGS or (f == '-h' and 'help' in str(p.get('help') or '').lower()):
            return '%s 是 help／version，不收' % f
        if not _in_text(f, evidence):
            return '旗標 %s 在原文裡找不到' % f
        if f in flags_seen:
            return '旗標 %s 已經有別格用了' % f
    if len(set(flags)) != len(flags):
        return '旗標重複'
    t = p.get('type')
    if kind == 'flag' and t not in (None, 'boolean'):
        return 'flag 的型別只能是 boolean'
    if kind == 'count' and t not in (None, 'integer'):
        return 'count 的型別只能是 integer'
    if kind in ('option', 'positional') and t not in ('string', 'integer', 'number'):
        return '型別 %r 不收（option／positional 只收 string、integer、number；開關請用 kind flag）' % (t,)
    for key in ('array', 'required'):
        if key in p and not isinstance(p[key], bool) and p[key] is not None:
            return '%s 要是 true／false' % key
    if p.get('array') and kind in ('flag', 'count'):
        return '%s 不能是陣列' % kind
    choices = p.get('choices')
    if choices is not None and choices != []:
        want = {'string': str, 'integer': int, 'number': (int, float)}.get(t)
        if not isinstance(choices, list) or len(choices) > 100 or want is None or not all(
                isinstance(c, want) and not isinstance(c, bool) for c in choices):
            return 'choices 要是跟型別一致的清單（≤ 100 個）'
    if 'help' in p and p['help'] is not None and not isinstance(p['help'], str):
        return 'help 要是字串'
    if CONTROL.search(str(p.get('help') or '')) or any(isinstance(c, str) and CONTROL.search(c)
                                                       for c in (choices or [])):
        return 'help 或 choices 含控制字元（ESC、NUL…）'
    if any(isinstance(v, float) and not math.isfinite(v) for v in list(choices or []) + [p.get('default')]):
        return 'choices 或 default 有 NaN／無限大（寫不成標準 JSON）'        # 09-25 複審 M3
    nargs = p.get('nargs')
    if nargs is not None:
        if nargs in ('+', '*') or (isinstance(nargs, int) and not isinstance(nargs, bool) and 1 <= nargs <= MAX_NARGS):
            if not p.get('array') or kind not in ('option', 'positional'):
                return 'nargs 只給陣列的 option／positional'
        else:
            return 'nargs 只收 +、*、1～%d' % MAX_NARGS
    return None


# ------------------------------------------------------------------ 模型版 ----

LLM_SYSTEM = ('You read the help text (or argparse source) of a command-line program and list its parameters as JSON. '
              'Reply with one JSON object only, no prose.')
LLM_FORMAT = '''Return {"description": "<one sentence: what the program does>", "params": [ ... ]}.
Each param is an object:
  "name": snake_case identifier (letters, digits, underscore),
  "flags": ["-x", "--long"] exactly as written in the text, without "=VALUE" (empty list for positional arguments),
  "kind": "flag" (on/off switch) | "count" (switch that can be repeated, like -vv) | "option" (takes a value) | "positional",
  "type": "boolean" for flag, "integer" for count, otherwise "string" | "integer" | "number",
  "array": true if it can take several values (repeatable option, or FILE...),
  "required": true or false,
  "choices": list of allowed values, or null,
  "help": short description.
List positional arguments in order. Skip -h/--help and --version.'''


def llm_prompt(cmd, mode, evidence):
    what = 'argparse source code' if mode == 'argparse' else 'help text'
    body = evidence if len(evidence) <= LLM_CAP else evidence[:LLM_CAP] + '\n[...truncated]\n'
    return '%s\n\nProgram: %s\nIts %s:\n<<<\n%s>>>' % (LLM_FORMAT, cmd, what, body)


def llm_table(cmd, mode, evidence, alias=None, ask=None):
    """問模型一次 → (描述, 收的參數, 丟掉的, ask 的回傳)。模型回的格式不對＝BadModelOutput。"""
    import aos_llm_ask
    ask = ask or aos_llm_ask.ask_json
    data, got = ask(LLM_SYSTEM, llm_prompt(cmd, mode, evidence), alias=alias)
    if isinstance(data, list):
        data = {'params': data}
    if not isinstance(data, dict) or 'params' not in data:
        raise AgentError('BadModelOutput', '模型回的 JSON 沒有 params 陣列')
    params, dropped = check_params(data['params'], evidence)
    desc = data.get('description')
    if isinstance(desc, str) and CONTROL.search(desc):
        dropped.append(('description', '含控制字元（ESC、NUL…），不收'))
        desc = None
    desc = ' '.join(desc.split())[:HELP_MAX] if isinstance(desc, str) and desc.strip() else None
    return desc, params, dropped, got
