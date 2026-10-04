"""aos7-daemon：常駐程式——只跑登記在 `.aosd/nodes.json` 的 node（不掃資料夾）、每條時間線一個迴圈、讀控制檔、寫 status.json
（spec.md 第 1、2 節，S-03～S-06）。

    aos7-daemon <root>

SIGTERM／SIGINT＝stop 加 kill（S-21 路一：子 daemon 被父時間線 kill 時帶走自己的任務）。
起點是 proto7-1 lib/aos7_daemon.py；掃描、rescan、log.jsonl（改成 log.on 開關）、retention／disk 拿掉，加上 register／unregister、
pause owner、node 消失的 inode 比對。

由人或父 node 的任務經 bin/aos7-daemon 啟動（S-21）；daemon 只管理登記與程序生命週期。
讀寫 root/.aosd/ 的 nodes.json、paused.json、gen.json、owner.json、控制請求／回條、status.json；
持有 daemon.lock，按需處理 stopped.json 與 log.on/log.jsonl，讀 node 的回合／任務狀態供監督（spec §2.8、§9）。
"""
import datetime
import errno
import fcntl
import os
import shutil
import signal
import stat
import sys
import threading
import time

import aos7_proc
import aos7_task
from aos7_daemon_timeline import POLL, Timeline
from aos7_fs import (FD_PREFIX, GONE_ERRNO, append_jsonl, canonical_node, inject, is_int, is_regular, locked, node_path,
                     now, read_json, sweep_tmp, write_json)

CTL_BATCH = 200      # 一圈最多處理幾個控制檔（2.3）
CTL_BUDGET_S = 0.05  # 一圈處理控制檔最多花幾秒（跟 CTL_BATCH 取先到的）
LIVE_EVERY = 0.25    # status.json 的 live 與記著的 pgid 多久重算一次（秒；2.6、2.8）
SWEEP_EVERY = 1.0    # 多久清一次 .aosd／ctl／ctl-done 裡寫者已死的暫存檔（秒；A2-07）
# GONE_ERRNO（ENOENT／ENOTDIR）才算「確定不存在」；其他（ESTALE、EIO、EACCES…）是「看不到」——定義在 aos7_fs 共用。


def norm_id(node):
    """將控制檔的 node 值正規化為相對 id，根為「.」（spec §1）。
    參數 node 可為任意值；非法或不可判讀時回 None，合法時回以 / 分隔的字串。"""
    if not isinstance(node, str) or node.startswith("/") or "\0" in node:
        return None
    parts = [p for p in node.split("/") if p not in ("", ".")]
    if any(p == ".." or p.startswith(".") for p in parts):
        return None
    return "/".join(parts) or "."


def _replace(src, dst):
    """把 src 原物搬到 dst，蓋掉同名舊物（含資料夾），只留最近一份（spec §2.3；P2-11、P2-13）。
    src、dst 是來源與目的路徑；成功回 None，檔案系統錯誤向上拋。"""
    if os.path.isdir(dst) and not os.path.islink(dst):
        shutil.rmtree(dst)
    os.replace(src, dst)


