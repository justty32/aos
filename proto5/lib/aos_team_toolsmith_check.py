"""工具草稿 tool_draft 的欄位驗：名字、參數表（JSON Schema 子集）、程式碼、附的例子、整份申請。"""
import ast
import re

from aos_team_format import bad


FIELDS = ('name', 'description', 'parameters', 'code', 'lang', 'cases')
NAME = re.compile(r'[a-z][a-z0-9_]{0,39}\Z')
TYPES = ('string', 'integer', 'number', 'boolean', 'array', 'object')
PROP_KEYS = ('type', 'description', 'enum', 'items', 'minimum', 'maximum')
MAX_CODE, MAX_DESC, MAX_PROPS, MAX_CASES = 20000, 600, 8, 5


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
