"""aos 指示詞（directive）機制：讓 JSON 的值「從別處來」。

機制說明在 proto5/spec/directives/，inst 這個宿主的規則在 proto6/spec/inst.md。這個檔是**純函式庫**、只用標準庫、沒有命令列，也不知道
inst.json 或任何宿主文件長什麼樣：它只管「一個值是不是指示詞、怎麼解成別的值」。
哪些位置要解、解完該是什麼型別、`$opt` 認得哪些選項名——都是宿主的事。

四種指示詞 key，同一個物件裡出現多個時只跑優先順序最高的那個（其餘 key 一律忽略）：

    $opt  >  $ref  >  $fmt  >  $env

- `$env`：讀解析者自己的環境變數（`Context.env`）。
- `$fmt`：模板＋本地變數表，`${name}` 只查表、展開一次。
- `$ref`（可帶 `#位置`）＋`$at`：讀另一份 JSON（或目前這份）的某個位置；檔名空＝目前文件，
  位置的 `./`／`../` 相對於「目前位置」（目前文件＝這個指示詞物件所在的實體路徑；
  別的檔＝那份檔的根）。
- `$opt`：選項物件。`resolve()` **原樣回傳**不碰；宿主用 `split_option()`／`option_names()`
  拆開，要的話再對 `$val` 呼叫 `resolve()`。

「位置」一律是原始 JSON 的實體路徑（含 `$fmt`／`$val`／`$opt` 這些 key）：`$fmt` 的變數 `p`
在 `<這格>/$fmt/p`、模板在 `<這格>/$fmt/$val`、選項物件的值在 `<這格>/$val`。

解析器一路帶著 `Context`（目前文件、中心路徑、環境、循環鏈）和「目前位置」（token 串）；
經過 `$ref` 之後文件與位置會換成被引用的那邊，所以 `resolve_located()` 把它們一起回傳，
宿主要往容器裡面繼續解時才有正確的文件／位置可用。

底層型別（DirectiveError、Document、Context、Located、Option…）在 aos_directives_base.py，
選項物件（split_option／option_names／parse_options）在 aos_directives_options.py；這裡是解析本體，
並 re-export 它們，對外 import 一個都不變。
"""
import os
import re

from aos_directives_base import (  # noqa: F401  （對外照舊 re-export）
    Context, DirectiveError, Document, Located, Option, _show, is_directive, is_option_object, load_document,
)
from aos_directives_options import _VAL_RULES, option_names, parse_options, split_option  # noqa: F401

__all__ = [
    "DirectiveError", "Document", "Context", "Located", "Option",
    "load_document", "is_directive", "is_option_object",
    "resolve", "resolve_located", "split_option", "option_names", "parse_options",
]

# 取值指示詞的優先順序（`$opt` 排在它們前面，但由 `resolve` 的呼叫者處理）
_VALUE_DIRECTIVES = ("$ref", "$fmt", "$env")
# `$fmt` 的模板：只有 ${…} 會被代換，單獨的 $ 與 $NAME 都是字面
_FMT = re.compile(r"\$\{([^{}]*)\}")


def resolve(value, ctx, position):
    """把 `position` 這一格的值解到底，只回值。等同 `resolve_located(...).value`。"""
    return resolve_located(value, ctx, position).value


def resolve_located(value, ctx, position):
    """把 `position`（token 串，根＝`[]`）這一格的值解到底，回 `Located(value, ctx, position)`。

    - 不是指示詞（字串、數字、陣列、沒有 `$` key 的物件…）→ 原樣回，不走進容器裡面。
    - 選項物件（有 `$opt`）→ **原樣回**，交給宿主用 `split_option()` 拆。
    - `$ref`／`$fmt`／`$env`（照這個優先序取一個）→ 解開一層；解出來還是指示詞就繼續，
      經過 `$ref` 之後「目前文件」變成被引用的檔、「目前位置」變成取到的位置，
      回傳的 `ctx`／`position` 就是最後那個值真正所在的地方。
    - 有 `$` key 但四個都不是 → `UnknownDirective`。

    循環鏈以「進來時的 (文件, 位置)」起頭，所以 `{"$ref":"", "$at":"."}` 一步就撞到自己。
    """
    position = tuple(position)
    ctx = ctx._visited((ctx.doc.ident, position))
    while is_directive(value) and not is_option_object(value):
        value, ctx, position = _apply(value, ctx, position)
    return Located(value, ctx, list(position))


