"""槽與任務（spec.md 第 5、6 節）：槽名、槽的判定（spec 5.4 的表）、lost 前的身分掃描、kill、在槽裡起新的 run。
tick、tock、daemon 共用。讀寫一律經呼叫的人給的路徑（tick／tock 給 `/proc/self/fd/N/...`：node 中途被刪就寫不進去，不建鬼目錄）。"""
import collections
import os
import re
import shutil
import subprocess
import sys
import time

import aos7_mount
import aos7_proc
from aos7_fs import (BIN, N, OK, U, Unknown, env_with_bin, fact, inject, is_gone, is_int, now, proc_starttime, read_json,
                     test_point, write_json)

NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
SLOT_RE = re.compile(r"^([A-Za-z0-9_-]+)(?:\.([1-9][0-9]*))?$")

# 換 run 時清掉的基礎設施檔；任務自己寫的檔（state、usage…）與 ctl.json／ctl-done.json 留著（回條要活過新 run 起來那一刻）
INFRA_FILES = ("birth.json", "pid.json", "out.log", "exit.json", "tock.json", "writes.jsonl")
INFRA_DIRS = ("mnt", "mount-req", "mount-done")

EMPTY, LIVE, ENDED, UNKNOWN, SUSPECT = "empty", "live", "ended", "unknown", "suspect"


# ---------- 路徑與名字 ----------

def slot_dir(node, slot):
    """`<node>/.aos/tasks/<槽>`。"""
    return os.path.join(node, ".aos", "tasks", slot)


def slot_names(name, max_live=1):
    """name 的槽名：`name`、`name.1`…`name.(max_live−1)`。"""
    return [name] + ["%s.%d" % (name, k) for k in range(1, max(1, max_live))]


def run_id(slot, run):
    """`<槽>#<run>`：status、總結、回條裡指「哪一次」都用它。"""
    return "%s#%s" % (slot, run)


def list_slots(node):
    """`.aos/tasks/` 底下的槽名，回 (清單, 錯誤或 None)。資料夾確定不在＝沒有槽；列不出來＝不知道（回錯誤）。"""
    d = os.path.join(node, ".aos", "tasks")
    try:
        inject("listdir", d)
        names = os.listdir(d)
    except OSError as e:
        return [], (None if is_gone(e) else repr(e)[:200])
    return sorted(n for n in names if not n.startswith(".") and SLOT_RE.match(n)), None


# ---------- 判定一個槽（spec 5.4） ----------

def _same_run(path, run):
    """讀 pid.json／exit.json：回 (N／OK／U, 值或說明)。run 不是這一次的（上一個 run 沒清乾淨）當不存在；
    讀不到、壞掉＝U（核心自己寫的檔，壞了只能是被手改或磁碟壞）。"""
    st, v = fact(path)
    if st == OK and isinstance(v, dict):
        return (OK, v) if v.get("run") == run else (N, None)
    if st == N:
        return N, None
    return U, (v if st != OK else "%s 內容不是物件" % os.path.basename(path))


class View(dict):
    """一個槽的判定結果：state、run，有的話 birth、pid、exit、why、unsure。"""
    state = property(lambda self: self["state"])
    run = property(lambda self: self.get("run"))


def judge(fslot, node, slot, cur_round):
    """spec 5.4 的表，回 View；不做任何破壞性動作，疑似 lost（SUSPECT）交給 resolve。
    讀不到＝UNKNOWN；birth.json 壞掉也是 UNKNOWN（不從其他證據推回 run）；程序的身分讀不到、或剛起還在交接＝LIVE 加
    unsure（保守當活，不讓 tick 再起一份）。"""
    bst, birth = fact(os.path.join(fslot, "birth.json"))
    if bst == N:
        return View(state=EMPTY, run=None)
    if bst == U:
        return View(state=UNKNOWN, run=None, why=birth)
    if bst != OK or not isinstance(birth, dict) or not is_int(birth.get("run")):
        return View(state=UNKNOWN, run=None, why="birth.json 壞了；確認沒在跑後刪掉 birth.json 就會當空槽")
    run = birth["run"]
    v = View(state=None, run=run, birth=birth)
    est, ex = _same_run(os.path.join(fslot, "exit.json"), run)
    if est != N:
        return View(v, state=ENDED, exit=ex) if est == OK else View(v, state=UNKNOWN, why=ex)
    pst, pid = _same_run(os.path.join(fslot, "pid.json"), run)
    if pst == U:
        return View(v, state=UNKNOWN, why=pid)
    runner = birth.get("runner") if isinstance(birth.get("runner"), dict) else None
    states = [aos7_proc.same_process(runner.get("pid"), runner.get("starttime"))] if runner else []
    if pst == OK:
        v["pid"] = pid
        states.append(aos7_proc.same_process(pid.get("pid"), pid.get("starttime")))
    if aos7_proc.ALIVE in states:
        return View(v, state=LIVE)
    if aos7_proc.UNKNOWN in states:
        return View(v, state=LIVE, unsure="任務或 runner 的 /proc（pid／starttime）讀不到，當活")
    if pst == OK or runner:
        return _recheck(v, fslot, run, "任務與 runner 都不在" if pst == OK else "沒有 pid.json，runner 已不在")
    # 沒有 runner 也沒有 pid.json：birth 寫了、runner 還沒記上的交接空窗。起了兩回合以上還這樣，才去掃描判 lost
    br = birth.get("round")
    if is_int(br) and is_int(cur_round) and br <= cur_round - 2:
        return _recheck(v, fslot, run, "沒有 pid.json、沒有 runner，起了兩回合以上")
    return View(v, state=LIVE, unsure="剛起")


