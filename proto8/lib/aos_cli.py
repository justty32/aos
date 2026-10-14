"""aos_cli：inst、loop、daemon 共用的命令列與三扇門（NORMS N-12 的程式範本）。純標準庫。

    PROG [--key 值 ...] [TARGET | -] [-- argv...]

- 設定從哪來（D-3）：給 TARGET（`檔#/位置`）就讀那份檔、不讀 stdin；寫 `-` 讀 stdin；兩個都沒給＝從 `{}` 起
  （只靠旗標與 `--`）。檔與 stdin 都用指示詞 lib 解，基準＝呼叫者的 cwd。
- 旗標（D-1）：`--times 3` ＝設定的頂層 key `times`（`-` 換成 `_`），蓋過檔或 stdin 的值。每個旗標都要帶一個值；
  值先當 JSON 解（`3`、`null`、`true`），解不了就當字串。只認各程式給的那幾個純量 key，其他＝UnknownFlag。
- `--`（D-2）：後面整段交給程式自己（inst 拿去蓋 `argv`；不收的程式報 Usage）。
- stdin 是 JSON 串流（N-12）：只看第一份，其餘在 stderr 警告一次（04 第 5 題）；壞尾丟掉（Q6）。
- stdout／stderr 也是 JSON 串流：`emit()` 一份一行；錯誤 `{"error": {"code", "msg"}}`、警告 `{"warning": {...}}`。
"""
import json
import os
import sys

from aos_directives import DirectiveError, resolve, split_target, target_id

__all__ = ["CliError", "config", "emit", "error", "load_target", "parse_argv", "read_stream", "warn"]


class CliError(Exception):
    """設定或命令列不對。`code`＝錯誤代號，`msg`＝白話，`str(e)`＝「代號: 白話」。各程式的錯誤類別繼承它。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg


# ---- 三扇門：JSON 串流 ----

def read_stream(text):
    """JSON 串流（一串 JSON 值，可單行可跨行）→ list。壞掉的尾巴丟掉（前面能解的算）。"""
    dec, out, i = json.JSONDecoder(), [], 0
    while True:
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            return out
        try:
            v, i = dec.raw_decode(text, i)
        except ValueError:
            return out
        out.append(v)


def emit(doc, stream=None):
    """往 stdout（或給的 stream）吐一份 JSON，一行。"""
    stream = stream or sys.stdout
    stream.write(json.dumps(doc, ensure_ascii=False) + "\n")
    stream.flush()


def error(code, msg):
    emit({"error": {"code": code, "msg": msg}}, sys.stderr)


def warn(code, msg):
    emit({"warning": {"code": code, "msg": msg}}, sys.stderr)


# ---- 命令列 ----

def parse_argv(args, flags):
    """args → (TARGET 或 None, 旗標 dict, `--` 後面的 list 或 None)。flags＝可以鏡射的頂層 key。"""
    target, over, rest, i = None, {}, None, 0
    while i < len(args):
        a = args[i]
        if a == "--":
            rest = args[i + 1:]
            break
        if a.startswith("--"):
            key = a[2:].replace("-", "_")
            if key not in flags:
                raise CliError("UnknownFlag", "不認得的旗標 %s" % a)
            if i + 1 >= len(args):
                raise CliError("Usage", "%s 少了值" % a)
            over[key] = _value(args[i + 1])
            i += 2
            continue
        if target is not None:
            raise CliError("Usage", "只能給一個 TARGET（或 -），多了 %s" % a)
        target, i = a, i + 1
    return target, over, rest


def _value(s):
    try:
        return json.loads(s)
    except ValueError:
        return s


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise CliError("ReadFailed", "讀不到 %s：%s" % (path, e))
    try:
        return json.loads(raw)
    except ValueError as e:
        raise CliError("JsonSyntax", "%s 不是合法 JSON：%s" % (path, e))


def load_target(target, find=None):
    """TARGET（`檔#/位置`）→ (解好的那一格 dict, id)。id＝realpath（有位置就接 `#/位置`）。
    `find(檔)` → realpath，可換（inst 的 TARGET 可以是資料夾）。"""
    try:
        file, pos = split_target(target)
        real = find(file) if find else os.path.realpath(file)
        root = _read_json(real)
        doc = resolve(root, os.getcwd(), real, pos)
    except DirectiveError as e:
        raise CliError(e.code, e.msg)
    ident = target_id(real, pos)
    if not isinstance(doc, dict):
        raise CliError("FieldType", "%s 要是物件，不是 %s" % (ident, type(doc).__name__))
    return doc, ident


def _load_stdin():
    docs = read_stream(sys.stdin.read())
    if not docs:
        raise CliError("JsonSyntax", "stdin 沒有 JSON")
    if len(docs) > 1:
        warn("ExtraInput", "stdin 有 %d 份 JSON，只看第一份" % len(docs))
    try:
        doc = resolve(docs[0], os.getcwd(), "<stdin>")
    except DirectiveError as e:
        raise CliError(e.code, e.msg)
    if not isinstance(doc, dict):
        raise CliError("FieldType", "stdin 的設定要是物件，不是 %s" % type(doc).__name__)
    return doc


def config(args, flags, find=None):
    """命令列 → (設定 dict, id, 是不是從 stdin 來, `--` 後面的 list 或 None)。
    id＝設定裡的 `id`（字串）＞ TARGET 的 id ＞ None。旗標蓋過檔或 stdin。"""
    target, over, rest = parse_argv(args, flags)
    ident, piped = None, target == "-"
    if piped:
        doc = _load_stdin()
    elif target is not None:
        doc, ident = load_target(target, find)
    else:
        doc = {}
    doc = dict(doc, **over)
    if isinstance(doc.get("id"), str):
        ident = doc["id"]
    return doc, ident, piped, rest
