"""暫存器替換：步的字串欄裡 ${名} 由 exec 在跑之前用串的 regs 替換。

內建：${frame}=堆疊框路徑、${land}=這塊地根、${tick}=目前格號。
WRITER-BRIEF 4.2 結尾。
"""
import re

PAT = re.compile(r"\$\{([A-Za-z0-9_-]{1,64})\}")


class MissingReg(Exception):
    """引用了不存在的暫存器。錯誤要指路：講出是哪一個、有哪些可用。"""


def builtins(land, series, tick):
    return {
        "land": land.root,
        "frame": land.frame(series["id"]),
        "tick": str(tick),
        "series": series["id"],
    }


def table(land, series, tick):
    t = dict(builtins(land, series, tick))
    t.update({k: str(v) for k, v in (series.get("regs") or {}).items()})
    return t


def sub_str(s, t):
    def one(m):
        name = m.group(1)
        if name not in t:
            raise MissingReg(
                "暫存器 `${%s}` 沒有值；這條串目前有：%s"
                % (name, "、".join(sorted(t)) or "（空）")
            )
        return str(t[name])
    return PAT.sub(one, s)


def sub(obj, t):
    """遞迴替換字串欄。{"b64": ...} 原樣保留（非 UTF-8 位元組）。"""
    if isinstance(obj, str):
        return sub_str(obj, t)
    if isinstance(obj, list):
        return [sub(x, t) for x in obj]
    if isinstance(obj, dict):
        if set(obj.keys()) == {"b64"}:
            return obj
        return {k: sub(v, t) for k, v in obj.items()}
    return obj