def _recheck(v, fslot, run, why):
    """判疑似 lost 前再看一次 exit.json（runner 可能剛好在這一瞬間寫完）。"""
    est, ex = _same_run(os.path.join(fslot, "exit.json"), run)
    if est == OK:
        return View(v, state=ENDED, exit=ex)
    return View(v, state=UNKNOWN, why=ex) if est == U else View(v, state=SUSPECT, why=why)


def resolve(v, fslot, node, slot, cur_round):
    """疑似 lost 先做身分掃描（NODE＋TID＋RUN）：這個 run 的 aos7-run 還在＝當活（它等一下就起任務）；有相符的程序先照 Q1
    收掉再判 lost；確定沒有就判 lost，寫 exit.json `{"run", "code": null, "lost": true}`。掃描不完整、收不掉、最後重讀
    exit.json 讀不到＝不知道，不判（判了 keep 就會重起、跟還活著的前任雙開）。非 SUSPECT 原樣回。"""
    if v.state != SUSPECT:
        return v
    pgid = (v.get("pid") or {}).get("pgid")
    try:
        found = aos7_proc.env_procs(node, slot, v.run)
        everyone = aos7_proc.env_procs(node, slot, v.run, runners=True)
        grp = bool(pgid) and aos7_proc.group_alive(pgid)
    except Unknown as e:
        return View(v, state=UNKNOWN, why="疑似 lost（%s），但身分掃描讀不完整，先不判：%s" % (v.get("why"), e))
    if set(everyone) - set(found):
        return View(v, state=LIVE, unsure="疑似 lost（%s），但這個 run 的 aos7-run 還在，當活" % v.get("why"))
    ex = {"run": v.run, "code": None, "lost": True, "at": now(), "round": cur_round}
    if found or grp:   # 先收殘留再宣告 lost，keep 重起才不會跟前任雙開
        clean, msg = aos7_proc.kill_identity(node, slot, v.run, pgid)
        if not clean:
            return View(v, state=UNKNOWN, why="疑似 lost，但相符的程序收不掉或確認不了：%s" % msg)
        ex["note"] = "lost 前收掉相符的殘留程序：%s" % msg
    est, old = _same_run(os.path.join(fslot, "exit.json"), v.run)
    if est != N:   # runner 可能剛寫了真的結果：讀到就用它，讀不到不能覆寫成 lost
        return View(v, state=ENDED, exit=old) if est == OK else View(v, state=UNKNOWN, why="疑似 lost，但最後重讀 exit.json 讀不到：%s" % old)
    if never_started(v, fslot):
        ex["never_started"] = True   # 事實出口：給模組（例如 once 保證包）讀，核心自己不據此做事
    write_json(os.path.join(fslot, "exit.json"), ex)
    return View(v, state=ENDED, exit=ex)


def never_started(v, fslot):
    """lost 的 run 看起來從沒起來過嗎：birth 沒記到 runner、沒有 pid.json、out.log 不存在或是空的（讀不到大小＝不知道＝False）。"""
    if (v.get("birth") or {}).get("runner") or v.get("pid") is not None:
        return False
    try:
        return os.stat(os.path.join(fslot, "out.log")).st_size == 0
    except OSError as e:
        return is_gone(e)


def judge_resolved(fslot, node, slot, cur_round):
    """判定一個槽，疑似 lost 的接著做身分掃描（必要時收程序、寫 lost）。"""
    return resolve(judge(fslot, node, slot, cur_round), fslot, node, slot, cur_round)


