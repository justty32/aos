"""掛載（spec.md 4.5，S-23）：tick 把 tasks.json 的 `mounts` 做成任務資料夾裡的 `mnt/<名字>`（指向目標的**相對**符號連結，
整個空間搬家也不壞），並審核任務執行中寫的加掛請求。目標寫成空間裡的路徑（相對空間根，跟 node id 同一套）。
只是合作式的方便，不是權限隔離（spec §11）。任務端的 resolver／request 在工具包（modules/tools/aos7_taskside.py）。"""
import hashlib
import os
import re

from aos7_fs import node_path, now, read_json, write_json

MNT = "mnt"
REQ = "mount-req"     # 任務寫：<槽>/mount-req/<名字>.json＝{"name", "path", "why"}
DONE = "mount-done"   # tick 寫：同名回條，請求內容加 {"result": {"ok", "msg", "at"}}


def _norm(p):
    """空間路徑正規化（`a/b/../c` → `a/c`；根是 "."），只整理字面。"""
    return os.path.normpath(p).replace(os.sep, "/") if p not in ("", ".") else "."


def check(decl):
    """檢查掛載宣告，回 (好的 {名字: 空間路徑}, 錯誤)。名字不能有 `/`、不能 `.` 開頭；路徑不能是絕對、不能跑出空間根（字面）。"""
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
    """空間路徑沿符號連結走到的實際位置還在空間根內嗎（看 realpath，不只看字面）。"""
    r, t = os.path.realpath(root), os.path.realpath(node_path(root, to))
    return t == r or t.startswith(r + os.sep)


def make(root, taskdir, decl, fs_taskdir=None, node=None, fnode=None):
    """建掛載點，回寫進 birth.json 的 `mounts`：{名字: {"to", "at"}}，壞的記成 {"error"}（一個壞不擋其他）。
    目標不存在先建成資料夾（收訊資料夾常常還沒人建過）；沿連結跑出空間根的不掛。fs_taskdir＝實際建連結的位置（tick 經
    node 的 fd 寫）；`at` 與連結內容照 taskdir（實際路徑）算，不把 /proc/self/fd 寫進連結。目標在 node 底下的經抓著的
    fnode 建：node 中途被搬走，不會照舊路徑把它建回來。"""
    good, bad = check(decl)
    out = {}
    for name, to in sorted(good.items()):
        real = node_path(root, to)
        at = os.path.join(taskdir, MNT, name)
        fat = os.path.join(fs_taskdir or taskdir, MNT, name)
        freal = os.path.join(fnode, os.path.relpath(real, node)) if node and fnode and (
            real == node or real.startswith(node + os.sep)) else real
        if not in_root(root, to):
            out[name] = {"to": to, "error": "%s 沿符號連結跑出空間根" % to}
            continue
        try:
            os.makedirs(freal, exist_ok=True)
            os.makedirs(os.path.dirname(fat), exist_ok=True)
            os.symlink(os.path.relpath(real, os.path.dirname(at)), fat)
            out[name] = {"to": to, "at": at}
        except OSError as e:
            out[name] = {"to": to, "error": str(e)}
    for i, msg in enumerate(bad):
        out["?%d" % i] = {"error": msg}
    return out


# ---------- 執行中加掛：任務寫請求，下一個 tick 審核 ----------

def req_name(path):
    """由空間路徑推掛載名字（`team/agents/bob/inbox` → `team_agents_bob_inbox`）。不同路徑一定推出不同名字：
    只有英數、`-`、`/` 時 `/` 換 `_` 不會撞；其他情況（含 `_`、`.`）後面加路徑的短雜湊。"""
    p = _norm(path)
    if re.fullmatch(r"[A-Za-z0-9-]+(/[A-Za-z0-9-]+)*", p):
        return p.replace("/", "_")
    base = re.sub(r"[^A-Za-z0-9_-]", "_", p).strip("_") or "root"
    return "%s-%s" % (base, hashlib.sha1(p.encode()).hexdigest()[:8])


def allowed(root, path, allow):
    """tasks.json 的 `mount_allow`（空間路徑前綴清單，比 realpath 後的實際位置）；沒寫＝空間根內全給，跑出空間根的一律不給。"""
    if not in_root(root, path):
        return False
    if allow is None:
        return True
    p = os.path.realpath(node_path(root, _norm(path)))
    for a in allow if isinstance(allow, list) else []:
        if isinstance(a, str) and not os.path.isabs(a):
            a = os.path.realpath(node_path(root, _norm(a)))
            if p == a or p.startswith(a + os.sep):
                return True
    return False


def serve(root, taskdir, allow, real_taskdir=None):
    """處理一個任務的所有加掛請求（`.` 開頭的是寫到一半的暫存檔，不算），回 [{"name", "path", "ok", "msg"}]。
    taskdir＝讀寫用的路徑，real_taskdir＝實際路徑（掛載點的 `at`）。先寫回條、寫成才刪請求：回條寫不進去就留著請求、
    這筆記錯，下次重處理是冪等的（同名同目標已經掛了就直接補回條）。壞請求也一定有回條，不拖垮整個 tick。"""
    rdir = os.path.join(taskdir, REQ)
    try:
        names = sorted(n for n in os.listdir(rdir) if n.endswith(".json") and not n.startswith("."))
    except OSError:
        return []
    out = []
    for fn in names:
        item = read_json(os.path.join(rdir, fn))
        try:
            item, r = _serve_one(root, taskdir, allow, item, real_taskdir)
        except Exception as e:   # noqa: BLE001
            item = item if isinstance(item, dict) else {"raw": item}
            r = {"name": None, "path": None, "ok": False, "msg": "請求處理失敗：%s: %s" % (type(e).__name__, e)}
        item["result"] = {"ok": r["ok"], "msg": r["msg"], "at": now()}
        try:
            write_json(os.path.join(taskdir, DONE, fn), item)
        except OSError as e:
            r = dict(r, receipt_error=repr(e)[:200], msg="%s；回條寫不進去，請求留著：%s" % (r["msg"], e))
        else:
            try:
                os.remove(os.path.join(rdir, fn))
            except OSError:
                pass
        out.append(r)
    return out


def _serve_one(root, taskdir, allow, item, real_taskdir=None):
    """審一個請求，回 (要寫回條的請求內容, {"name", "path", "ok", "msg"})。給了就建 mnt/<名字>、在 birth.json 記下並標 dyn。"""
    if not isinstance(item, dict):
        return {"raw": item}, {"name": None, "path": None, "ok": False, "msg": "not a JSON object"}
    path, name = item.get("path"), item.get("name")
    if name is None and isinstance(path, str):
        name = req_name(path)
    if not isinstance(name, str) or not isinstance(path, str):
        return item, {"name": name if isinstance(name, str) else None, "path": path if isinstance(path, str) else None,
                      "ok": False, "msg": "name 與 path 要是字串（name 可省）"}
    good, bad = check({name: path})
    bpath = os.path.join(taskdir, "birth.json")
    birth = read_json(bpath, {}) or {}
    mounts = birth.get("mounts") or {}
    ok = False
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
            m["dyn"] = True   # 執行中加掛的（事實）：控制包 reload 重起時靠它分出要另外帶過去的掛載
            mounts[name] = m
            birth["mounts"] = mounts
            write_json(bpath, birth)
    return item, {"name": name, "path": path, "ok": ok, "msg": msg}
