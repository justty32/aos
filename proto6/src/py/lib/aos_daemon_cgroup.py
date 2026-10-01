"""aos-daemon 的收屍／cgroup 模組（plan m3m-daemon-modules.md 模組二）。

設定檔寫 `"modules": {"cgroup": {}}` 時掛上（使用者 2026-10-01 第十二批：C1～C4 照 plan 建議）：

- **子樹根＝daemon 自己所在的 cgroup**（`/proc/self/cgroup` 的 `0::` 那行），要求是委派給自己的
  cgroup v2 子樹，例如 `systemd-run --user --scope -p Delegate=yes aos-daemon --config F`。
  自己已經在 `<根>/daemon` 裡（同一個 scope 裡重開的 daemon）就拿上一層當根。
- 開起來先建 `<根>/daemon`，把根上所有程序搬進去（cgroup v2「no internal processes」：開了 controller
  的那層不能放程序），再在根的 `cgroup.subtree_control` 開 `cpu`、`memory`、`pids` 裡根上有的那幾個。
- **每一項一個葉框** `<根>/i-<h>`（`<h>`＝inst 字面值 UTF-8 的 sha256 前 16 個 hex，C4）；開框時 stdout 印一次
  `inst=<inst> cgroup=i-<h>`。框已經在（同一棵子樹裡上次留下的）：開起來時有程序就先 `cgroup.kill` 清空。
- **上限**（C2）：那一項設定的 `"cgroup": {"memory.max": "512M", ...}`，鍵＝cgroup 檔名、值＝字串，原樣寫進框；
  不認得也不檢查。
- 每次開 `aos-exec`：子程序先把自己寫進那一項框的 `cgroup.procs` 再 exec（`sh -c` 墊一層，不用 preexec_fn：
  daemon 有很多執行緒）。`aos-exec` 結束後框裡還有程序就寫 `cgroup.kill`（C3：直接 SIGKILL，不先 SIGTERM），
  等 `cgroup.events` 的 `populated 0` 才算這次結束；有清到東西時 stdout 另印 `inst=<inst> reaped`。
- 重讀設定拿掉的項：最後一次跑完、清完之後刪框（那個 inst 已經又被加回來就不刪）。

〔使用者方向 2026-10-01〕POC 默認一切正常；沒有委派好的 cgroup v2（例如直接在 WSL 的 /init.scope 開）就讓程式
自然丟錯、回 1（C1），不退回別的做法。
"""
import hashlib
import os
import time

CGROUP_FS = "/sys/fs/cgroup"
CONTROLLERS = ("cpu", "memory", "pids")
DAEMON_LEAF = "daemon"
POLL = 0.01                 # 等框清空時多久看一次 cgroup.events


def frame_name(inst):
    """C4：`i-` 加 inst 字面值 UTF-8 的 sha256 前 16 個小寫 hex。"""
    return "i-" + hashlib.sha256(inst.encode("utf-8")).hexdigest()[:16]


def own_cgroup():
    """自己所在的 cgroup 絕對路徑（`/proc/self/cgroup` 的 `0::` 行；純 cgroup v2）。沒有那行自然丟錯。"""
    with open("/proc/self/cgroup") as f:
        rel = [l[3:].rstrip("\n") for l in f if l.startswith("0::")][0]
    return CGROUP_FS + rel


def _read(path):
    with open(path) as f:
        return f.read()


def _write(path, text):
    with open(path, "w") as f:
        f.write(text)


def populated(frame):
    for line in _read(os.path.join(frame, "cgroup.events")).splitlines():
        k, v = line.split()
        if k == "populated":
            return v == "1"
    raise RuntimeError("cgroup.events 沒有 populated：%s" % frame)


def clear(frame):
    """框裡有程序就 `cgroup.kill`、等到 populated 0。回有沒有清到東西。"""
    if not populated(frame):
        return False
    _write(os.path.join(frame, "cgroup.kill"), "1")
    while populated(frame):
        time.sleep(POLL)
    return True


class Tree:
    """daemon 的子樹。建的時候就把 daemon 搬進 `daemon/`、開好 controller。"""

    def __init__(self):
        here = own_cgroup()
        self.root = os.path.dirname(here) if os.path.basename(here) == DAEMON_LEAF else here
        leaf = os.path.join(self.root, DAEMON_LEAF)
        os.makedirs(leaf, exist_ok=True)
        # 根上所有程序搬進 daemon/（一般就 daemon 自己；systemd-run 墊的 sh 之類也一起）
        while True:
            pids = _read(os.path.join(self.root, "cgroup.procs")).split()
            if not pids:
                break
            for pid in pids:
                try:
                    _write(os.path.join(leaf, "cgroup.procs"), pid)
                except ProcessLookupError:       # 讀到之後才結束的
                    pass
        have = _read(os.path.join(self.root, "cgroup.controllers")).split()
        want = " ".join("+" + c for c in CONTROLLERS if c in have)
        if want:
            _write(os.path.join(self.root, "cgroup.subtree_control"), want)

    def frame(self, inst):
        return os.path.join(self.root, frame_name(inst))

    def make(self, item, startup):
        """建（或接手）這一項的框、寫上限，記在 `item.frame`。startup＝daemon 開起來時：框裡有舊程序先清。
        不印對照行（呼叫的人在適當的時機叫 `announce()`）。"""
        frame = self.frame(item.inst)
        try:
            os.mkdir(frame)
        except FileExistsError:
            if startup:
                clear(frame)
        self.limits(frame, item.cgroup)
        item.frame = frame

    @staticmethod
    def limits(frame, limits):
        """C2：鍵＝cgroup 檔名、值＝字串，原樣寫進框（不認得也不檢查；檔不在或值不對自然丟錯）。"""
        for name, value in limits.items():
            _write(os.path.join(frame, name), value)

    @staticmethod
    def announce(item, say):
        say("inst=%s cgroup=%s" % (item.inst, os.path.basename(item.frame)))

    @staticmethod
    def argv(frame, argv):
        """子程序先把自己（`$$`）寫進框的 `cgroup.procs`，再 exec 原本的 argv（pid 不變、碼原樣）。"""
        return ["/bin/sh", "-c", 'echo $$ > "$0/cgroup.procs" && exec "$@"', frame] + list(argv)

    @staticmethod
    def remove(frame):
        """刪框（拿掉的項最後一次跑完之後）：還有程序先清。"""
        clear(frame)
        os.rmdir(frame)
