"""aos-daemon 每一項的迴圈：叫一次 aos-exec、等、印、照週期睡（從 aos_daemon.py 拆出；plan m3 步驟 2–4、m3n 步驟 2）。

執行期的共用狀態（`_items`、`_items_lock`、`_cg`、`_acct`、`_state`）留在母模組 aos_daemon，
`main()` 會換掉其中幾個，所以這裡呼叫時才去 `aos_daemon` 讀。對外照舊從 aos_daemon import（那裡 re-export）。
"""
import os
import subprocess
import threading
import time

from aos_daemon_output import drain, now, say, write_outputs

EXEC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "aos-exec")


def run_once(item, start):
    """m3 步驟 2：叫一次 aos-exec，等它結束，回 (碼, 毫秒, 有沒有收屍)。被訊號殺的碼換成 128+N。
    stdout／stderr 沒設路徑就直接丟到 /dev/null；有設就收齊再一次寫出（共用出口才不交錯）。

    m3m 模組二（掛了 cgroup，`item.frame` 有值）：子程序先進那一項的框再 exec aos-exec；aos-exec 一結束
    （毫秒算到這裡）就清框（框裡還有程序就 `cgroup.kill`、等清空），清完才收齊輸出、回來。
    殘留的程序可能還拿著輸出的 pipe，所以 pipe 另開執行緒讀，清完框它才讀得到結尾。
    收的時候每條最多留 `item.out_max` bytes（第十九批，`drain()`）；沒掛 cgroup 時毫秒照舊算到輸出也收齊。"""
    import aos_daemon
    t0 = time.monotonic()
    pipe = lambda path: subprocess.DEVNULL if path is None else subprocess.PIPE
    argv = [EXEC, item.inst]
    if aos_daemon._acct is not None and aos_daemon._acct.via_root(item):   # m3m 模組五：別的帳號的項經 root 端開（框也由它放）
        import aos_daemon_account
        code, ms, reaped, out, err = aos_daemon_account.run_via_root(aos_daemon._acct, item, start, argv)
        write_outputs(item, out, err)
        return code, ms, reaped
    if item.frame is not None:
        argv = aos_daemon._cg.argv(item.frame, argv)
    p = subprocess.Popen(argv, cwd=start, env=item.env, start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=pipe(item.out_path), stderr=pipe(item.err_path))
    item.pid = p.pid                    # 第十九批：新 session，程序群組 id＝pid（kill 用）
    got = {"out": (b"", 0), "err": (b"", 0)}
    readers = []
    for key, f in (("out", p.stdout), ("err", p.stderr)):
        if f is not None:
            t = threading.Thread(target=drain, args=(os.dup(f.fileno()), item.out_max, got, key), daemon=True)
            f.close()
            t.start()
            readers.append(t)
    p.wait()
    reaped = False
    if item.frame is None:
        for t in readers:
            t.join()
        ms = int((time.monotonic() - t0) * 1000)
    else:
        ms = int((time.monotonic() - t0) * 1000)
        import aos_daemon_cgroup
        reaped = aos_daemon_cgroup.clear(item.frame)
        for t in readers:
            t.join()
    item.pid = None
    code = p.returncode
    write_outputs(item, got["out"], got["err"])
    return (128 - code if code < 0 else code), ms, reaped



def _next_run(item):
    """在 cond 的鎖底下等到該跑：有待補就跑（回它的 keep_schedule）；暫停、已停就一直等；
    否則等到 due（照週期跑的那次，回 False）。m3n 步驟 2。被重讀設定拿掉了回 None。"""
    while True:
        if item.removed:
            return None
        if item.pending and not item.stopped:
            keep = item.pending_keep
            item.pending = item.pending_keep = False
            return keep
        if item.stopped or item.paused:
            item.cond.wait()
            continue
        left = item.due - time.monotonic()
        if left <= 0:
            return False
        item.cond.wait(left)


