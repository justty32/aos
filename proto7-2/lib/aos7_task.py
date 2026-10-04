"""槽與任務：槽名、三態判定、lost 判定前的身分掃描、kill（任務控制）、在槽裡起新的 run（spec.md 第 4.1、5、6 節）。

tick、tock、daemon 共用。起點是 proto7-1 lib/aos7_task.py，改成「槽＝照名字重用的任務資料夾」＋ run 號。
讀寫一律經呼叫的人給的路徑（tick／tock 給 `/proc/self/fd/N/...`，node 中途被刪就寫不進去、不建鬼目錄）。

讀取 .aos/tasks.json、各槽 birth／pid／exit／ctl；
寫出生／結束／控制回條，重建槽的基礎設施與掛載；實際任務交 aos7-run 啟動（S-10）。
不變條件二在 judge／resolve／start_in_slot 分段落實；換 run 保留上層 state 是不變條件三（spec §5.3、§8）。"""
import os
import re
import shutil
import subprocess
import sys
import time

import aos7_mount
import aos7_proc
from aos7_fs import (BIN, N, OK, U, Unknown, env_with_bin, fact, inject, is_gone, is_int, now,
                     proc_starttime, read_json, test_point, write_json)

NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
SLOT_RE = re.compile(r"^([A-Za-z0-9_-]+)(?:\.([1-9][0-9]*))?$")

# 換 run 時清掉的基礎設施檔（spec 5.1）。ctl.json／ctl-done.json 不清（problems.md P2-04）。
INFRA_FILES = ("birth.json", "pid.json", "out.log", "exit.json", "tock.json", "writes.jsonl")
INFRA_DIRS = ("mnt", "mount-req", "mount-done")

EMPTY, LIVE, ENDED, UNKNOWN, SUSPECT = "empty", "live", "ended", "unknown", "suspect"


# ---------- 路徑與名字 ----------

def tasks_dir(node):
    """`<node>/.aos/tasks/`。

    node 是實際或 fd 路徑；回任務目錄字串，不存取磁碟（spec §5.1）。"""
    return os.path.join(node, ".aos", "tasks")


def slot_dir(node, slot):
    """以 node 路徑與 slot 槽名回槽目錄字串，不建立目錄（spec §5.1）。"""
    return os.path.join(tasks_dir(node), slot)


def slot_names(name, max_live=1):
    """name 的槽名：`name`、`name.1`…`name.(max_live−1)`（spec 5.1）。

    name 是已驗證任務名，max_live 是槽數；回槽名清單，至少包含 name。型別與正值由 tick 先驗證（P2-18）。"""
    return [name] + ["%s.%d" % (name, k) for k in range(1, max(1, max_live))]


def run_id(slot, run):
    """以 slot 槽名與 run 序號回 `<slot>#<run>` 字串，供 status／總結／回條識別執行（spec §5.2）。"""
    return "%s#%s" % (slot, run)


def list_slots(node):
    """`.aos/tasks/` 底下的槽名（略過 `.` 開頭與名字不合的）。回 (清單, 錯誤或 None)：列不出來（I/O）＝不知道。

    node 是實際或 fd 路徑；確定目錄不存在回 ([], None)，其他 I/O 回 ([], 錯誤字串)。
    呼叫端據此保留未知狀態，不在列目錄失敗時重用槽（spec §0、§4.2、P2-09）。"""
    try:
        inject("listdir", tasks_dir(node))
        names = os.listdir(tasks_dir(node))
    except OSError as e:
        if is_gone(e):
            return [], None
        return [], repr(e)[:200]
    return sorted(n for n in names if not n.startswith(".") and SLOT_RE.match(n)), None


# ---------- 讀一個槽 ----------

def _same_run(path, run):
    """讀 pid.json／exit.json／tock.json：回 (N／OK／U, 值或說明)。`run` 跟這次不同（上一個 run 沒清乾淨的）當不存在（spec 5.1）；
    讀不到、不是一般檔、內容壞掉＝U（核心自己寫的檔，壞了只能是被手改或磁碟壞）。"""
    st, v = fact(path)
    if st == OK and isinstance(v, dict):
        return (OK, v) if v.get("run") == run else (N, None)
    if st == N:
        return N, None
    return U, (v if st != OK else "%s 內容不是物件" % os.path.basename(path))


