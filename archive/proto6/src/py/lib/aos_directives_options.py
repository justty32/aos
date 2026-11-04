"""aos 指示詞的選項物件（`$opt`）：拆開、驗選項名（從 aos_directives.py 拆出）。

對外照舊從 aos_directives import（那裡 re-export）。
"""
from aos_directives_base import DirectiveError, Option, _show, is_option_object

# 選項表裡 "val" 欄位認得的值
_VAL_RULES = ("required", "forbidden", "optional")


def split_option(value):
    """把選項物件拆開，**零驗證**：回 `Option(is_option, opt, val, has_val)`。

    - 是選項物件（有 `$opt`）→ `Option(True, $opt 的原始值, $val 的值或 None, 有沒有 $val)`。
      `$opt` 的值任何 JSON 都可以，機制不解讀、不驗型別、不解指示詞，原樣交給宿主；
      `$val` 也原樣（宿主要的話再拿去 `resolve`，位置＝這格 + `["$val"]`）；其他 key 一律忽略。
    - 不是選項物件 → `Option(False, None, value, True)`：值就是原本那個。
    """
    if not is_option_object(value):
        return Option(False, None, value, True)
    return Option(True, value["$opt"], value.get("$val"), "$val" in value)


def option_names(opt, has_val, position, table):
    """給「`$opt` 是名字或名字陣列」慣例的宿主用：驗 `opt`，回選項名的 frozenset。

    `table` 是這個位置認得的選項：`{名字: {"val": "required"|"forbidden"|"optional", "alone": bool}}`
    （沒寫的欄位＝`optional`／`False`）；空表＝這個位置不吃任何選項。

    - `opt` 不是字串也不是非空字串陣列 → `DirectiveValueTypeMismatch`。
    - 名字重複、不在表裡、或表是空的 → `UnknownOption`。
    - `val` 規則不合（`required` 沒帶、`forbidden` 帶了）、`alone` 的選項跟別的一起出現 → `OptionConflict`。
    """
    where = _show(position)
    for name, spec in table.items():
        if spec.get("val", "optional") not in _VAL_RULES:
            raise ValueError("選項表 %r 的 val 要是 %s 之一" % (name, "／".join(_VAL_RULES)))
    names = [opt] if isinstance(opt, str) else opt
    if not (isinstance(names, list) and names and all(isinstance(n, str) for n in names)):
        raise DirectiveError("DirectiveValueTypeMismatch",
                             "%s 的 $opt 要是字串或非空的字串陣列，不是 %r" % (where, opt))
    seen = []
    for n in names:
        if n in seen:
            raise DirectiveError("UnknownOption", "%s 的 $opt 重複了 %r" % (where, n))
        if n not in table:
            raise DirectiveError("UnknownOption",
                                 "%s 的 $opt 不認得 %r，這個位置%s"
                                 % (where, n, ("只有 " + "／".join(table)) if table else "沒有任何選項可用"))
        seen.append(n)
    for n in seen:
        spec = table[n]
        if spec.get("alone", False) and len(seen) > 1:
            raise DirectiveError("OptionConflict",
                                 "%s 的 %s 不能跟別的選項一起用，這裡還有 %s"
                                 % (where, n, "／".join(x for x in seen if x != n)))
        rule = spec.get("val", "optional")
        if rule == "forbidden" and has_val:
            raise DirectiveError("OptionConflict", "%s 的 %s 不能帶 $val" % (where, n))
        if rule == "required" and not has_val:
            raise DirectiveError("OptionConflict", "%s 的 %s 一定要帶 $val" % (where, n))
    return frozenset(seen)


def parse_options(value, position, table):
    """`split_option` ＋ `option_names` 合在一起的方便寫法：回 `(選項名 frozenset, $val, 有沒有 $val)`。

    不是選項物件 → `(frozenset(), value, True)`。`$val` 不解、不驗——交回給宿主。
    """
    o = split_option(value)
    if not o.is_option:
        return frozenset(), value, True
    return option_names(o.opt, o.has_val, position, table), o.val, o.has_val
