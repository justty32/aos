"""adapt 確定性轉換鏈（spec §2）。"""
import decimal
from aos7_adapt_common import (
    CMP_KEYS, EXACT, META, STEP_KINDS, dec, is_num, publish, round_half_up,
)  # noqa: F401

# ---------- 鏈（spec §2） ----------

def pick(doc, path):
    """點分路徑取值；走不到回 (False, None)。"""
    cur = doc
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def leaves(obj, prefix=""):
    """物件的葉路徑（點分）。"""
    if isinstance(obj, dict) and obj:
        out = []
        for k, v in obj.items():
            out += leaves(v, prefix + k if not prefix else prefix + "." + k)
        return out
    return [prefix] if prefix else []


def omitted_of(doc, selected):
    """來源物件裡沒被選到的葉路徑（扣掉信封欄 v／seq／round／at）。"""
    keep = [p for p in leaves({k: v for k, v in doc.items() if k not in META})
            if not (p == selected or p.startswith(selected + "."))]
    return sorted(keep)


def band(op, t, lo, hi):
    """區間 [lo, hi] 對門檻 t：整段成立 True、整段不成立 False、跨過 None。"""
    if op == "ge":
        return True if lo >= t else (False if hi < t else None)
    if op == "gt":
        return True if lo > t else (False if hi <= t else None)
    if op == "le":
        return True if hi <= t else (False if lo > t else None)
    return True if hi < t else (False if lo >= t else None)   # lt


def run_chain(steps, doc):
    """跑一次鏈。回 {"out", "err", "trace", "omitted", "fail", "band", "range"}：fail＝走 unknown 分支的原因
    （select_missing／not_number），band＝落在誤差帶的產出欄，range＝超出 float 範圍、不能發布的產出欄（A8-04）。
    從固定的 doc 重算，不讀上一跳。中間值都是精確十進位，只有寫進 out／err／trace 時才轉成 JSON 數字。"""
    out, errs, trace, x, e = {}, {}, [], None, decimal.Decimal(0)
    selected, fail, inband, outrange = "", None, [], []
    for s in steps:
        k = next(k for k in STEP_KINDS if k in s)
        a = s[k]
        if k == "select":
            selected = a
            found, x = pick(doc, a)
            if not found:
                fail = "select_missing"
                break
            trace.append({"step": "select", "x": x, "err": 0})
            if is_num(x):
                x = dec(x)
            continue
        if not isinstance(x, decimal.Decimal):
            fail = "not_number"
            break
        if k == "scale":
            x = EXACT.multiply(x, dec(a["mul"]))
            if "round" in a:
                x = round_half_up(x, a["round"])
            e = EXACT.add(EXACT.multiply(abs(dec(a["mul"])), e), dec(a["q"]))
            v, ev = publish(x, e)
            trace.append({"step": "scale", "x": v if ev is not None else str(x), "err": ev if ev is not None else str(e)})
            if "as" in a:
                if ev is None:
                    outrange.append(a["as"])
                out[a["as"]], errs[a["as"]] = v, ev
        else:
            op = next(c for c in CMP_KEYS if c in a)
            v = band(op, dec(a[op]), EXACT.subtract(x, e), EXACT.add(x, e))
            trace.append({"step": "threshold", op: a[op], "as": a["as"], "v": v})
            out[a["as"]] = v
            if v is None:
                inband.append(a["as"])
    return {"out": out, "err": errs, "trace": trace, "fail": fail, "band": inband, "range": outrange,
            "omitted": omitted_of(doc, selected) if selected and isinstance(doc, dict) else []}


