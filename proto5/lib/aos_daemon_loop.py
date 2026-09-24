"""daemon-reconcile §1～§7：一圈怎麼走——收屍、狀態機、退避、節流、fd 預算、批次階梯、停機。

每圈的工作只跟「這圈有事的」成比例：收屍用 waitpid(-1)；dead／failed 的到期、活滿 stable_ms、
階梯的下一段都放在同一個按時間排的堆積裡；可以拉的號每池一條佇列，只有佇列不空的池參加輪流
（輪流用 deque）；要重算成員、要發布摘要的池各一個待處理集合（review P9），刪池失敗的另記待刪（P5）。
"""
import collections
import heapq
import itertools
import json
import os
from pathlib import Path
import shutil
import time

import aos_daemon_pools as pools
import aos_daemon_rpc
import aos_daemon_ticks
import aos_home
from aos_exec_run import DEFAULT_DIR_TARGET
from aos_exec_spawn import SpawnError

Kid, Pool = pools.Kid, pools.Pool


class Batch:
    """同一圈開始收的一批（daemon-reconcile §6）；記 gen，免得砍到同號重拉的下一代。"""

    def __init__(self, kids, stage):
        self.kids, self.stage = kids, stage          # kids: [(pool, kid, gen)]


class Daemon(aos_daemon_rpc.Requests, aos_daemon_ticks.TicksMixin):
    """一個活著的主人。真正的狀態＝記憶體＋pool.json＋kernels/*.json；kids／summary 是給外人看的影子。"""

    def __init__(self, home, info, budget=None):
        self.home, self.info = Path(home), info
        self.state = {"pid": os.getpid(), "stopping": False, "current": None}
        self.pools = {}
        self.by_pid = {}                             # pid -> (pool, kid)：活著＋killing 的
        self.timers = []                             # (monotonic, seq, kind, payload)
        self.seq = itertools.count()
        self.rotation = collections.deque()          # 有可以拉的號的池，輪流
        self.todo = ({}, {})                         # (要重算的池, 要發布的池)：有序集合
        self.removing = set()                        # 刪失敗的池名：待刪、每圈重試到成功
        self.batch = []                              # 這圈要開始收的
        self.unflushed = {}                          # kid -> (gen, bytes)：EAGAIN 沒寫完的
        self.stop_requested = False
        self.budget = info["max_children"] if budget is None else budget
        self.tokens, self.refilled = float(info["spawn_per_sec"]), time.monotonic()
        self.init_ticks()

    # ---- 小工具 ----

    def save(self):
        aos_home.write_state(self.home, self.state)

    def new_pool(self, decl):
        """建池並登記進 todo；同名池還在待刪就取消（新宣告要用這個資料夾）。"""
        self.removing.discard(decl["pool"])
        return Pool(self.home, decl, self.todo)

    def current(self, pool):
        return self.pools.get(pool.name) is pool

    def declared(self):
        return sum(pool.count for pool in self.pools.values())

    def at(self, delay_ms, kind, payload):
        heapq.heappush(self.timers, (time.monotonic() + delay_ms / 1000, next(self.seq), kind, payload))

    def backoff_ms(self, streak):
        return min(self.info["restart_delay_ms"] * 2 ** (streak - 1), self.info["restart_max_ms"])

    def enqueue(self, pool, kid):
        if not kid.queued:
            kid.queued = True
            pool.ready.append(kid.i)
            if not pool.in_rotation:
                pool.in_rotation = True
                self.rotation.append(pool)

    def write_line(self, kid, method):
        """非阻塞寫一行；EAGAIN 留到下一圈再寫。回 False＝EPIPE（孩子不聽了）。"""
        data = (json.dumps({"jsonrpc": "2.0", "method": method}) + "\n").encode()
        self.unflushed[kid] = (kid.gen, data)
        return self.flush(kid)

    def flush(self, kid):
        gen, data = self.unflushed[kid]
        if kid.handle is None or kid.gen != gen:
            del self.unflushed[kid]
            return True
        try:
            written = os.write(kid.handle.process.stdin.fileno(), data)
        except BlockingIOError:
            return True
        except (BrokenPipeError, OSError):
            del self.unflushed[kid]
            return False
        if written < len(data):
            self.unflushed[kid] = (gen, data[written:])
        else:
            del self.unflushed[kid]
        return True

    # ---- 狀態轉移 ----

    def start_killing(self, pool, kid):
        """running → killing：寫檔、排進這一圈的批（daemon-reconcile §6）。"""
        pool.update(kid, state="killing", restarting=False, next_at=None)
        kid.stage = "stop"
        pool.write_kid(kid)
        self.batch.append((pool, kid, kid.gen))

    def forget(self, pool, kid):
        """停機時拿掉：成員的檔改成 pending（pid null），下次開機不會去砍到被重用的 pid（D-58）。"""
        pool.drop(kid)
        self.unflushed.pop(kid, None)
        if not kid.member:
            pool.delete_kid(kid)
        elif kid.has_file:
            kid.pid = kid.since = kid.next_at = None
            kid.state, kid.streak = "pending", 0
            pool.write_kid(kid)

    def request_stop(self):
        if self.state["stopping"]:
            return
        self.state["stopping"] = True
        self.save()
        self.stop_ticks()
        for pool in self.pools.values():
            for kid in list(pool.kids.values()):
                if kid.state == "running":
                    self.start_killing(pool, kid)
                elif kid.state != "killing":
                    self.forget(pool, kid)

    def died(self, pool, kid, code):
        now = time.monotonic()
        lived = now - kid.started if kid.started is not None else 0
        pool.update(kid, exits=kid.exits + 1, last_exit=code)
        kid.stage = None
        self.unflushed.pop(kid, None)
        if self.state["stopping"]:
            self.forget(pool, kid)
        elif kid.state == "killing":
            if kid.member:                                   # kill＝砍掉重來：不加 streak、不用等
                pool.update(kid, state="pending", restarting=False, next_at=None)
                kid.due = None
                pool.write_kid(kid)
                self.enqueue(pool, kid)
            else:
                pool.drop(kid)
                pool.delete_kid(kid)
        else:
            streak = 1 if lived * 1000 >= self.info["stable_ms"] else kid.streak + 1
            self.to_waiting(pool, kid, "dead", streak)

    def to_waiting(self, pool, kid, state, streak):
        wait = self.backoff_ms(streak)
        pool.update(kid, state=state, streak=streak, restarting=False,
                    next_at=time.time() + wait / 1000)
        kid.due = time.monotonic() + wait / 1000
        pool.write_kid(kid)
        self.at(wait, "due", (pool, kid, kid.gen, kid.due))

    # ---- 一圈的各步 ----

    def reap(self):
        """waitpid(-1, WNOHANG) 收到沒有為止；只碰死掉的（daemon-reconcile §2 第 3 步）。"""
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return
            if pid == 0:
                return
            entry = self.by_pid.pop(pid, None)
            if entry is None:
                self.tick_exited(pid, pools.exit_code(status))   # one-boot：kernel 的一格
                continue
            pool, kid = entry
            code = pools.exit_code(status)
            pools.finish(kid, code)
            self.died(pool, kid, code)

    def reconcile(self, pool):
        """成員重算（O(池大小)，只在宣告變了）：新號 pending，拿掉的照 §1 收。"""
        pool.dirty = False
        wanted = set(pools.members(pool.count, pool.decl["skip"]))
        for kid in list(pool.kids.values()):
            member = kid.i in wanted
            if member == kid.member:
                continue
            if member:
                pool.update(kid, member=True)                # 收到一半又加回來：死透後當 pending
            elif kid.state == "running":
                pool.update(kid, member=False)
                self.start_killing(pool, kid)
            elif kid.state == "killing":
                pool.update(kid, member=False)
            else:
                pool.drop(kid)
                self.unflushed.pop(kid, None)
                pool.delete_kid(kid)
        for i in sorted(wanted.difference(pool.kids)):
            kid = Kid(i)
            pool.add(kid)
            self.enqueue(pool, kid)
        pool.members = wanted

    def next_ready(self, pool):
        now = time.monotonic()
        while pool.ready:
            kid = pool.kids.get(pool.ready.popleft())
            if kid is None or not kid.queued:
                continue
            kid.queued = False
            if kid.member and kid.state in ("pending", "dead", "failed") and \
                    (kid.due is None or kid.due <= now):
                return kid
        return None

    def spawn_round(self):
        """拉：令牌桶（spawn_per_sec）、池之間一次一顆輪流、每拉前看活著＋killing 有沒有到 fd 預算。"""
        if self.state["stopping"]:
            return
        now, rate = time.monotonic(), self.info["spawn_per_sec"]
        self.tokens = min(float(rate), self.tokens + (now - self.refilled) * rate)
        self.refilled = now
        while self.rotation and self.tokens >= 1 and len(self.by_pid) < self.budget:
            pool = self.rotation.popleft()
            if not self.current(pool):
                continue
            kid = self.next_ready(pool)
            if kid is not None:
                self.tokens -= 1
                self.launch(pool, kid)
            if pool.ready:
                self.rotation.append(pool)
            else:
                pool.in_rotation = False

    def launch(self, pool, kid):
        """proto5 §2 的 go 握手：fork → 寫 kids 檔（running）→ go。"""
        try:
            handle = pools.spawn_child(pool.target(kid.i), pool.decl.get("dir_target") or
                                       DEFAULT_DIR_TARGET)
        except SpawnError as exc:
            pools.log("SpawnFailed", "池 %s 的 %d 號拉不起來：%s" % (pool.name, kid.i, exc.msg))
            self.to_waiting(pool, kid, "failed", kid.streak + 1)
            return
        pid = handle.process.pid
        kid.handle, kid.started, kid.due = handle, time.monotonic(), None
        pool.update(kid, state="running", pid=pid, gen=kid.gen + 1, since=time.time(),
                    next_at=None, restarting=kid.streak > 0)
        self.by_pid[pid] = (pool, kid)
        if not pool.write_kid(kid):
            handle.process.stdin.close()                     # 沒登記就不送 go：孩子讀到 EOF 自己退
            return
        self.at(self.info["stable_ms"], "stable", (pool, kid, kid.gen))
        self.write_line(kid, "go")

    def start_batch(self):
        if not self.batch:
            return
        kids, self.batch, broken = self.batch, [], []
        for pool, kid, gen in kids:
            if kid.handle is not None and kid.gen == gen and not self.write_line(kid, "stop"):
                broken.append((pool, kid, gen))
        self.at(self.info["stop_wait_ms"], "stage", Batch(kids, "stop"))
        if broken:                                           # EPIPE＝不聽了，直接跳下一階
            self.term(Batch(broken, "stop"))

    def alive(self, batch, stage):
        return [(pool, kid, gen) for pool, kid, gen in batch.kids
                if kid.handle is not None and kid.gen == gen and kid.stage == stage]

    def term(self, batch):
        kids = self.alive(batch, "stop")
        for pool, kid, gen in kids:
            self.unflushed.pop(kid, None)
            kid.stage = "term"
            pools.signal_pid(kid.pid, pools.TERM)            # 只給孩子本身
        if kids:
            self.at(self.info["kill_wait_ms"], "stage", Batch(kids, "term"))

    def kill_group(self, batch):
        for pool, kid, gen in self.alive(batch, "term"):
            kid.stage = "kill"
            pools.signal_pid(kid.pid, pools.KILL, group=True)  # 整組

    def run_timers(self):
        now = time.monotonic()
        while self.timers and self.timers[0][0] <= now:
            _, _, kind, payload = heapq.heappop(self.timers)
            if kind == "stage":
                (self.term if payload.stage == "stop" else self.kill_group)(payload)
                continue
            pool, kid, gen = payload[:3]
            if pool.kids.get(kid.i) is not kid or kid.gen != gen:
                continue
            if kind == "stable" and kid.state == "running":
                pool.update(kid, streak=0, restarting=False)
            elif kind == "due" and kid.state in ("dead", "failed") and kid.due == payload[3]:
                self.enqueue(pool, kid)

    def publish(self):
        """有變的池重寫 summary；count 0 收完的整池拿掉（先 summary、再 pool.json、再資料夾）。
        只看 todo 裡登記過的池：池變成「count 0 收完」那一刻一定剛設過 changed（drop／scale／新建）。
        寫失敗留在 todo、刪失敗記進 removing，下一圈都再試，直到成功（review P5）。"""
        now = time.time()
        for name in list(self.removing):
            if pools.remove_pool(self.home, name, quiet=True):
                self.removing.discard(name)
        todo = list(self.todo[1])
        self.todo[1].clear()
        for pool in todo:
            if not self.current(pool):
                continue
            if pool.count == 0 and not pool.kids:
                del self.pools[pool.name]
                if not pools.remove_pool(self.home, pool.name):
                    self.removing.add(pool.name)
            elif pool.changed and not pool.write_summary(now):
                self.todo[1][pool] = None                    # 寫失敗：下一圈再試

    def step(self):
        if self.stop_requested:
            self.request_stop()
        aos_home.scan_controls(self.home, self.request_stop)
        for name in aos_home.list_requests(self.home):
            if self.stop_requested:
                self.request_stop()
            self.process_request(name)
        for kid in list(self.unflushed):
            self.flush(kid)
        self.reap()
        todo = list(self.todo[0])
        self.todo[0].clear()
        for pool in todo:
            if pool.dirty and self.current(pool):
                self.reconcile(pool)
        self.run_timers()
        self.spawn_round()
        self.start_batch()
        self.publish()
        self.ticks_step()
        return self.state["stopping"] and not self.by_pid and not self.tick_pids

    def sleep_s(self):
        """睡到 poll_ms 或下一個到期時間，取較短的（daemon-reconcile §2 第 8 步）。"""
        delay = self.info["poll_ms"] / 1000
        now = time.monotonic()
        if self.timers:
            delay = min(delay, self.timers[0][0] - now)
        if self.rotation and not self.state["stopping"] and len(self.by_pid) < self.budget:
            delay = min(delay, (1 - self.tokens) / self.info["spawn_per_sec"])
        return max(self.ticks_sleep(delay), 0.0005)

    def close(self):
        for pool, kid in list(self.by_pid.values()):
            if kid.handle is not None:
                try:
                    kid.handle.process.stdin.close()
                except OSError:
                    pass

    # ---- 開機（handoff §2）----

    def adopt(self, decls, old_kids):
        """舊孩子死透之後：kids 檔改 pending（非成員刪），照 pool.json 把成員排進 pending。"""
        for decl in decls:
            pool = self.new_pool(decl)
            self.pools[pool.name] = pool
            self.reconcile(pool)
        for name, i, path, record in old_kids:
            pool = self.pools.get(name)
            kid = pool.kids.get(i) if pool is not None else None
            if kid is None:
                try:
                    os.unlink(path)
                except OSError:
                    pass
                continue
            kid.load(record)
            kid.has_file = True
            pool.write_kid(kid)
        for path in pools.pools_dir(self.home).iterdir():
            if path.is_dir() and path.name not in self.pools:      # 沒有 pool.json 的殘骸
                shutil.rmtree(path, ignore_errors=True)
        self.publish()
