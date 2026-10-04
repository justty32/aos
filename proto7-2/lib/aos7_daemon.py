"""aos7-daemon <root>：常駐程式（spec.md 第 1、2 節，S-03～S-06）。只跑登記在 `.aosd/nodes.json` 的 node（不掃資料夾），
每個 node 一條時間線（thread）；每圈處理控制檔、檢查 node 在不在、寫 status.json。`.aosd/` 一律經 root 的 fd 讀寫。
SIGTERM／SIGINT＝stop 加 kill（子 daemon 被父任務收掉時帶走自己的任務）。"""
import datetime
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
from aos7_fs import (FD_PREFIX, GONE_ERRNO, N, OK, U, Unknown, append_jsonl, canonical_node, errname, fact, hold, inject,
                     is_int, locked, node_path, now, read_json, sweep_tmp, write_json)

CTL_BATCH = 200      # 一圈最多處理幾個控制檔
CTL_BUDGET_S = 0.05  # 一圈處理控制檔最多花幾秒（跟 CTL_BATCH 取先到的）：控制檔湧入時 node 檢查與 status 照樣前進
LIVE_EVERY = 0.25    # status 的 live 與記著的 pgid 多久重算一次（秒）
SWEEP_EVERY = 1.0    # 多久清一次 .aosd／ctl／ctl-done 裡寫者已死的暫存檔（秒）


def norm_id(node):
    """控制檔的 node 值 → 相對 id（根是 "."）；絕對路徑、`..`、`.` 開頭的段＝不合，回 None。"""
    if not isinstance(node, str) or node.startswith("/") or "\0" in node:
        return None
    parts = [p for p in node.split("/") if p not in ("", ".")]
    if any(p == ".." or p.startswith(".") for p in parts):
        return None
    return "/".join(parts) or "."


def _replace(src, dst):
    """把 src 原物搬到 dst，蓋掉同名舊物（含資料夾：舊回條路徑被佔成資料夾也不會永遠擋路）。"""
    if os.path.isdir(dst) and not os.path.islink(dst):
        shutil.rmtree(dst)
    os.replace(src, dst)