def ended_record(v, fslot):
    """已結束的 run → 總結 `ended` 的一筆；被 kill 收掉的帶 `by_ctl`（回條要是同一個 run 的，不把前一次的算到這次）。"""
    ex = v.get("exit") or {}
    rec = {"run": run_id(os.path.basename(fslot), v.run), "code": ex.get("code")}
    for k in ("lost", "never_started"):
        if ex.get(k):
            rec[k] = True
    if ex.get("error"):
        rec["error"] = str(ex["error"])[:200]
    cd = read_json(os.path.join(fslot, "ctl-done.json"))
    res = cd.get("result") if isinstance(cd, dict) else None
    if isinstance(res, dict) and res.get("run") == rec["run"] and cd.get("op") == "kill" and res.get("ok"):
        rec["by_ctl"] = {"op": "kill", "by": cd.get("by")}
    return rec


def unreported(v):
    """已結束、還沒在任何回合的總結報過（exit.json 沒有 seen_round）。"""
    return v.state == ENDED and not is_int((v.get("exit") or {}).get("seen_round"))


# ---------- 任務控制（spec 第 6 節：只有 kill） ----------

def kill_run(fslot, node, slot, v):
    """收掉 v 這一次 run（Q1 範圍），回 (ok, msg)。已結束算成功、順便收相符的殘留。
    剛起、pid.json 還沒寫的先等一下（免得 kill 打在任務起來之前）；收完給 runner 一點時間寫 exit.json，總結才看得到結束。"""
    if v.state == ENDED:
        clean, msg = aos7_proc.kill_identity(node, slot, v.run)
        return clean, "already ended" + ("" if msg.startswith("no process") else "; leftover: " + msg)
    pid = v.get("pid")
    end = time.monotonic() + aos7_proc.KILL_GRACE
    while pid is None and v.state == LIVE and time.monotonic() < end:
        st, pj = _same_run(os.path.join(fslot, "pid.json"), v.run)
        if st == OK or _same_run(os.path.join(fslot, "exit.json"), v.run)[0] == OK:
            pid = pj or {}
            break
        time.sleep(0.02)
    pid = pid or {}
    clean, msg = aos7_proc.kill_identity(node, slot, v.run, pid.get("pgid"),
                                         (pid.get("pid"), pid.get("starttime")) if is_int(pid.get("pid")) else None)
    end = time.monotonic() + 0.5
    while time.monotonic() < end and _same_run(os.path.join(fslot, "exit.json"), v.run)[0] != OK:
        time.sleep(0.02)
    return clean, msg


def run_ctl(ctx, slot):
    """執行槽的 ctl.json（若有）：寫 ctl-done.json（蓋掉舊的），再刪請求。回紀錄 dict 或 None。
    請求只有 `{"op": "kill", "run": 整數, "by", "why"}`：op 不是 kill、run 缺或不是整數＝輸入不合，回條 ok:false、刪請求；
    run 不是槽現在的（已換人）＝ok:false。帶 run 讓重播天然冪等：處理到一半被殺或請求刪不掉，再執行也只對同一個 run。
    ctl.json 讀不到、槽的狀態不知道＝請求留著，下一次再看。restart／reload 在控制包（modules/control）。"""
    fslot = slot_dir(ctx.fnode, slot)
    path = os.path.join(fslot, "ctl.json")
    st, ctl = fact(path)
    if st == N:
        return None
    if st == U:
        return {"slot": slot, "op": None, "ok": False, "err": "%s（請求留著，下一次再看）" % ctl}
    v = View(state=None, run=None)
    if st != OK or not isinstance(ctl, dict):
        ok, msg = False, "unreadable JSON" if st != OK else "not a JSON object"
        ctl = {"raw": "unreadable" if st != OK else ctl}
    elif ctl.get("op") != "kill":
        ok, msg = False, "op 只有 kill（restart／reload 見控制包 modules/control），拿到 %r" % (ctl.get("op"),)
    elif not is_int(ctl.get("run")):
        ok, msg = False, "run 必填、要是整數（要收的是哪一次），拿到 %r" % (ctl.get("run"),)
    else:
        v = judge_resolved(fslot, ctx.node, slot, ctx.round)
        if v.state == UNKNOWN:
            return {"slot": slot, "op": "kill", "ok": False, "err": "槽的狀態不知道（%s），請求留著，下一次再看" % v.get("why")}
        if v.state == EMPTY or v.run is None:
            ok, msg = False, "槽裡沒有可以 kill 的 run"
        elif ctl["run"] != v.run:
            ok, msg = False, "指定的 run %d 已經不是現在的（現在是 %s），沒執行" % (ctl["run"], run_id(slot, v.run))
        else:
            ok, msg = kill_run(fslot, ctx.node, slot, v)
    rid = run_id(slot, v.run) if v.run is not None else None
    ctl["result"] = {"ok": ok, "msg": msg, "at": now(), "run": rid}
    write_json(os.path.join(fslot, "ctl-done.json"), ctl)
    test_point("ctl-after-done")
    rec = {"slot": slot, "run": rid, "op": ctl.get("op"), "ok": ok}
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as e:
        rec["err"] = "ctl.json 刪不掉：%r；下一次再執行也只對同一個 run" % (e,)
    return rec


