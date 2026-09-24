"""aos-directives：人用的指示詞工具（tool-era T3 隊）。

兩件事，同一支指令：
1. 人格（system prompt，agent 家 info.json 的 system 指的檔，內容 {"content": 字串}）按 Markdown 標題
   分節來看與改：ls／show／set／add／rm／export／import／versions／revert。每次寫之前把舊的存一份版本，
   revert 還原（還原本身也先存一份，所以還原可以再還原）。
2. 解／驗一份 aos JSON 檔的指示詞（$env／$ref／$fmt／$opt）：resolve／check（catalog T-directive）。

分節規則跟 files 工具包的 md_section 同一份程式（proto5/tools/files/_mdsec.py）。
寫入持跟 tools／access 同一把管理鎖（<家>/.admin.lock）；人格檔整份 .tmp＋rename、縮排 2、不跳脫中文。
錯誤一律 AgentError（代號＋白話）；CLI 印 `aos-directives: 代號: 白話` 退 1，用法錯退 2。
"""
import json
import os
import sys
import time
from pathlib import Path

import aos_home
from aos_agent_home import AgentError, read_info_doc, resolve_field
from aos_agent_tools_edit import info_lock
from aos_directives import (Context, DirectiveError, Document, is_option_object, load_document,
                            resolve_located)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools' / 'files'))
import _mdsec as M  # noqa: E402

VERSIONS_DIR = '.versions'
KEEP = 20
LAST = '下一次問模型就用新的人格，不用重 start'


# ------------------------------------------------------------------ 人格檔 ----

def system_path(home):
    doc = read_info_doc(home)
    ctx = Context(doc, base_dir=str(home), env=dict(os.environ))
    value = resolve_field(doc, ctx, ['system']) if 'system' in doc.root else 'prompts/system.json'
    if not isinstance(value, str) or not value:
        raise AgentError('FieldTypeMismatch', 'info.json 的 system 要是路徑字串')
    return Path(home, os.path.expanduser(value)).absolute()


def read_persona(path, for_write=False):
    """回 (整個物件, content)。檔不在＝({}, '')。"""
    if not path.exists():
        return {}, ''
    try:
        obj = aos_home.read_json(path)
    except Exception as e:  # noqa: BLE001 — read_json 丟的是 HomeError
        raise AgentError(getattr(e, 'code', 'JsonSyntax'), '人格檔 %s 讀不了：%s' % (path, getattr(e, 'msg', e)))
    if not isinstance(obj, dict) or 'content' not in obj:
        raise AgentError('MessageInvalid', '人格檔 %s 要是含 content 的物件' % path)
    if not isinstance(obj['content'], str):
        raise AgentError('FieldTypeMismatch', '人格檔 %s 的 content 不是字面字串（可能用了指示詞）；%s'
                         % (path, '這種請直接用文字編輯器改' if for_write else '只能看原文'))
    return obj, obj['content']


def version_dir(path):
    return path.parent / VERSIONS_DIR


def versions(path):
    """新到舊：[(id, 檔)]；id＝存的時間（奈秒）。只看這個人格檔名的版本。"""
    d = version_dir(path)
    if not d.is_dir():
        return []
    prefix = path.stem + '-'
    out = []
    for p in d.iterdir():
        if p.name.startswith(prefix) and p.suffix == '.json' and p.stem[len(prefix):].isdigit():
            out.append((p.stem[len(prefix):], p))
    return sorted(out, key=lambda x: int(x[0]), reverse=True)


def save_version(path, obj):
    if not obj:
        return None
    d = version_dir(path)
    d.mkdir(exist_ok=True)
    vid = str(time.time_ns())
    aos_home.write_json(d / ('%s-%s.json' % (path.stem, vid)), obj, indent=2)
    for _, old in versions(path)[KEEP:]:
        old.unlink(missing_ok=True)
    return vid


def write_persona(path, obj, content):
    """先存舊版、再整份換掉；回版本 id（原本沒檔＝None）。"""
    vid = save_version(path, obj)
    new = dict(obj) if obj else {}
    new['content'] = content
    path.parent.mkdir(parents=True, exist_ok=True)
    aos_home.write_json(path, new, indent=2)
    return vid


