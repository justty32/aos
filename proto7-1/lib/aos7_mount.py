"""掛載（S-23）：tick 把 tasks.json 的 `mounts` 做成任務資料夾裡的符號連結；任務用 resolve 把「空間裡的路徑」換成掛進來的路徑（spec.md 第 4、5 節）。

掛載點＝`<taskdir>/mnt/<名字>`，是指向目標的**相對**符號連結（整個空間搬家也不壞）。
目標寫成空間裡的路徑（相對空間根，跟 node id 同一套，例如 `team/agents/bob/inbox`、`.aosd/ctl`）。
"""
import hashlib
import os
import re

from aos7_fs import node_path, now, read_json, write_json

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


def in_root(root, to):
    """空間路徑沿符號連結走到的實際位置還在空間根內嗎（astra-2 二-3：不能只看字面）。"""
    r, t = os.path.realpath(root), os.path.realpath(node_path(root, to))
    return t == r or t.startswith(r + os.sep)


def make(root, taskdir, decl, fs_taskdir=None, node=None, fnode=None):
    """建掛載點，回寫進 birth.json 的 `mounts`：{名字: {"to", "at"}}，壞的宣告記成 {"error"}。

    目標不存在就先建成資料夾（收訊資料夾常常還沒人建過；problems.md M-2）。沿連結會跑出空間根的目標不掛。
    fs_taskdir＝實際建連結的位置（tick 經 node 的 fd 寫，astra-5 F-09）；`at` 與連結內容照 taskdir（實際路徑）算。
    node／fnode＝任務的 node 實際路徑與 tick 抓著的 fd 路徑：目標在 node 底下時經 fnode 建，node 中途被搬走
    不會照舊路徑把它建回來（astra-6 G-02）。"""
    good, bad = check(decl)
    out = {}
    for name, to in sorted(good.items()):
        real = node_path(root, to)
        at = os.path.join(taskdir, MNT, name)
        fat = os.path.join(fs_taskdir or taskdir, MNT, name)
        freal = real
        if node and fnode and (real == node or real.startswith(node + os.sep)):
            freal = os.path.join(fnode, os.path.relpath(real, node))
        if not in_root(root, to):
            out[name] = {"to": to, "error": "%s 沿符號連結跑出空間根" % to}
            continue
        try:
            if not os.path.exists(freal):
                os.makedirs(freal, exist_ok=True)
            os.makedirs(os.path.dirname(fat), exist_ok=True)
            os.symlink(os.path.relpath(real, os.path.dirname(at)), fat)
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


# ---------- 執行中加掛（M-6，使用者選 (b)）：任務寫請求，下一個 tick 審核 ----------

REQ = "mount-req"     # 任務寫：<taskdir>/mount-req/<名字>.json＝{"name", "path", "why"}
DONE = "mount-done"   # tick 寫：同名回條，請求內容加 {"result": {"ok", "msg", "at"}}


def req_name(path):
    """由空間路徑推一個掛載名字（`team/agents/bob/inbox` → `team_agents_bob_inbox`）。

    不同路徑一定推出不同名字（astra-2 二-2：`a/b` 與 `a_b` 原本都變 `a_b`）：路徑只有英數、`-`、`/` 時
    `/` 換 `_` 就不會撞；其他情況（含 `_`、`.`）後面加路徑的短雜湊。"""
    p = _norm(path)
    if re.fullmatch(r"[A-Za-z0-9-]+(/[A-Za-z0-9-]+)*", p):
        return p.replace("/", "_")
    base = re.sub(r"[^A-Za-z0-9_-]", "_", p).strip("_") or "root"
    return "%s-%s" % (base, hashlib.sha1(p.encode()).hexdigest()[:8])


def request(taskdir, path, why="", name=None):
    """任務這邊用：要 path 能經過掛載點碰到。回 "mounted"／"pending"／"refused: 原因"；需要時寫請求檔（已有就不重寫）。

    被拒的回條留著，同一個名字不再自動重請；要再請就刪掉 mount-done 裡那份。"""
    if resolver(taskdir)(path) is not None:
        return "mounted"
    n = name or req_name(path)
    done = read_json(os.path.join(taskdir, DONE, n + ".json"))
    if isinstance(done, dict) and not (done.get("result") or {}).get("ok", True):
        return "refused: %s" % done["result"].get("msg")
    req = os.path.join(taskdir, REQ, n + ".json")
    if not os.path.exists(req):
        write_json(req, {"name": n, "path": path, "why": why})
    return "pending"