class View(dict):
    """一個槽的判定結果：state、run、birth、pid、exit、why。"""

    @property
    def state(self):
        """以 self 判定結果回 state 字串；欄位缺少時拋 KeyError，不自行猜狀態。"""
        return self["state"]

    @property
    def run(self):
        """以 self 判定結果回 run 序號；未能辨識時回 None（spec §5.4）。"""
        return self.get("run")


def judge(fslot, node, slot, cur_round):
    """spec 5.4 的表：回 View。fslot＝讀寫用的槽路徑；node＝node 的實際路徑（身分掃描比 AOS7_NODE）。

    不做任何破壞性動作；SUSPECT（疑似 lost）交給 resolve。

    slot 是槽名、cur_round 是目前回合；檔案 I/O 回 UNKNOWN，pid／starttime 讀不到回 LIVE 加 unsure，
    暫未完成交接也保守當 LIVE（spec §0、§5.3 不變條件二、P2-08）。birth.json 內容壞掉也是 UNKNOWN：生命週期檔只有核心寫，
    壞了只能是被手改或磁碟壞，不從其他證據推回 run。"""
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
    if est == OK:
        return View(v, state=ENDED, exit=ex)
    if est == U:
        return View(v, state=UNKNOWN, why=ex)
    pst, pid = _same_run(os.path.join(fslot, "pid.json"), run)
    if pst == U:
        return View(v, state=UNKNOWN, why=pid)
    runner = birth.get("runner") if isinstance(birth.get("runner"), dict) else None
    r_state = aos7_proc.same_process(runner.get("pid"), runner.get("starttime")) if runner else None
    if pst == OK:
        t_state = aos7_proc.same_process(pid.get("pid"), pid.get("starttime"))
        if aos7_proc.ALIVE in (t_state, r_state):
            return View(v, state=LIVE, pid=pid)
        # spec §5.3 不變條件二、P2-08：身分不明用 LIVE＋unsure 保住槽，不讓 tick 再起一份。
        if aos7_proc.UNKNOWN in (t_state, r_state):
            return View(v, state=LIVE, pid=pid, unsure="任務或 runner 的 /proc（pid／starttime）讀不到，當活（K-05、A2-01）")
        return _recheck(View(v, pid=pid), fslot, run, "任務與 runner 都不在")
    if runner:
        if r_state == aos7_proc.ALIVE:
            return View(v, state=LIVE)
        if r_state == aos7_proc.UNKNOWN:
            return View(v, state=LIVE, unsure="runner 的 /proc（pid／starttime）讀不到，當活（K-05、A2-01）")
        return _recheck(v, fslot, run, "沒有 pid.json，runner 已不在")
    br = birth.get("round")
    # spec §5.4、P2-02：birth 與 runner 登記有交接空窗，等兩回合才走 lost 掃描；once 不自動重起。
    if is_int(br) and is_int(cur_round) and br <= cur_round - 2:
        return _recheck(v, fslot, run, "沒有 pid.json、沒有 runner，起了兩回合以上")
    return View(v, state=LIVE, unsure="剛起")


def _recheck(v, fslot, run, why):
    """判成疑似 lost 前再看一次 exit.json（runner 可能剛好在這一瞬間寫完；proto7-1 P-07）。

    v 是原 View、fslot 是槽路徑、run 是序號、why 是疑似失聯原因；
    回 ENDED／UNKNOWN／SUSPECT 的新 View，讀不到 exit 時保留未知（spec §5.4）。"""
    est, ex = _same_run(os.path.join(fslot, "exit.json"), run)
    if est == OK:
        return View(v, state=ENDED, exit=ex)
    if est == U:
        return View(v, state=UNKNOWN, why=ex)
    return View(v, state=SUSPECT, why=why)