def _apply(d, ctx, position):
    """解一層取值指示詞，回 `(值, ctx, position)`。"""
    key = next((k for k in _VALUE_DIRECTIVES if k in d), None)
    if key is None:
        raise DirectiveError(
            "UnknownDirective",
            "%s 的指示詞 %s 不認得，只有 $opt／%s"
            % (_show(position), "、".join(repr(k) for k in d if k.startswith("$")),
               "／".join(_VALUE_DIRECTIVES)))
    val = d[key]
    if key == "$fmt":
        return _fmt(val, ctx, position), ctx, position
    if not isinstance(val, str):
        raise DirectiveError("DirectiveValueTypeMismatch",
                             "%s 的 %s 值要是字串，不是 %s"
                             % (_show(position), key, type(val).__name__))
    if key == "$env":
        return _env(val, ctx, position), ctx, position
    return _ref(val, d.get("$at"), ctx, position)


def _env(name, ctx, position):
    """`{"$env": "NAME"}`：查 `ctx.env`。不存在＝錯誤；存在但空＝空字串。"""
    if name not in ctx.env:
        raise DirectiveError("EnvironmentVariableMissing",
                             "%s 的 $env 找不到變數 %s（存在但空字串才算空字串）"
                             % (_show(position), name))
    return ctx.env[name]


def _fmt(d, ctx, position):
    """`{"$fmt": {"$val": "${p}:/opt/bin", "p": {"$env": "PATH"}}}`：接字串用的。

    值必須是物件；`$val` 是模板（必填），其餘 key 是本地變數。模板與變數值都可以再是
    指示詞（位置照實體路徑：變數 `p` 在 `<這格>/$fmt/p`、模板在 `<這格>/$fmt/$val`，
    所以變數之間能用 `{"$ref":"","$at":"../a"}` 互指），解完必須是字串。
    `${name}` 只查本地表、展開一次、不再掃結果；單獨的 `$`、`$NAME` 是字面。
    """
    where = _show(position)
    if not isinstance(d, dict):
        raise DirectiveError("DirectiveValueTypeMismatch",
                             "%s 的 $fmt 值要是物件（{\"$val\": 模板, 變數名: 值, …}），不是 %s"
                             % (where, type(d).__name__))
    if "$val" not in d:
        raise DirectiveError("DirectiveValueTypeMismatch", "%s 的 $fmt 少了 $val（模板）" % where)
    table = {}
    for name, v in d.items():
        if name == "$val":
            continue
        if name == "" or name.startswith("$") or "{" in name or "}" in name:
            raise DirectiveError("FormatVariableInvalid",
                                 "%s 的 $fmt 變數名不能是空字串、$ 開頭、或含大括號：%r"
                                 % (where, name))
        table[name] = _fmt_str(resolve(v, ctx, position + ("$fmt", name)), "%s 的 $fmt 變數 %s" % (where, name))
    template = _fmt_str(resolve(d["$val"], ctx, position + ("$fmt", "$val")), "%s 的 $fmt 的 $val" % where)

    def one(m):
        name = m.group(1)
        if name not in table:
            raise DirectiveError("UnknownFormatVariable",
                                 "%s 的 $fmt 模板用了表裡沒有的變數 ${%s}（表裡有：%s）"
                                 % (where, name, "、".join(sorted(table)) or "沒有"))
        return table[name]
    return _FMT.sub(one, template)


def _fmt_str(v, where):
    """`$fmt` 的模板與變數解完都要是字串。"""
    if not isinstance(v, str):
        raise DirectiveError("DirectiveValueTypeMismatch",
                             "%s 解完要是字串，不是 %s" % (where, type(v).__name__))
    return v


