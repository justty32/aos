"""`aos-directives resolve／check`：把一份 aos JSON 檔的指示詞整份解開（可指定中心與 JSON Pointer）或只驗。"""
import json
import os

from aos_agent_home import AgentError
from aos_directives import (Context, DirectiveError, Document, is_option_object, load_document,
                            resolve_located)


# ------------------------------------------------------------ resolve／check ----

def _deep(value, ctx, pos):
    if is_option_object(value):
        out = dict(value)
        if '$val' in value:
            out['$val'] = _deep(value['$val'], ctx, pos + ['$val'])
        return out
    loc = resolve_located(value, ctx, pos)
    v = loc.value
    if isinstance(v, dict):
        return {k: _deep(x, loc.ctx, loc.position + [k]) for k, x in v.items()}
    if isinstance(v, list):
        return [_deep(x, loc.ctx, loc.position + [str(i)]) for i, x in enumerate(v)]
    return v


def resolve_doc(doc, center=None, pointer=None, env=None):
    """整份（或 pointer 那格）解開；$opt 物件原樣留著、只解它的 $val。錯＝AgentError（代號照指示詞規範）。"""
    ctx = Context(doc, base_dir=center or os.path.dirname(doc.path or '.'),
                  env=dict(os.environ) if env is None else env)
    value, pos = doc.root, []
    for token in _pointer(pointer or ''):
        if isinstance(value, list) and token.isdigit() and int(token) < len(value):
            value = value[int(token)]
        elif isinstance(value, dict) and token in value:
            value = value[token]
        else:
            raise AgentError('NotFound', '原文沒有 %s（pointer 走的是原文，不是解開後的值）' % pointer)
        pos.append(token)
    try:
        return _deep(value, ctx, pos)
    except DirectiveError as e:
        raise AgentError(e.code, e.msg) from e


def _pointer(p):
    if p == '':
        return []
    if not p.startswith('/'):
        raise AgentError('Usage', 'pointer 要是 "" 或 / 開頭，例如 /envs/PATH')
    return [t.replace('~1', '/').replace('~0', '~') for t in p[1:].split('/')]


def load_file(path):
    try:
        return load_document(path)
    except DirectiveError as e:
        raise AgentError(e.code, e.msg) from e


def cmd_resolve(path, center=None, pointer=None):
    return json.dumps(resolve_doc(load_file(path), center, pointer), indent=2, ensure_ascii=False)


def cmd_check(path, center=None):
    resolve_doc(load_file(path), center)
    return 'ok：%s 的指示詞都解得開' % path


def check_value(path, value, center=None):
    """給 aos-json --check-directives：改好、還沒寫的內容解一次，解不過＝AgentError。"""
    resolve_doc(Document(path, value), center)