# ------------------------------------------------------------------ 分節 ----

def parse(content):
    lines = M.split_lines(content)
    return lines, M.sections(lines)


def prelude_end(lines, secs):
    return secs[0].start if secs else len(lines)


def pick(lines, secs, spec):
    """SECTION：數字（ls 的編號，0＝第一個標題之前的開頭）或標題文字（# 可省）。回 Section 或 'prelude'。"""
    if spec.isdigit():
        n = int(spec)
        if n == 0:
            return 'prelude'
        if 1 <= n <= len(secs):
            return secs[n - 1]
        raise AgentError('NotFound', '沒有第 %d 節；人格一共 %d 節（aos-directives ls 看編號）' % (n, len(secs)))
    hits = M.find(secs, spec)
    if not hits:
        raise AgentError('NotFound', '人格裡沒有標題 %r；有：%s' % (spec, '、'.join(s.heading for s in secs) or '（沒有標題）'))
    if len(hits) > 1:
        raise AgentError('NotUnique', '標題 %r 有 %d 個（第 %s 節）；用編號指定'
                         % (spec, len(hits), '、'.join(str(s.index + 1) for s in hits)))
    return hits[0]


def section_text(lines, secs, sec):
    if sec == 'prelude':
        return ''.join(lines[:prelude_end(lines, secs)])
    return ''.join(lines[sec.start:sec.end])


def label(sec):
    return '開頭（第一個標題之前）' if sec == 'prelude' else '第 %d 節 %s' % (sec.index + 1, sec.heading)


def replace_body(lines, secs, sec, text):
    nl = M.newline_of(lines)
    body = M.as_lines(text, nl)
    if sec == 'prelude':
        end = prelude_end(lines, secs)
        if body and end < len(lines) and body[-1].strip():
            body.append(nl)
        return lines[:0] + body + lines[end:]
    start, end = M.body_range(sec, lines)
    if body and body[0].strip():
        body.insert(0, nl)
    if body and end == sec.end and end < len(lines):
        body.append(nl)
    return lines[:start] + body + lines[end:]


# ------------------------------------------------------------------ 指令 ----

def cmd_ls(home):
    path = system_path(home)
    _, content = read_persona(path)
    lines, secs = parse(content)
    out = ['人格檔：%s（%d 字）' % (path, len(content))]
    pre = section_text(lines, secs, 'prelude')
    if pre.strip() or not secs:
        out.append('%3d  %s  %d 字' % (0, '（開頭，沒有標題）', len(pre)))
    for s in secs:
        out.append('%3d  %s%s  %d 字' % (s.index + 1, '  ' * (s.level - 1), s.heading,
                                        len(section_text(lines, secs, s))))
    vs = versions(path)
    out.append('存了 %d 個舊版本（aos-directives versions）' % len(vs) if vs else '還沒有舊版本')
    return '\n'.join(out)


def cmd_show(home, spec=None):
    _, content = read_persona(system_path(home))
    if spec is None:
        return content
    lines, secs = parse(content)
    return section_text(lines, secs, pick(lines, secs, spec))


def _edit(home, fn):
    """鎖內：讀、算新內容、存舊版、寫。fn(content) → (新內容, 做了什麼)。"""
    with info_lock(home):
        path = system_path(home)
        obj, content = read_persona(path, for_write=True)
        new, what = fn(content)
        if new == content:
            return '沒改：%s（內容一樣，沒寫檔）' % what
        vid = write_persona(path, obj, new)
    kept = '；舊的存成版本 %s（aos-directives revert %s 可還原）' % (vid, vid) if vid else ''
    return '%s → %s%s\n%s' % (what, path, kept, LAST)


def cmd_set(home, spec, text):
    def fn(content):
        lines, secs = parse(content)
        sec = pick(lines, secs, spec)
        return ''.join(replace_body(lines, secs, sec, text)), '改了%s的內容' % label(sec)
    return _edit(home, fn)


