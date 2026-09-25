"""`aos-directives` 的人格檔與分節：prompts/system.json 讀寫與版本（.versions/、留最近 KEEP 份），Markdown 標題分節、挑節、換節內容。"""
import os
import sys
import time
from pathlib import Path

import aos_home
from aos_agent_home import AgentError, read_info_doc, resolve_field
from aos_directives import Context

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


def read_persona(path, for_write=False, missing_ok=True):
    """回 (整個物件, content)。檔不在＝({}, '')（missing_ok=False＝NotFound，讀舊版本用）。"""
    if not path.exists():
        if not missing_ok:
            raise AgentError('NotFound', '版本檔 %s 不在了（可能剛被別的指令淘汰）' % path)
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
    try:
        vid = save_version(path, obj)
        new = dict(obj) if obj else {}
        new['content'] = content
        path.parent.mkdir(parents=True, exist_ok=True)
        aos_home.write_json(path, new, indent=2)
    except OSError as e:
        raise AgentError('WriteFailed', '寫不進 %s：%s' % (path, e.strerror or e))
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
