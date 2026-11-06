# aos_agent/decl.py - 讀取介面宣告並呼叫定義中的子介面入口。
import json
import os
import subprocess
import sys
from .common import Agent, DECL, Fail, IFACE, daemon_path, note, table
from .hints import _same


# ---------------------------------------------------------------- 定義與宣告（03）

def read_decl(folder, iface):
    """<folder>/interfaces.json 裡 iface 那個 key 的值（物件）。沒檔、沒 key＝(None, 原因)；讀不懂＝InterfaceBad。"""
    p = os.path.join(folder, DECL)
    if not os.path.isfile(p):
        return None, "%s has no %s" % (folder, DECL)
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        raise Fail("InterfaceBad", "cannot read %s: %s" % (p, e))
    if not isinstance(d, dict):
        raise Fail("InterfaceBad", "%s must be a JSON object" % p)
    if iface not in d:
        return None, "%s does not declare %s" % (p, iface)
    if not isinstance(d[iface], dict):
        raise Fail("InterfaceBad", "%s in %s must be an object (e.g. {\"%s\": {}})" % (iface, p, iface))
    return d[iface], None


def show_limits(v):
    return " ".join("%s=%s" % (k, x) for k, x in v.items()) if isinstance(v, dict) else json.dumps(v, ensure_ascii=False)


def def_of(a):
    """表那一列的 def 欄（daemon_ctl.add_letter 帶上的 XXX 絕對路徑）＝定義資料夾。沒有這欄＝InterfaceMissing。
    11-04 使用者「那就b。」：不再從 exec 欄倒推（loop.json 的 exec 是陣列或指到別的資料夾會推錯）。"""
    d = a.row.get("def")
    if not isinstance(d, str) or not d:
        raise Fail("InterfaceMissing", "the daemon table row of %s has no def column, so its definition cannot be found (aos-agent ctl rm %s, then ctl add again)" % (a.name, a.name))
    return d


def agent_decl(a):
    folder = def_of(a)
    decl, why = read_decl(folder, IFACE)
    if decl is None:
        raise Fail("InterfaceMissing", "%s: the definition does not declare the aos-agent interface (%s)" % (a.name, why))
    return folder, decl


def same_def(a, folder):
    """同一份定義掛出來的其他名字（表上 def 欄跟 folder 是同一個）。"""
    out = []
    for n, r in table(quiet=True).items():
        if n == a.name:
            continue
        try:
            if _same(def_of(Agent(n, r)), folder):
                out.append(n)
        except Fail:
            continue
    return out


def warn_shared(a, folder):
    others = same_def(a, folder)
    if others:
        note("this definition (%s) is also used by %s; only %s's own copy (in its stack) changed, theirs did not (to change them all, edit the definition: aos-tools / aos-json)" % (folder, ", ".join(others), a.name))


def sub_entry(a, key, iface, missing, bad):
    """選配子介面（screen）：宣告值＝定義裡的資料夾程式，自己宣告 aos-agent/<x>。回 (定義, 入口資料夾)。"""
    folder, decl = agent_decl(a)
    rel = decl.get(key)
    if not isinstance(rel, str) or not rel:
        raise Fail(*missing(folder))
    entry = os.path.join(folder, rel)
    if not os.path.isdir(entry):
        raise Fail(bad, "the %s entry declared by %s is not a folder: %s" % (key, folder, entry))
    d, why = read_decl(entry, iface)
    if d is None:
        raise Fail(bad, "%s does not declare %s (%s)" % (entry, iface, why))
    return folder, entry


def run_entry(a, entry, args, capture_err=True):
    """aos-exec --ws <ws> --stack <stack> <入口> args…；stdin／stdout 接呼叫者的。回 (結束碼, stderr)。"""
    argv = ["aos-exec", "--ws", a.ws, "--stack", a.stack, entry] + list(args)
    try:
        r = subprocess.run(argv, stderr=subprocess.PIPE if capture_err else None, text=True,
                           env=dict(os.environ, AOS_DAEMON=daemon_path()))   # --daemon 給的也傳下去（screen 的 watch 靠它讀表）
    except OSError as e:
        raise Fail("CommandMissing", "cannot run aos-exec (proto8/impls/aos-exec/bin must be on PATH): %s" % e)
    return r.returncode, (r.stderr or "")


def pass_err(rc, err):
    """入口自己的錯原樣轉（C-53）：stderr 照印、退 1。"""
    if err:
        sys.stderr.write(err if err.endswith("\n") else err + "\n")
    if rc != 0:
        sys.exit(1)


def screen_entry(a):
    return sub_entry(a, "screen", "aos-agent/screen",
                     lambda f: ("ScreenMissing", "%s does not declare the screen sub-interface (no screen); follow answers with aos-agent listen --follow --target %s" % (a.name, a.name)),
                     "ScreenBad")


def close_screen_if_any(a):
    """rm／stop 前：宣告了 screen 就先 close（正在答＝入口報 SessionBad，原樣轉、不往下做）。沒宣告就略過。"""
    try:
        _, entry = screen_entry(a)
    except Fail as e:
        if e.code in ("ScreenMissing", "InterfaceMissing"):
            return
        raise
    rc, err = run_entry(a, entry, ["close"])
    if rc != 0:
        pass_err(rc, err)
