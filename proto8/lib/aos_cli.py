"""aos_cli：inst、loop、daemon 共用的命令列、三扇門（NORMS N-12 的程式範本）、`檔#/位置`（N-35）與指示詞（語法糖）。純標準庫。

    PROG [--key 值 ...] [TARGET | -] [-- argv...]

- 設定從哪來（N-21）：給 TARGET（`檔#/位置`）就讀那份檔、不讀 stdin；寫 `-` 讀 stdin；兩個都沒給＝從 `{}` 起
  （只靠旗標與 `--`）。檔與 stdin 都先解指示詞，基準＝呼叫者的 cwd。
- 旗標（N-22）：`--times 3` ＝設定的頂層 key `times`（`-` 換成 `_`），蓋過檔或 stdin 的值。每個旗標都要帶一個值；
  值先當 JSON 解（`3`、`null`、`true`），解不了就當字串。只認各程式給的那幾個純量 key，其他＝FlagUnknown。
- `--`（N-24）：後面整段交給程式自己（inst 拿去蓋 `argv`；不收的程式報 Usage）。
- stdin 是 JSON 串流（N-12）：設定只要一份，多了＝入口錯 `InputExtra`；壞尾丟掉。
- stdout／stderr 也是 JSON 串流：`emit()` 一份一行；錯誤 `{"error": {"code", "msg"}}`（N-29）。沒有「警告」。

`檔#/位置`（N-35；TARGET 與 `$ref` 同一套）：遇到第一個 `#` 就切（檔名含 `#` 不支援）；`#` 後面只認 `/` 開頭、
從那份檔的根算的位置，段落照 key 名或陣列的十進位索引；空段落忽略（`/a/`＝`/a`），名字是空字串、含 `/` 的 key 指不到；
空的或 `#/`＝整份。不對＝`PointerBad`。`split_target(target)` → (檔, 位置)、`target_id(realpath, 位置)` → id
（整份＝純 realpath，否則 `realpath#/位置`）、`locate(root, 位置, ident)` → 那一格的原值。

指示詞（C-48、N-45：只是把自己的檔拆小、讀環境變數的便利，設計不靠它）。一個物件只要有 `$` 開頭的 key 就是指示詞，
兩種都寫了只看 `$ref`，其餘 key 忽略：
- `{"$ref": "file.json#/a/0"}`：讀一份 JSON 的某個位置。檔名相對於 `base_dir`；位置從那份檔的根算（寫法同上）；
  取回來的值接著解（裡面的指示詞照它所在的那份檔算）。
- `{"$env": "NAME"}`：讀環境變數；不存在＝錯。
`resolve(doc, base_dir, ident="<input>", at=())` 解整份（`at`＝只解那一格，是整份檔的視窗：裡面的 `$ref` 照整份檔算），回新的值。
指示詞的錯一律 `DirectiveBad`（不認得、型別不對、變數沒有、檔讀不到或不是 JSON、繞回自己）；位置走不到＝`PointerBad`。
"""
import json
import os
import sys

__all__ = ["CliError", "config", "emit", "error", "expand", "is_int", "load_target", "locate", "parse_argv",
           "read_stream", "resolve", "split_target", "target_id"]


