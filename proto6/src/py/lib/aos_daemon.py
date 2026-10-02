"""最核心的 aos-daemon：一個叫 aos-exec 的 cron（plan m3-daemon-core.md）。

讀設定檔裡的 inst 清單，每一項一條執行緒，照自己的週期叫一次 `<bin>/aos-exec <inst 字面值>`，
等它結束、stdout 印一行。沒有 socket、沒有登記、沒有收屍。核心沒有 id 這個概念：一項就是
它在 `insts` 物件裡的鍵（inst 字面值）與鍵的位置（使用者 2026-10-01）。
整份設定檔先經 aos 指示詞展開再讀（`expand()`）；頂層 `modules` 核心認得、不解讀。
〔使用者方向 2026-10-01〕POC 默認一切正常：設定檔讀得懂、路徑都對、aos-exec 叫得起來；
不寫異常處理，出事讓 Python 自然丟錯（traceback、回 1）。
設定檔寫了 `modules.control` 就掛上控制模組（plan m3n-control-module.md，`lib/aos_daemon_ctl.py`）：
多開一個 unix socket 收 wake／pause／resume／status，並把 `AOS_DAEMON_CTL_SOCKET`、`AOS_DAEMON_INST`
放進每次 aos-exec 的環境。沒寫時跟 m3 一模一樣（沒人叫醒迴圈、不傳 env=）。
寫了 `modules.reload` 就收 SIGHUP 重讀同一份設定檔（plan m3m 模組一，`lib/aos_daemon_reload.py`）；
寫了 `modules.state`（原始值必須是 `{"$ref": "<檔>"}`）就把暫停／已停記進那個檔、重開時讀回
（plan m3m 模組三，`lib/aos_daemon_state.py`）；寫了 `modules.cgroup` 就每項一個 cgroup 框、
`aos-exec` 結束後清掉框裡的殘留才算這次結束（plan m3m 模組二，`lib/aos_daemon_cgroup.py`）；
寫了 `modules.mq` 就每扇門另開一個 unix socket 收寄信、取信，每項一個信箱（plan m3m 模組四，`lib/aos_daemon_mq.py`；
第二十五批改成多扇門）；
daemon 建的 socket 檔（控制、訊息）一律 chmod 666，誰能連由 socket 所在資料夾的權限決定（第二十五批）。
寫了 `modules.account` 就要用 root 開：開出 root 端 `aos-daemon-root` 後主程式永久降成預設帳號，別的帳號的項
經 root 端開（plan m3m 模組五，`lib/aos_daemon_account.py`、`lib/aos_daemon_root.py`）。

〔使用者 2026-10-01 第十九批〕三件跟「daemon 跑 daemon」有關的事：
- 收 aos-exec 的 stdout／stderr 每次、每條最多留頂層 `exec_output_max_bytes`（預設 1 MiB；各項共用，
  每項不能覆蓋——寫在某項裡照不認得的鍵忽略），邊讀邊丟最早的，標頭多 `dropped=<bytes>`
  （下層 daemon 永遠不結束，不能先全收）。
- 開起來對鎖檔（預設 `<設定檔>.lock`，頂層 `lock_path` 可改）取非阻塞 flock；拿不到＝另一個 daemon 正用這份設定：
  stderr `aos-daemon: lock: another aos-daemon holds <鎖檔>`、回 1（在開 socket、建 cgroup、開 root 端之前）。
- 控制模組的 `kill`／`restart`（`aos_daemon_ctl`）要的：記下那一次的程序群組（`Item.pid`）或 root 端的請求 id、
  每次跑一個序號（`Item.run_seq`），`signal_run()`／`kill_run()` 送訊號。

拆檔（母模組留原路徑當入口，對外 import 一個都不變）：設定檔與 `Item` 在 aos_daemon_config.py、
stdout 與 aos-exec 輸出在 aos_daemon_output.py、每一項的迴圈在 aos_daemon_run.py、kill／restart 送訊號在
aos_daemon_kill.py；這裡留執行期的共用狀態與 `main()`。
"""
import argparse
import fcntl
import os
import signal
import sys
import threading

from aos_directives import DirectiveError
# 以下 re-export：別的模組與測試照舊用 aos_daemon.X
from aos_daemon_config import (  # noqa: F401
    INST_MARK, OUTPUT_MAX, Item, Setup, _state_ref, err_path_for, expand, load_config, load_full, load_setup, read_config,
)
from aos_daemon_output import _block, _out, clock, drain, now, say, write_outputs  # noqa: F401
from aos_daemon_run import (  # noqa: F401
    EXEC, _gone, _next_run, give_env, loop, run_once, snapshot, start_item, state_changed,
)
from aos_daemon_kill import kill_run, kill_targets, signal_run  # noqa: F401

# 控制模組、訊息模組的 socket 絕對路徑；退出前要刪（m3n 步驟 6）
_sock_paths = []

# 記住狀態模組（aos_daemon_state.StateFile）；沒掛＝None
_state = None

# 收屍／cgroup 模組（aos_daemon_cgroup.Tree）；沒掛＝None
_cg = None

# 帳號模組（aos_daemon_account.Account）；沒掛＝None
_acct = None

# 第十九批：設定檔的鎖檔 fd（握到程序結束；os.open 開的預設不可繼承）
_lock_fd = None

# 目前的清單 {inst 字面值: Item}。控制模組、記住狀態、重讀設定共用同一個 dict 物件；
# 重讀設定加減項時在 _items_lock 底下原地改（m3m 模組一）
_items = {}
_items_lock = threading.Lock()


