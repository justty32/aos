"""adapt 宣告檢查器（spec §6）。"""
import decimal
import os
from aos7_fs import is_int
from aos7_adapt_common import (
    AS_RE, CMP_KEYS, DECL_KEYS, NAME_RE, REQUIRED, STEP_KINDS, dec, is_num, space_path_ok,
)  # noqa: F401

# ---------- 檢查器（spec §6） ----------

def check(d):
    """回 [{"level", "where", "rule", "why"}]；不執行、不拋例外（壞型別也回診斷）。"""
    out = []

    def err(where, rule, why):
        out.append({"level": "error", "where": where, "rule": rule, "why": why})

    if not isinstance(d, dict):
        err(None, "struct", "宣告要是 JSON 物件")
        return out
    for k in sorted(set(d) - DECL_KEYS):
        err(k, "struct", "不認得的欄 %r" % k)
    for k in REQUIRED:
        if k not in d:
            err(k, "struct", "缺必填欄 %s" % k)
    if "v" in d and d["v"] != 1:
        err("v", "struct", "v 只准 1")
    if "sense" in d and not (isinstance(d["sense"], str) and NAME_RE.match(d["sense"])):
        err("sense", "type", "sense 要是英數、_、-，最多 32 字")
    for k in ("src", "src_clock"):
        if k in d and not space_path_ok(d[k]):
            err(k, "type", "%s 要是空間路徑（相對空間根、不含 ..）" % k)
    if space_path_ok(d.get("src_clock")) and os.path.basename(d["src_clock"]) != "round.json":
        err("src_clock", "clock", "src_clock 要指到來源 node 的 .aos/round.json（v1 只認來源回合這一條鐘）")
    for k in ("max_age", "patience", "stall"):
        if k in d and d[k] is not None and not (is_int(d[k]) and d[k] >= 0):
            err(k, "time", "%s 要是非負整數（回合數）或 null；不收秒、毫秒、期限" % k)
    produced = []
    steps = d.get("steps")
    if "steps" in d and not (isinstance(steps, list) and steps):
        err("steps", "type", "steps 要是非空陣列")
        steps = []
    for i, s in enumerate(steps or []):
        where = "steps[%d]" % i
        kinds = [k for k in STEP_KINDS if isinstance(s, dict) and k in s]
        if not isinstance(s, dict) or len(kinds) != 1 or set(s) - {kinds[0], "note"}:
            err(where, "step", "每步恰一個種類鍵（%s），可另帶 note" % "／".join(STEP_KINDS))
            continue
        k, a = kinds[0], s[kinds[0]]
        if k == "select":
            if i != 0:
                err(where, "step", "select 只能是第一步、只能一個（v1 一條鏈一個來源值）")
            if not (isinstance(a, str) and a and all(a.split("."))):
                err(where, "type", "select 要是點分路徑字串（每段非空）")
            continue
        if i == 0:
            err(where, "step", "第一步要是 select")
        if not isinstance(a, dict):
            err(where, "type", "%s 的參數要是物件" % k)
            continue
        if k == "scale":
            bad = set(a) - {"mul", "q", "round", "as"}
            if bad:
                err(where, "struct", "scale 不認得的欄 %s" % sorted(bad))
            if not is_num(a.get("mul")):
                err(where, "type", "scale.mul 要是數字")
            if not (is_num(a.get("q")) and a["q"] >= 0):
                err(where, "type", "scale.q（取整誤差界）要是非負數字")
            if "round" in a and not (is_int(a["round"]) and 0 <= a["round"] <= 12):
                err(where, "type", "scale.round 要是 0～12 的整數（小數位數）")
            elif "round" in a and is_num(a.get("q")) and dec(a["q"]) < decimal.Decimal(5).scaleb(-a["round"] - 1):
                err(where, "err", "scale.q=%r 蓋不住取整到小數 %d 位的誤差（至少 %g）"
                    % (a["q"], a["round"], 0.5 * 10 ** -a["round"]))
        else:   # threshold
            cmp = [c for c in CMP_KEYS if c in a]
            bad = set(a) - set(CMP_KEYS) - {"as"}
            if bad:
                err(where, "struct", "threshold 不認得的欄 %s" % sorted(bad))
            if len(cmp) != 1 or not is_num(a.get(cmp[0] if cmp else "")):
                err(where, "type", "threshold 要恰一個比較鍵（%s）且值是數字" % "／".join(CMP_KEYS))
            if "as" not in a:
                err(where, "struct", "threshold 要有 as（產出欄名）")
        if "as" in a:
            if not (isinstance(a["as"], str) and AS_RE.match(a["as"])):
                err(where, "type", "as 要是英數與 _，最多 32 字")
            elif a["as"] in produced:
                err(where, "struct", "as %r 重複" % a["as"])
            else:
                produced.append(a["as"])
    need = d.get("need")
    if "need" in d:
        if not (isinstance(need, list) and need and all(isinstance(n, str) for n in need)):
            err("need", "type", "need 要是非空字串陣列")
        else:
            for n in need:
                if n not in produced:
                    err("need", "need", "need 欄 %r 不在鏈的產出裡（產出：%s）" % (n, produced))
    return out


