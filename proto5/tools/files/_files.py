"""files 工具包（json_edit、md_section）共用：讀檔、sha、expect_sha、寫前檢查（信任資料、保護檔名）。

根目錄、錯誤格式、路徑關在根目錄裡：一律用 _common.py（跟 base 同一份，不另外算根）。
"""
import contextlib
import fcntl
import hashlib
import json
import os
import time

from _common import HERE, fail, open_regular, write_atomic, rel
import _trust

MAX_FILE = 10 * 1024 * 1024
SHA_LEN = 16
DEFAULT_PROTECTED = ('SESSION-LOG.md', 'WAIT_USER.md')


@contextlib.contextmanager
def locked(full, wait=10.0):
    """寫的人之間互斥：flock 檔案所在的資料夾（資料夾不會被 rename，檔會）。
    讀、比 expect_sha、改、寫整段都在鎖內，兩個人不會都比對通過再互蓋（審查 M2）。等 wait 秒拿不到＝Busy。
    只有走這套的寫者（json_edit、md_section、aos-json）互斥；base 的 write／edit 不拿這把。"""
    parent = os.path.dirname(full)
    os.makedirs(parent, exist_ok=True)
    fd = os.open(parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_CLOEXEC', 0))
    try:
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    fail('Busy', 'another edit of a file in %s is still running; try again in a moment'
                         % os.path.basename(parent))
                time.sleep(0.05)
        yield
    finally:
        os.close(fd)


def sha(data):
    return hashlib.sha256(data).hexdigest()[:SHA_LEN]


def read_text(root, full, path):
    """回 (文字, 原始位元組)；不是 UTF-8＝BinaryFile。"""
    with open_regular(root, full, path, max_bytes=MAX_FILE) as f:
        data = f.read()
    try:
        return data.decode('utf-8'), data
    except UnicodeDecodeError:
        fail('BinaryFile', '%s is not UTF-8 text' % path)


def check_sha(expect, data, path):
    if expect is None:
        return
    now = sha(data)
    if expect != now:
        fail('Conflict', '%s changed since you read it (expect_sha %s, now %s); read it again (op get) and '
             'redo your change on the new content' % (path, expect, now), sha=now)


def protected_names():
    """config.json 的 "protected"（檔名清單）；沒寫＝SESSION-LOG.md、WAIT_USER.md（書記在寫）。"""
    try:
        with open(os.path.join(HERE, 'config.json'), encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return DEFAULT_PROTECTED
    names = data.get('protected', DEFAULT_PROTECTED) if isinstance(data, dict) else DEFAULT_PROTECTED
    return tuple(n for n in names if isinstance(n, str)) if isinstance(names, list) else DEFAULT_PROTECTED


def guard_write(root, full, path):
    """寫之前：保護檔名、信任資料。"""
    if os.path.basename(full) in protected_names():
        fail('Protected', '%s is kept by the team clerk, not edited directly; send a request to the lead '
             'instead (you cannot fix this yourself)' % path)
    label = _trust.blocked(full)
    if label:
        fail('TrustedData', "%s is the agent's %s (trusted data); tools may not change it. This is not "
             'something you can fix; ask the user' % (path, label))


def save(root, full, text, path):
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        write_atomic(root, full, text, path)
    except OSError as e:
        fail('WriteFailed', 'cannot write %s: %s' % (path, e.strerror or e))
    return rel(root, full)
