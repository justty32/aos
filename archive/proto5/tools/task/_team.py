"""task 工具包共用：讀 arguments、讀團隊設定（config.json）、往自己的 outbox 放申請、讀任務表、統一的錯誤格式。

約定（spec/team/templates.md、mail.md）：
- config.json 在本資料夾（牢裡是 /opt/tool/config.json），aos-team init 寫：
  {"member", "mail_to", "members", "outbox", "board", "tz"}；outbox／board 是工具看到的路徑（牢裡 /work/outbox、/work/board）。
- 申請寫成 <outbox>/<epoch ns>-<pid>-<member>.json：暫存檔（. 開頭）＋rename。郵差再驗一次身分與格式。
- 成功：純文字、退 0。失敗：stdout 最後一行 {"ok": false, "error": 代號, "message": …}、退 1。
"""
import datetime
import json
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TASK_ID = re.compile(r't-[0-9]{4,}(\.r[0-9]+)?\Z')


class ToolError(Exception):
    def __init__(self, code, message, **extra):
        super().__init__(message)
        self.code, self.message, self.extra = code, message, extra


def fail(code, message, **extra):
    raise ToolError(code, message, **extra)


def run(main):
    try:
        args = read_args()
        out = main(args, config())
        sys.stdout.write(out if out.endswith('\n') else out + '\n')
        return 0
    except ToolError as e:
        sys.stdout.write(json.dumps(dict({'ok': False, 'error': e.code, 'message': e.message}, **e.extra),
                                    ensure_ascii=False) + '\n')
        return 1
    except Exception as e:  # 沒料到的錯也照約定：最後一行 JSON
        sys.stdout.write(json.dumps({'ok': False, 'error': 'InternalError', 'message': '%s: %s' % (type(e).__name__, e)},
                                    ensure_ascii=False) + '\n')
        return 1


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


def config():
    path = os.path.join(HERE, 'config.json')
    try:
        with open(path, encoding='utf-8') as f:
            cfg = json.load(f)
    except FileNotFoundError:
        fail('ConfigInvalid', 'this tool is not set up for a team (no %s); ask the user to run aos-team init' % path)
    except (OSError, ValueError) as e:
        fail('ConfigInvalid', 'cannot read %s: %s' % (path, e))
    if not isinstance(cfg, dict) or not isinstance(cfg.get('member'), str):
        fail('ConfigInvalid', '%s has no "member"; ask the user to run aos-team init' % path)
    return cfg


def arg(args, name, kind, default=None, required=False):
    if name not in args or args[name] is None:
        if required:
            fail('BadArguments', 'missing required argument "%s"' % name)
        return default
    value = args[name]
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        names = {str: 'a string', int: 'an integer', bool: 'a boolean', list: 'an array', dict: 'an object'}
        fail('BadArguments', 'argument "%s" must be %s' % (name, names[kind]))
    if kind is str and (not value.strip() or '\0' in value):
        fail('BadArguments', 'argument "%s" must be a non-empty string' % name)
    return value


def only_keys(args, allowed):
    extra = sorted(set(args) - set(allowed))
    if extra:
        fail('BadArguments', 'unknown argument(s): %s (allowed: %s)' % (', '.join(extra), ', '.join(allowed)))


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec='seconds')


def send(cfg, kind, body):
    """把一份申請放進自己的 outbox；回 id。"""
    outbox = cfg.get('outbox')
    if not isinstance(outbox, str) or not os.path.isdir(outbox):
        fail('NoOutbox', 'outbox %s is not mounted; ask the user to run aos-agent check' % outbox)
    rid = '%d-%d-%s' % (time.time_ns(), os.getpid(), cfg['member'])
    obj = dict({'id': rid, 'from': cfg['member'], 'kind': kind, 'at': now_iso()}, **body)
    fd, tmp = tempfile.mkstemp(dir=outbox, prefix='.%s.' % rid, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False)
        os.rename(tmp, os.path.join(outbox, rid + '.json'))
        tmp = None
    except OSError as e:
        fail('WriteFailed', 'cannot write to outbox: %s' % e)
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)
    return rid


def board_dir(cfg):
    board = cfg.get('board')
    if not isinstance(board, str) or not os.path.isdir(board):
        fail('NoBoard', 'task board %s is not mounted; ask the user to run aos-agent check' % board)
    return board


def load_ticket(cfg, tid):
    if not TASK_ID.match(tid):
        fail('BadArguments', '%r is not a task id (like t-0001 or t-0001.r1)' % tid)
    path = os.path.join(board_dir(cfg), tid + '.json')
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        fail('NotFound', 'no task %s' % tid)
    except (OSError, ValueError) as e:
        fail('ReadFailed', 'cannot read task %s: %s' % (tid, e))


def tickets(cfg):
    out = []
    folder = board_dir(cfg)
    for name in sorted(os.listdir(folder)):
        if name.endswith('.json') and not name.startswith('.'):
            try:
                with open(os.path.join(folder, name), encoding='utf-8') as f:
                    t = json.load(f)
            except (OSError, ValueError):
                continue
            if isinstance(t, dict) and isinstance(t.get('id'), str):
                out.append(t)
    return out