def resolve(v, fslot, node, slot, cur_round):
    """疑似 lost 一律先做身分掃描（NODE＋TID＋RUN）：找到相符的活程序先照 Q1 收掉，再判 lost；找不到就判 lost（spec 5.4）。
    lost 寫 exit.json `{"run", "code": null, "lost": true}`。收不乾淨（SIGKILL 後還在）＝不知道，不判 lost。回新的 View。

    v 是原判定、fslot 是槽路徑，node／slot 是掃描身分，cur_round 是寫 lost 的回合；
    非 SUSPECT 原樣回傳。tick 重用槽前也呼叫，讓漏失的結束先進 reaped（spec §4.2、P2-03）。"""
    if v.state != SUSPECT:
        return v
    pgid = (v.get("pid") or {}).get("pgid")
    try:
        found = aos7_proc.env_procs(node, slot, v.run)
        everyone = aos7_proc.env_procs(node, slot, v.run, runners=True)
        grp = bool(pgid) and aos7_proc.group_alive(pgid)
    except Unknown as e:
        # A2-01：掃描不完整＝不知道有沒有相符的程序，不能判 lost（判了 keep 就會重起、跟還活著的前任雙開）。
        return View(v, state=UNKNOWN, why="疑似 lost（%s），但身分掃描讀不完整，先不判：%s" % (v.get("why"), e))
    if set(everyone) - set(found):
        # 這個 run 的 aos7-run 還活著（birth 沒記到 runner、pid.json 還沒寫：例如 tick 被殺在 after-popen，而回合跑得比 runner
        # 起來還快）：它等一下就會起任務、寫 pid.json／exit.json。判 lost 會讓 keep 雙開、once 被收掉，所以當活（矩陣 after-popen）。
        return View(v, state=LIVE, unsure="疑似 lost（%s），但這個 run 的 aos7-run 還在，當活" % v.get("why"))
    note = None
    # spec §5.3 不變條件二、§5.4：先收殘留再宣告 lost，keep 才不會跟前任雙開（K-04）。
    if found or grp:
        clean, msg = aos7_proc.kill_identity(node, slot, v.run, pgid)
        if not clean:
            return View(v, state=UNKNOWN, why="疑似 lost，但相符的程序收不掉或確認不了：%s" % msg)
        note = "lost 前收掉相符的殘留程序：%s" % msg
    est, ex = _same_run(os.path.join(fslot, "exit.json"), v.run)
    if est == OK:
        return View(v, state=ENDED, exit=ex)
    if est == U:
        # 最後重讀 exit.json 讀不到：不能覆寫成 lost（runner 可能剛寫了真的結果）
        return View(v, state=UNKNOWN, why="疑似 lost，但最後重讀 exit.json 讀不到：%s" % ex)
    ex = {"run": v.run, "code": None, "lost": True, "at": now(), "round": cur_round}
    if note:
        ex["note"] = note
    if never_started(v, fslot):
        ex["never_started"] = True   # 事實出口：給模組（例如 once 保證包）讀，核心自己不據此做事
    write_json(os.path.join(fslot, "exit.json"), ex)
    return View(v, state=ENDED, exit=ex)


def never_started(v, fslot):
    """lost 的 run 看起來從沒起來過嗎：birth.json 沒記到 runner、沒有 pid.json、out.log 不存在或是空的。
    out.log 讀不到大小＝不知道＝回 False（不帶這個事實）。"""
    b = v.get("birth") or {}
    if b.get("runner") or v.get("pid") is not None:
        return False
    try:
        return os.stat(os.path.join(fslot, "out.log")).st_size == 0
    except OSError as e:
        return is_gone(e)


def judge_resolved(fslot, node, slot, cur_round):
    """以 fslot 槽路徑、node 實際路徑、slot 槽名、cur_round 回合判定並處理疑似 lost；
    回 View，未知沿用 judge／resolve 的處置，必要時會收程序並寫 exit.json（spec §5.4）。"""
    return resolve(judge(fslot, node, slot, cur_round), fslot, node, slot, cur_round)


def ended_record(v, fslot):
    """已結束的 run → last-round.json `ended` 的一筆。被任務控制收掉的帶 `by_ctl`。

    v 是已結束 View，fslot 是槽路徑；回總結 dict。ctl-done 讀不到或不是同一 run 就不附 by_ctl，
    避免保留的前次回條誤算到這次（spec §3、§6、P2-04）。"""
    ex = v.get("exit") or {}
    rec = {"run": run_id(os.path.basename(fslot), v.run), "code": ex.get("code")}
    if ex.get("lost"):
        rec["lost"] = True
    if ex.get("never_started"):
        rec["never_started"] = True
    if ex.get("error"):
        rec["error"] = str(ex["error"])[:200]
    cd = read_json(os.path.join(fslot, "ctl-done.json"))
    res = cd.get("result") if isinstance(cd, dict) else None
    if isinstance(res, dict) and res.get("run") == rec["run"] and cd.get("op") == "kill" and res.get("ok"):
        rec["by_ctl"] = {"op": cd.get("op"), "by": cd.get("by")}
    return rec


