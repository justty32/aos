"""aos 指示詞：讓 JSON 裡某一格的值「從別處來」。純函式庫，只用標準庫。

入口只有一個：`resolve(doc, base_dir, ident="<input>")`——把整份 JSON 裡的指示詞全部解掉，回一份新的 JSON（不動原本那份）。
`base_dir` 是相對檔名的基準路徑，整趟都用它，進了別的檔也不換。
`ident` 是 doc 從哪來（讀檔來的就給那個檔的 realpath），錯誤訊息裡用它指出是哪份檔；`$ref` 指回同一個檔也算同一份。

兩種指示詞。一個物件只要有 `$` 開頭的 key 就算指示詞物件；兩種都寫了只看 `$ref`，其餘 key 一律忽略：

- `{"$ref": "file.json#/a/0"}`：讀一份 JSON 的某個位置。
  - `#` 前面是檔名：相對檔名從 `base_dir` 起算；空字串＝目前這份文件（不重讀）。
  - `#` 後面是位置；也可以另寫 `"$at": "/a/0"`，有 `$at` 就以 `$at` 為準。都沒寫＝整份。
  - 位置開頭 `/`＝從那份文件的根算；`./`、`../`＝從「目前位置」算：目前文件是這個指示詞所在的位置，
    別的檔是那份檔的根。段落照 JSON pointer：`~1`→`/`、`~0`→`~`，陣列用十進位索引。
  - 取回來的值會接著解：裡面的指示詞以「它所在的那份文件、那個位置」為準。
- `{"$env": "NAME"}`：讀環境變數 `NAME`。不存在＝錯誤；存在但空＝空字串。

錯了一律丟 `DirectiveError`，`code` 是下面七種之一：
`UnknownDirective`、`DirectiveValueTypeMismatch`、`EnvironmentVariableMissing`、
`ReferenceReadFailed`、`ReferenceJsonInvalid`、`ReferencePointerInvalid`、`ReferenceCycle`。

命令列 TARGET 的 `檔#/位置`（aos_inst、aos_loop、aos_daemon 共用，位置的寫法同 `$ref`）：
- `split_target(target)` → (檔, 位置)：遇到第一個 `#` 就切（檔名含 `#` 的不支援）；位置只收 `/` 開頭，
  空的或只有 `/`＝整份（`()`）；段落規矩同 `$ref`（`~1`、`~0`、`.`、`..`）。不對＝`ReferencePointerInvalid`。
- `target_id(realpath, 位置)` → id：整份＝純 realpath；否則 realpath ＋ `#` ＋ 位置（正規化過的 JSON pointer）。
- `locate(root, 位置, ident)` → 那一格的原值（不解指示詞）；走不到＝`ReferencePointerInvalid`。
- `resolve(..., at=位置)` 只解那一格：是整份檔的一個視窗，裡面的 `$ref` 位置照整份檔算（`#/` 是檔的根、`../` 可以往外摸）。
"""
import json
import os

__all__ = ["DirectiveError", "locate", "resolve", "split_target", "target_id"]


