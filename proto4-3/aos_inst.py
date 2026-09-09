#!/usr/bin/env python3
"""inst.json 的讀、驗、解指示詞——「格式」那一層，跟「怎麼跑」分開（跑在 aos_exec.py）。

格式是 proto4 筆記第 11 節那套（凍結分支 `core/inst` 的 SPEC §C-3～§C-6 改過來的）：
一份 inst.json 是嚴格一個 JSON 物件、**七個**欄位、只有 `argv` 必填、**未知的 key
一律拒絕**（不是忽略）。

    argv     字串（或指示詞）陣列，必填；argv[0] 走疊加後 env 的 PATH
    stdin    檔案當標準輸入，沒寫＝/dev/null
    stdout   標準輸出寫到這個檔（建立並清空），沒寫＝/dev/null
    stderr   同上；或 {"$opt":"merge"}＝跟 stdout 同一條，沒寫＝/dev/null
    exit     跑完把結束碼寫進去，沒寫＝不寫
    cwd      工作目錄，沒寫＝xxx 本身
    envs     物件，疊在 aos-exec 的環境上只加不減；或 {"$opt":"clear","$envs":{…}}＝
             從空環境開始只放 $envs 的；整包也可以用 $ref 從別的檔拿

**先解、再驗**：inst.json 裡**任何一個值的位置**都能改寫一個指示詞——頂層整份、每個
欄位、`argv` 整個陣列與它的每個元素、`envs` 整個物件與它的每個值、`$envs`。指示詞解
出來的東西就當成本來寫在那個位置，**解出來又是指示詞就繼續解**（巢狀），最後才照那個
位置該有的型別驗（頂層要物件、argv 要非空字串陣列、路徑欄要字串、envs 要物件）。型別
不對就是 `NotAnObject`／`FieldTypeMismatch`／`EmptyArgv` 那些代號。

指示詞三種：`{"$env":"NAME"}`、`{"$ref":"file.json#/pointer"}`、`{"$fmt":"模板"}`，
外加兩個位置專用的 `$opt`：`stderr` 的 `merge`、`envs` 的 `clear`。**一個 dict 只要有
`$` 開頭的 key 就當指示詞看**，所以環境變數名不能是 `$` 開頭的。`$fmt` 的模板寫法沿用
repo 既有的那套（`wf/workflows/common/data-files-fmt.md`），只有 `env:` 一個 namespace。

**循環**：`$ref` 沿著一條鏈記「檔案 realpath ＋ pointer」，任何深度都記；同一條鏈再遇到
同一個身分＝`ReferenceCycle`（頂層 `{"$ref":"自己"}` 也擋得到）。

相對路徑的中心是**解出來的 cwd**，只有頂層與 `cwd` 自己以 `xxx`（base）為中心，所以順序
是：先解頂層 → 解 `cwd` → 其餘欄位。

驗不過就丟 InstError；`str(e)` 是「代號: 白話」，aos-exec 原樣印一行到 stderr、退出碼
125（aos-exec 自己失敗，不是子程式的碼）。
"""
import json
import os
import re

FIELDS = ("argv", "stdin", "stdout", "stderr", "exit", "cwd", "envs")
PATH_FIELDS = ("stdin", "stdout", "stderr", "exit")
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


def load(path, base):
    """讀 path 這份 inst.json，指示詞全解好，回一個欄位都填好的 dict。

    base ＝ `xxx`（資料夾本身，或那份 `.json` 所在的資料夾）：頂層與 `cwd` 用它當起點。
    `cwd` 解完之後，其他欄位與它們的 `$ref` 一律以**解出來的 cwd** 為中心。

    回傳的 dict：`argv`（list）、`stdin`／`stdout`／`stderr`／`exit`（絕對路徑，
    ""＝沒寫）、`cwd`（絕對路徑）、`envs`（dict）、`envs_clear`（bool）、
    `stderr_merge`（bool）。
    """
    base = os.path.abspath(base)
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        raise InstError("ReadFailed", "讀不到 %s：%s" % (path, e))
    try:
        obj = json.loads(raw)
    except ValueError as e:
        raise InstError("JsonSyntax", "JSON 語法錯：%s" % e)
    obj = _resolve(obj, base, "inst.json", [])          # 頂層整份也能是指示詞
    if not isinstance(obj, dict):
        raise InstError("NotAnObject", "inst.json 必須是一個 JSON 物件，不是 %s"
                        % type(obj).__name__)
    for k in obj:
        if k not in FIELDS:
            raise InstError("UnknownKey", "不認得的欄位 %r，只有這七個：%s"
                            % (k, "、".join(FIELDS)))

    inst = {"argv": [], "stdin": "", "stdout": "", "stderr": "", "exit": "",
            "cwd": "", "envs": {}, "envs_clear": False, "stderr_merge": False}

    # cwd 先解：它是所有相對路徑的中心，自己的相對路徑則以 base（xxx）為中心。
    cwd_raw = _str(_resolve(obj["cwd"], base, "cwd", []), "cwd") if "cwd" in obj else ""
    cwd = abspath(base, cwd_raw) if cwd_raw else base
    inst["cwd"] = cwd

    argv = _resolve(obj.get("argv"), cwd, "argv", [])
    if argv is None:
        raise InstError("EmptyArgv", "argv 必填")
    if not isinstance(argv, list):
        raise InstError("FieldTypeMismatch", "argv 要是陣列，不是 %s" % type(argv).__name__)
    inst["argv"] = [_str(_resolve(x, cwd, "argv[%d]" % i, []), "argv[%d]" % i)
                    for i, x in enumerate(argv)]

    _envs(_resolve(obj.get("envs", {}), cwd, "envs", []), cwd, inst)

    for name in PATH_FIELDS:
        if name not in obj:
            continue
        v = _resolve(obj[name], cwd, name, [])
        if name == "stderr" and isinstance(v, dict) and "$opt" in v:
            _opt(v, name, "merge")              # {"$opt":"merge"}＝跟 stdout 同一條
            inst["stderr_merge"] = True
            continue
        v = _str(v, name)
        if v:
            inst[name] = abspath(cwd, v)

    if not inst["argv"] or inst["argv"][0] == "":
        raise InstError("EmptyArgv", "argv 解出來是空的，或 argv[0] 是空字串")
    return inst


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