class Daemon:
    """管理一個 root 的登記、控制、狀態與多條時間線；共享狀態由主迴圈及時間線協作更新（spec §2）。"""

    def __init__(self, root):
        """建立管理 root 空間根的 daemon 狀態，抓住目錄 fd（spec §1、§2.5）。
        root 是已存在的資料夾路徑；初始化回 None，開目錄失敗向上拋；此時尚未拿 daemon.lock。"""
        # A2-04：以實際路徑當空間根——node 的身分（canonical_node）照實際位置比，根本身是連結也不會把 "." 判成連結。
        self.root = os.path.realpath(root)
        # spec §2.5：/proc/self/fd 固定指向已開啟的 inode，路徑被換掉也不會寫進替身 root。
        # 自己的 `.aosd` 一律經 root 的 fd 讀寫：root 被搬走寫到新位置，被刪就寫不進去（2.5）
        self.rfd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        self.aosd = FD_PREFIX + str(self.rfd) + "/.aosd"
        self.root_gone = False
        self.registry = {}           # nodes.json 的內容 {id: {"by", "at"}}
        self.timelines = {}          # {id: Timeline}
        self.missing = {}            # {id: {"since", "why"}}：已登記、資料夾不在
        self.node_errors = {}        # {id: last_error}：沒有時間線時的錯誤（看不到…）
        self.reapers = {}            # {id: thread}：node 消失時在背景收程序；收完才重開時間線
        self.retiring = {}           # {id: (Timeline, kill)}：unregister 中
        self.stopping = False
        self.stopping_since = None
        self.kill_on_stop = False
        self._lock = threading.Lock()
        self.paused = {}             # {id: [owner...]}（2.4）
        self.steps = {}              # {id: {owner: left}}：resume 帶 rounds，按 owner 各記一份（A2-06）
        self._live = {}              # {id: (monotonic, [run id])}
        self._pgids = {}             # {id: {pgid}}：活任務的程序群組，node 消失時收（2.6）
        self._uncertain = {}         # {id: [{"slot","run","why"}]}：判不出的槽（UNKNOWN／unsure），進 status（A2-08）
        self._swept = 0.0            # 上次清暫存檔的 monotonic 時刻（A2-07）
        self.root_error = None       # 看 root 時的「看不到」錯誤（不是消失；註解疑點 daemon:595）
        self.gen = None
        self.io_errors = 0
        self.ctl_backlog = False
        self.ctl_stuck = set()
        self.last_ctl_error = None
        self.last_event = None

    # ---------- 小工具 ----------

    def log(self, **kw):
        """以事件欄位 kw 更新 last_event；有 log.on 才追加 log.jsonl（spec §2.8、§9；W9）。
        回 None；事件檔寫入失敗不阻止主流程，記憶體仍留最近事件。"""
        ev = dict(at=now(), **kw)
        self.last_event = ev
        try:
            if os.path.lexists(os.path.join(self.aosd, "log.on")):
                with self._lock:
                    append_jsonl(os.path.join(self.aosd, "log.jsonl"), ev)
        except OSError:
            pass

    def save_nodes(self):
        """將記憶體 registry 原子覆寫為 nodes.json（spec §1）；無額外參數，回 None，寫入錯誤向上拋。"""
        write_json(os.path.join(self.aosd, "nodes.json"), {"nodes": self.registry})

    def save_paused(self):
        """將記憶體非空 owner 清單原子寫回 paused.json（spec §2.4）。
        無額外參數，回 None；呼叫端負責協調記憶體存取，寫入錯誤向上拋。
        daemon 是 paused.json 唯一的寫者（daemon.lock 保證只有一個），照 spec §0 仍對 paused.json.lock 拿 flock
        （註解疑點 daemon:106），讓讀—改—寫的外部工具有一致的約定。"""
        path = os.path.join(self.aosd, "paused.json")
        with locked(path, timeout=1.0):
            write_json(path, {"paused": {k: v for k, v in sorted(self.paused.items()) if v}})

    def load_state(self):
        """啟動時讀 nodes.json、paused.json 恢復登記與 pause owner（spec §1、§2.4）。
        無額外參數，回 None；非 None 的 JSON 若 nodes 結構不合就記錯；非法 id 略過，讀取失敗當空值，相容舊 pause 清單。"""
        nj = read_json(os.path.join(self.aosd, "nodes.json"))
        nodes = nj.get("nodes") if isinstance(nj, dict) else None
        if isinstance(nodes, dict):
            self.registry = {k: (v if isinstance(v, dict) else {}) for k, v in nodes.items() if norm_id(k) == k}
        elif nj is not None:
            self.node_errors["."] = {"prog": "nodes.json", "at": now(), "err": "nodes.json 讀不懂，當空的（沒改它）"}
        pj = read_json(os.path.join(self.aosd, "paused.json"), {})
        pl = pj.get("paused") if isinstance(pj, dict) else None
        if isinstance(pl, dict):
            self.paused = {k: [o for o in v if isinstance(o, str)] for k, v in pl.items() if isinstance(v, list)}
        elif isinstance(pl, list):   # proto7-1 的格式：一個 node 一個開關 → 不帶 owner 的那一格
            self.paused = {k: [""] for k in pl if isinstance(k, str)}

    def is_paused(self, nid):
        """查 nid 的記憶體 owner 清單是否非空（spec §2.4），回 bool。
        不讀磁碟；沒有 nid 或清單為空回 False，這不是磁碟可讀性的判定。"""
        return bool(self.paused.get(nid))

    def round_done(self, nid):
        """時間線確認關回合後，對 nid 每個 owner 的 rounds 倒數各扣一；到零的以那個 owner 再 pause（spec §2.4；A2-06）。
        回 None；沒有倒數就不動，paused.json 寫入錯誤向上拋。"""
        done = []
        with self._lock:
            s = self.steps.get(nid)
            if not s:
                return
            for owner in list(s):
                s[owner] -= 1
                if s[owner] <= 0:
                    del s[owner]
                    done.append(owner)
            if not s:
                del self.steps[nid]
            if not done:
                return
            lst = self.paused.setdefault(nid, [])
            for owner in done:
                if owner not in lst:
                    lst.append(owner)
            self.save_paused()
        for owner in done:
            self.log(ev="steps-done", node=nid, owner=owner)

    def other_root(self, nid):
        """沿 nid 的路徑找帶 .aosd/ 的子根，回其 id，否則 None（spec §1、§2.3；S-15）。
        nid 須已正規化；isdir 看不到目錄也會視作未發現，這裡沒有獨立的未知回傳值。"""
        parts = [p for p in nid.split("/") if p not in ("", ".")]
        for k in range(1, len(parts) + 1):
            sub = "/".join(parts[:k])
            if os.path.isdir(os.path.join(node_path(self.root, sub), ".aosd")):
                return sub
        return None

    def owner(self):
        """讀 owner.json 的 owner 塊，判定控制檔 stop 的權限（spec §2.7；S-21）。
        無額外參數；lexists 未看見檔回 None（頂層），可見但讀不懂或缺 owner 回 {}，不允許 stop。"""
        path = os.path.join(self.aosd, "owner.json")
        if not os.path.lexists(path):
            return None
        ow = read_json(path)
        o = ow.get("owner") if isinstance(ow, dict) else None
        return o if isinstance(o, dict) else {}

    def claim_owner(self):
        """拿到 daemon.lock 後，依 tick 的三個 owner 環境變數認領子根（spec §2.7；K-08）。
        無額外參數，回 None；任務重起重寫權限，人手重開沿用，daemon 塊每次更新。
        變數用完移除；頂層不寫，舊 owner 壞掉則保留以拒絕 stop；寫入錯誤向上拋。"""
        env = os.environ
        onode, otid, allow = env.pop("AOS7_OWNER_NODE", None), env.pop("AOS7_OWNER_TID", None), \
            env.pop("AOS7_ALLOW_STOP", None)
        sub = env.get("AOS7_SUBROOT")
        path = os.path.join(self.aosd, "owner.json")
        owner = None
        if onode and otid and sub:
            try:
                if os.path.samestat(os.stat(sub), os.fstat(self.rfd)):
                    owner = {"node": onode, "tid": otid, "allow_stop": allow == "1"}
            except OSError:
                pass
        if owner is None:
            if not os.path.lexists(path):
                return
            cur = read_json(path)
            if not (isinstance(cur, dict) and isinstance(cur.get("owner"), dict)):
                return   # 壞掉的不蓋（stop 照樣當不允許）
            owner = cur["owner"]
        write_json(path, {"owner": owner, "daemon": {"pid": os.getpid(), "since": now()}})

    # ---------- 控制檔 ----------

    def apply(self, ctl):
        """解析控制物件 ctl，檢查 node 與子 daemon 邊界，再派送操作（spec §2.3）。
        回 (ok, msg)；無效 op、node 或越界回 False 與原因，執行例外交給控制檔隔離流程。"""
        op = ctl.get("op")
        if op in ("register", "unregister", "pause", "resume", "wake"):
            nid = norm_id(ctl.get("node"))
            if nid is None:
                return False, "%s 要給 node（相對空間根的路徑，不能是絕對、不能有 .. 或 . 開頭的段），拿到 %r" % (
                    op, ctl.get("node"))
            if op != "unregister":
                sub = self.other_root(nid)
                if sub:
                    return False, "%s 屬於 daemon %s（寫那個 daemon 的控制檔）" % (nid, sub)
            return getattr(self, "op_" + op)(nid, ctl)
        if op == "stop":
            return self.op_stop(ctl)
        return False, "unknown op %r" % (op,)

    def op_register(self, nid, ctl):
        """依控制物件 ctl 的 by 登記 nid，檢查 realpath 不出根（spec §1）。
        回 (ok, msg)；已登記或資料夾尚未出現仍成功，越界或既存非目錄回 False；I/O 例外向上拋。"""
        if nid in self.registry:
            return True, "%s 已登記" % nid
        real_root = os.path.realpath(self.root)
        p = node_path(self.root, nid)
        q = p
        while not os.path.lexists(q) and q != self.root:
            q = os.path.dirname(q)
        rq = os.path.realpath(q)
        if not (rq == real_root or rq.startswith(real_root + os.sep)):
            return False, "%s 沿符號連結跑出空間根（%s），不登記" % (nid, rq)
        if os.path.realpath(p) != canonical_node(self.root, nid):
            # A2-04：登記綁定實際路徑；路徑上有符號連結（即使指在空間根內）就不登記，請登記實際位置。
            return False, "%s 的路徑經過符號連結（實際在 %s），請登記實際位置" % (nid, os.path.realpath(p))
        if os.path.lexists(p) and not os.path.isdir(p):
            return False, "%s 不是資料夾，不登記" % nid
        self.registry[nid] = {"by": ctl.get("by"), "at": now()}
        self.save_nodes()
        self.log(ev="register", node=nid, by=ctl.get("by"))
        return True, "registered %s%s" % (nid, "" if os.path.isdir(p) else "（資料夾目前不在，出現時才開回合）")

    def op_unregister(self, nid, ctl):
        """依 ctl 取消 nid 登記，安排現有回合收尾與可選 kill（spec §2.3；P2-10）。
        回 (ok, msg)；未登記視為成功，預設 kill；成功只表示已接受，時間線可能仍在收尾。"""
        if nid not in self.registry:
            return True, "%s 沒有登記" % nid
        kill = ctl.get("kill", True) is not False
        # P2-10：先持久化取消登記，死在收尾途中也不會於重啟後自動再開；重登記時才恢復舊回合。
        del self.registry[nid]
        self.save_nodes()
        tl = self.timelines.pop(nid, None)
        self.missing.pop(nid, None)
        self.steps.pop(nid, None)
        if tl and tl.is_alive():
            tl.retire, tl.retire_kill = True, kill
            tl.wake.set()
            self.retiring[nid] = (tl, kill)
        elif kill:
            self.reap(nid, node_path(self.root, nid), "unregister-kill")
        self.log(ev="unregister", node=nid, by=ctl.get("by"), kill=kill)
        return True, "unregistered %s（%s）" % (nid, "活任務會被收掉" if kill else "kill: false，任務留著、從此收不到 tock")

    def op_pause(self, nid, ctl):
        """把 ctl.owner 加進 nid 的 pause 清單並取消同 owner 倒數（spec §2.4）。
        回 (ok, msg)；owner 非字串回 False，否則持久化後回 True；本回合仍照常收尾。"""
        owner = ctl.get("owner", "")
        if not isinstance(owner, str):
            return False, "owner 要是字串"
        with self._lock:
            lst = self.paused.setdefault(nid, [])
            if owner not in lst:
                lst.append(owner)
            self._drop_steps(nid, owner)
            self.save_paused()
        return True, "pause %s（owner %r；現在：%s）%s" % (nid, owner, self.paused[nid], self._note(nid))

    def op_resume(self, nid, ctl):
        """依 ctl 移除 nid 的 owner（或 all 全清），可設定 rounds 倒數（spec §2.4）。
        回 (ok, msg)；owner 或 rounds 不合法回 False；沒人 pause 才喚醒，I/O 例外向上拋。"""
        owner = ctl.get("owner", "")
        rounds = ctl.get("rounds")
        if not isinstance(owner, str):
            return False, "owner 要是字串"
        if rounds is not None and (not is_int(rounds) or rounds < 1):
            return False, "rounds 要是正整數"
        with self._lock:
            lst = self.paused.setdefault(nid, [])
            was = bool(lst)
            if ctl.get("all") is True:
                lst.clear()
                self.steps.pop(nid, None)
            else:
                if owner in lst:
                    lst.remove(owner)
                self._drop_steps(nid, owner)
            if rounds is not None:
                # A2-06：倒數按 owner 各記一份；B 的 rounds 不會蓋掉 A 的。
                self.steps.setdefault(nid, {})[owner] = rounds
            self.save_paused()
            left = list(lst)
        if not left and was:
            # 因此變成沒人 pause：順便 wake（N-84）。本來就沒人 pause 的 resume 不 wake——P2-01 之後 wake 會提前結束
            # 固定 interval 的回合，一個沒作用的 resume 不該切掉正在跑的回合
            self._kick(nid)
        return True, "resume %s（owner %r%s%s）；%s%s" % (
            nid, owner, "，all" if ctl.get("all") is True else "", "，rounds=%d" % rounds if rounds else "",
            "還有 %s 在 pause" % left if left else ("沒人 pause 了，馬上開回合" if was else "本來就沒人 pause"),
            self._note(nid))

    def _drop_steps(self, nid, owner):
        """拿掉 nid 上 owner 的 rounds 倒數（同一 owner 再 pause／resume 時清掉；spec §2.4、A2-06）。呼叫的人拿著 _lock。"""
        s = self.steps.get(nid)
        if s:
            s.pop(owner, None)
            if not s:
                del self.steps[nid]

    def op_wake(self, nid, ctl):
        """依控制請求喚醒 nid 等下一回合的時間線（spec §2.3；ctl 為派送介面的控制物件）。
        回 (True, msg) 表示已接受；node 不存在也只提示。固定 interval 的 node 回合中收到會提前結束這回合、馬上開下一回合
        （P2-01 選 (b)）；early_tock 的 node 回合中照舊不起作用（A2-11）。"""
        self._kick(nid)
        return True, "wake %s%s" % (nid, self._note(nid))

    def _kick(self, nid):
        """替 nid 的現有時間線記下 kick 時刻並喚醒 Event（spec §2.1、§2.3）。
        回 None；沒有時間線就不動。時間線只認回合關上之後的 kick（A2-11：回合中的 wake 不留到 idle 才生效）。"""
        tl = self.timelines.get(nid)
        if tl:
            tl.kick = time.monotonic()
            tl.wake.set()

    def _note(self, nid):
        """按 nid 是否登記、是否有時間線，回控制回條的補充文字（spec §2.3）。
        只讀記憶體，不驗證磁碟；都有時回空字串，未登記或尚無時間線時回提示。"""
        if nid not in self.registry:
            return "（%s 沒有登記，登記後才生效）" % nid
        return "" if nid in self.timelines else "（目前沒有這個 node 的資料夾，出現時才生效）"

    def op_stop(self, ctl):
        """處理 ctl 的整體停止請求與子 daemon stop 權限（spec §2.7；S-21）。
        回 (ok, msg)；帶 node、owner 不明或不允許時回 False；子 daemon 先落 stopped.json 才要求停止。"""
        if ctl.get("node") is not None:
            return False, "stop 是整個 daemon，不收 node；要停一個 node 用 pause 或 unregister"
        ow = self.owner()
        if ow is not None and ow.get("allow_stop") is not True:
            return False, ("這個 daemon 屬於 node %s（任務 %s），不允許外部 stop；要停請 %s 在 tasks.json 那項設 "
                           "allow_stop: true，或由 %s kill 這個任務" % (ow.get("node", "?"), ow.get("tid", "?"),
                                                                      ow.get("node", "?"), ow.get("node", "?")))
        if ow is not None:
            # spec §2.7：先留停止標記，父 node 下次 tick 才不會立刻把已允許停止的子 daemon 補起。
            write_json(os.path.join(self.aosd, "stopped.json"),
                       {"by": ctl.get("by"), "why": ctl.get("why"), "at": now(), "kill": bool(ctl.get("kill"))})
        self.stop(bool(ctl.get("kill")))
        return True, "stopping" + (" with kill" if self.kill_on_stop else "") + (
            "；已寫 .aosd/stopped.json，%s 不會再起它（刪掉才會）" % ow.get("node", "?") if ow is not None else "")

    def handle_ctl(self):
        """每圈依件數與時間預算處理 ctl/，單件失敗隔離（spec §2.3）。
        無額外參數，回 None；列目錄失敗本圈不做，個別例外交 ctl_failed，下一圈再看。"""
        cdir = os.path.join(self.aosd, "ctl")
        try:
            names = sorted(n for n in os.listdir(cdir) if not n.startswith("."))
        except OSError:
            return
        self.ctl_stuck &= set(names)
        # spec §2.3：處理失敗的「效果可能已生效，不重做」——搬不走而卡在 ctl/ 的不再執行，只每圈再試著搬到 ctl-failed/
        # （註解疑點 daemon:346／416：以前會排到最後再執行一次）。daemon 重開後記憶體清空，才會再被當新請求。
        for n in sorted(self.ctl_stuck):
            self._move_failed(cdir, n)
        names = [n for n in names if n not in self.ctl_stuck]
        self.ctl_backlog = False
        # spec §2.3：件數與單調時間雙重預算，控制檔持續湧入仍要讓 node 檢查與 status 前進。
        t_end = time.monotonic() + CTL_BUDGET_S
        for k, n in enumerate(names):
            if k >= CTL_BATCH or time.monotonic() >= t_end:
                self.ctl_backlog = True   # 剩下的下一圈接著做（照檔名順序）
                break
            try:
                self.ctl_one(cdir, n)
            except Exception as e:   # noqa: BLE001  一件出事不擋同圈其他件（特別是 stop）
                self.ctl_failed(cdir, n, e)

    def ctl_one(self, cdir, n):
        """處理 cdir 中檔名 n 的一件請求，寫同名最近回條再移除請求（spec §2.3）。
        回 None；格式錯誤回 ok:false，執行或寫回條失敗向上拋，避免把接受誤當已完成收尾。"""
        path = os.path.join(cdir, n)
        done = os.path.join(self.aosd, "ctl-done")
        bad = None
        if not n.endswith(".json"):
            bad = "檔名要以 .json 結尾"
        elif not is_regular(path):
            bad = "不是一般檔（FIFO、資料夾…）"
        if bad:
            # P2-11：壞檔保留原物為 .bad，另寫可讀 JSON 回條，FIFO 不能為了回條而阻塞讀取。
            os.makedirs(done, exist_ok=True)
            base = n if n.endswith(".json") else n + ".json"
            try:
                _replace(path, os.path.join(done, n + ".bad" if n.endswith(".json") else base[:-5] + ".bad"))
            except OSError:
                pass
            write_json(os.path.join(done, base), {"raw": "not read", "result": {"ok": False, "msg": bad, "at": now(),
                                                                              "queued_at": None}})
            self.log(ev="ctl", file=n, op=None, ok=False, msg=bad)
            return
        ctl = read_json(path)
        if isinstance(ctl, dict):
            ok, msg = self.apply(ctl)
        else:
            ctl, ok, msg = {"raw": "unreadable"}, False, "not a JSON object"
        try:
            queued = datetime.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="milliseconds")
        except OSError:
            queued = None
        ctl["result"] = {"ok": ok, "msg": msg, "at": now(), "queued_at": queued}
        try:
            dst = os.path.join(done, n)
            if os.path.isdir(dst) and not os.path.islink(dst):
                # P2-13：同名覆蓋也含資料夾，避免舊回條路徑變成永久擋路的毒丸。
                shutil.rmtree(dst)
            write_json(dst, ctl)   # 同名的舊回條直接蓋掉（每個名字只留最近一份；W3）
        except Exception as e:   # noqa: BLE001
            raise RuntimeError("已執行（ok=%s：%s），但回條寫不進去：%r" % (ok, msg, e)) from e
        try:
            os.remove(path)
        except OSError:
            pass
        self.log(ev="ctl", file=n, op=ctl.get("op"), node=ctl.get("node"), by=ctl.get("by"), ok=ok, msg=msg)

    def ctl_failed(self, cdir, n, err):
        """將 cdir/n 的失敗原物移到 ctl-failed，記 err 與最近錯誤（spec §2.3）。
        回 None；搬不走就留在 ctl/，之後排到最後；同名目的原物覆蓋（P2-13）。"""
        self.io_errors += 1
        self.ctl_stuck.add(n)
        moved = self._move_failed(cdir, n)
        self.last_ctl_error = {"file": n, "at": now(), "err": repr(err)[:300], "moved_to": moved}
        self.log(ev="ctl-error", file=n, err=repr(err)[:300], moved_to=moved)

    def _move_failed(self, cdir, n):
        """把處理失敗的 cdir/n 搬到 ctl-failed/（蓋掉同名舊的）；搬成就從 ctl_stuck 拿掉、回新位置，搬不走回 None。"""
        try:
            fdir = os.path.join(self.aosd, "ctl-failed")
            os.makedirs(fdir, exist_ok=True)
            _replace(os.path.join(cdir, n), os.path.join(fdir, n))
        except OSError:
            return None
        self.ctl_stuck.discard(n)
        return "ctl-failed/" + n

    def stop(self, kill):
        """要求所有時間線停止；kill 為是否一併收任務（spec §2.7）。
        回 None；重複呼叫不重置停止起點，已要求 kill 不會被後來的 False 撤銷。"""
        if not self.stopping:
            self.stopping_since = time.monotonic()
        self.stopping = True
        self.kill_on_stop = self.kill_on_stop or kill
        for tl in self.timelines.values():
            tl.wake.set()

    # ---------- node ----------

    def check_nodes(self):
        """只檢查已登記 node，確定消失或 inode 換了才停線、收程序（spec §2.6）。
        無額外參數，回 None；三態的「不知道」保留現狀並記錯；重現後等舊程序收完才重開，登記保留。"""
        if self.stopping:
            return
        for nid, (tl, kill) in list(self.retiring.items()):
            if not tl.is_alive():
                del self.retiring[nid]
                if kill and nid not in self.registry:
                    self.reap(nid, tl.node, "unregister-kill")
        for nid in sorted(self.registry):
            path = node_path(self.root, nid)
            tl = self.timelines.get(nid)
            try:
                inject("stat", path)
                st = os.lstat(path)
                if stat.S_ISLNK(st.st_mode):
                    gone = "換成符號連結了（A2-04：登記綁定實際資料夾，不跟著連結走）"
                elif not stat.S_ISDIR(st.st_mode):
                    gone = "不是資料夾了"
                elif os.path.realpath(path) != canonical_node(self.root, nid):
                    gone = "路徑經過符號連結（實際在 %s；A2-04）" % os.path.realpath(path)
                else:
                    gone = None
            except OSError as e:
                if e.errno not in GONE_ERRNO:
                    # spec §0、§2.6 三態：看不到不是消失；不能因此殺任務或丟掉原時間線。錯誤類型分欄記（A2-08）。
                    err = {"prog": "daemon", "rc": None, "at": now(), "kind": errno.errorcode.get(e.errno, str(e.errno)),
                           "err": "%s：看不到 node（%r），保留現狀" % (errno.errorcode.get(e.errno, e.errno), e)}
                    if tl:
                        tl.last_error = err
                    else:
                        self.node_errors[nid] = err
                    continue
                gone, st = "不存在", None
            if tl and not gone and (st.st_dev, st.st_ino) != tl.node_ident:
                # spec §2.6：同一路徑可能已是另一個目錄，不能讓新目錄承接舊任務的生命週期。
                gone = "inode 換了（被搬走或換成別的資料夾）"
            if gone:
                if tl:
                    self.timelines.pop(nid)
                    tl.gone = True
                    tl.wake.set()
                    self.steps.pop(nid, None)
                    self._live.pop(nid, None)
                    self.reap(nid, path, "node-gone-kill", why=gone)
                if nid not in self.missing:
                    self.missing[nid] = {"since": now(), "why": gone}
                continue
            if tl:
                continue
            r = self.reapers.get(nid)
            if r is not None and r.is_alive():
                continue   # 收程序還沒做完：新時間線的任務會被一起收掉，等它
            if any(t.node_id == nid for t, _ in self.retiring.values()):
                continue
            self.missing.pop(nid, None)
            self.node_errors.pop(nid, None)
            tl = Timeline(self, nid, (st.st_dev, st.st_ino))
            self.timelines[nid] = tl
            tl.start()
            self.log(ev="node+", node=nid, round=tl.round, **({"paused": True} if self.is_paused(nid) else {}))

    def reap(self, nid, node, ev, why=None):
        """在背景收 node 的任務，nid 用來取記住的 pgid，ev／why 用於事件（spec §2.6）。
        回 None；Q1 範圍是記住的 pgid 加 AOS7_NODE/AOS7_TID 身分掃描，不阻塞主迴圈。"""
        known = self._pgids.pop(nid, set())

        def work():
            """依外層捕獲的 node、known 收程序，將 ev／nid／why 與收尾結果記事件（spec §2.6）。
            無參數，回 None；clean=False 也照實記錄，不在背景另開新時間線。"""
            n, clean = aos7_proc.kill_node(node, known)
            self.log(ev=ev, node=nid, groups=n, ok=clean, **({"why": why} if why else {}))
        th = threading.Thread(target=work, name="reap:" + nid, daemon=True)
        self.reapers[nid] = th
        th.start()

    def kill_live(self, nid, node):
        """時間線要求收 nid／node 的活任務，先逐槽再掃 Q1 範圍（spec §2.6、§2.7）。
        回 None；單槽判定或 kill 例外只記錯並繼續，不把未知身分直接當可殺。"""
        slots, _ = aos7_task.list_slots(node)
        for slot in slots:
            fslot = aos7_task.slot_dir(node, slot)
            try:
                v = aos7_task.judge(fslot, node, slot, None)
                if v.state in (aos7_task.LIVE, aos7_task.SUSPECT) and v.run is not None:
                    ok, msg = aos7_task.kill_run(fslot, node, slot, v)
                    self.log(ev="kill", node=nid, run=aos7_task.run_id(slot, v.run), ok=ok, msg=msg)
            except Exception as e:   # noqa: BLE001
                self.log(ev="kill-error", node=nid, slot=slot, err=repr(e)[:200])
        aos7_proc.kill_node(node, self._pgids.get(nid, ()))

    def live_of(self, nid, tl):
        """取 nid／tl 的活 run id 清單，每 LIVE_EVERY 秒重算並記 pgid（spec §2.6、§2.8）。
        回清單；只讀不殺，疑似 lost 不列，UNKNOWN 有 run 時保守列入（P2-08）；單槽例外略過。"""
        t, live = self._live.get(nid, (None, None))
        if t is not None and time.monotonic() - t < LIVE_EVERY:
            return live
        live, pgids, uncertain = [], set(), []
        slots, lerr = aos7_task.list_slots(tl.node)
        if lerr:
            # 註解疑點 daemon:522：列不出槽＝不知道，保留上次的 live 與記著的 pgid（不能清空，不然 node 消失時漏收）。
            prev = (self._live.get(nid) or (None, []))[1] or []
            self._live[nid] = (time.monotonic(), prev)
            self._uncertain[nid] = [{"slot": None, "run": None, "why": "列不出槽：%s" % lerr}]
            return prev
        for slot in slots:
            fslot = aos7_task.slot_dir(tl.node, slot)
            try:
                v = aos7_task.judge(fslot, tl.node, slot, tl.round)
            except Exception as e:   # noqa: BLE001
                uncertain.append({"slot": slot, "run": None, "why": repr(e)[:200]})
                continue
            if v.state == aos7_task.UNKNOWN or v.get("unsure") or v.get("broken"):
                # A2-08：判不出的槽進 status，不再「保守停著但看似正常」。
                uncertain.append({"slot": slot, "run": v.run, "why": v.get("unsure") or v.get("why")})
            if v.state in (aos7_task.LIVE, aos7_task.UNKNOWN):
                # P2-08：status 對未知仍保守列活；這個觀測不授權重用槽（不變條件二，spec §5.4）。
                live.append(aos7_task.run_id(slot, v.run if v.run is not None else "?"))
                pid = read_json(os.path.join(fslot, "pid.json"))
                if isinstance(pid, dict) and is_int(pid.get("pgid")) and (v.run is None or pid.get("run") == v.run):
                    pgids.add(pid["pgid"])
                elif v.state == aos7_task.UNKNOWN:
                    pgids |= {g for g in self._pgids.get(nid, ()) if g}   # 判不出的槽：沿用記著的群組，不丟
        self._live[nid] = (time.monotonic(), live)
        self._pgids[nid] = pgids
        self._uncertain[nid] = uncertain
        return live

    def sweep_leftovers(self):
        """停止時按已登記 node 掃環境身分，補收殘留並記結果（spec §2.7）。
        無額外參數，回 None；沒有 node 就不掃，程序掃描的未知結果由事件 ok 呈現。"""
        nodes = [node_path(self.root, n) for n in self.registry]
        if nodes:
            n, clean = aos7_proc.sweep_nodes(nodes)
            self.log(ev="stop-sweep", groups=n, ok=clean)

    # ---------- status ----------

    def write_status(self, stopped=False):
        """彙整登記、運行與 unregister 收尾中的狀態，覆寫 status.json（spec §2.8；P2-12）。
        stopped 表示是否為正常退出前快照；回 None，未知 round_open 保留 null，寫入錯誤向上拋。"""
        nodes = {}
        retiring = {nid: t for nid, (t, _k) in self.retiring.items() if t.is_alive()}
        for nid in sorted(set(self.registry) | set(self.timelines) | set(retiring)):
            tl = self.timelines.get(nid) or retiring.get(nid)
            by = list(self.paused.get(nid) or [])
            if tl is None:
                row = {"round": None, "round_open": None, "recovery_pending": False,
                       "phase": "missing" if nid in self.missing else ("stopped" if stopped else "idle"),
                       "paused_by": by, "pause_pending": False, "interval_ms": None, "early_tock": None, "live": []}
                if nid in self.missing:
                    row["missing"] = self.missing[nid]
                if nid in self.node_errors:
                    row["last_error"] = self.node_errors[nid]
            else:
                phase = "paused" if by and tl.phase == "idle" else tl.phase
                if nid in retiring and phase != "stopped":
                    phase = "unregistering"   # P2-12：unregister 了，本回合收完才結束（spec §2.3、§2.8）
                row = {"round": tl.round, "round_open": tl.round_open, "recovery_pending": tl.recovery_pending,
                       "phase": phase, "paused_by": by,
                       "pause_pending": bool(by) and phase not in ("paused", "stopped", "error"),
                       "interval_ms": tl.interval_ms, "early_tock": tl.early_tock, "live": self.live_of(nid, tl)}
                if tl.last_error:
                    row["last_error"] = tl.last_error
                if self._uncertain.get(nid):
                    row["uncertain"] = self._uncertain[nid]
                if tl.last_event:
                    row["last_event"] = tl.last_event
            if nid in self.steps:
                row["steps_left"] = dict(self.steps[nid])   # {owner: 剩幾回合}（A2-06）
            nodes[nid] = row
        st = {"pid": os.getpid(), "root": self.root, "at": now(), "poll_s": POLL, "gen": self.gen,
              "io_errors": self.io_errors, "stopping": self.stopping, "stopped": stopped,
              "last_event": self.last_event, "nodes": nodes}
        if self.last_ctl_error:
            st["last_ctl_error"] = self.last_ctl_error
        if self.root_gone:
            st["root_gone"] = True
        if self.root_error:
            st["last_error"] = self.root_error
        write_json(os.path.join(self.aosd, "status.json"), st)

    def check_root(self):
        """比對 root 路徑與已抓住 fd 的 inode（spec §2.5），確定消失或 inode 更換才 stop 加 kill。
        無額外參數，回 None；ENOENT／ENOTDIR 算消失，其他讀取錯誤不改狀態。"""
        try:
            same = os.path.samestat(os.stat(self.root), os.fstat(self.rfd))
        except OSError as e:
            if e.errno not in GONE_ERRNO:
                # 看不到 root 不是消失：保留現狀，但記下來（註解疑點 daemon:595），status 頂層 last_error 看得到。
                self.root_error = {"prog": "daemon", "at": now(), "kind": errno.errorcode.get(e.errno, str(e.errno)),
                                   "err": "看不到 root（%r），保留現狀" % e}
                return
            same = False
        self.root_error = None
        if not same and not self.root_gone:
            self.root_gone = True
            self.stop(True)
            self.log(ev="root-gone", root=self.root)

    # ---------- 主迴圈 ----------

    def run(self):
        """拿單實例鎖、建立世代並跑主迴圈，停止時等時間線與收尾（spec §2.1、§2.5、§2.7）。
        無額外參數；正常結束回 0，鎖拿不到回 1；每圈步驟由 guard 隔離例外。"""
        os.makedirs(os.path.join(self.aosd, "ctl"), exist_ok=True)
        # spec §2.5：flock 綁 inode，不能 unlink 鎖檔，否則新舊程序可各鎖一個同名 inode。
        lock = open(os.path.join(self.aosd, "daemon.lock"), "a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("aos7-daemon: %s 已經有 daemon 在跑" % self.root, file=sys.stderr)
            return 1
        for s in (signal.SIGTERM, signal.SIGINT):
            signal.signal(s, lambda *_: self.stop(True))
        self.claim_owner()
        self.load_state()
        self.save_paused()   # 一起來就寫一份（空的也寫）
        if not os.path.lexists(os.path.join(self.aosd, "nodes.json")):
            self.save_nodes()
        old = read_json(os.path.join(self.aosd, "gen.json"), {}) or {}
        # spec §2.5：先獨占 daemon.lock 才遞增 gen；舊動作晚拿到 action.lock 時可辨識自己已過期。
        self.gen = (old.get("gen", 0) if isinstance(old, dict) and is_int(old.get("gen")) else 0) + 1
        write_json(os.path.join(self.aosd, "gen.json"), {"gen": self.gen, "pid": os.getpid(), "at": now()})
        self.log(ev="start", pid=os.getpid(), gen=self.gen)
        sp = os.path.join(self.aosd, "stopped.json")
        if os.path.lexists(sp):
            was = read_json(sp)
            try:
                os.remove(sp)
            except OSError:
                pass
            self.log(ev="stopped-cleared", was=was)
        while not self.stopping:
            for step in (self.check_root, self.handle_ctl, self.check_nodes, self.write_status, self.sweep_tmps):
                self.guard(step)
            if not self.ctl_backlog:
                time.sleep(POLL)
        self.guard(lambda: self.log(ev="stopping", kill=self.kill_on_stop))
        alive = list(self.timelines.values()) + [t for t, _ in self.retiring.values()]
        while any(tl.is_alive() for tl in alive):
            self.guard(self.write_status)
            time.sleep(POLL)
        if self.kill_on_stop:
            self.guard(self.sweep_leftovers)
        for th in list(self.reapers.values()):
            th.join(5)
        self._live.clear()
        self.guard(lambda: self.write_status(stopped=True))
        self.guard(lambda: self.log(ev="stop"))
        return 0

    def sweep_tmps(self):
        """每 SWEEP_EVERY 秒清一次 `.aosd/`、`ctl/`、`ctl-done/` 裡寫者已死的原子寫暫存檔（A2-07）。回 None。"""
        if time.monotonic() - self._swept < SWEEP_EVERY:
            return
        self._swept = time.monotonic()
        for d in (self.aosd, os.path.join(self.aosd, "ctl"), os.path.join(self.aosd, "ctl-done")):
            gone = sweep_tmp(d)
            if gone:
                self.log(ev="tmp-swept", dir=os.path.basename(d), files=gone[:20], n=len(gone))

    def guard(self, step):
        """執行無參數回呼 step，隔離主迴圈錯誤（spec §2.1；S-06）。
        回 None；例外增加 io_errors、寫 stderr 與事件，讓下一步／下一圈仍可繼續。"""
        try:
            step()
        except Exception as e:   # noqa: BLE001
            self.io_errors += 1
            print("aos7-daemon: %s 失敗：%r" % (getattr(step, "__name__", "step"), e), file=sys.stderr, flush=True)
            try:
                self.log(ev="error", step=getattr(step, "__name__", "step"), msg=repr(e)[:300])
            except Exception:   # noqa: BLE001
                pass


def main(argv=None):
    """解析人或任務啟動 aos7-daemon 的 argv（不含程式名），None 使用 sys.argv（spec §1）。
    回退出碼：參數或 root 不合法為 1，否則沿用 Daemon.run；初始化 I/O 例外向上拋。"""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or not os.path.isdir(argv[0]):
        print("用法: aos7-daemon <root>（root 要是已存在的資料夾）", file=sys.stderr)
        return 1
    return Daemon(argv[0]).run()
