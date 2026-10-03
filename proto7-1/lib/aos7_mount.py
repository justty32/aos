"""掛載（S-23）：tick 把 tasks.json 的 `mounts` 做成任務資料夾裡的符號連結；任務用 resolve 把「空間裡的路徑」換成掛進來的路徑（spec.md 第 4、5 節）。

掛載點＝`<taskdir>/mnt/<名字>`，是指向目標的**相對**符號連結（整個空間搬家也不壞）。
目標寫成空間裡的路徑（相對空間根，跟 node id 同一套，例如 `team/agents/bob/inbox`、`.aosd/ctl`）。
"""
import os

from aos7_fs import node_path, read_json

MNT = "mnt"


def _norm(p):
    """空間路徑正規化：`a/b/../c` → `a/c`；根是 "."。"""
    return os.path.normpath(p).replace(os.sep, "/") if p not in ("", ".") else "."


def check(decl):
    """檢查 mounts 宣告，回 (好的 {名字: 空間路徑}, 錯誤清單)。名字不能有 `/`、不能以 `.` 開頭；路徑不能是絕對、不能跑出空間根。"""
    good, bad = {}, []
    if not isinstance(decl, dict):
        return good, ["mounts 要是 {名字: 空間路徑}"] if decl else []
    for name, to in decl.items():
        if not isinstance(name, str) or not name or "/" in name or name.startswith("."):
            bad.append("掛載名字不合：%r" % (name,))
        elif not isinstance(to, str) or os.path.isabs(to) or _norm(to).split("/")[0] == "..":
            bad.append("%s：目標要是空間裡的相對路徑，拿到 %r" % (name, to))
        else:
            good[name] = _norm(to)
    return good, bad


def make(root, taskdir, decl):
    """建掛載點，回寫進 birth.json 的 `mounts`：{名字: {"to", "at"}}，壞的宣告記成 {"error"}。

    目標不存在就先建成資料夾（收訊資料夾常常還沒人建過；problems.md M-2）。"""
    good, bad = check(decl)
    out = {}
    for name, to in sorted(good.items()):
        real = node_path(root, to)
        at = os.path.join(taskdir, MNT, name)
        try:
            if not os.path.exists(real):
                os.makedirs(real, exist_ok=True)
            os.makedirs(os.path.dirname(at), exist_ok=True)
            os.symlink(os.path.relpath(real, os.path.dirname(at)), at)
            out[name] = {"to": to, "at": at}
        except OSError as e:
            out[name] = {"to": to, "error": str(e)}
    for i, msg in enumerate(bad):
        out["?%d" % i] = {"error": msg}
    return out


def decl_of(birth):
    """birth.json 的 mounts → 原本的宣告 {名字: 空間路徑}（restart 時抄回 spawn 用）。"""
    m = (birth or {}).get("mounts") or {}
    return {n: v["to"] for n, v in m.items() if isinstance(v, dict) and "to" in v and "at" in v}


def resolver(taskdir):
    """回一個函式 resolve(空間路徑) → 經過掛載點的實際路徑；沒有掛載蓋到這個路徑就回 None。

    比對以路徑段為單位，取最長的掛載目標（`team/agents/bob/inbox` 蓋得到 `team/agents/bob/inbox/x.json`）。"""
    m = (read_json(os.path.join(taskdir, "birth.json"), {}) or {}).get("mounts") or {}
    table = sorted(((v["to"], v["at"]) for v in m.values() if isinstance(v, dict) and "at" in v),
                   key=lambda x: -len(x[0]))

    def resolve(path):
        p = _norm(path)
        if p.split("/")[0] == "..":
            return None
        for to, at in table:
            if to == "." or p == to or p.startswith(to + "/"):
                rest = p if to == "." else p[len(to) + 1:]
                return os.path.join(at, rest) if rest and rest != "." else at
        return None
    return resolve