def _quit(signum, frame):
    """m3 步驟 5：SIGINT／SIGTERM 直接退出、回 0，不殺也不等子程序。
    控制模組、訊息模組掛著時先刪 socket 檔（m3n 步驟 6）。"""
    _die(0)


def _die(code):
    """刪 socket 檔、直接退出（帳號模組的 root 端不見了也走這裡，回 1）。"""
    for path in _sock_paths:
        try:
            os.unlink(path)
        except FileNotFoundError:       # 訊號來在 bind 之前：還沒建
            pass
    os._exit(code)


class _Parser(argparse.ArgumentParser):
    """aos 結束碼慣例：argparse 的用法錯預設回 2，改回 1。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, "%s: error: %s\n" % (self.prog, message))


def _catch_hup():
    """m3m 模組一：接 SIGHUP，回一個 pipe 的讀端；主執行緒讀它等 SIGHUP。
    用 `signal.set_wakeup_fd`：每個訊號的編號都會寫進 pipe，所以訊號來在任何時候都不會漏；
    重讀中又來幾次，讀出來是同一批，讀完再重讀一次就好。SIGHUP 的 Python handler 什麼都不做
    （只為了不被預設動作殺掉）。"""
    r, w = os.pipe()
    os.set_blocking(w, False)
    signal.set_wakeup_fd(w)
    signal.signal(signal.SIGHUP, lambda signum, frame: None)
    return r


def main(argv=None):
    ap = _Parser(prog="aos-daemon", description="照設定檔的清單，定期叫 aos-exec")
    ap.add_argument("--config", required=True, metavar="F", help="設定檔（JSON）")
    a = ap.parse_args(argv)
    global _state, _cg, _acct, _lock_fd
    try:
        setup = load_full(a.config)
    except (ValueError, DirectiveError) as e:
        sys.stderr.write("aos-daemon: config: %s\n" % e)
        return 1
    # 第十九批：鎖檔先開（開 socket、建 cgroup、開 root 端、降權之前；fd 握到結束）。
    # 拿不到＝另一個 daemon 正用這份設定：stderr 一行、回 1（使用者：「拿不到鎖就報錯退出」）
    _lock_fd = os.open(setup.lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.stderr.write("aos-daemon: lock: another aos-daemon holds %s\n" % setup.lock_path)
        return 1
    policy = None
    if setup.account:                   # m3m 模組五：先核帳號（還是 root，A6：查不到就回 1）
        import aos_daemon_account
        try:
            if os.geteuid() != 0:
                raise aos_daemon_account.AccountError("掛了 modules.account 要用 root 開")
            policy = aos_daemon_account.Policy(setup.modules["account"])
            policy.check_items(setup.items)
        except aos_daemon_account.AccountError as e:
            sys.stderr.write("aos-daemon: account: %s\n" % e)
            return 1
    start, items, sock = setup.start, setup.items, setup.sock
    signal.signal(signal.SIGINT, _quit)
    signal.signal(signal.SIGTERM, _quit)
    if setup.cgroup:                    # m3m 模組二：沒有委派好的 cgroup v2 就自然丟錯、回 1（C1）
        import aos_daemon_cgroup
        _cg = aos_daemon_cgroup.Tree()
        for item in items:
            _cg.make(item, startup=True)
            _cg.announce(item, say)
    if policy is not None:              # m3m 模組五：子樹交給預設帳號 → 開 root 端 → 主程式永久降權
        if _cg is not None:
            pw = aos_daemon_account.lookup(policy.default)
            aos_daemon_account.chown_tree(_cg.root, pw.pw_uid, pw.pw_gid)
        _acct = aos_daemon_account.Account(policy)
        _acct.drop()
    with _items_lock:
        _items.update((item.inst, item) for item in items)
    if setup.state_path is not None:    # m3m 模組三：照檔恢復暫停、已停（不在清單上的鍵丟掉）
        import aos_daemon_state
        _state = aos_daemon_state.StateFile(setup.state_path, setup.state_data)
        aos_daemon_state.restore(items, setup.state_data)
    for item in items:
        give_env(item, setup)
    if sock is not None:                # m3n：先開好 socket 再起各項，任務一開始就叫得到
        import aos_daemon_ctl
        aos_daemon_ctl.set_grace(setup.modules["control"])
        _sock_paths.append(sock)        # 先記好再 bind：bind 完立刻來的訊號也刪得到
        aos_daemon_ctl.serve(sock, _items)
        os.chmod(sock, 0o666)           # 第二十五批：一律 666，誰能連看所在資料夾的權限
    if setup.mq_doors:                  # m3m 模組四：同上，每扇門一個 socket（第二十五批）
        import aos_daemon_mq
        for name, path in setup.mq_doors.items():
            _sock_paths.append(path)
            aos_daemon_mq.serve(name, path, _items)
            os.chmod(path, 0o666)
    hup = None
    if setup.reload:                    # m3m 模組一：沒掛時 SIGHUP 照 Python 預設（daemon 被殺）
        import aos_daemon_reload
        hup = _catch_hup()
    for item in items:
        start_item(item, start)
    while True:                         # 所有項都停了也照樣開著（使用者 2026-10-01）
        if hup is None:
            signal.pause()
        elif signal.SIGHUP in os.read(hup, 512):
            aos_daemon_reload.reload(a.config, setup)
