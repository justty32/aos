"""base 工具包共用：讀 arguments、找工作根目錄、把路徑關在根目錄裡、統一的錯誤格式。

約定（proto5/tools/README.md）：
- cwd＝agent 家（aos-agent 預設）；arguments 從 stdin 來（JSON 字串）。
- 工作根目錄＝本資料夾 config.json 的 "root"；相對路徑相對 agent 家（＝cwd）；沒寫＝workspace。
- 成功：純文字印到 stdout、退 0。
- 失敗：stdout 最後一行印一個 JSON {"ok": false, "error": 代號, "message": 白話, …}、退 1。
  帶輸出的失敗（bash 退出碼非 0、逾時）先原樣印輸出，JSON 放最後一行。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_BYTES = 50 * 1024      # 單次輸出上限（位元組）
MAX_LINE = 2000            # 單行字元上限（read）


class ToolError(Exception):
    def __init__(self, code, message, output=None, **extra):
        super().__init__(message)
        self.code, self.message, self.output, self.extra = code, message, output, extra


def fail(code, message, output=None, **extra):
    raise ToolError(code, message, output, **extra)


def run(main):
    """包住工具主程式：main(args, root) 回要印的字串；ToolError 轉成 JSON 錯誤、退 1。"""
    try:
        args = read_args()
        root = work_root()
        out = main(args, root)
        sys.stdout.write(out if out.endswith('\n') else out + '\n')
        return 0
    except ToolError as e:
        if e.output:
            sys.stdout.write(e.output if e.output.endswith('\n') else e.output + '\n')
        sys.stdout.write(json.dumps(dict({'ok': False, 'error': e.code, 'message': e.message}, **e.extra),
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


def config_path():
    return os.path.join(HERE, 'config.json')


def work_root():
    """config.json 的 root（相對＝相對 cwd，也就是 agent 家）；沒檔或沒欄＝workspace。不存在＝RootMissing。"""
    root = 'workspace'
    cfg = config_path()
    if os.path.exists(cfg):
        try:
            with open(cfg, encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            fail('ConfigInvalid', 'cannot read %s: %s' % (cfg, e))
        if not isinstance(data, dict):
            fail('ConfigInvalid', '%s must be a JSON object' % cfg)
        root = data.get('root', root)
        if not isinstance(root, str) or not root:
            fail('ConfigInvalid', '%s: "root" must be a non-empty string' % cfg)
    root = os.path.realpath(os.path.expanduser(root))
    if not os.path.isdir(root):
        fail('RootMissing', 'project directory (work root) %s does not exist (set "root" in %s)' % (root, cfg))
    return root


def arg(args, name, kind, default=None, required=False):
    """取一個參數並驗型別；kind 是 str／int／bool（int 不收 bool）。"""
    if name not in args or args[name] is None:
        if required:
            fail('BadArguments', 'missing required argument "%s"' % name)
        return default
    value = args[name]
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        fail('BadArguments', 'argument "%s" must be %s' % (name, {str: 'a string', int: 'an integer',
                                                                    bool: 'a boolean'}[kind]))
    return value


def resolve(root, path, must_exist=True):
    """相對路徑相對 root；絕對路徑也收。解開符號連結後必須還在 root 裡，否則 OutsideRoot。"""
    if not isinstance(path, str) or not path:
        fail('BadArguments', 'path must be a non-empty string')
    if '\0' in path:
        fail('BadArguments', 'path must not contain NUL')
    full = os.path.realpath(os.path.join(root, os.path.expanduser(path)))
    if not inside(root, full):
        fail('OutsideRoot', '%s is outside the project directory %s' % (path, root))
    if must_exist and not os.path.exists(full):
        fail('NotFound', 'no such file or directory: %s' % path, path=path)
    return full


def inside(root, full):
    return full == root or full.startswith(root.rstrip(os.sep) + os.sep)


def rel(root, full):
    return os.path.relpath(full, root)


def write_atomic(full, content):
    """同目錄暫存檔再 rename；已有的檔保留權限位。"""
    tmp = '%s.aos-tmp-%d' % (full, os.getpid())
    try:
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        if os.path.exists(full):
            os.chmod(tmp, os.stat(full).st_mode & 0o7777)
        os.replace(tmp, full)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)



def truncate_tail(text, max_lines, max_bytes=MAX_BYTES):
    """保留結尾（bash 用：錯誤通常在最後）；回 (文字, 被砍掉幾行)。"""
    lines = text.splitlines(True)
    kept, size = [], 0
    for line in reversed(lines[-max_lines:]):
        b = len(line.encode('utf-8'))
        if size + b > max_bytes:
            if not kept:  # 單一行就超過上限：留它的尾巴
                kept.append(line.encode('utf-8')[-max_bytes:].decode('utf-8', 'ignore'))
            break
        kept.append(line)
        size += b
    kept.reverse()
    return ''.join(kept), len(lines) - len(kept)
