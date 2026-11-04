"""JSON Pointer（RFC 6901）定位改 JSON：json_edit 工具與 aos-json 指令共用。

五種 op：get／set／del／append／merge（merge＝RFC 7396 merge patch，值是 null 的鍵刪掉）。
改完整份重新 dumps→loads 一次，是合法 JSON 才交給呼叫者寫；照原檔的縮排、分隔、跳脫風格重寫。
錯誤一律丟 _common.ToolError（fail）。
"""
import copy
import json
import re

from _common import fail

OPS = ('get', 'set', 'del', 'append', 'merge')
INDEX = re.compile(r'(0|[1-9][0-9]*)\Z')


def parse_doc(text, path):
    try:
        return json.loads(text)
    except ValueError as e:
        fail('JsonSyntax', '%s is not valid JSON (%s); fix it with edit or write first' % (path, e))


def parse_pointer(pointer):
    if pointer == '':
        return []
    if not pointer.startswith('/'):
        fail('BadPointer', 'pointer %r must be "" (whole document) or start with "/", e.g. "/a/b/0"' % pointer)
    tokens = []
    for raw in pointer[1:].split('/'):
        if re.search(r'~(?![01])', raw):
            fail('BadPointer', 'pointer %r: "~" must be written "~0" and "/" inside a key "~1"' % pointer)
        tokens.append(raw.replace('~1', '/').replace('~0', '~'))
    return tokens


def show(tokens):
    return ''.join('/' + t.replace('~', '~0').replace('/', '~1') for t in tokens) or '""'


def _keys_hint(node):
    if isinstance(node, dict):
        keys = list(node)[:20]
        return 'keys there: %s%s' % (', '.join(json.dumps(k, ensure_ascii=False) for k in keys) or '(none)',
                                     ', …' if len(node) > 20 else '')
    if isinstance(node, list):
        return 'that array has %d items (index 0..%d, or "-" for the end)' % (len(node), len(node) - 1)
    return 'the value there is %s, not an object or array' % type_name(node)


def type_name(v):
    return {dict: 'an object', list: 'an array', str: 'a string', bool: 'a boolean',
            type(None): 'null'}.get(type(v), 'a number')


def _step(node, token, tokens, i, allow_end=False):
    """走一步；回 (容器, 鍵或索引)。allow_end：陣列可用 "-" 或 len 表示尾巴（回 len）。"""
    here = show(tokens[:i])
    if isinstance(node, dict):
        return token
    if isinstance(node, list):
        if token == '-' and allow_end:
            return len(node)
        if not INDEX.match(token):
            fail('PointerNotFound', '%s: %r is not an array index; %s' % (show(tokens[:i + 1]), token,
                                                                        _keys_hint(node)))
        idx = int(token)
        if idx < len(node) or (allow_end and idx == len(node)):
            return idx
        fail('PointerNotFound', '%s does not exist; %s' % (show(tokens[:i + 1]), _keys_hint(node)))
    fail('PointerNotFound', '%s: cannot go into %s (value at %s)' % (show(tokens[:i + 1]), type_name(node),
                                                                   here))


def lookup(doc, tokens):
    node = doc
    for i, t in enumerate(tokens):
        key = _step(node, t, tokens, i)
        if isinstance(node, dict) and key not in node:
            fail('PointerNotFound', '%s does not exist; %s' % (show(tokens[:i + 1]), _keys_hint(node)))
        node = node[key]
    return node


def _parent(doc, tokens):
    return lookup(doc, tokens[:-1])


def merge_patch(target, patch):
    if not isinstance(patch, dict):
        return copy.deepcopy(patch)
    out = dict(target) if isinstance(target, dict) else {}
    for k, v in patch.items():
        if v is None:
            out.pop(k, None)
        else:
            out[k] = merge_patch(out.get(k), v)
    return out


def apply(doc, op, tokens, value=None):
    """回改好的新文件（不改原本的）。"""
    doc = copy.deepcopy(doc)
    if op == 'set':
        if not tokens:
            return copy.deepcopy(value)
        parent = _parent(doc, tokens)
        key = _step(parent, tokens[-1], tokens, len(tokens) - 1, allow_end=True)
        if isinstance(parent, list) and key == len(parent):
            parent.append(value)
        else:
            parent[key] = value
        return doc
    if op == 'del':
        if not tokens:
            fail('BadArguments', 'op del needs a pointer to a key or item; it cannot delete the whole document')
        parent = _parent(doc, tokens)
        key = _step(parent, tokens[-1], tokens, len(tokens) - 1)
        if isinstance(parent, dict) and key not in parent:
            fail('PointerNotFound', '%s does not exist; %s' % (show(tokens), _keys_hint(parent)))
        del parent[key]
        return doc
    target = lookup(doc, tokens)
    if op == 'append':
        if not isinstance(target, list):
            fail('TypeMismatch', 'op append needs an array at %s, but it is %s' % (show(tokens),
                                                                                 type_name(target)))
        target.append(value)
        return doc
    if op == 'merge':
        if not isinstance(target, dict) or not isinstance(value, dict):
            fail('TypeMismatch', 'op merge needs an object at %s and an object value (got %s there, value is %s)'
                 % (show(tokens), type_name(target), type_name(value)))
        merged = merge_patch(target, value)
        if not tokens:
            return merged
        parent = _parent(doc, tokens)
        parent[_step(parent, tokens[-1], tokens, len(tokens) - 1)] = merged
        return doc
    fail('BadArguments', 'op must be one of %s' % ', '.join(OPS))


def style_of(text):
    """原檔的寫法：縮排、分隔、要不要跳脫非 ASCII、結尾換行。"""
    body = text.strip()
    style = {'trailing_nl': text.endswith('\n'), 'indent': None, 'separators': (', ', ': '),
             'ensure_ascii': bool(re.search(r'\\u[0-9a-fA-F]{4}', text)) and text.isascii()}
    if '\n' in body:
        for line in body.split('\n')[1:]:
            ws = line[:len(line) - len(line.lstrip(' \t'))]
            if ws:
                style['indent'] = '\t' if ws.startswith('\t') else len(ws)
                break
        else:
            style['indent'] = 2
        style['separators'] = (',', ': ')
    elif body and not re.search(r'[,:] ', body):
        style['separators'] = (',', ':')
    if '\r\n' in text:
        style['crlf'] = True
    return style


def dumps(doc, style):
    try:
        out = json.dumps(doc, indent=style['indent'], separators=style['separators'],
                         ensure_ascii=style['ensure_ascii'], allow_nan=False)
    except ValueError as e:
        fail('BadArguments', 'result is not valid JSON: %s' % e)
    json.loads(out)  # 改完再解析一次（防萬一）
    if style.get('crlf'):
        out = out.replace('\n', '\r\n')
    if style['trailing_nl']:
        out += '\r\n' if style.get('crlf') else '\n'
    return out
