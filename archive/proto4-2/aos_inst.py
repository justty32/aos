#!/usr/bin/env python3
"""inst.json 的讀、驗、解指示詞——「格式」那一層，跟「怎麼跑」分開（跑在 aos_cpu.py）。

格式是凍結分支 `core/inst` 那套（SPEC §C-3～§C-6）搬過來的：一份 inst.json 是嚴格
一個 JSON 物件、八個欄位、只有 `argv` 必填、**未知的 key 一律拒絕**（不是忽略）。

    argv        字串（或指示詞）陣列，必填；argv[0] 走 PATH
    stdin       檔案路徑，空＝不餵（/dev/null）
    stdout      檔案路徑，空＝cpu 抓回 last.json
    stderr      檔案路徑或 {"$opt":"merge"}，空＝cpu 抓回 last.json
    exit        檔案路徑，空＝不寫；有寫＝跑完把結束碼寫進去
    cwd         工作目錄，空＝資料夾本身
    env         物件，值是字串，疊在繼承來的環境上（只加不減）
    timeout_ms  這一次執行的上限（毫秒），0＝不限

相對路徑一律從**資料夾**（DIR）起算。`argv` 的每個元素、五個路徑欄位、`env` 的值都
可以寫指示詞 `{"$env":"NAME"}` 或 `{"$ref":"file.json#/pointer"}`；`stderr` 另可寫
`{"$opt":"merge"}`。`env` 的 key 與 `timeout_ms` 不吃指示詞。

驗不過就丟 InstError；`str(e)` 是「代號: 白話」，原樣進 last.json 的 `error`，
這次不跑、cpu 照活。代號對應 SPEC §C-6 的拒絕表（外加解析那幾個）。
"""
import json
import os

FIELDS = ("argv", "stdin", "stdout", "stderr", "exit", "cwd", "env", "timeout_ms")
PATH_FIELDS = ("stdin", "stdout", "stderr", "exit", "cwd")
DIRECTIVES = ("$opt", "$env", "$ref")
MERGE = object()            # stderr 的 {"$opt":"merge"}：跟 stdout 走同一條


class InstError(Exception):
    """格式／解析被拒。不是程式炸了，是這份 inst.json 有問題。"""

    def __init__(self, code, msg):
        super().__init__("%s: %s" % (code, msg))
        self.code = code


def abspath(base, p):
    """inst.json 裡的路徑：絕對的照字面用，相對的從資料夾起算。"""
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))


def load(path, base):
    """讀 path 這份 inst.json，指示詞全解好，回一個八欄都填好的 dict。

    base ＝資料夾（DIR）：相對路徑與 `$ref` 的起點，整趟解析都用這一個，不會因為
    引用跑進別的檔就跟著換。
    """
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
            raise InstError("UnknownKey", "不認得的欄位 %r，只有這八個：%s"
                            % (k, "、".join(FIELDS)))

    inst = {"argv": [], "stdin": "", "stdout": "", "stderr": "", "exit": "",
            "cwd": "", "env": {}, "timeout_ms": 0, "stderr_merge": False}

    if "timeout_ms" in obj:
        v = obj["timeout_ms"]
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise InstError("FieldTypeMismatch",
                            "timeout_ms 要是非負整數（也不吃指示詞），不是 %r" % (v,))
        inst["timeout_ms"] = v

    argv = obj.get("argv")
    if argv is None:
        raise InstError("EmptyArgv", "argv 必填")
    if not isinstance(argv, list):
        raise InstError("FieldTypeMismatch", "argv 要是陣列，不是 %s" % type(argv).__name__)
    inst["argv"] = [_value(x, base, "argv[%d]" % i, False) for i, x in enumerate(argv)]

    env = obj.get("env", {})
    if not isinstance(env, dict):
        raise InstError("FieldTypeMismatch", "env 要是物件，不是 %s" % type(env).__name__)
    for k, v in env.items():
        if k == "" or "=" in k:
            raise InstError("EnvKeyInvalid", "env 的 key 不能是空字串、也不能含 '='：%r" % (k,))
        inst["env"][k] = _value(v, base, "env[%r]" % k, False)

    for name in PATH_FIELDS:
        if name not in obj:
            continue
        v = _value(obj[name], base, name, name == "stderr")
        if v is MERGE:
            inst["stderr_merge"] = True
        else:
            inst[name] = v

    if not inst["argv"] or inst["argv"][0] == "":
        raise InstError("EmptyArgv", "argv 解出來是空的，或 argv[0] 是空字串")
    return inst


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
        if val not in os.environ:
            raise InstError("EnvironmentVariableMissing",
                            "%s 的 $env 找不到變數 %s（存在但空字串才算空字串）" % (where, val))
        return os.environ[val]
    return _ref(val, base, where, allow_opt, chain)


def _ref(spec, base, where, allow_opt, chain):
    """{"$ref":"file.json#/a/b"}：相對於資料夾讀檔、`#` 後面是 RFC 6901 JSON Pointer。

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
