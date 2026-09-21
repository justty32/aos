"""inst.json 的指示詞展開、參照解析與欄位型別驗證。"""
import json
import os
import re

# 同一個物件裡好幾個指示詞 key 一起出現時，只跑排最前面的那一個（$opt 又排在這三個前面）
DIRECTIVES = ("$ref", "$fmt", "$env")
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
    """`envs` 位置：普通的「變數名→值」物件，或清空型式 `{"$opt":"clear","$val":{…}}`。

    清空型式先把繼承來的環境整個丟掉，再只放 `$val` 裡的（`$val` 可省＝完全空的環境）。
    兩者都可以是指示詞解出來的（整包 `$ref` 從別的檔拿），`$val` 一樣還能再是指示詞。
    key 是純字串、不解指示詞，而且不能 `$` 開頭——那種 key 一出現整包就被當指示詞看了。
    """
    where = "envs"
    opts, v, has_val = options(v, where, OPTIONS["envs"])
    if "clear" in opts:
        inst["envs_clear"] = True
        where = "envs 的 $val"
        v = _resolve(v if has_val else {}, cwd, where, [])
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
    """一個 dict 只要有 `$` 開頭的 key 就是指示詞物件；選項物件（有 `$opt` 的）除外——
    `$opt` 的優先序最高，所以有它就不在這裡解，交給各位置自己用 `options()` 認。"""
    return "$opt" not in d and any(k.startswith("$") for k in d)


def _apply(d, base, where, chain):
    """解一層指示詞，回 `(值, 新的鏈)`。

    物件裡可以有任何別的 key，不認得的一律忽略；好幾個指示詞 key 一起出現就只跑
    `DIRECTIVES` 裡排最前面的（`$ref` > `$fmt` > `$env`），其餘不看。`$env`／`$ref` 的
    值是字串，`$fmt` 的值是物件（模板＋變數表）。有 `$` 開頭的 key 但三個都不是＝
    `UnknownDirective`。
    """
    key = next((k for k in DIRECTIVES if k in d), None)
    if key is None:
        raise InstError("UnknownDirective",
                        "%s 的指示詞 %s 不認得，只有 %s（外加各位置自己的 $opt 選項物件）"
                        % (where, "、".join(repr(k) for k in d if k.startswith("$")),
                           "／".join(DIRECTIVES)))
    val = d[key]
    if key == "$fmt":
        return _fmt(val, base, where, chain), chain
    if not isinstance(val, str):
        raise InstError("DirectiveValueTypeMismatch",
                        "%s 的 %s 值要是字串，不是 %s" % (where, key, type(val).__name__))
    if key == "$env":
        return _lookup(val, where, "$env"), chain
    return _ref(val, base, where, chain)


# 各位置認得的選項名（小寫、區分大小寫）。沒列在這裡的位置（argv、envs 的值…）一個都不吃。
OPTIONS = {
    "stdin": ("inherit",),
    "stdout": ("append", "mkdir", "inherit"),
    "stderr": ("append", "mkdir", "inherit", "merge"),
    "exit": ("append", "mkdir"),
    "cwd": ("mkdir",),
    "envs": ("clear",),
}
_NO_VAL = ("inherit", "merge")          # 帶了 $val 就衝突
_NEED_VAL = ("append", "mkdir")         # 沒帶 $val 就衝突（clear 可省）
_ALONE = ("inherit", "merge")           # 跟任何別的選項都互斥


def options(v, where, allowed):
    """一個位置解出來的值 `v`：是選項物件就拆開驗，回 `(選項名集合, $val, 有沒有 $val)`；
    不是選項物件就原樣回 `(空集合, v, True)`。

    選項物件長 `{"$opt": "名字"}`／`{"$opt": ["名字1","名字2"], "$val": 值}`：只認 `$opt`
    跟 `$val`，其他 key（含 `$ref`／`$fmt`／`$env`、舊的 `$envs`）一律忽略——所以舊寫法
    `{"$opt":"clear","$envs":{…}}` 不報錯、但 `$envs` 沒人看，等於清成空環境；
    `$opt` 是字串或非空字串陣列；
    名字重複、或不是這個位置（`allowed`）認得的＝`UnknownOption`；帶不帶 `$val` 跟哪些
    能一起出現，不合＝`OptionConflict`。`$val` 這裡**不解、不驗型別**——它本來就是「該直接
    寫在那一格的值」，交回去給那一格照自己的規則處理（所以還能再是指示詞）。
    """
    if not (isinstance(v, dict) and "$opt" in v):
        return frozenset(), v, True
    raw = v["$opt"]
    names = [raw] if isinstance(raw, str) else raw
    if not (isinstance(names, list) and names and all(isinstance(n, str) for n in names)):
        raise InstError("DirectiveValueTypeMismatch",
                        "%s 的 $opt 要是字串或非空的字串陣列，不是 %r" % (where, raw))
    seen = []
    for n in names:
        if n in seen:
            raise InstError("UnknownOption", "%s 的 $opt 重複了 %r" % (where, n))
        if n not in allowed:
            raise InstError("UnknownOption",
                            "%s 的 $opt 不認得 %r，這個位置%s"
                            % (where, n, ("只有 " + "／".join(allowed)) if allowed
                               else "沒有任何選項可用"))
        seen.append(n)
    has_val = "$val" in v
    for n in seen:
        if n in _ALONE and len(seen) > 1:
            raise InstError("OptionConflict",
                            "%s 的 %s 不能跟別的選項一起用，這裡還有 %s"
                            % (where, n, "／".join(x for x in seen if x != n)))
        if n in _NO_VAL and has_val:
            raise InstError("OptionConflict", "%s 的 %s 不能帶 $val" % (where, n))
        if n in _NEED_VAL and not has_val:
            raise InstError("OptionConflict", "%s 的 %s 一定要帶 $val（路徑）" % (where, n))
    return frozenset(seen), v.get("$val"), has_val