def _ref(spec, at, ctx, position):
    """`{"$ref": "file.json#/a/b"}` 或 `{"$ref": "file.json", "$at": "/a/b"}`：回 `(值, 新 ctx, 新位置)`。

    - `$ref` 字串以**第一個 `#`** 切開：前面是檔案、後面是位置（文法同 `$at`）；沒有 `#`＝整份。
      代價：檔名含 `#` 的檔沒辦法被 `$ref`。`$at` 有寫就以 `$at` 為準、`#` 後面那段忽略。
    - 檔案非空＝檔名，相對於 `ctx.base_dir`；空字串＝目前文件（不重讀）。
    - 位置開頭 `/`＝從那份文件的根算；`./`／`../`＝相對於「目前位置」：目前文件＝這個指示詞
      物件所在的實體路徑，別的檔＝那份檔的根（所以 `x.json#./a` 就是 `/a`）。
    - 同一條鏈再撞到同一個 (文件身分, 絕對位置) ＝ `ReferenceCycle`；確認不是循環才讀檔。
    """
    where = _show(position)
    file, hashed, frag = spec.partition("#")
    if at is None and hashed:
        at = frag
    if file == "":
        doc, ident, here = ctx.doc, ctx.doc.ident, position
    else:
        doc, here = None, ()
        ident = os.path.realpath(file if os.path.isabs(file) else os.path.join(ctx.base_dir, file))
    target = _at(at, here, where)
    if (ident, target) in ctx._chain:
        walked = " → ".join("%s:%s" % (c[0], _show(c[1])) for c in ctx._chain + ((ident, target),))
        raise DirectiveError("ReferenceCycle", "%s 的 $ref 繞回自己了：%s" % (where, walked))
    if doc is None:
        doc = load_document(ident)
    value = _walk(doc, target, where)
    return value, ctx.child(doc=doc)._visited((ident, target)), target


def _at(at, here, where):
    """位置字串 → 絕對位置的 token 串（tuple）。`here`＝目前位置（目前文件＝指示詞所在處、別的檔＝根）。

    以 `/` 分段：開頭 `/` 從根算、開頭 `./`／`../`（或整串就是 `.`／`..`）從 `here` 算；
    `.` 段略過、`..` 段往上一層（爬過根＝不行）；其餘段 `~1`→`/`、`~0`→`~`，空段就是 key `""`。
    不是這三種開頭的＝不行。兩種「不行」都是 `ReferencePointerInvalid`。`at` 是 None＝整份。
    """
    if at is None:
        return ()
    if not isinstance(at, str):
        raise DirectiveError("DirectiveValueTypeMismatch",
                             "%s 的 $at 要是字串，不是 %s" % (where, type(at).__name__))
    if at.startswith("/"):
        pos, segs = [], at[1:].split("/")
    elif at in (".", "..") or at.startswith("./") or at.startswith("../"):
        pos, segs = list(here), at.split("/")
    else:
        raise DirectiveError("ReferencePointerInvalid",
                             "%s 的位置 %r 要以 /、./ 或 ../ 開頭" % (where, at))
    for seg in segs:
        if seg == ".":
            continue
        if seg == "..":
            if not pos:
                raise DirectiveError("ReferencePointerInvalid",
                                     "%s 的位置 %r 用 .. 爬過文件的根了" % (where, at))
            pos.pop()
            continue
        pos.append(seg.replace("~1", "/").replace("~0", "~"))
    return tuple(pos)


def _walk(doc, pos, where):
    """從文件的根照 token 串走下去：物件用 key、陣列用十進位索引；走不到＝`ReferencePointerInvalid`。"""
    shown = _show(pos)
    cur = doc.root
    for tok in pos:
        if isinstance(cur, dict):
            if tok not in cur:
                raise DirectiveError("ReferencePointerInvalid",
                                     "%s 要的位置 %s 在 %s 裡找不到 %r" % (where, shown, doc.ident, tok))
            cur = cur[tok]
        elif isinstance(cur, list):
            if not tok.isdigit() or int(tok) >= len(cur):
                raise DirectiveError("ReferencePointerInvalid",
                                     "%s 要的位置 %s 在 %s 裡索引不到 %r" % (where, shown, doc.ident, tok))
            cur = cur[int(tok)]
        else:
            raise DirectiveError("ReferencePointerInvalid",
                                 "%s 要的位置 %s 在 %s 裡走到 %s 就走不下去了"
                                 % (where, shown, doc.ident, type(cur).__name__))
    return cur
