"""inst.json 的指示詞展開、參照解析與欄位型別驗證。"""
import json
import os
import re

DIRECTIVES = ("$env", "$ref", "$fmt")
# $fmt 的模板：只有 ${…} 會被代換，單獨的 $ 與 $NAME 都是字面
_FMT = re.compile(r"\$\{([^{}]*)\}")


class InstError(Exception):
    """格式／解析被拒。不是程式炸了，是這份 inst.json 有問題。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code


def abspath(base, p):
    """inst.json 裡的路徑：絕對的照字面用，相對的從 base 起算。"""
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))


def _envs(v, cwd, inst):
    """`envs` 位置：普通的「變數名→值」物件，或清空型式 `{"$opt":"clear","$envs":{…}}`。

    清空型式先把繼承來的環境整個丟掉，再只放 `$envs` 裡的（`$envs` 可省＝完全空的環境）。
    兩者都可以是指示詞解出來的（整包 `$ref` 從別的檔拿），`$envs` 一樣還能再是指示詞。
    key 是純字串、不解指示詞，而且不能 `$` 開頭——那種 key 一出現整包就被當指示詞看了。
    """
    where = "envs"
    if isinstance(v, dict) and "$opt" in v:
        inst["envs_clear"] = True
        where = "envs 的 $envs"
        v = _resolve(_opt(v, "envs", "clear"), cwd, where, [])
    if not isinstance(v, dict):
        raise InstError("FieldTypeMismatch", "%s 要是物件，不是 %s" % (where, type(v).__name__))
    for k, val in v.items():
        if k == "" or "=" in k or k.startswith("$"):
            raise InstError("EnvKeyInvalid",
                            "envs 的 key 不能是空字串、含 '='、或 $ 開頭：%r" % (k,))
        w = "envs[%r]" % k
        inst["envs"][k] = _str(_resolve(val, cwd, w, []), w)


def _resolve(v, base, where, chain):
    """任何一個值的位置：是指示詞就解開，解出來的當成本來寫在那裡，再看一次（巢狀）。

    `chain` 是這條鏈走過的 `$ref` 身分（realpath ＋ pointer），繞回來＝ReferenceCycle。
    """
    while isinstance(v, dict) and _is_directive(v):
        v, chain = _apply(v, base, where, chain)
    return v


def _is_directive(d):
    """一個 dict 只要有 `$` 開頭的 key 就是指示詞；`$opt` 的兩種型式除外（stderr 與
    envs 自己認，因為清空型式是唯一可以有兩個 key 的）。"""
    return "$opt" not in d and any(k.startswith("$") for k in d)


def _apply(d, base, where, chain):
    """解一層指示詞，回 `(值, 新的鏈)`。指示詞＝剛好一個 key、值一定是字串。"""
    if len(d) != 1:
        raise InstError("DirectiveKeyCountInvalid",
                        "%s 的指示詞要剛好一個 key，這個有 %d 個" % (where, len(d)))
    key, val = next(iter(d.items()))
    if key not in DIRECTIVES:
        raise InstError("UnknownDirective",
                        "%s 的指示詞 %r 不認得，只有 %s（外加 stderr／envs 的 $opt）"
                        % (where, key, "／".join(DIRECTIVES)))
    if not isinstance(val, str):
        raise InstError("DirectiveValueTypeMismatch",
                        "%s 的 %s 值要是字串，不是 %s" % (where, key, type(val).__name__))
    if key == "$env":
        return _lookup(val, where, "$env"), chain
    if key == "$fmt":
        return _fmt(val, where), chain
    return _ref(val, base, where, chain)


def _opt(d, where, want):
    """`$opt` 的兩種型式：`stderr` 的 merge、`envs` 的 clear。回清空型式的 `$envs`。

    `want=None`＝這個位置根本不准 `$opt`（一定丟）。
    """
    extra = [k for k in d if k not in ("$opt", "$envs")]
    if extra:
        raise InstError("DirectiveKeyCountInvalid",
                        "%s 的 $opt 型式只能有 $opt 與 $envs，多了 %s"
                        % (where, "、".join(repr(k) for k in extra)))
    v = d["$opt"]
    if not isinstance(v, str):
        raise InstError("DirectiveValueTypeMismatch",
                        "%s 的 $opt 值要是字串，不是 %s" % (where, type(v).__name__))
    if want is None:
        raise InstError("UnknownDirective",
                        "%s 不能用 $opt（只有 stderr 的 merge 與 envs 的 clear）" % where)
    if v != want:
        raise InstError("UnknownOption",
                        "%s 的 $opt 只認得 %r，不是 %r" % (where, want, v))
    return d.get("$envs", {})


def _str(v, where):
    """字串位置：解完之後不是字串就是型別錯（`$opt` 放錯地方也在這裡被抓）。"""
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and "$opt" in v:
        _opt(v, where, None)
    raise InstError("FieldTypeMismatch",
                    "%s 要是字串或指示詞，不是 %s" % (where, type(v).__name__))


def _lookup(name, where, kind):
    """從 **aos-exec 自己的**環境取一個變數。不存在＝錯誤；存在但空＝空字串。"""
    if name not in os.environ:
        raise InstError("EnvironmentVariableMissing",
                        "%s 的 %s 找不到變數 %s（存在但空字串才算空字串）"
                        % (where, kind, name))
    return os.environ[name]


def _fmt(s, where):
    """{"$fmt":"${env:PATH}:/opt/bin"}：接字串用的。

    寫法沿用 repo 既有的那套（`wf/workflows/common/data-files-fmt.md`），這裡只有
    `env:` 這一個 namespace：

    - 只有 `${…}` 會被代換；單獨的 `$` 與 `$NAME` 都是**字面**，不展開也不用跳脫。
    - `${env:NAME}` 讀 **aos-exec 自己的**環境（不是 inst.json 的 `envs`，跟 `$env`
      同一個來源）。不存在＝錯誤；存在但空＝空字串。
    - 不是 `env:` 開頭的 `${…}`＝不認得的變數＝錯誤，不猜。
    - **展開一次、不再掃結果**：換進來的值裡再出現 `${…}` 就是字面。
    """
    def one(m):
        name = m.group(1)
        if not name.startswith("env:"):
            raise InstError("UnknownFormatVariable",
                            "%s 的 $fmt 不認得變數 ${%s}（這一版只有 ${env:NAME}）"
                            % (where, name))
        return _lookup(name[len("env:"):], where, "$fmt 的 ${env:…}")
    return _FMT.sub(one, s)


def _ref(spec, base, where, chain):
    """{"$ref":"file.json#/a/b"}：相對於 base 讀檔、`#` 後面是 RFC 6901 JSON Pointer。

    取回來的值**原樣**當成本來寫在那個位置（字串、陣列、物件都行，型別由那個位置自己
    驗）；又是指示詞就繼續解。同一條鏈再撞到同一個「realpath ＋ pointer」＝循環。
    """
    rel, sep, pointer = spec.partition("#")
    path = os.path.realpath(abspath(base, rel))
    ident = (path, pointer if sep else "")
    if ident in chain:
        walked = " → ".join("%s#%s" % c for c in chain + [ident])
        raise InstError("ReferenceCycle", "%s 的 $ref 繞回自己了：%s" % (where, walked))
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise InstError("ReferenceReadFailed", "%s 的 $ref 讀不到 %s：%s" % (where, path, e))
    try:
        doc = json.loads(raw)
    except ValueError as e:
        raise InstError("ReferenceJsonInvalid",
                        "%s 的 $ref 目標 %s 不是合法 JSON：%s" % (where, path, e))
    return _pointer(doc, ident[1], where, path), chain + [ident]


def _pointer(doc, pointer, where, path):
    """RFC 6901：空字串＝整份；`~1`→`/`、`~0`→`~`；陣列用十進位索引。"""
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise InstError("ReferencePointerInvalid",
                        "%s 的 pointer %r 要以 '/' 開頭" % (where, pointer))
    cur = doc
    for tok in pointer[1:].split("/"):
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict):
            if tok not in cur:
                raise InstError("ReferencePointerInvalid",
                                "%s 的 pointer %r 在 %s 裡找不到 %r" % (where, pointer, path, tok))
            cur = cur[tok]
        elif isinstance(cur, list):
            if not tok.isdigit() or int(tok) >= len(cur):
                raise InstError("ReferencePointerInvalid",
                                "%s 的 pointer %r 在 %s 裡索引不到 %r" % (where, pointer, path, tok))
            cur = cur[int(tok)]
        else:
            raise InstError("ReferencePointerInvalid",
                            "%s 的 pointer %r 走到 %s 就走不下去了"
                            % (where, pointer, type(cur).__name__))
    return cur