def _str(v, where):
    """字串位置：解完之後不是字串就是型別錯（選項物件放到不吃選項的位置也在這裡被抓）。"""
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and "$opt" in v:
        options(v, where, ())
    raise InstError("FieldTypeMismatch",
                    "%s 要是字串或指示詞，不是 %s" % (where, type(v).__name__))


def _lookup(name, where, kind):
    """從 **aos-exec 自己的**環境取一個變數。不存在＝錯誤；存在但空＝空字串。"""
    if name not in os.environ:
        raise InstError("EnvironmentVariableMissing",
                        "%s 的 %s 找不到變數 %s（存在但空字串才算空字串）"
                        % (where, kind, name))
    return os.environ[name]


def _fmt(d, base, where, chain):
    """{"$fmt": {"$val": "${p}:/opt/bin", "p": {"$env": "PATH"}}}：接字串用的。

    值**必須是物件**：`$val` 是模板（必填），其餘每個 key 都是**本地變數**。模板裡只有
    `${name}` 會被代換、只查這張本地表，沒有任何 namespace（要環境變數就在表裡寫
    `"x": {"$env": "NAME"}`）；單獨的 `$` 與 `$NAME` 都是**字面**，不展開也不用跳脫。

    - 模板與每個變數值都可以再是指示詞（`$env`／`$ref`／巢狀 `$fmt`），用同一個中心路徑
      與同一條 `$ref` 鏈解，解完**必須是字串**（不是 → `DirectiveValueTypeMismatch`）。
    - 變數名不能 `$` 開頭、不能空、不能含 `{`／`}` → `FormatVariableInvalid`。
    - 表裡沒有的 `${name}` → `UnknownFormatVariable`；定義了沒用到的沒關係。
    - **展開一次、不再掃結果**：換進來的值裡再出現 `${…}` 就是字面。
    """
    if not isinstance(d, dict):
        raise InstError("DirectiveValueTypeMismatch",
                        "%s 的 $fmt 值要是物件（{\"$val\": 模板, 變數名: 值, …}），不是 %s"
                        % (where, type(d).__name__))
    if "$val" not in d:
        raise InstError("DirectiveValueTypeMismatch", "%s 的 $fmt 少了 $val（模板）" % where)
    table = {}
    for name, v in d.items():
        if name == "$val":
            continue
        if name == "" or name.startswith("$") or "{" in name or "}" in name:
            raise InstError("FormatVariableInvalid",
                            "%s 的 $fmt 變數名不能是空字串、$ 開頭、或含大括號：%r" % (where, name))
        w = "%s 的 $fmt 變數 %s" % (where, name)
        table[name] = _fmt_str(_resolve(v, base, w, chain), w)
    w = "%s 的 $fmt 的 $val" % where
    template = _fmt_str(_resolve(d["$val"], base, w, chain), w)

    def one(m):
        name = m.group(1)
        if name not in table:
            raise InstError("UnknownFormatVariable",
                            "%s 的 $fmt 模板用了表裡沒有的變數 ${%s}（表裡有：%s）"
                            % (where, name, "、".join(sorted(table)) or "沒有"))
        return table[name]
    return _FMT.sub(one, template)


def _fmt_str(v, where):
    """`$fmt` 的模板與變數解完都要是字串。"""
    if not isinstance(v, str):
        raise InstError("DirectiveValueTypeMismatch",
                        "%s 解完要是字串，不是 %s" % (where, type(v).__name__))
    return v


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