class CliError(Exception):
    """設定或命令列不對。`code`＝錯誤代號，`msg`＝白話，`str(e)`＝「代號: 白話」。各程式的錯誤類別繼承它。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg


def is_int(v, least=None):
    """JSON 整數（true／false 不算）；給了 least 就還要 ≥ least。各程式驗設定共用。"""
    return isinstance(v, int) and not isinstance(v, bool) and (least is None or v >= least)


def expand(v):
    """值的雙形（C-48、C-55）收成物件：物件照抄一份、純值包成 `{"val": v}`、None 照回 None。
    讀的人一律先 expand 再只看自己認得的 key。型別各程式自己驗。"""
    if v is None:
        return None
    return dict(v) if isinstance(v, dict) else {"val": v}


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


# ---- 檔#/位置 ----

def split_target(target):
    """命令列 TARGET → (檔, 位置 tuple)。遇到第一個 `#` 就切；位置只收 `/` 開頭；空的或 `/`＝整份 `()`。"""
    file, _, frag = target.partition("#")
    return file, _at(frag, target)


def target_id(path, pos):
    """id：整份＝`path`（realpath）；否則 `path#位置`。"""
    return path + "#" + _show(pos) if pos else path


def locate(root, pos, ident):
    """`root` 照位置走下去的原值（不解指示詞）；走不到＝`PointerBad`。"""
    return _walk(_Doc(ident, root), pos, ident)


def _at(at, where):
    """位置字串 → 位置 tuple。空＝整份；否則要 `/` 開頭，空段落忽略。"""
    if not at:
        return ()
    if not at.startswith("/"):
        raise CliError("PointerBad", "%s 的位置 %r 要以 / 開頭" % (where, at))
    return tuple(seg for seg in at[1:].split("/") if seg)


def _walk(doc, pos, where):
    cur = doc.root
    for tok in pos:
        if isinstance(cur, dict) and tok in cur:
            cur = cur[tok]
            continue
        if isinstance(cur, list):
            digits = tok.lstrip("0") or "0"
            if tok.isascii() and tok.isdigit() and len(digits) <= len(str(len(cur))) and int(digits) < len(cur):
                cur = cur[int(digits)]
                continue
        raise CliError("PointerBad", "%s 要的位置 %s 在 %s 裡走不到 %r" % (where, _show(pos), doc.ident, tok))
    return cur


def _show(pos):
    return "/" + "/".join(pos)


# ---- 指示詞 ----

class _Doc:
    def __init__(self, ident, root):
        self.ident = ident
        self.root = root


def resolve(doc, base_dir, ident="<input>", at=()):
    """把 `doc`（parse 好的 JSON 值）裡的指示詞全部解掉，回新的值（原本那份不動）。`base_dir`＝`$ref` 相對檔名的基準；
    `ident`＝doc 從哪來（檔案的 realpath；不是讀檔來的就用預設）；`at`＝只解這一格（整份檔的視窗）。"""
    d = _Doc(ident, doc)
    return _Resolver(os.path.abspath(base_dir)).node(_walk(d, at, ident), d, at, ())


class _Resolver:
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def node(self, value, doc, pos, stack):
        stack = stack + ((doc.ident, pos),)
        if isinstance(value, dict):
            if any(isinstance(k, str) and k.startswith("$") for k in value):
                return self.directive(value, doc, pos, stack)
            return {k: self.node(v, doc, pos + (k,), stack) for k, v in value.items()}
        if isinstance(value, list):
            return [self.node(v, doc, pos + (str(i),), stack) for i, v in enumerate(value)]
        return value

    def directive(self, d, doc, pos, stack):
        where = "%s:%s" % (doc.ident, _show(pos))
        if "$ref" in d:
            return self.ref(d["$ref"], stack, where)
        if "$env" in d:
            name = d["$env"]
            if not isinstance(name, str):
                raise CliError("DirectiveBad", "%s 的 $env 要是字串，不是 %s" % (where, type(name).__name__))
            if name not in os.environ:
                raise CliError("DirectiveBad", "%s 的 $env 找不到變數 %s" % (where, name))
            return os.environ[name]
        raise CliError("DirectiveBad", "%s 的 %s 不認得，只有 $ref、$env"
                       % (where, "、".join(repr(k) for k in d if isinstance(k, str) and k.startswith("$"))))

    def ref(self, spec, stack, where):
        if not isinstance(spec, str):
            raise CliError("DirectiveBad", "%s 的 $ref 要是字串，不是 %s" % (where, type(spec).__name__))
        file, frag = split_target(spec)
        if not file:
            raise CliError("DirectiveBad", "%s 的 $ref 要寫檔名（同一份檔裡要共用就拆成小檔）" % where)
        ident = os.path.realpath(os.path.join(self.base_dir, file))
        for s_ident, s_pos in stack:        # 指到正在解的位置本身或它的上層＝永遠解不完
            if s_ident == ident and s_pos[:len(frag)] == frag:
                walked = " → ".join("%s:%s" % (i, _show(p)) for i, p in stack + ((ident, frag),))
                raise CliError("DirectiveBad", "%s 的 $ref 繞回自己了：%s" % (where, walked))
        doc = _load(ident)
        return self.node(_walk(doc, frag, where), doc, frag, stack)


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise CliError("DirectiveBad", "讀不到 %s：%s" % (path, e))
    try:
        return _Doc(path, json.loads(raw))
    except ValueError as e:
        raise CliError("DirectiveBad", "%s 不是合法 JSON：%s" % (path, e))


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
                raise CliError("FlagUnknown", "不認得的旗標 %s" % a)
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
    file, pos = split_target(target)
    real = find(file) if find else os.path.realpath(file)
    doc = resolve(_read_json(real), os.getcwd(), real, pos)
    ident = target_id(real, pos)
    if not isinstance(doc, dict):
        raise CliError("FieldType", "%s 要是物件，不是 %s" % (ident, type(doc).__name__))
    return doc, ident


def _load_stdin():
    docs = read_stream(sys.stdin.read())
    if not docs:
        raise CliError("JsonSyntax", "stdin 沒有 JSON")
    if len(docs) > 1:
        raise CliError("InputExtra", "stdin 有 %d 份 JSON，設定只要一份" % len(docs))
    doc = resolve(docs[0], os.getcwd(), "<stdin>")
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