def unreported(v):
    """已結束、但還沒在任何回合的 last-round.json 報過（exit.json 沒有 seen_round）。

    v 是槽的 View；回 bool，只有 ENDED 且 seen_round 不是整數才是 True；
    UNKNOWN 回 False，不能據此抹掉未知的結果（spec §4.2、§7、P2-03）。"""
    return v.state == ENDED and not is_int((v.get("exit") or {}).get("seen_round"))


# ---------- 任務控制（第 6 節） ----------

def _wait_pid_json(fslot, run, v, limit=aos7_proc.KILL_GRACE):
    """剛起、aos7-run 還沒寫 pid.json：等一下（最多 limit 秒），免得 kill 打在任務起來之前。

    fslot 是槽路徑、run 是序號、v 是呼叫端 View（目前未使用）、limit 是秒數；
    回同 run 的 pid 字典，已結束或等不到（含讀不到）回 None（spec §5.3、§6）。"""
    end = time.monotonic() + limit
    while time.monotonic() < end:
        st, pid = _same_run(os.path.join(fslot, "pid.json"), run)
        if st == OK:
            return pid
        est, _ = _same_run(os.path.join(fslot, "exit.json"), run)
        if est == OK:
            return None
        time.sleep(0.02)
    return None


def kill_run(fslot, node, slot, v):
    """收掉 v 這一次 run（Q1 範圍），回 (ok, msg)。已結束算成功，順便收相符的殘留。

    fslot 是槽路徑，node／slot 是掃描身分，v 是已判定的 run；回 (bool, 說明)，
    程序收乾淨與否由 kill_identity 決定，exit 等不到不更改該結果（spec §6）。"""
    if v.state == ENDED:
        clean, msg = aos7_proc.kill_identity(node, slot, v.run)
        return clean, "already ended" + ("" if msg.startswith("no process") else "; leftover: " + msg)
    pid = v.get("pid")
    if pid is None and v.state == LIVE:
        pid = _wait_pid_json(fslot, v.run, v)
    pid = pid or {}
    # 帶上 pid.json 記的任務 (pid, starttime)：kill 之後它還活著（例如群組核對不了而沒送訊號）就不能回成功
    clean, msg = aos7_proc.kill_identity(node, slot, v.run, pid.get("pgid"),
                                         (pid.get("pid"), pid.get("starttime")) if is_int(pid.get("pid")) else None)
    # 給 runner 一點時間寫 exit.json（code 負數＝被訊號殺），回合總結才看得到結束
    end = time.monotonic() + 0.5
    while time.monotonic() < end:
        if _same_run(os.path.join(fslot, "exit.json"), v.run)[0] == OK:
            break
        time.sleep(0.02)
    return clean, msg


def run_ctl(ctx, slot):
    """執行 `<槽>/ctl.json`（若有），搬成 ctl-done.json（蓋掉舊的）。回紀錄 dict 或 None（spec §6）。

    請求只有 `{"op": "kill", "run": 整數, "by", "why"}`。op 不是 kill、run 缺或不是整數＝輸入不合（B）：回條 ok:false、刪請求。
    run 不是槽現在的 run（已換人）＝ok:false、沒執行；那個 run 已結束＝ok:true（順便收殘留）；kill 之後確認任務程序不在才 ok:true。
    帶 run 讓重播天然冪等：處理到一半被殺或請求刪不掉，下一次再執行也只對同一個 run。ctl.json 讀不到、槽的狀態不知道（U）＝請求留著，
    下一次再看。restart／reload 在控制包（modules/control）由請求端做。"""
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
    """對每個槽執行 ctl.json。一個槽處理失敗只在它那筆記 `ok: false`＋`err`，其他照做。

    ctx 是本次動作環境；回每份控制的紀錄清單，列槽失敗回一筆錯誤，
    不把「不知道」當成已成功執行（spec §0、§4.2、§7）。"""
    out = []
    slots, err = list_slots(ctx.fnode)
    if err:
        return [{"slot": None, "op": None, "ok": False, "err": "列不出槽：%s" % err}]
    for slot in slots:
        try:
            r = run_ctl(ctx, slot)
        except Exception as e:   # noqa: BLE001
            r = {"slot": slot, "op": None, "ok": False, "err": repr(e)[:200]}
        if r:
            out.append(r)
    return out


# ---------- 起任務（5.3） ----------