def cmd_add(home, heading, text, after=None):
    level, title = M.normalize(heading)
    if level is None or not title:
        raise AgentError('Usage', '新節的標題要以 # 開頭，例如 "## 回話規則"')

    def fn(content):
        lines, secs = parse(content)
        if M.find(secs, heading):
            raise AgentError('AlreadyExists', '已經有 %s 這節；要改內容用 aos-directives set' % heading)
        nl = M.newline_of(lines)
        if lines and not lines[-1].endswith(('\n', '\r')):
            lines[-1] += nl
        at = len(lines)
        if after is not None:
            sec = pick(lines, secs, after)
            at = prelude_end(lines, secs) if sec == 'prelude' else sec.end
        block = [('#' * level + ' ' + title) + nl] + ([nl] + M.as_lines(text, nl) if text else [])
        if at > 0 and lines[at - 1].strip():
            block.insert(0, nl)
        if at < len(lines):
            block.append(nl)
        return ''.join(lines[:at] + block + lines[at:]), '加了一節 %s' % ('#' * level + ' ' + title)
    return _edit(home, fn)


def cmd_rm(home, spec):
    def fn(content):
        lines, secs = parse(content)
        sec = pick(lines, secs, spec)
        if sec == 'prelude':
            return ''.join(lines[prelude_end(lines, secs):]), '刪了開頭（第一個標題之前）'
        return ''.join(lines[:sec.start] + lines[sec.end:]), '刪了%s（含子節）' % label(sec)
    return _edit(home, fn)


def cmd_export(home, out=None):
    _, content = read_persona(system_path(home))
    if out is None:
        return content
    Path(out).write_text(content, encoding='utf-8')
    return '人格寫到 %s（%d 字）；用文字編輯器改完，aos-directives import %s 放回去' % (out, len(content), out)


def cmd_import(home, src, text):
    return _edit(home, lambda content: (text, '整份人格換成 %s 的內容' % src))


def cmd_versions(home):
    path = system_path(home)
    vs = versions(path)
    if not vs:
        return '%s 還沒有舊版本（每次用 aos-directives 改都會先存一份）' % path
    out = ['%s 的舊版本（新到舊；aos-directives revert ID）：' % path]
    for vid, p in vs:
        try:
            _, content = read_persona(p)
            size = '%d 字' % len(content)
        except AgentError as e:
            size = '壞了（%s）' % e.code
        out.append('  %s  %s  %s' % (vid, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(vid) / 1e9)), size))
    return '\n'.join(out)


def cmd_revert(home, vid=None):
    path = system_path(home)
    vs = versions(path)
    if not vs:
        raise AgentError('NotFound', '%s 沒有舊版本可以還原' % path)
    chosen = dict(vs).get(vid) if vid else vs[0][1]
    if chosen is None:
        raise AgentError('NotFound', '沒有版本 %s；有：%s' % (vid, '、'.join(v for v, _ in vs)))
    _, old = read_persona(chosen)
    return _edit(home, lambda content: (old, '還原成版本 %s' % (vid or vs[0][0])))


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


# ------------------------------------------------------------------ CLI ----

USAGE = '''用法：
  aos-directives ls       [--target 家]                 人格分幾節、每節多長
  aos-directives show     [SECTION] [--target 家]       印整份人格或一節
  aos-directives set      SECTION (--text T | --file F) [--target 家]   換掉一節的內容（標題留著）
  aos-directives add      "## 標題" [--text T | --file F] [--after SECTION] [--target 家]   加一節
  aos-directives rm       SECTION [--target 家]         刪一節（含子節）
  aos-directives export   [--out F.md] [--target 家]    人格寫成 md，給文字編輯器改
  aos-directives import   F.md [--target 家]            整份換成 md 檔的內容
  aos-directives versions [--target 家]                 列舊版本（每次改之前自動存）
  aos-directives revert   [ID] [--target 家]            還原成某個舊版本（省略＝最近一個）
  aos-directives resolve  FILE [--center DIR] [--pointer /x]   把 aos JSON 檔的 $env/$ref/$fmt 解開印出來
  aos-directives check    FILE [--center DIR]           只驗解不解得開
SECTION＝ls 的編號（0＝第一個標題之前的開頭）或標題文字（# 可省）。--file - ＝從 stdin 讀。
人格檔＝家裡 info.json 的 system 指的檔（沒寫＝prompts/system.json），格式 {"content": 字串}。'''

