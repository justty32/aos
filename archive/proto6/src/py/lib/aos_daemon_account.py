"""aos-daemon 的帳號模組：主程式那一側（plan m3m-daemon-modules.md 模組五）。

設定檔寫 `"modules": {"account": {...}}` 時掛上，要用 root 開（`sudo aos-daemon --config F`）：

- **預設帳號**＝`modules.account.user`，沒寫用 `SUDO_USER`；兩個都沒有、查不到、或是 root（UID 0）＝設定錯。
- **名單**：`allow`（白名單）、`deny`（黑名單），字串陣列；一個字串是完整帳號名，或結尾一個 `*` 當前綴
  （`agent-*`；單獨 `*` 比所有帳號），`*` 在別處＝設定錯。黑名單比到就不准 → 白名單比到才准 → 都沒比到不准；
  root 不管名單一律不准。預設帳號不受名單管，但 `deny` 比得到預設帳號＝設定錯（不論 `allow` 有沒有寫，
  使用者 2026-10-01 第十三批與 A7）。
- 每一項的帳號（`insts` 那一項的 `"account": {"user": …}`，沒寫＝預設帳號）要照名單是准的、`getpwnam`
  查得到（A6）；開起來時不合回 1，重讀時不合整份不套用（重讀照開起來時的名單，名單改了只警告）。
- 開起來（root）：cgroup 子樹整棵 chown 給預設帳號 → fork＋exec root 端 `bin/aos-daemon-root`、交 socketpair
  的一頭 → 主程式 `initgroups`／`setgid`／`setuid` 永久降成預設帳號（`HOME`、`USER`、`LOGNAME` 也換掉）。
- 預設帳號的項主程式自己開；別的帳號的項經 root 端開（`Account.run()`），一條執行緒收回應、照 id 分給等的那一項。
  控制模組的 `kill`／`restart`（第十九批）對這種項經 root 端送訊號（`Account.signal()`，root 端對那個子程序的
  程序群組送）；主程式降權了送不到別的帳號。
  root 端不見了（讀到 EOF）：stderr 一行、整個 daemon 回 1（A5）。

〔使用者方向 2026-10-01〕POC 默認一切正常。
"""
import json
import os
import pwd
import socket
import subprocess
import sys
import threading
import time

BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
ROOT = os.path.join(BIN, "aos-daemon-root")
MAX = 1 << 20               # 一個封包最大多少（請求裡帶整份環境）


class AccountError(ValueError):
    """帳號模組的設定錯：開起來時回 1，重讀時整份不套用。"""


def _patterns(conf, key):
    v = conf.get(key, [])
    if not isinstance(v, list) or not all(isinstance(p, str) and p for p in v):
        raise AccountError("modules.account.%s 要是非空字串的陣列" % key)
    for p in v:
        if "*" in p[:-1]:
            raise AccountError("modules.account.%s 的 %s：* 只能寫在結尾" % (key, json.dumps(p)))
    return v


def match(pattern, name):
    """完整名，或結尾 `*` 當前綴。"""
    return name.startswith(pattern[:-1]) if pattern.endswith("*") else name == pattern


class Policy:
    """預設帳號與名單。`conf`＝展開後的 `modules.account`；`env` 拿 `SUDO_USER`。"""

    def __init__(self, conf, env=None):
        env = os.environ if env is None else env
        if not isinstance(conf, dict):
            raise AccountError("modules.account 要是物件")
        user = conf.get("user")
        if user is not None and not isinstance(user, str):
            raise AccountError("modules.account.user 要是字串")
        self.default = user or env.get("SUDO_USER") or None
        if not self.default:
            raise AccountError("沒有預設帳號：modules.account.user 沒寫，也沒有 SUDO_USER")
        self.allow = _patterns(conf, "allow")
        self.deny = _patterns(conf, "deny")
        pw = lookup(self.default)
        if pw.pw_uid == 0:
            raise AccountError("預設帳號 %s 是 root" % self.default)
        if any(match(p, self.default) for p in self.deny):
            raise AccountError("deny 比得到預設帳號 %s" % self.default)

    def allowed(self, name):
        """名單准不准（預設帳號不受名單管；root 一律不准）。帳號查不到丟 AccountError。"""
        if lookup(name).pw_uid == 0:
            return False
        if name == self.default:
            return True
        if any(match(p, name) for p in self.deny):
            return False
        return any(match(p, name) for p in self.allow)

    def check_items(self, items):
        """每一項的帳號都要查得到、名單准（A6）；不合丟 AccountError。"""
        for item in items:
            name = item.user or self.default
            if not self.allowed(name):
                raise AccountError("insts 的 %s：帳號 %s 名單不准" % (json.dumps(item.inst, ensure_ascii=False), name))

    def wire(self):
        return {"default": self.default, "allow": self.allow, "deny": self.deny}


def lookup(name):
    try:
        return pwd.getpwnam(name)
    except KeyError:
        raise AccountError("no such user %s" % name)