class Ctx:
    """一次 tick／tock 的環境：root、node_id、node（實際路徑）、fnode（讀寫用的 fd 路徑）、round。"""

    def __init__(self, root, node_id, node, fnode, rnd):
        """以 root 根、node_id、node 實際路徑、fnode fd 路徑與 rnd 回合保存動作上下文；回 None。"""
        self.root, self.node_id, self.node, self.fnode, self.round = root, node_id, node, fnode, rnd


def clear_slot(fslot):
    """換 run：清掉上一個 run 的基礎設施檔，任務自己寫的檔留著（spec 5.1，W6）。

    fslot 是槽路徑；回 None，清檔失敗通常向外拋（檔名被佔成資料夾時 rmtree 忽略錯誤）。state／usage 等任務檔保留，
    使同槽重起接得上累計（spec §8 不變條件三）；ctl 與回條也保留（P2-04）。"""
    import errno
    # spec §5.1、§8 不變條件三：只清列名的設施檔，上層 state／usage 不能因換 run 歸零。
    for n in INFRA_FILES:
        try:
            os.unlink(os.path.join(fslot, n))
        except IsADirectoryError:
            shutil.rmtree(os.path.join(fslot, n), ignore_errors=True)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
    for n in INFRA_DIRS:
        p = os.path.join(fslot, n)
        if os.path.islink(p) or os.path.isfile(p):
            os.unlink(p)
        elif os.path.isdir(p):
            shutil.rmtree(p)


def start_in_slot(ctx, item, slot, run):
    """在槽裡起新的 run（spec 5.3 第 2～5 步；第 1 步的判定由呼叫的人做完）。回 run id。

    起不來（開不了槽 fd、aos7-run 起不了）照樣寫 exit.json code 127，任務不會永遠算剛起。

    ctx 是動作環境，item 是已驗證的定義，slot／run 指定本次執行。
    清槽／掛載等前置 I/O 例外向外拋；捕捉到的開槽 fd／Popen 失敗寫 exit 127（spec §5.3）。"""
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
        birth["x"] = item["x"]   # 模組用的宣告欄位：核心不看內容，照抄（擴充點）
    bpath = os.path.join(fslot, "birth.json")
    # spec §5.3 不變條件二：先留下 birth，再起 runner；中途被殺仍有可恢復的交接證據。
    write_json(bpath, birth)
    test_point("after-birth")
    env = env_with_bin()
    # spec §5.5：每次重建身分，動作控制與測試鉤子不傳給任務。AOS7_TEST_HOOKS、AOS7_TEST_RUNNER_CRASH 留給 aos7-run
    # （它交給任務的環境拿掉全部 AOS7_TEST_*）。
    for k in ("AOS7_GEN", "AOS7_EARLY", "AOS7_INCOMPLETE", "AOS7_TEST_CRASH", "AOS7_TEST_HANG", "AOS7_TEST_FAULT",
              "AOS7_TEST_FAULT_HITS"):
        env.pop(k, None)
    env.update({"AOS7_ROOT": root, "AOS7_NODE": node, "AOS7_NODE_ID": ctx.node_id, "AOS7_TASK": tdir,
                "AOS7_TID": slot, "AOS7_RUN": str(run)})
    try:
        tfd = os.open(fslot, os.O_RDONLY | os.O_DIRECTORY)
    except OSError as e:
        write_json(os.path.join(fslot, "exit.json"), {"run": run, "code": 127, "at": now(), "round": rnd,
                                                      "error": str(e)})
        return run_id(slot, run)
    try:
        # spec §2.5、§5.3：傳已開的槽 fd 並用抓住的 cwd，字串路徑被換掉也不另建鬼目錄。
        p = subprocess.Popen([sys.executable, os.path.join(BIN, "aos7-run"), tdir, str(tfd)], cwd=fnode, env=env,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True, pass_fds=(tfd,))
    except OSError as e:
        write_json(os.path.join(fslot, "exit.json"), {"run": run, "code": 127, "at": now(), "round": rnd,
                                                      "error": str(e)})
    else:
        test_point("after-popen")
        birth["runner"] = {"pid": p.pid, "starttime": proc_starttime(p.pid)}
        try:
            cur = read_json(bpath)
            if isinstance(cur, dict) and cur.get("run") == run:
                cur["runner"] = birth["runner"]   # 保留 runner 之前可能已經被別的步驟改過的欄位
                write_json(bpath, cur)
        except OSError:
            pass
        test_point("after-runner")
    finally:
        os.close(tfd)
    return run_id(slot, run)