def run_all_ctl(ctx):
    """對每個槽執行 ctl.json，回紀錄清單。一個槽出事只在它那筆記 ok:false＋err；列不出槽回一筆錯誤。"""
    slots, err = list_slots(ctx.fnode)
    if err:
        return [{"slot": None, "op": None, "ok": False, "err": "列不出槽：%s" % err}]
    out = []
    for slot in slots:
        try:
            r = run_ctl(ctx, slot)
        except Exception as e:   # noqa: BLE001
            r = {"slot": slot, "op": None, "ok": False, "err": repr(e)[:200]}
        if r:
            out.append(r)
    return out


# ---------- 起任務（spec 5.3） ----------

# 一次 tick／tock 的環境：root、node_id、node（實際路徑）、fnode（讀寫用的 fd 路徑）、round
Ctx = collections.namedtuple("Ctx", "root node_id node fnode round")


def clear_slot(fslot):
    """換 run：清掉上一個 run 的基礎設施檔（被佔成資料夾的也清），任務自己寫的檔留著——同槽的下一個 run 接得上（spec §8）。"""
    for n in INFRA_FILES + INFRA_DIRS:
        p = os.path.join(fslot, n)
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p, ignore_errors=n in INFRA_FILES)
        elif os.path.lexists(p):
            os.unlink(p)


def start_in_slot(ctx, item, slot, run):
    """在槽裡起新的 run（spec 5.3 第 2～5 步；第 1 步的判定由呼叫的人做完），回 run id：清槽、建掛載、先寫 birth.json
    （中途被殺也留下交接證據）、起 aos7-run（傳槽的 fd、cwd 是抓著的 node：字串路徑被換掉也不建鬼目錄）、補上 runner。
    開不了槽 fd 或 aos7-run 起不了＝照樣寫 exit.json code 127，任務不會永遠算剛起。"""
    root, node, fnode, rnd = ctx.root, ctx.node, ctx.fnode, ctx.round
    tdir = slot_dir(node, slot)
    fslot = slot_dir(fnode, slot)
    os.makedirs(fslot, exist_ok=True)
    clear_slot(fslot)
    birth = {"name": item.get("name"), "slot": slot, "run": run, "round": rnd, "node": ctx.node_id,
             "once": item.get("mode") == "once", "at": now(), "runner": None}
    if "inst" in item:
        birth["inst"] = item["inst"]
    else:
        birth["argv"] = item.get("argv", [])
    birth["mounts"] = aos7_mount.make(root, tdir, item.get("mounts") or {}, fs_taskdir=fslot, node=node, fnode=fnode)
    if "x" in item:
        birth["x"] = item["x"]   # 模組用的宣告欄位：核心不看內容，照抄
    bpath = os.path.join(fslot, "birth.json")
    write_json(bpath, birth)
    test_point("after-birth")
    env = env_with_bin()
    # 動作控制與測試鉤子不傳給任務；AOS7_TEST_HOOKS／RUNNER_CRASH 留給 aos7-run（它交給任務前拿掉全部 AOS7_TEST_*）
    for k in ("AOS7_GEN", "AOS7_EARLY", "AOS7_INCOMPLETE", "AOS7_TEST_CRASH", "AOS7_TEST_HANG", "AOS7_TEST_FAULT",
              "AOS7_TEST_FAULT_HITS"):
        env.pop(k, None)
    env.update({"AOS7_ROOT": root, "AOS7_NODE": node, "AOS7_NODE_ID": ctx.node_id, "AOS7_TASK": tdir,
                "AOS7_TID": slot, "AOS7_RUN": str(run)})
    tfd = None
    try:
        tfd = os.open(fslot, os.O_RDONLY | os.O_DIRECTORY)
        p = subprocess.Popen([sys.executable, os.path.join(BIN, "aos7-run"), tdir, str(tfd)], cwd=fnode, env=env,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True, pass_fds=(tfd,))
    except OSError as e:
        write_json(os.path.join(fslot, "exit.json"), {"run": run, "code": 127, "at": now(), "round": rnd, "error": str(e)})
        return run_id(slot, run)
    finally:
        if tfd is not None:
            os.close(tfd)
    test_point("after-popen")
    cur = read_json(bpath)
    if isinstance(cur, dict) and cur.get("run") == run:   # 只補 runner，保留 birth 其他欄位
        cur["runner"] = {"pid": p.pid, "starttime": proc_starttime(p.pid)}
        try:
            write_json(bpath, cur)
        except OSError:
            pass
    test_point("after-runner")
    return run_id(slot, run)
