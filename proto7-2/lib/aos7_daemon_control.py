"""Daemon 的控制請求、回條與停止要求（DaemonControl mixin，Daemon 繼承它）。

aos7_fs 的函式（fact、write_json、now…）與 norm_id、_replace、CTL_* 一律經 aos7_daemon 模組取用，測試替換 aos7_daemon.<名字> 照樣生效；檔尾才 import，避免循環。"""
import datetime
import os
import shutil
import stat
import time

from aos7_fs import N, OK, U, Unknown


class DaemonControl:
    # ---------- 控制檔 ----------

    def apply(self, ctl):
        """執行一份控制請求，回 (ok, msg)。op、node 不合或 node 屬於別的 daemon＝ok:false。"""
        op = ctl.get("op")
        if op in ("register", "unregister", "pause", "resume", "wake"):
            nid = daemon.norm_id(ctl.get("node"))
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
        p = daemon.node_path(self.root, nid)
        real, r = os.path.realpath(p), os.path.realpath(self.root)
        if real != daemon.canonical_node(self.root, nid):   # 登記綁定實際位置：路上有符號連結（即使指在空間根內）就不收
            out = not (real == r or real.startswith(r + os.sep))
            return False, "%s %s（實際在 %s），%s" % (nid, "沿符號連結跑出空間根" if out else "的路徑經過符號連結", real,
                                                    "不登記" if out else "請登記實際位置")
        if os.path.lexists(p) and not os.path.isdir(p):
            return False, "%s 不是資料夾，不登記" % nid
        new = dict(self.registry)
        new[nid] = {"by": ctl.get("by"), "at": daemon.now()}
        try:
            self.save_nodes(registry=new)
        except OSError as e:
            return False, "nodes.json 寫不進去（%s），登記沒有改；請重送" % e
        self.registry = new
        self.log(ev="register", node=nid, by=ctl.get("by"))
        return True, "registered %s%s" % (nid, "" if os.path.isdir(p) else "（資料夾目前不在，出現時才開回合）")

    def op_unregister(self, nid, ctl):
        """取消登記（spec §2.3）：馬上從 nodes.json 拿掉，本回合照常收完；預設 kill 那個 node 的活任務。"""
        if nid not in self.registry:
            return True, "%s 沒有登記" % nid
        kill = ctl.get("kill", True) is not False
        # 先寫回 nodes.json：死在收尾途中，重開也不會自動再跑它
        new_reg, new_rp = dict(self.registry), dict(self.reaping)
        del new_reg[nid]
        if kill:
            new_rp.setdefault(nid, {"since": daemon.now(), "why": "unregister-kill"})
        try:
            self.save_nodes(new_reg, new_rp)
        except OSError as e:
            return False, "nodes.json 寫不進去（%s），登記沒有改；請重送" % e
        self.registry, self.reaping = new_reg, new_rp
        tl = self.timelines.pop(nid, None)
        self.missing.pop(nid, None)
        with self._lock:
            self.steps.pop(nid, None)
            self.owe.pop(nid, None)
        self._save_paused_quiet()
        if tl and tl.is_alive():
            tl.retire, tl.retire_kill = True, kill
            tl.wake.set()
            self.retiring[nid] = (tl, kill)
        self.log(ev="unregister", node=nid, by=ctl.get("by"), kill=kill)
        return True, "unregistered %s（%s）" % (nid, "活任務會被收掉" if kill else "kill: false，任務留著、從此收不到 tock")

    def op_pause(self, nid, ctl):
        """把 owner 加進 nid 的 pause 清單、清掉同 owner 的倒數（spec §2.4）。本回合照常收完才停。"""
        owner = ctl.get("owner", "")
        with self._lock:
            if getattr(self.timelines.get(nid), "settle_pending", None) is not None:
                return False, "%s 上一回合的倒數結算還沒寫進 paused.json，pause 沒有改；稍後重送" % nid
            paused = {k: list(v) for k, v in self.paused.items()}
            steps = {k: dict(v) for k, v in self.steps.items()}
            owe = dict(self.owe)
            lst = paused.setdefault(nid, [])
            if owner not in lst:
                lst.append(owner)
            self._drop_steps(steps, nid, owner)
            self._drop_stale_owe(owe, nid)
            try:
                self.save_paused(paused, steps, owe)
            except (OSError, Unknown) as e:
                return False, "paused.json 寫不進去（%s），pause 沒有改；請重送" % e
            self.paused, self.steps, self.owe = paused, steps, owe
        return True, "pause %s（owner %r；現在：%s）%s" % (nid, owner, self.paused[nid], self._note(nid))

    def op_resume(self, nid, ctl):
        """拿掉自己 owner 的 pause（`all` 全清），可帶 rounds 倒數（spec §2.4）。因此變成沒人 pause 就順便 wake。"""
        owner, rounds = ctl.get("owner", ""), ctl.get("rounds")
        if rounds is not None and (not daemon.is_int(rounds) or rounds < 1):
            return False, "rounds 要是正整數"
        with self._lock:
            if getattr(self.timelines.get(nid), "settle_pending", None) is not None:
                return False, "%s 上一回合的倒數結算還沒寫進 paused.json，resume 沒有改；稍後重送" % nid
            paused = {k: list(v) for k, v in self.paused.items()}
            steps = {k: dict(v) for k, v in self.steps.items()}
            owe = dict(self.owe)
            lst = paused.setdefault(nid, [])
            was = bool(lst)
            if ctl.get("all") is True:
                lst.clear()
                steps.pop(nid, None)
            else:
                if owner in lst:
                    lst.remove(owner)
                self._drop_steps(steps, nid, owner)
            if rounds is not None:
                # 倒數按 owner 各記一份：B 的 rounds 不會蓋掉 A 的
                steps.setdefault(nid, {})[owner] = rounds
            self._drop_stale_owe(owe, nid)
            try:
                self.save_paused(paused, steps, owe)
            except (OSError, Unknown) as e:
                return False, "paused.json 寫不進去（%s），resume 沒有改；請重送" % e
            self.paused, self.steps, self.owe = paused, steps, owe
            left = list(lst)
        if not left and was:
            # 本來就沒人 pause 的 resume 不 wake：wake 會提前結束固定 interval 的回合，沒作用的 resume 不該切掉它
            self._kick(nid)
        return True, "resume %s（owner %r%s%s）；%s%s" % (
            nid, owner, "，all" if ctl.get("all") is True else "", "，rounds=%d" % rounds if rounds else "",
            "還有 %s 在 pause" % left if left else ("沒人 pause 了，馬上開回合" if was else "本來就沒人 pause"),
            self._note(nid))

    def _drop_stale_owe(self, owe, nid):
        """沒有時間線就改倒數：候選表的舊待結算不扣到新倒數上。呼叫的人拿著 _lock。"""
        if nid not in self.timelines:
            owe.pop(nid, None)

    def _drop_steps(self, steps, nid, owner):
        """拿掉候選表中 nid 上 owner 的 rounds 倒數。呼叫的人拿著 _lock。"""
        s = steps.get(nid, {})
        s.pop(owner, None)
        if not s:
            steps.pop(nid, None)

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
        st, g = daemon.fact(os.path.join(self.aosd, "stop-guard.json"))
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
        t_end = time.monotonic() + daemon.CTL_BUDGET_S
        for k, n in enumerate(names):
            if k >= daemon.CTL_BATCH or time.monotonic() >= t_end:
                self.ctl_backlog = True   # 剩下的下一圈接著做
                break
            try:
                self.ctl_one(cdir, n)
            except Exception as e:   # noqa: BLE001
                self.io_errors += 1
                self.ctl_stuck.add(n)
                self._drop(cdir, n)
                self.last_ctl_error = {"file": n, "at": daemon.now(), "err": repr(e)[:300]}
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
            st, ctl = daemon.fact(path)
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
                daemon._replace(path, os.path.join(done, n + ".bad"))
            except OSError:
                pass
            daemon.write_json(os.path.join(done, base), {"raw": "not read", "result": {"ok": False, "msg": bad, "at": daemon.now(),
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
        ctl["result"] = {"ok": ok, "msg": msg, "at": daemon.now(), "queued_at": queued}
        try:
            dst = os.path.join(done, n)
            if os.path.isdir(dst) and not os.path.islink(dst):
                shutil.rmtree(dst)
            daemon.write_json(dst, ctl)
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


import aos7_daemon as daemon