def allowed(root, path, allow):
    """tasks.json 的 `mount_allow`（空間路徑前綴清單）；沒寫＝全給。

    比的是沿符號連結走到的實際位置（realpath），不是字面（astra-2 二-3）；跑出空間根的一律不給。"""
    if not in_root(root, path):
        return False
    if allow is None:
        return True
    rp = os.path.realpath
    p = rp(node_path(root, _norm(path)))
    for a in allow if isinstance(allow, list) else []:
        if not isinstance(a, str) or os.path.isabs(a):
            continue
        a = rp(node_path(root, _norm(a)))
        if p == a or p.startswith(a + os.sep):
            return True
    return False


def serve(root, taskdir, allow, real_taskdir=None):
    """tick 這邊用：處理一個任務的所有加掛請求，給了就補連結、更新 birth.json。回 [{"name", "path", "ok", "msg"}]。

    taskdir＝讀寫用的路徑，real_taskdir＝實際路徑（掛載點的 `at`；tick 經 node 的 fd 寫時兩者不同）。
    **先寫回條、成功才刪請求**（astra-5 F-07）：回條寫不進去就留著請求、這筆記錯，同一輪其他請求照做；
    下次重處理同一請求是冪等的（已經掛了同名同目標就直接補回條）。"""
    rdir = os.path.join(taskdir, REQ)
    try:
        names = sorted(n for n in os.listdir(rdir) if n.endswith(".json"))
    except OSError:
        return []
    out = []
    for fn in names:
        item = read_json(os.path.join(rdir, fn))
        try:
            item, r = _serve_one(root, taskdir, allow, item, real_taskdir)
        except Exception as e:  # 任何壞請求都要有回條，不拖垮整個 tick（astra-2 二-1）
            item = item if isinstance(item, dict) else {"raw": item}
            r = {"name": None, "path": None, "ok": False, "msg": "請求處理失敗：%s: %s" % (type(e).__name__, e)}
        item["result"] = {"ok": r["ok"], "msg": r["msg"], "at": now()}
        try:
            write_json(os.path.join(taskdir, DONE, fn), item)
        except OSError as e:
            # 回條寫不進去（mount-done/x.json 是資料夾…）：請求留著，下個 tick 再試；這筆標出來
            r = dict(r, receipt_error=repr(e)[:200], msg="%s；回條寫不進去，請求留著：%s" % (r["msg"], e))
            out.append(r)
            continue
        try:
            os.remove(os.path.join(rdir, fn))
        except OSError:
            pass
        out.append(r)
    return out


def _serve_one(root, taskdir, allow, item, real_taskdir=None):
    """審一個請求，回 (要寫回條的請求內容, {"name", "path", "ok", "msg"})。"""
    if not isinstance(item, dict):
        return {"raw": item}, {"name": None, "path": None, "ok": False, "msg": "not a JSON object"}
    path, name = item.get("path"), item.get("name")
    if name is None and isinstance(path, str):
        name = req_name(path)
    ok, msg = False, ""
    if not isinstance(name, str) or not isinstance(path, str):
        msg = "name 與 path 要是字串（name 可省）"
        name = name if isinstance(name, str) else None
        return item, {"name": name, "path": path if isinstance(path, str) else None, "ok": False, "msg": msg}
    good, bad = check({name: path})
    bpath = os.path.join(taskdir, "birth.json")
    birth = read_json(bpath, {}) or {}
    mounts = birth.get("mounts") or {}
    if bad:
        msg = bad[0]
    elif not allowed(root, path, allow):
        msg = "%s 不在這個 node 的 mount_allow 裡（或沿連結跑出空間根）" % _norm(path)
    elif name in mounts:
        ok = mounts[name].get("to") == good[name]
        msg = "已經掛了" if ok else "名字 %s 已經掛了別的（%s）" % (name, mounts[name].get("to"))
    else:
        m = make(root, real_taskdir or taskdir, good, fs_taskdir=taskdir)[name]
        ok = "at" in m
        msg = "掛上 mnt/%s → %s" % (name, good[name]) if ok else m.get("error", "?")
        if ok:
            m["dyn"] = True   # 執行中加掛的：restart reload 照新定義重起時要另外帶過去（Q6）
            mounts[name] = m
            birth["mounts"] = mounts
            write_json(bpath, birth)
    return item, {"name": name, "path": path, "ok": ok, "msg": msg}