class DirectiveError(Exception):
    """指示詞被拒。不是程式炸了，是這份 JSON 有問題。`code` 是錯誤代號，`msg` 是白話，`str(e)`＝「代號: 白話」。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code
        self.msg = msg


def resolve(doc, base_dir, ident="<input>", at=()):
    """把 `doc`（已經 parse 好的 JSON 值）裡的指示詞全部解掉，回新的值。`base_dir`＝相對檔名的基準路徑；
    `ident`＝doc 從哪來（檔案的 realpath；不是讀檔來的就用預設）。
    `at`＝只解 doc 裡這一格（位置 tuple，`split_target()` 給的）；裡面的指示詞照它在整份 doc 裡的位置解。"""
    d = _Doc(ident, doc)
    return _Resolver(os.path.abspath(base_dir)).node(_walk(d, at, ident), d, at, ())


def split_target(target):
    """命令列 TARGET → (檔, 位置 tuple)。遇到第一個 `#` 就切；位置只收 `/` 開頭，空的或只有 `/`＝整份 `()`。"""
    file, _, frag = target.partition("#")
    if frag in ("", "/"):
        return file, ()
    if not frag.startswith("/"):
        raise DirectiveError("ReferencePointerInvalid", "%s 的位置 %r 要以 / 開頭" % (target, frag))
    return file, _at(frag, (), target)


def target_id(path, pos):
    """id：整份＝`path`（realpath）；否則 `path#位置`（位置正規化成 JSON pointer）。"""
    return path + "#" + _show(pos) if pos else path


def locate(root, pos, ident):
    """`root` 照位置走下去的原值（不解指示詞）；走不到＝`ReferencePointerInvalid`。"""
    return _walk(_Doc(ident, root), pos, ident)


class _Doc:
    """一份文件：`ident`（檔案＝realpath；傳進來的那份＝resolve 的 ident）＋ `root`。"""

    def __init__(self, ident, root):
        self.ident = ident
        self.root = root


class _Resolver:
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def node(self, value, doc, pos, stack):
        """解 `doc` 裡位置 `pos` 的值。`stack`＝正在解的 (文件, 位置) 一路下來，拿來抓循環。"""
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
            return self.ref(d["$ref"], d.get("$at", _NO_AT), doc, pos, stack, where)
        if "$env" in d:
            name = d["$env"]
            if not isinstance(name, str):
                raise DirectiveError("DirectiveValueTypeMismatch",
                                     "%s 的 $env 要是字串，不是 %s" % (where, type(name).__name__))
            if name not in os.environ:
                raise DirectiveError("EnvironmentVariableMissing", "%s 的 $env 找不到變數 %s" % (where, name))
            return os.environ[name]
        raise DirectiveError("UnknownDirective",
                             "%s 的 %s 不認得，只有 $ref、$env"
                             % (where, "、".join(repr(k) for k in d if isinstance(k, str) and k.startswith("$"))))

    def ref(self, spec, at, doc, pos, stack, where):
        if not isinstance(spec, str):
            raise DirectiveError("DirectiveValueTypeMismatch",
                                 "%s 的 $ref 要是字串，不是 %s" % (where, type(spec).__name__))
        file, hashed, frag = spec.partition("#")
        if at is _NO_AT:
            at = frag if hashed else None
        elif not isinstance(at, str):
            raise DirectiveError("DirectiveValueTypeMismatch",
                                 "%s 的 $at 要是字串，不是 %s" % (where, type(at).__name__))
        if file == "":
            ident, here = doc.ident, pos
        else:
            ident, here = os.path.realpath(os.path.join(self.base_dir, file)), ()
        target = _at(at, here, where)
        # 目標是任何一個正在解的位置本身或它的上層 → 取回來的東西裡又有自己，永遠解不完
        for s_ident, s_pos in stack:
            if s_ident == ident and s_pos[:len(target)] == target:
                walked = " → ".join("%s:%s" % (i, _show(p)) for i, p in stack + ((ident, target),))
                raise DirectiveError("ReferenceCycle", "%s 的 $ref 繞回自己了：%s" % (where, walked))
        if ident != doc.ident:
            doc = _load(ident)
        return self.node(_walk(doc, target, where), doc, target, stack)


_NO_AT = object()


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise DirectiveError("ReferenceReadFailed", "讀不到 %s：%s" % (path, e))
    try:
        return _Doc(path, json.loads(raw))
    except ValueError as e:
        raise DirectiveError("ReferenceJsonInvalid", "%s 不是合法 JSON：%s" % (path, e))


def _at(at, here, where):
    """位置字串 → 絕對位置（token 的 tuple）。`None`＝整份。"""
    if at is None:
        return ()
    if at.startswith("/"):
        pos, segs = [], at[1:].split("/")
    elif at in (".", "..") or at.startswith("./") or at.startswith("../"):
        pos, segs = list(here), at.split("/")
    else:
        raise DirectiveError("ReferencePointerInvalid", "%s 的位置 %r 要以 /、./ 或 ../ 開頭" % (where, at))
    for seg in segs:
        if seg == ".":
            continue
        if seg == "..":
            if not pos:
                raise DirectiveError("ReferencePointerInvalid", "%s 的位置 %r 用 .. 爬過文件的根了" % (where, at))
            pos.pop()
            continue
        pos.append(seg.replace("~1", "/").replace("~0", "~"))
    return tuple(pos)


def _walk(doc, pos, where):
    """從文件的根照位置走下去；走不到＝`ReferencePointerInvalid`。"""
    cur = doc.root
    for tok in pos:
        if isinstance(cur, dict) and tok in cur:
            cur = cur[tok]
            continue
        if isinstance(cur, list):
            digits = tok.lstrip("0") or "0"
            # 只收 ASCII 十進位；先比長度，超長的數字不轉 int
            if tok.isascii() and tok.isdigit() and len(digits) <= len(str(len(cur))) and int(digits) < len(cur):
                cur = cur[int(digits)]
                continue
        raise DirectiveError("ReferencePointerInvalid",
                             "%s 要的位置 %s 在 %s 裡走不到 %r" % (where, _show(pos), doc.ident, tok))
    return cur


def _show(pos):
    """位置顯示成 JSON pointer：根＝`/`。"""
    return "/" + "/".join(t.replace("~", "~0").replace("/", "~1") for t in pos)