def loop(item, start):
    """m3 步驟 3、4：叫 → 等 → 印 → 睡 interval_ms；非 0 且 stop_on_nonzero 就印 stopped、不再叫。
    m3n 步驟 2：睡改成等 cond（叫得醒）；停掉時執行緒不結束、一直等（resume 救得回來）。
    控制模組沒掛時沒人碰狀態，行為跟 m3 一樣。
    m3m：被重讀設定拿掉的項，正在跑的那次照樣跑完印完，之後執行緒結束（掛了 cgroup 就刪框）。
    掛了 cgroup：「這次結束」＝aos-exec 結束而且框清空；有清到東西時 `exit=` 之後多印一行 `reaped`。"""
    while True:
        with item.cond:
            keep = _next_run(item)
            if keep is not None:
                item.running = True
                item.run_seq += 1
                seq = item.run_seq
        if keep is None:
            _gone(item)
            return
        code, ms, reaped = run_once(item, start)
        say("inst=%s exit=%d ms=%d" % (item.inst, code, ms))
        if reaped:
            say("inst=%s reaped" % item.inst)
        stopped = False
        with item.cond:
            t = time.monotonic()
            item.running = False
            item.cond.notify_all()      # 第十九批：等這一次結束的 kill_run() 醒來
            item.last_exit, item.last_end, item.end_mono = code, now(), t
            removed = item.removed
            if not removed:
                # 照週期跑的、不帶 keep_schedule 的叫醒：週期從這次結束重新算；帶 keep_schedule 的
                # 不碰 due，除非 due 已經被這次蓋過去（不補跑漏掉的）
                if not keep or item.due <= t:
                    item.due = t + item.interval_ms / 1000.0
                # restart 殺掉的那一次不算（第十九批）；kill 殺掉的照算
                if code != 0 and item.stop_on_nonzero and item.restart_seq != seq:
                    item.stopped = stopped = True
                    item.pending = False
                    say("inst=%s stopped" % item.inst)
        if removed:
            _gone(item)
            return
        if stopped:
            state_changed()


def _gone(item):
    """被重讀設定拿掉的項，執行緒結束前：掛了 cgroup 就刪它的框（m3m 模組二）。
    同一個 inst 已經又被加回來（新的一項用同一個框）就不刪。在 _items_lock 底下做，跟重讀設定建框排開。
    呼叫時不能拿著 item.cond（鎖的順序是 _items_lock → item.cond）。"""
    if item.frame is None:
        return
    import aos_daemon
    with aos_daemon._items_lock:
        if item.inst not in aos_daemon._items:
            aos_daemon._cg.remove(item.frame)


def state_changed():
    """暫停或已停變了（pause、resume、stop_on_nonzero 停掉、重讀設定拿掉項）：掛了記住狀態模組就當場寫整份。"""
    import aos_daemon
    if aos_daemon._state is not None:
        aos_daemon._state.save(snapshot())


def snapshot():
    """目前清單的 [Item]（照鍵的順序），在 _items_lock 底下拷一份。"""
    import aos_daemon
    with aos_daemon._items_lock:
        return list(aos_daemon._items.values())


def give_env(item, setup):
    """控制模組掛著時，開 aos-exec 的環境多放 `AOS_DAEMON_CTL_SOCKET`（m3n 步驟 4；第二十五批由 AOS_DAEMON_SOCKET 改名）；
    訊息模組掛著時每扇門多放一個 `AOS_DAEMON_MQ_<門名>`（第二十五批，每項都拿到每一扇門）；
    掛了任何一個就放 `AOS_DAEMON_INST`（m3m 待問 M2）。都沒掛＝照 daemon 的環境。"""
    extra = {}
    if setup.sock is not None:
        extra["AOS_DAEMON_CTL_SOCKET"] = setup.sock
    for name, path in setup.mq_doors.items():
        extra["AOS_DAEMON_MQ_" + name] = path
    if extra:
        item.env = dict(os.environ, AOS_DAEMON_INST=item.inst, **extra)


def start_item(item, start):
    threading.Thread(target=loop, args=(item, start), daemon=True).start()