class Daemon:
    """一個空間根的 daemon：登記、控制檔、node 檢查、status、各 node 的時間線。"""

    def __init__(self, root):
        """抓住 root 的 fd（還沒拿 daemon.lock）。"""
        # 以實際路徑當空間根：登記檢查照實際位置比，根本身是連結也不會把 "." 判成連結。
        self.root = os.path.realpath(root)
        # `.aosd` 一律經 root 的 fd 讀寫：root 被搬走寫到新位置，被刪就寫不進去，不會寫進換上來的替身
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
        self.steps = {}              # {id: {owner: left}}：resume 帶 rounds，按 owner 各記一份
        self._live = {}              # {id: (monotonic, [run id])}
        self._pgids = {}             # {id: {pgid}}：活任務的程序群組，node 消失時收（2.6）
        self._swept = 0.0            # 上次清暫存檔的 monotonic 時刻
        self.root_error = None       # 看 root 時的「看不到」錯誤（不是消失）
        self.gen = None
        self.io_errors = 0
        self.ctl_backlog = False
        self.ctl_stuck = set()       # 處理丟例外、又刪不掉的控制檔名：不再執行，只每圈再試著刪
        self.last_ctl_error = None
        self.last_event = None

    # ---------- 小工具 ----------

    def log(self, **kw):
        """記一件事：更新 last_event；有 `.aosd/log.on` 才追加 log.jsonl（寫不進去不影響主流程）。"""
        ev = dict(at=now(), **kw)
        self.last_event = ev
        try:
            if os.path.lexists(os.path.join(self.aosd, "log.on")):
                with self._lock:
                    append_jsonl(os.path.join(self.aosd, "log.jsonl"), ev)
        except OSError:
            pass

    def save_nodes(self):
        """把登記表原子寫回 nodes.json。"""
        write_json(os.path.join(self.aosd, "nodes.json"), {"nodes": self.registry})

    def save_paused(self):
        """把 pause owner 清單原子寫回 paused.json。daemon 是唯一的寫者，仍照 spec §0 對 paused.json.lock 拿 flock，
        讓讀—改—寫的外部工具有一致的約定。"""
        path = os.path.join(self.aosd, "paused.json")
        with locked(path, timeout=1.0):
            write_json(path, {"paused": {k: v for k, v in sorted(self.paused.items()) if v}})

    def load_state(self):
        """起來時讀 nodes.json、paused.json、gen.json，回舊世代。三份都只有 daemon 寫：不存在＝新空間；讀不到或壞掉＝
        不知道 → 丟 Unknown，daemon 不起來（不能當空的照跑，也不能蓋掉它們）。"""
        def load(name, ok):
            st, v = fact(os.path.join(self.aosd, name))
            if st == N:
                return None
            if st == OK and ok(v):
                return v
            raise Unknown("%s %s，不知道原本的內容，daemon 不起來；修好或確認後刪掉再起" % (
                name, v if st != OK else "內容不合"), kind="state-unknown")
        nj = load("nodes.json", lambda v: isinstance(v, dict) and isinstance(v.get("nodes"), dict))
        pj = load("paused.json", lambda v: isinstance(v, dict) and isinstance(v.get("paused"), (dict, list)))
        gj = load("gen.json", lambda v: isinstance(v, dict) and is_int(v.get("gen")))
        if nj:
            self.registry = {k: (v if isinstance(v, dict) else {}) for k, v in nj["nodes"].items() if norm_id(k) == k}
        pl = pj["paused"] if pj else {}
        if isinstance(pl, dict):
            self.paused = {k: [o for o in v if isinstance(o, str)] for k, v in pl.items() if isinstance(v, list)}
        else:   # proto7-1 的格式：一個 node 一個開關 → 不帶 owner 的那一格
            self.paused = {k: [""] for k in pl if isinstance(k, str)}
        return gj["gen"] if gj else 0

    def is_paused(self, nid):
        """nid 有沒有人 pause（清單空了才開回合）。"""
        return bool(self.paused.get(nid))

    def round_done(self, nid):
        """時間線確認關上一回合後呼叫：nid 每個 owner 的 rounds 倒數各扣一，到零的以那個 owner 再 pause（spec §2.4）。"""
        with self._lock:
            s = self.steps.get(nid) or {}
            for owner in s:
                s[owner] -= 1
            done = [o for o, left in s.items() if left <= 0]
            for owner in done:
                self._drop_steps(nid, owner)
                if owner not in self.paused.setdefault(nid, []):
                    self.paused[nid].append(owner)
            if not done:
                return
            self.save_paused()
        for owner in done:
            self.log(ev="steps-done", node=nid, owner=owner)

    def other_root(self, nid):
        """nid 的路上有沒有別的 daemon 的根（帶 `.aosd/` 的資料夾，S-15）：有回它的 id，沒有回 None。"""
        parts = [p for p in nid.split("/") if p not in ("", ".")]
        for k in range(1, len(parts) + 1):
            sub = "/".join(parts[:k])
            if os.path.isdir(os.path.join(node_path(self.root, sub), ".aosd")):
                return sub
        return None

    # ---------- 控制檔 ----------

    def apply(self, ctl):
        """執行一份控制請求，回 (ok, msg)。op、node 不合或 node 屬於別的 daemon＝ok:false。"""
        op = ctl.get("op")
        if op in ("register", "unregister", "pause", "resume", "wake"):
            nid = norm_id(ctl.get("node"))
            if nid is None:
                return False, "%s 要給 node（相對空間根的路徑，不能是絕對、不能有 .. 或 . 開頭的段），拿到 %r" % (
                    op, ctl.get("node"))
            sub = self.other_root(nid) if op != "unregister" else None
            if sub:
                return False, "%s 屬於 daemon %s（寫那個 daemon 的控制檔）" % (nid, sub)
            if op in ("pause", "resume") and not isinstance(ctl.get("owner", ""), str):
                return False, "owner 要是字串"
            return getattr(self, "op_" + op)(nid, ctl)
        if op == "stop":
            return self.op_stop(ctl)
        return False, "unknown op %r" % (op,)

    def op_register(self, nid, ctl):
        """登記 nid（spec §1）：路徑要在 root 底下、路上沒有符號連結；資料夾還不在也接受（出現時才開回合）。"""
        if nid in self.registry:
            return True, "%s 已登記" % nid
        p = node_path(self.root, nid)
        real, r = os.path.realpath(p), os.path.realpath(self.root)
        if real != canonical_node(self.root, nid):   # 登記綁定實際位置：路上有符號連結（即使指在空間根內）就不收
            out = not (real == r or real.startswith(r + os.sep))
            return False, "%s %s（實際在 %s），%s" % (nid, "沿符號連結跑出空間根" if out else "的路徑經過符號連結", real,
                                                    "不登記" if out else "請登記實際位置")
        if os.path.lexists(p) and not os.path.isdir(p):
            return False, "%s 不是資料夾，不登記" % nid
        self.registry[nid] = {"by": ctl.get("by"), "at": now()}
        self.save_nodes()
        self.log(ev="register", node=nid, by=ctl.get("by"))
        return True, "registered %s%s" % (nid, "" if os.path.isdir(p) else "（資料夾目前不在，出現時才開回合）")

    def op_unregister(self, nid, ctl):
        """取消登記（spec §2.3）：馬上從 nodes.json 拿掉，本回合照常收完；預設 kill 那個 node 的活任務。"""
        if nid not in self.registry:
            return True, "%s 沒有登記" % nid
        kill = ctl.get("kill", True) is not False
        # 先寫回 nodes.json：死在收尾途中，重開也不會自動再跑它
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
        """把 owner 加進 nid 的 pause 清單、清掉同 owner 的倒數（spec §2.4）。本回合照常收完才停。"""
        owner = ctl.get("owner", "")
        with self._lock:
            lst = self.paused.setdefault(nid, [])
            if owner not in lst:
                lst.append(owner)
            self._drop_steps(nid, owner)
            self.save_paused()
        return True, "pause %s（owner %r；現在：%s）%s" % (nid, owner, self.paused[nid], self._note(nid))

    def op_resume(self, nid, ctl):
        """拿掉自己 owner 的 pause（`all` 全清），可帶 rounds 倒數（spec §2.4）。因此變成沒人 pause 就順便 wake。"""
        owner, rounds = ctl.get("owner", ""), ctl.get("rounds")
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
                # 倒數按 owner 各記一份：B 的 rounds 不會蓋掉 A 的
                self.steps.setdefault(nid, {})[owner] = rounds
            self.save_paused()
            left = list(lst)
        if not left and was:
            # 本來就沒人 pause 的 resume 不 wake：wake 會提前結束固定 interval 的回合，沒作用的 resume 不該切掉它
            self._kick(nid)
        return True, "resume %s（owner %r%s%s）；%s%s" % (
            nid, owner, "，all" if ctl.get("all") is True else "", "，rounds=%d" % rounds if rounds else "",
            "還有 %s 在 pause" % left if left else ("沒人 pause 了，馬上開回合" if was else "本來就沒人 pause"),
            self._note(nid))

    def _drop_steps(self, nid, owner):
        """拿掉 nid 上 owner 的 rounds 倒數。呼叫的人拿著 _lock。"""
        s = self.steps.get(nid, {})
        s.pop(owner, None)
        if not s:
            self.steps.pop(nid, None)

    def op_wake(self, nid, ctl):
        """wake（spec §2.3）：等下一回合的馬上開；固定 interval 的回合中收到會提前結束這回合，early_tock 的回合中不起作用。"""
        self._kick(nid)
        return True, "wake %s%s" % (nid, self._note(nid))

    def _kick(self, nid):
        """叫醒 nid 的時間線，記下時刻（時間線照時刻分辨回合中、回合後的 wake）。"""
        tl = self.timelines.get(nid)
        if tl:
            tl.kick = time.monotonic()
            tl.wake.set()

    def _note(self, nid):
        """回條的補充說明：nid 沒登記或資料夾還不在時提醒「之後才生效」。"""
        if nid not in self.registry:
            return "（%s 沒有登記，登記後才生效）" % nid
        return "" if nid in self.timelines else "（目前沒有這個 node 的資料夾，出現時才生效）"

    def op_stop(self, ctl):
        """整個 daemon 停止（spec §2.7）。`.aosd/stop-guard.json` 存在而 `allow` 不是 true（讀不到、壞掉也算）＝不停，
        回條帶守門檔的 `note`。核心不知道守門的語意，檔由寫它的模組管；SIGTERM 不看守門檔。"""
        if ctl.get("node") is not None:
            return False, "stop 是整個 daemon，不收 node；要停一個 node 用 pause 或 unregister"
        st, g = fact(os.path.join(self.aosd, "stop-guard.json"))
        good = st == OK and isinstance(g, dict)
        if st != N and not (good and g.get("allow") is True):
            note = g.get("note") if good else ("守門檔讀不到或不是一般檔" if st == U else "守門檔壞了")
            return False, "不允許外部 stop（.aosd/stop-guard.json）%s" % ("：%s" % note if isinstance(note, str) and note else "")
        self.stop(bool(ctl.get("kill")))
        return True, "stopping" + (" with kill" if self.kill_on_stop else "")

    def handle_ctl(self):
        """每圈處理 `.aosd/ctl/`（spec §2.3）：照檔名順序、有件數與時間預算，一件丟例外不擋同圈其他件（特別是 stop）。"""
        cdir = os.path.join(self.aosd, "ctl")
        try:
            names = sorted(n for n in os.listdir(cdir) if not n.startswith("."))
        except OSError:
            return
        # 處理丟例外的那件，效果可能已生效：不再執行，只每圈再試著刪（daemon 重開後才會當新請求）
        self.ctl_stuck &= set(names)
        for n in sorted(self.ctl_stuck):
            self._drop(cdir, n)
        names = [n for n in names if n not in self.ctl_stuck]
        self.ctl_backlog = False
        t_end = time.monotonic() + CTL_BUDGET_S
        for k, n in enumerate(names):
            if k >= CTL_BATCH or time.monotonic() >= t_end:
                self.ctl_backlog = True   # 剩下的下一圈接著做
                break
            try:
                self.ctl_one(cdir, n)
            except Exception as e:   # noqa: BLE001
                self.io_errors += 1
                self.ctl_stuck.add(n)
                self._drop(cdir, n)
                self.last_ctl_error = {"file": n, "at": now(), "err": repr(e)[:300]}
                self.log(ev="ctl-error", file=n, err=repr(e)[:300])

    def _drop(self, cdir, n):
        """刪掉處理丟過例外的請求；刪成就不再記著，刪不掉下圈再試。"""
        try:
            os.remove(os.path.join(cdir, n))
        except FileNotFoundError:
            pass
        except OSError:
            return
        self.ctl_stuck.discard(n)

    def ctl_one(self, cdir, n):
        """處理一件請求：執行、寫同名回條（蓋掉舊的，每個名字只留最近一份）、刪請求。
        壞的（不是 .json、不是一般檔、讀不懂）一律回條 ok:false；讀不到（U）的留著下一圈再看；寫回條失敗往外丟。"""
        path = os.path.join(cdir, n)
        done = os.path.join(self.aosd, "ctl-done")
        bad, ctl = None, None
        if not n.endswith(".json"):
            bad = "檔名要以 .json 結尾"
        else:
            st, ctl = fact(path)
            if st == N:
                return                     # 剛被拿走：沒有請求
            if st == U:
                try:
                    regular = stat.S_ISREG(os.stat(path).st_mode)
                except OSError:
                    regular = True
                if regular:
                    return                 # 讀不到：請求留著，下一圈再看
                bad = "不是一般檔（FIFO、資料夾…）"   # 請求本身不合（B）
        if bad:
            # 原物保留成 .bad（FIFO 不能為了回條去讀它），另寫一份讀得懂的回條
            os.makedirs(done, exist_ok=True)
            base = n if n.endswith(".json") else n + ".json"
            try:
                _replace(path, os.path.join(done, n + ".bad"))
            except OSError:
                pass
            write_json(os.path.join(done, base), {"raw": "not read", "result": {"ok": False, "msg": bad, "at": now(),
                                                                              "queued_at": None}})
            self.log(ev="ctl", file=n, op=None, ok=False, msg=bad)
            return
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
                shutil.rmtree(dst)
            write_json(dst, ctl)
        except Exception as e:   # noqa: BLE001
            raise RuntimeError("已執行（ok=%s：%s），但回條寫不進去：%r" % (ok, msg, e)) from e
        try:
            os.remove(path)
        except OSError:
            pass
        self.log(ev="ctl", file=n, op=ctl.get("op"), node=ctl.get("node"), by=ctl.get("by"), ok=ok, msg=msg)

    def stop(self, kill):
        """要求所有時間線停止；kill 一旦要求就不會被後來的 False 撤銷。"""
        if not self.stopping:
            self.stopping_since = time.monotonic()
        self.stopping = True
        self.kill_on_stop = self.kill_on_stop or kill
        for tl in self.timelines.values():
            tl.wake.set()

    # ---------- node ----------

    def check_nodes(self):
        """每圈看已登記的 node（spec §2.6）：確定不在、不是資料夾、inode 換了 → 停時間線、收任務、記 missing（登記保留）；
        看不到（EIO…）＝不知道，保留現狀、記錯；資料夾回來了，等舊程序收完才重開時間線。"""
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
                # 換成符號連結（lstat 看到連結本身）也算不是資料夾；路徑中間段換連結是誤用（spec §11）
                gone = None if stat.S_ISDIR(st.st_mode) else "不是資料夾了（或換成了符號連結）"
            except OSError as e:
                if e.errno not in GONE_ERRNO:
                    # 看不到不是消失：不能因此殺任務或丟掉時間線
                    err = hold("daemon", errname(e), "%s：看不到 node（%r），保留現狀" % (errname(e), e))
                    if tl:
                        tl.last_error = err
                    else:
                        self.node_errors[nid] = err
                    continue
                gone, st = "不存在", None
            if tl and not gone and (st.st_dev, st.st_ino) != tl.node_ident:
                # 同一路徑已是另一個資料夾：不能讓它承接舊任務
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
        """在背景收 node 的任務（記著的 pgid＋環境身分掃描，Q1），不擋主迴圈；結果記事件。"""
        known = self._pgids.pop(nid, set())

        def work():
            n, clean = aos7_proc.kill_node(node, known)
            self.log(ev=ev, node=nid, groups=n, ok=clean, **({"why": why} if why else {}))
        th = threading.Thread(target=work, name="reap:" + nid, daemon=True)
        self.reapers[nid] = th
        th.start()

    def kill_live(self, nid, node):
        """stop／unregister 帶 kill 時：逐槽收活任務，再掃一次 Q1 範圍。一個槽出事只記它。"""
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
        """status 的 live（每 LIVE_EVERY 秒重算），順便記下活任務的 pgid（node 消失時收）。只讀不殺。
        判不出的槽保守列活、沿用記著的群組；列不出槽就沿用上次的（不能清空，不然 node 消失時漏收）。
        判不出的細節（哪個槽、為什麼）status 不放，用診斷包 `aos7-diag` 按需重算。"""
        t, live = self._live.get(nid, (None, None))
        if t is not None and time.monotonic() - t < LIVE_EVERY:
            return live
        slots, lerr = aos7_task.list_slots(tl.node)
        if lerr:
            prev = (self._live.get(nid) or (None, []))[1] or []
            self._live[nid] = (time.monotonic(), prev)
            return prev
        live, pgids = [], set()
        for slot in slots:
            fslot = aos7_task.slot_dir(tl.node, slot)
            try:
                v = aos7_task.judge(fslot, tl.node, slot, tl.round)
            except Exception:   # noqa: BLE001
                continue
            if v.state in (aos7_task.LIVE, aos7_task.UNKNOWN):
                live.append(aos7_task.run_id(slot, v.run if v.run is not None else "?"))
                pid = read_json(os.path.join(fslot, "pid.json"))
                if isinstance(pid, dict) and is_int(pid.get("pgid")) and (v.run is None or pid.get("run") == v.run):
                    pgids.add(pid["pgid"])
                elif v.state == aos7_task.UNKNOWN:
                    pgids |= {g for g in self._pgids.get(nid, ()) if g}
        self._live[nid] = (time.monotonic(), live)
        self._pgids[nid] = pgids
        return live

    def sweep_leftovers(self):
        """stop 帶 kill 的最後收尾：照環境身分再掃一次所有已登記 node 的殘留（spec §2.7）。"""
        nodes = [node_path(self.root, n) for n in self.registry]
        if nodes:
            n, clean = aos7_proc.kill_node(nodes)
            self.log(ev="stop-sweep", groups=n, ok=clean)

    # ---------- status ----------

    def write_status(self, stopped=False):
        """覆寫 status.json（spec §2.8）。stopped＝正常退出前的最後一份。"""
        nodes = {}
        retiring = {nid: t for nid, (t, _k) in self.retiring.items() if t.is_alive()}
        for nid in sorted(set(self.registry) | set(self.timelines) | set(retiring)):
            tl = self.timelines.get(nid) or retiring.get(nid)
            by = list(self.paused.get(nid) or [])
            row = {"round": None, "round_open": None, "recovery_pending": False, "paused_by": by, "pause_pending": False,
                   "interval_ms": None, "early_tock": None, "live": []}
            if tl is None:
                row["phase"] = "missing" if nid in self.missing else ("stopped" if stopped else "idle")
                extra = {"missing": self.missing.get(nid), "last_error": self.node_errors.get(nid)}
            else:
                phase = "paused" if by and tl.phase == "idle" else tl.phase
                if nid in retiring and phase != "stopped":
                    phase = "unregistering"   # 已取消登記，本回合收完才結束
                row.update(round=tl.round, round_open=tl.round_open, recovery_pending=tl.recovery_pending, phase=phase,
                           pause_pending=bool(by) and phase not in ("paused", "stopped", "error"),
                           interval_ms=tl.interval_ms, early_tock=tl.early_tock, live=self.live_of(nid, tl))
                extra = {"last_error": tl.last_error, "last_event": tl.last_event}
            # steps_left＝{owner: 剩幾回合}：daemon 記憶體裡的狀態，只能從這裡看
            extra["steps_left"] = dict(self.steps[nid]) if nid in self.steps else None
            row.update({k: v for k, v in extra.items() if v})
            nodes[nid] = row
        st = {"pid": os.getpid(), "root": self.root, "at": now(), "poll_s": POLL, "gen": self.gen,
              "io_errors": self.io_errors, "stopping": self.stopping, "stopped": stopped,
              "last_event": self.last_event, "nodes": nodes}
        extra = {"last_ctl_error": self.last_ctl_error, "root_gone": self.root_gone or None, "last_error": self.root_error}
        st.update({k: v for k, v in extra.items() if v})
        write_json(os.path.join(self.aosd, "status.json"), st)

    def check_root(self):
        """root 確定不在或換了 inode → stop 加 kill（spec §2.5）；看不到（EIO…）保留現狀、記在 status 頂層。"""
        try:
            same = os.path.samestat(os.stat(self.root), os.fstat(self.rfd))
        except OSError as e:
            if e.errno not in GONE_ERRNO:
                self.root_error = hold("daemon", errname(e), "看不到 root（%r），保留現狀" % e)
                return
            same = False
        self.root_error = None
        if not same and not self.root_gone:
            self.root_gone = True
            self.stop(True)
            self.log(ev="root-gone", root=self.root)

    # ---------- 主迴圈 ----------

    def run(self):
        """拿 daemon.lock、換世代、跑主迴圈；停止時等時間線收完。回退出碼：0 正常、1 鎖拿不到、3 狀態檔不知道。"""
        os.makedirs(os.path.join(self.aosd, "ctl"), exist_ok=True)
        # flock 綁 inode：鎖檔不 unlink，不然新舊程序會各鎖一個同名的 inode
        lock = open(os.path.join(self.aosd, "daemon.lock"), "a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print("aos7-daemon: %s 已經有 daemon 在跑" % self.root, file=sys.stderr)
            return 1
        for s in (signal.SIGTERM, signal.SIGINT):
            signal.signal(s, lambda *_: self.stop(True))
        try:
            old_gen = self.load_state()
        except Unknown as e:
            print("aos7-daemon: %s" % e, file=sys.stderr)
            return 3
        self.save_paused()   # 一起來就寫一份（空的也寫）
        if not os.path.lexists(os.path.join(self.aosd, "nodes.json")):
            self.save_nodes()
        # 拿到 daemon.lock 才遞增世代：舊 daemon 的 tick／tock 晚拿到 action.lock 時認得出自己過期了
        self.gen = old_gen + 1
        write_json(os.path.join(self.aosd, "gen.json"), {"gen": self.gen, "pid": os.getpid(), "at": now()})
        self.log(ev="start", pid=os.getpid(), gen=self.gen)
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
        """每 SWEEP_EVERY 秒清一次 `.aosd/`、`ctl/`、`ctl-done/` 裡寫者已死的暫存檔（K：被殺在 rename 前留下的）。"""
        if time.monotonic() - self._swept < SWEEP_EVERY:
            return
        self._swept = time.monotonic()
        for d in (self.aosd, os.path.join(self.aosd, "ctl"), os.path.join(self.aosd, "ctl-done")):
            gone = sweep_tmp(d)
            if gone:
                self.log(ev="tmp-swept", dir=os.path.basename(d), files=gone[:20], n=len(gone))

    def guard(self, step):
        """跑主迴圈的一步；丟例外只記下來（io_errors、stderr、事件），下一步照跑。"""
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
    """命令列入口：`aos7-daemon <root>`。"""
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or not os.path.isdir(argv[0]):
        print("用法: aos7-daemon <root>（root 要是已存在的資料夾）", file=sys.stderr)
        return 1
    return Daemon(argv[0]).run()
