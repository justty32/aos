"""note 工具共用：讀 arguments、找筆記檔、flock 讀改寫、統一的錯誤格式（跟 tools/base/_common.py 同風格，
但這支自己獨立一份——notes 不 import base，見 proto5/tools/README.md）。

約定：
- cwd＝agent 家（沒關牢時）；arguments 從 stdin 來（JSON 字串）。
- 筆記檔＝環境變數 AOS_NOTES_FILE（有設就優先）；否則本資料夾 config.json 的 "file"
  （絕對路徑照用、相對路徑相對 cwd）；都沒有：關牢（有 AOS_TOOL_ROOT）＝/work/notes/notes.json，
  不關牢＝notes/notes.json（相對 cwd＝agent 家）。
- 存檔格式是 wf-table/1（見 workflows/common/data-files.md）：
  {"contract": "wf-table/1", "source": "", "extracted": "YYYY-MM-DD",
   "columns": ["key", "text", "tags", "at"], "rows": [{"key", "text", "tags": "a,b", "at": ISO 時間}]}。
- 成功：純文字印到 stdout、退 0。失敗：stdout 最後一行印 JSON {"ok": false, "error": 代號, "message": 白話}、退 1。
"""
import contextlib
import fcntl
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
COLUMNS = ['key', 'text', 'tags', 'at']
DEFAULT_FILE = 'notes/notes.json'
LOCK_TIMEOUT = 10.0


class ToolError(Exception):
    def __init__(self, code, message, **extra):
        super().__init__(message)
        self.code, self.message, self.extra = code, message, extra


def fail(code, message, **extra):
    raise ToolError(code, message, **extra)


def report(e):
    sys.stdout.write(json.dumps(dict({'ok': False, 'error': e.code, 'message': e.message}, **e.extra),
                                ensure_ascii=False) + '\n')
    return 1


def run(main):
    """包住 note 主程式：main(args) 回要印的字串；ToolError 轉成 JSON 錯誤、退 1。"""
    try:
        args = read_args()
        out = main(args)
        sys.stdout.write(out if out.endswith('\n') else out + '\n')
        return 0
    except ToolError as e:
        return report(e)
    except Exception as e:  # 沒料到的錯也要照約定：最後一行 JSON
        return report(ToolError('InternalError', '%s: %s' % (type(e).__name__, e)))


def read_args():
    raw = sys.stdin.buffer.read().decode('utf-8', 'replace')
    if not raw.strip():
        return {}
    try:
        args = json.loads(raw)
    except ValueError as e:
        fail('BadArguments', 'arguments is not valid JSON: %s' % e)
    if not isinstance(args, dict):
        fail('BadArguments', 'arguments must be a JSON object')
    return args


def arg(args, name, kind, default=None, required=False):
    """取一個參數並驗型別；kind 是 str／int／list。字串不收 NUL。"""
    if name not in args or args[name] is None:
        if required:
            fail('BadArguments', 'missing required argument "%s"' % name)
        return default
    value = args[name]
    if kind is list:
        if not isinstance(value, list):
            fail('BadArguments', 'argument "%s" must be an array' % name)
        return value
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        fail('BadArguments', 'argument "%s" must be %s'
             % (name, {str: 'a string', int: 'an integer'}[kind]))
    if kind is str and '\0' in value:
        fail('BadArguments', 'argument "%s" must not contain NUL characters' % name)
    return value


def today():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _config_file():
    cfg = os.path.join(HERE, 'config.json')
    if not os.path.exists(cfg):
        return None
    try:
        with open(cfg, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        fail('ConfigInvalid', 'cannot read %s: %s' % (cfg, e))
    if not isinstance(data, dict):
        fail('ConfigInvalid', '%s must be a JSON object' % cfg)
    value = data.get('file')
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        fail('ConfigInvalid', '%s: "file" must be a non-empty string' % cfg)
    return value


JAIL_NOTES = '/work/notes'


def notes_path():
    """算筆記檔絕對路徑：AOS_NOTES_FILE 優先，否則 config.json 的 file，否則預設。

    預設：關在牢裡（有 AOS_TOOL_ROOT）＝/work/notes/notes.json（要掛一個叫 notes 的可寫資料夾），
    不關牢＝cwd（agent 家）的 notes/notes.json。人用的 aos-agent notes 照同一條規則找（lib/aos_agent_notes.py）。
    """
    value = os.environ.get('AOS_NOTES_FILE') or _config_file()
    if value is not None and os.environ.get('AOS_TOOL_ROOT') and not os.path.isabs(os.path.expanduser(value)):
        # 關牢時相對路徑會相對牢裡的起點，人看的 aos-agent notes 對不上（astra M6）：要寫 /work/<名>/…
        fail('ConfigInvalid', 'notes file %r is relative; inside the jail it must be /work/<mount>/…' % value)
    if value is None and os.environ.get('AOS_TOOL_ROOT'):
        if not os.path.isdir(JAIL_NOTES):
            fail('ConfigInvalid', 'no notes folder mounted at %s; ask the user to run: '
                 'aos-agent access set notes <folder> --rw' % JAIL_NOTES)
        value = JAIL_NOTES + '/notes.json'
    return os.path.abspath(os.path.expanduser(value or DEFAULT_FILE))


def default_table():
    return {'contract': 'wf-table/1', 'source': '', 'extracted': today(), 'columns': list(COLUMNS), 'rows': []}


def validate_table(path, data):
    if not isinstance(data, dict):
        fail('ConfigInvalid', '%s must be a JSON object (wf-table/1)' % path)
    rows = data.get('rows')
    if not isinstance(rows, list):
        fail('ConfigInvalid', '%s: "rows" must be a list (wf-table/1)' % path)
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get('key'), str) or not isinstance(row.get('text'), str):
            fail('ConfigInvalid', '%s: rows[%d] must have a string "key" and "text" (wf-table/1)' % (path, i))


def read_table(path):
    """檔不在＝空表；壞掉（不是 JSON、不是 wf-table 形狀）＝ConfigInvalid（不覆寫）。"""
    if not os.path.exists(path):
        return default_table()
    try:
        with open(path, encoding='utf-8') as f:
            raw = f.read()
    except OSError as e:
        fail('ReadFailed', 'cannot read %s: %s' % (path, e))
    try:
        data = json.loads(raw)
    except ValueError as e:
        fail('ConfigInvalid', '%s is not valid JSON: %s' % (path, e))
    validate_table(path, data)
    return data


def write_table(path, table):
    """同資料夾暫存檔（. 開頭 .tmp 結尾）＋ os.replace；每次寫都刷新 extracted。"""
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    table = dict(table, extracted=today())
    fd, tmp = tempfile.mkstemp(dir=parent, prefix='.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(table, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, path)
        tmp = None
    except OSError as e:
        fail('WriteFailed', 'cannot write %s: %s' % (path, e))
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


@contextlib.contextmanager
def locked(path):
    """筆記檔旁邊的 .notes.lock：獨占、阻塞，最多等 10 秒，逾時 Busy。"""
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    lock_path = os.path.join(parent, '.notes.lock')
    lock_file = open(lock_path, 'a')
    try:
        deadline = time.monotonic() + LOCK_TIMEOUT
        while True:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    fail('Busy', 'notes file is busy (another note op holds the lock for %gs): %s'
                         % (LOCK_TIMEOUT, lock_path))
                time.sleep(0.05)
        yield
    finally:
        lock_file.close()
