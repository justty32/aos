"""aos-json：人用的 JSON Pointer 改檔（tool-era T3 隊；catalog T-json 的人用那一半）。

跟模型工具 json_edit 同一份程式（proto5/tools/files/_jsonedit.py）：get／set／del／append／merge、
照原檔縮排風格重寫、改完是合法 JSON 才寫、--expect-sha 對不上＝Conflict。
人用的版本**不關在工作根目錄、也不擋信任資料**（人本來就能改自己的 agent）；
改 aos 設定檔時加 --check-directives：改好的內容先用 aos_directives 解一次，解不過就不寫。
"""
import json
import os
import sys
from pathlib import Path

from aos_agent_home import AgentError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools' / 'files'))
import _common  # noqa: E402
import _files  # noqa: E402
import _jsonedit as J  # noqa: E402

USAGE = '''用法：
  aos-json get    FILE [POINTER]
  aos-json set    FILE POINTER VALUE [--expect-sha S] [--check-directives [--center DIR]]
  aos-json append FILE POINTER VALUE [同上]
  aos-json merge  FILE POINTER VALUE [同上]      （JSON merge patch：值是 null 的鍵刪掉）
  aos-json del    FILE POINTER       [同上]
POINTER 是 JSON Pointer（"" 是整份、/a/b/0、陣列尾巴 /a/-）。VALUE 是 JSON：字串要帶引號，例如 '"abc"'；- ＝從 stdin 讀。
get 印值與 sha；寫的時候給 --expect-sha，檔在這之間被改過就不寫（Conflict）。'''

NEW_STYLE = {'indent': 2, 'separators': (',', ': '), 'ensure_ascii': False, 'trailing_nl': True}


class Usage(Exception):
    pass


def parse_argv(argv):
    if not argv or argv[0] in ('-h', '--help', 'help'):
        raise Usage(None)
    op, pos, opts, i = argv[0], [], {}, 1
    if op not in J.OPS:
        raise Usage('不認得的子命令 %r（只有 %s）' % (op, '／'.join(J.OPS)))
    while i < len(argv):
        a = argv[i]
        if a == '--check-directives':
            opts['check'] = True
        elif a in ('--expect-sha', '--center'):
            if i + 1 >= len(argv):
                raise Usage('%s 後面要接值' % a)
            opts[a[2:].replace('-', '_')] = argv[i + 1]
            i += 1
        elif a in ('-h', '--help'):
            raise Usage(None)
        elif a.startswith('--'):
            raise Usage('不認得的選項 %s' % a)
        else:
            pos.append(a)
        i += 1
    want = {'get': (1, 2), 'del': (2, 2)}.get(op, (3, 3))
    if not want[0] <= len(pos) <= want[1]:
        raise Usage('%s 要 %s 個參數' % (op, want[0] if want[0] == want[1] else '%d～%d' % want))
    if op == 'get' and opts:
        raise Usage('get 不收 --expect-sha／--check-directives／--center')
    if 'center' in opts and 'check' not in opts:
        raise Usage('--center 只跟 --check-directives 一起用')
    return op, pos, opts


def run(argv, stdin=None):
    op, pos, opts = parse_argv(argv)
    path = pos[0]
    tokens = J.parse_pointer(pos[1] if len(pos) > 1 else '')
    value = None
    if len(pos) > 2:
        raw = (sys.stdin if stdin is None else stdin).read() if pos[2] == '-' else pos[2]
        try:
            value = json.loads(raw)
        except ValueError as e:
            raise Usage('VALUE 不是 JSON（%s）；字串要帶引號，例如 \'"abc"\'' % e)
    full = os.path.abspath(os.path.expanduser(path))
    exists = os.path.exists(full)
    if not exists and not (op == 'set' and not tokens):
        raise AgentError('NotFound', '沒有這個檔：%s' % path)
    if os.path.isdir(full):
        raise AgentError('IsADirectory', '%s 是資料夾' % path)
    root = os.path.dirname(full)
    text, data = _files.read_text(root, full, path) if exists else ('', b'')
    doc = J.parse_doc(text, path) if exists else None
    if op == 'get':
        return '%s\nsha=%s' % (json.dumps(J.lookup(doc, tokens), indent=2, ensure_ascii=False), _files.sha(data))
    _files.check_sha(opts.get('expect_sha'), data, path)
    new = J.apply(doc, op, tokens, value)
    if opts.get('check'):
        import aos_directives_edit
        aos_directives_edit.check_value(full, new, opts.get('center'))
    if exists and json.dumps(new) == json.dumps(doc):
        return '沒改：%s %s 已經是這個值（sha=%s）' % (path, J.show(tokens), _files.sha(data))
    out = J.dumps(new, J.style_of(text) if text.strip() else NEW_STYLE)
    os.makedirs(root, exist_ok=True)
    try:
        _common.write_atomic(root, full, out, path)
    except OSError as e:
        raise AgentError('WriteFailed', '寫不進 %s：%s' % (path, e.strerror or e))
    verb = {'set': '設了', 'del': '刪了', 'append': '加到陣列尾巴', 'merge': '合併進'}[op]
    return '%s %s（%s）；sha=%s' % (verb, J.show(tokens), path, _files.sha(out.encode('utf-8')))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        out = run(argv)
    except Usage as e:
        if e.args[0]:
            print('aos-json: Usage: %s' % e.args[0], file=sys.stderr)
        print(USAGE, file=sys.stderr if e.args[0] else sys.stdout)
        return 2 if e.args[0] else 0
    except AgentError as e:
        print('aos-json: %s: %s' % (e.code, e.msg), file=sys.stderr)
        return 1
    except _common.ToolError as e:
        print('aos-json: %s: %s' % (e.code, e.message), file=sys.stderr)
        return 1
    sys.stdout.write(out + '\n')
    return 0
