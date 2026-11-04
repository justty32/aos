"""暫存器替換：步的字串欄裡 ${名} 由 exec 在跑之前用串的 regs 替換。

內建：${frame}=堆疊框路徑、${land}=這塊地根、${tick}=目前格號、${series}=串 id，
外加裁決 S-03 的 ${home}=$AOS_HOME、${llm_world}=LLM 世界那塊地。
WRITER-BRIEF 4.2 結尾。
"""
import re

from . import layout

PAT = re.compile(r"\$\{([A-Za-z0-9_-]{1,64})\}")


class MissingReg(Exception):
    """引用了不存在的暫存器。錯誤要指路：講出是哪一個、有哪些可用。"""


def builtins(land, series, tick):
    home = layout.Home()
    return {
        "land": land.root,
        "frame": land.frame(series["id"]),
        "tick": str(tick),
        "series": series["id"],
        # 裁決 S-03：這兩個是內建暫存器，不然地上的程式沒辦法講出「家」跟
        # 「LLM 世界」在哪（那是每台機器不一樣的絕對路徑）。
        "home": home.root,
        "llm_world": home.llm_world,
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
