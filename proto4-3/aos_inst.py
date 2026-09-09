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
    envs     物件，疊在 aos-exec 的環境上只加不減；
             或 {"$opt":"clear","$envs":{…}}＝從空環境開始只放 $envs 的

跟 proto4-2 不同的三件事（第 11.2 節）：

1. **沒有 `timeout_ms`**——時限歸 aos-exec 的命令列旗標管，寫在 inst.json 裡算未知 key。
2. **相對路徑的中心是解析完的 cwd**，不是 xxx。`stdin`／`stdout`／`stderr`／`exit`
   和 `$ref` 都一樣。只有 `cwd` 自己的相對路徑從 `xxx` 起算（不然沒有中心可言），
   所以 `cwd` 是**最先**解的那一個。
3. `envs` 多一個整個物件層級的 `{"$opt":"clear"}`，這是唯一一個「指示詞物件可以有
   兩個 key」的例外（`$opt` ＋ `$envs`）。

指示詞四種：`{"$env":"NAME"}`、`{"$ref":"file.json#/pointer"}`、`{"$fmt":"模板"}`，
外加只有 `stderr` 能用的 `{"$opt":"merge"}`。`$fmt` 的模板寫法沿用 repo 既有的那套
（`wf/workflows/common/data-files-fmt.md`），這裡只有 `env:` 這一個 namespace。

驗不過就丟 InstError；`str(e)` 是「代號: 白話」，aos-exec 原樣印一行到 stderr、退出碼 1。
"""
import json
import os
import re

FIELDS = ("argv", "stdin", "stdout", "stderr", "exit", "cwd", "envs")
PATH_FIELDS = ("stdin", "stdout", "stderr", "exit")
DIRECTIVES = ("$opt", "$env", "$ref", "$fmt")
# $fmt 的模板：只有 ${…} 會被代換，單獨的 $ 與 $NAME 都是字面
_FMT = re.compile(r"\$\{([^{}]*)\}")
MERGE = object()            # stderr 的 {"$opt":"merge"}：跟 stdout 走同一條


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

    base ＝ `xxx`（資料夾本身，或那份 `.json` 所在的資料夾）：只有 `cwd` 用它當起點。
    `cwd` 解完之後，其他路徑欄位與 `$ref` 一律以**解出來的 cwd** 為中心。

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
    cwd_raw = _value(obj["cwd"], base, "cwd", False) if "cwd" in obj else ""
    cwd = abspath(base, cwd_raw) if cwd_raw else base
    inst["cwd"] = cwd

    argv = obj.get("argv")
    if argv is None:
        raise InstError("EmptyArgv", "argv 必填")
    if not isinstance(argv, list):
        raise InstError("FieldTypeMismatch", "argv 要是陣列，不是 %s" % type(argv).__name__)
    inst["argv"] = [_value(x, cwd, "argv[%d]" % i, False) for i, x in enumerate(argv)]

    _envs(obj.get("envs", {}), cwd, inst)

    for name in PATH_FIELDS:
        if name not in obj:
            continue
        v = _value(obj[name], cwd, name, name == "stderr")
        if v is MERGE:
            inst["stderr_merge"] = True
        elif v:
            inst[name] = abspath(cwd, v)

    if not inst["argv"] or inst["argv"][0] == "":
        raise InstError("EmptyArgv", "argv 解出來是空的，或 argv[0] 是空字串")
    return inst


def _envs(env, cwd, inst):
    """`envs` 欄位：一般是「變數名→值」的物件，只加不減。

    例外只有一個：物件裡出現 `$opt` 這個 key，就當成**清空型式**
    `{"$opt":"clear","$envs":{…}}`——先把繼承來的環境整個丟掉，再只放 `$envs`
    裡的（`$envs` 可省＝完全空的環境）。所以真的想傳一個叫 `$opt` 的環境變數，
    這一版做不到。
    """
    if not isinstance(env, dict):
        raise InstError("FieldTypeMismatch", "envs 要是物件，不是 %s" % type(env).__name__)
    src = env
    if "$opt" in env:
        extra = [k for k in env if k not in ("$opt", "$envs")]
        if extra:
            raise InstError("DirectiveKeyCountInvalid",
                            "envs 的清空型式只能有 $opt 與 $envs，多了 %s"
                            % "、".join(repr(k) for k in extra))
        v = env["$opt"]
        if not isinstance(v, str):
            raise InstError("DirectiveValueTypeMismatch",
                            "envs 的 $opt 值要是字串，不是 %s" % type(v).__name__)
        if v != "clear":
            raise InstError("UnknownOption", "envs 的 $opt 只認得 \"clear\"，不是 %r" % (v,))
        inst["envs_clear"] = True
        src = env.get("$envs", {})
        if not isinstance(src, dict):
            raise InstError("FieldTypeMismatch",
                            "envs 的 $envs 要是物件，不是 %s" % type(src).__name__)
    for k, v in src.items():
        if k == "" or "=" in k:
            raise InstError("EnvKeyInvalid", "envs 的 key 不能是空字串、也不能含 '='：%r" % (k,))
        inst["envs"][k] = _value(v, cwd, "envs[%r]" % k, False)


def _value(v, base, where, allow_opt):
    """一個「字串值位置」：字面字串直接用，物件當指示詞解。"""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return _directive(v, base, where, allow_opt, [])
    raise InstError("FieldTypeMismatch",
                    "%s 要是字串或指示詞，不是 %s" % (where, type(v).__name__))


def _directive(obj, base, where, allow_opt, chain):
    """指示詞物件：剛好一個 key、值一定是字串。chain＝這條 $ref 鏈走過的身分。"""
    if len(obj) != 1:
        raise InstError("DirectiveKeyCountInvalid",
                        "%s 的指示詞要剛好一個 key，這個有 %d 個" % (where, len(obj)))
    key, val = next(iter(obj.items()))
    if key not in DIRECTIVES:
        raise InstError("UnknownDirective",
                        "%s 的指示詞 %r 不認得，只有 %s" % (where, key, "／".join(DIRECTIVES)))
    if not isinstance(val, str):
        raise InstError("DirectiveValueTypeMismatch",
                        "%s 的 %s 值要是字串，不是 %s" % (where, key, type(val).__name__))
    if key == "$opt":
        if val != "merge":
            raise InstError("UnknownOption", "%s 的 $opt 只認得 \"merge\"，不是 %r" % (where, val))
        if not allow_opt:
            raise InstError("UnknownDirective", "%s 不能用 $opt，只有 stderr 可以" % where)
        return MERGE
    if key == "$env":
        return _lookup(val, where, "$env")
    if key == "$fmt":
        return _fmt(val, where)
    return _ref(val, base, where, allow_opt, chain)


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


def _ref(spec, base, where, allow_opt, chain):
    """{"$ref":"file.json#/a/b"}：相對於 cwd 讀檔、`#` 後面是 RFC 6901 JSON Pointer。

    取回來的值就當成本來寫在那個位置：字串直接用、又是指示詞就繼續解、陣列／物件＝錯誤。
    同一條鏈再撞到同一個「realpath ＋ pointer」＝循環。
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
    val = _pointer(doc, ident[1], where, path)
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return _directive(val, base, where, allow_opt, chain + [ident])
    raise InstError("ReferenceValueInvalid",
                    "%s 的 $ref 取到 %s，只能是字串或指示詞" % (where, type(val).__name__))


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