ARGS = {'ls': (0, 0), 'show': (0, 1), 'set': (1, 1), 'add': (1, 1), 'rm': (1, 1), 'export': (0, 0),
        'import': (1, 1), 'versions': (0, 0), 'revert': (0, 1), 'resolve': (1, 1), 'check': (1, 1)}
FLAGS = {'--target': 'target', '--text': 'text', '--file': 'file', '--after': 'after', '--out': 'out',
         '--center': 'center', '--pointer': 'pointer'}
ALLOWED = {'set': {'text', 'file'}, 'add': {'text', 'file', 'after'}, 'export': {'out'},
           'resolve': {'center', 'pointer'}, 'check': {'center'}}


class Usage(Exception):
    pass


def parse_argv(argv):
    if not argv or argv[0] in ('-h', '--help', 'help'):
        raise Usage(None)
    cmd, rest, pos, opts = argv[0], argv[1:], [], {}
    if cmd not in ARGS:
        raise Usage('不認得的子命令 %r' % cmd)
    i = 0
    while i < len(rest):
        a = rest[i]
        if a in ('-h', '--help'):
            raise Usage(None)
        if a in FLAGS:
            if i + 1 >= len(rest):
                raise Usage('%s 後面要接值' % a)
            key = FLAGS[a]
            if key in opts:
                raise Usage('%s 給了兩次' % a)
            opts[key] = rest[i + 1]
            i += 2
            continue
        if a.startswith('--'):
            raise Usage('不認得的選項 %s' % a)
        pos.append(a)
        i += 1
    lo, hi = ARGS[cmd]
    if not lo <= len(pos) <= hi:
        raise Usage('%s 要 %s 個參數' % (cmd, lo if lo == hi else '%d～%d' % (lo, hi)))
    allowed = ALLOWED.get(cmd, set()) | ({'target'} if cmd not in ('resolve', 'check') else set())
    extra = set(opts) - allowed
    if extra:
        raise Usage('%s 不收 %s' % (cmd, '、'.join('--' + k for k in sorted(extra))))
    if 'text' in opts and 'file' in opts:
        raise Usage('--text 跟 --file 只能給一個')
    if cmd == 'set' and 'text' not in opts and 'file' not in opts:
        raise Usage('set 要 --text 或 --file')
    return cmd, pos, opts


def _read_text(src, stdin):
    if src == '-':
        return stdin.read()
    try:
        return Path(src).read_text(encoding='utf-8')
    except (OSError, UnicodeError) as e:
        raise AgentError('ReadFailed', '讀不到 %s：%s' % (src, e))


def run(argv, stdin=None):
    stdin = sys.stdin if stdin is None else stdin
    cmd, pos, opts = parse_argv(argv)
    home = Path(os.path.abspath(os.path.expanduser(opts.get('target', '.'))))
    text = _read_text(opts['file'], stdin) if 'file' in opts else opts.get('text')
    if cmd == 'resolve':
        return cmd_resolve(pos[0], opts.get('center'), opts.get('pointer'))
    if cmd == 'check':
        return cmd_check(pos[0], opts.get('center'))
    if cmd == 'import':
        return cmd_import(home, pos[0], _read_text(pos[0], stdin))
    arg = pos[0] if pos else None
    return {'ls': lambda: cmd_ls(home), 'show': lambda: cmd_show(home, arg),
            'set': lambda: cmd_set(home, arg, text), 'add': lambda: cmd_add(home, arg, text or '', opts.get('after')),
            'rm': lambda: cmd_rm(home, arg), 'export': lambda: cmd_export(home, opts.get('out')),
            'versions': lambda: cmd_versions(home), 'revert': lambda: cmd_revert(home, arg)}[cmd]()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        out = run(argv)
    except Usage as e:
        if e.args[0]:
            print('aos-directives: Usage: %s' % e.args[0], file=sys.stderr)
        print(USAGE, file=sys.stderr if e.args[0] else sys.stdout)
        return 2 if e.args[0] else 0
    except (AgentError, aos_home.HomeError) as e:
        print('aos-directives: %s: %s' % (e.code, e.msg), file=sys.stderr)
        return 1
    if out:
        sys.stdout.write(out if out.endswith('\n') else out + '\n')
    return 0