def item_user(entry):
    """`insts` 那一項的 `account.user`；沒寫回 None（＝預設帳號）。模組沒掛時沒人看。"""
    acc = entry.get("account")
    if acc is None:
        return None
    if not isinstance(acc, dict) or not isinstance(acc.get("user", ""), str):
        raise AccountError("insts 的 account 要是物件、user 要是字串")
    return acc.get("user") or None


def chown_tree(path, uid, gid):
    """cgroup 子樹整棵（資料夾與裡面的檔）交給預設帳號（跟 systemd 委派給一般帳號一樣）。"""
    for top, dirs, files in os.walk(path):
        os.chown(top, uid, gid)
        for f in files:
            os.chown(os.path.join(top, f), uid, gid)


class Account:
    """開起來時（還是 root）建：開 root 端；`drop()` 之後主程式就是預設帳號。"""

    def __init__(self, policy):
        self.policy = policy
        self.pw = lookup(policy.default)
        here, there = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        # 另一個 session：終端機的 Ctrl-C 不會打到 root 端；它只看 socketpair 關了沒
        self.proc = subprocess.Popen([sys.executable, ROOT, str(there.fileno())], pass_fds=[there.fileno()],
                                     stdin=subprocess.DEVNULL, start_new_session=True)
        there.close()
        self.sock = here
        here.send(json.dumps(policy.wire(), ensure_ascii=False).encode("utf-8"))
        self._send = threading.Lock()
        self._wait = {}                 # id → [threading.Event, 回應]
        self._ids = 0

    def drop(self):
        """永久降成預設帳號；之後才起執行緒（收回應的這條也是）。"""
        pw = self.pw
        os.initgroups(pw.pw_name, pw.pw_gid)
        os.setgid(pw.pw_gid)
        os.setuid(pw.pw_uid)
        os.environ.update(HOME=pw.pw_dir, USER=pw.pw_name, LOGNAME=pw.pw_name)
        threading.Thread(target=self._replies, daemon=True).start()

    def via_root(self, item):
        return item.user is not None and item.user != self.policy.default

    def _replies(self):
        while True:
            data = self.sock.recv(MAX)
            if not data:
                sys.stderr.write("aos-daemon: account: root 端不見了\n")
                sys.stderr.flush()
                import aos_daemon
                aos_daemon._die(1)
            rep = json.loads(data.decode("utf-8"))
            slot = self._wait.pop(rep["id"])
            slot[1] = rep
            slot[0].set()

    def run(self, item, start, argv, out_fd, err_fd, frame):
        """請 root 端用 item.user 開 argv，等它結束。回 (碼, 錯誤說明或 None)。out_fd／err_fd 交出去後由呼叫的人關。
        等的時候 `item.root_rid` 是這次請求的 id（第十九批 kill 用）。"""
        slot = [threading.Event(), None]
        with self._send:
            self._ids += 1
            rid = self._ids
            self._wait[rid] = slot
            req = {"id": rid, "user": item.user, "argv": argv, "cwd": start,
                   "env": dict(item.env if item.env is not None else os.environ), "frame": frame}
            socket.send_fds(self.sock, [json.dumps(req, ensure_ascii=False).encode("utf-8")], [out_fd, err_fd])
            item.root_rid = rid
        slot[0].wait()
        item.root_rid = None
        rep = slot[1]
        if "error" in rep:
            return 1, rep["error"]
        return rep["exit"], None

    def signal(self, rid, final):
        """第十九批：請 root 端對請求 rid 開的那個子程序送 SIGTERM（final=False）或 SIGKILL（final=True），
        對象照 `aos_daemon.kill_targets()` 的規則；不等回應（已經結束就沒事）。"""
        with self._send:
            self.sock.send(json.dumps({"signal": rid, "final": bool(final)}).encode("utf-8"))


def run_via_root(acct, item, start, argv):
    """`aos_daemon.run_once()` 的帳號分支：開好 pipe 交給 root 端，回 (碼, 毫秒, 有沒有收屍, out, err)。"""
    import aos_daemon
    t0 = time.monotonic()
    ends, readers, got = [], [], {}
    for name, path in (("out", item.out_path), ("err", item.err_path)):
        if path is None:
            fd = os.open(os.devnull, os.O_WRONLY)
            ends.append(fd)
            got[name] = (b"", 0)
        else:
            r, w = os.pipe()
            ends.append(w)
            # 第十九批：邊讀邊丟最早的，最多留 item.out_max
            t = threading.Thread(target=aos_daemon.drain, args=(r, item.out_max, got, name), daemon=True)
            t.start()
            readers.append(t)
    try:
        code, error = acct.run(item, start, argv, ends[0], ends[1], item.frame)
    finally:
        for fd in ends:
            os.close(fd)
    ms = int((time.monotonic() - t0) * 1000)
    if error is not None:
        sys.stderr.write("aos-daemon: account: %s\n" % error)
        sys.stderr.flush()
    reaped = False
    if item.frame is not None:
        import aos_daemon_cgroup
        reaped = aos_daemon_cgroup.clear(item.frame)
    for t in readers:
        t.join()
    return code, ms, reaped, got["out"], got["err"]
