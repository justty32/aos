import json
import math
import os
import pwd
import re
import time
from pathlib import Path

MAX_INT = 9007199254740991
MAX_LINE = 262144
ID_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z')


class Fault(Exception):
    def __init__(self, code, message, exit_code=125, rpc_code=-32000):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.rpc_code = rpc_code


def pairs_unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('重複 key: ' + key)
        obj[key] = value
    return obj


def reject_constant(value):
    raise ValueError('非有限數: ' + value)


def loads(raw):
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    obj = json.loads(raw, object_pairs_hook=pairs_unique, parse_constant=reject_constant)
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('非有限數')
        if isinstance(value, dict):
            for v in value.values():
                finite(v)
        elif isinstance(value, list):
            for v in value:
                finite(v)
    finite(obj)
    return obj


def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def read_json(path):
    return loads(Path(path).read_bytes())


def integer(value, minimum=0, maximum=MAX_INT):
    return type(value) is int and minimum <= value <= maximum


def node_id(value):
    return (isinstance(value, str) and value.startswith('/') and value != '/'
            and '\0' not in value and all(x not in ('', '.', '..') for x in value.split('/')[1:]))


def fields(obj, allowed, required=()):
    if not isinstance(obj, dict) or set(obj) - set(allowed) or set(required) - set(obj):
        raise ValueError('欄位缺少、未知或不是物件')


def uid(value, inherited=None):
    if value == '' or value is None:
        return os.getuid() if inherited is None else inherited
    if integer(value):
        return value
    if isinstance(value, str):
        try:
            return pwd.getpwnam(value).pw_uid
        except KeyError:
            pass
    raise Fault('UserInvalid', '帳號不存在或 user 格式不合法')


def inst_source(target):
    target = Path(target)
    if target.is_dir():
        source = target / '.aos/inst.json'
        if not source.exists():
            source = target / 'inst.json'
        base = target
    else:
        source, base = target, target.parent
    if not source.is_file():
        raise Fault('ReadFailed', '找不到 inst: ' + str(source), 2)
    return source, base


def read_inst(target):
    source, base = inst_source(target)
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise Fault('ReadFailed', str(exc))
    return raw, source, base


def now_ms():
    return time.time_ns() // 1000000


def within(path, root):
    try:
        Path(path).relative_to(root)
        return True
    except ValueError:
        return False


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish_new(path, obj):
    """link() publishes a complete fsynced temporary file without overwriting."""
    import tempfile
    path = Path(path)
    temporary = path.parent / '.tmp'
    temporary.mkdir(exist_ok=True)
    fd, name = tempfile.mkstemp(dir=temporary)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encode(obj))
            stream.flush()
            os.fsync(stream.fileno())
        os.link(name, path)
        sync_dir(path.parent)
    finally:
        os.unlink(name)
