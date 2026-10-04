"""寫入紀錄（spec.md 第 5 節「只碰給的資料夾」）：環境有 AOS7_AUDIT 且在任務裡時，Python 啟動就裝一個 audit hook，
把每個「寫」的動作記到 `$AOS7_TASK/writes.jsonl`：{"op", "path"（實際位置）, "ok", "pid", "via"（經過連結時寫的路徑）}。

- 只記空間根（AOS7_ROOT）底下的寫入；空間外（/dev/null、__pycache__ 等）不管。
- ok＝寫入的實際位置落在自己的 node（不含裡面巢狀的別的 node／daemon 根）或某個掛載點的目標底下。
- 只看得到 Python 程序（含 Python 起的 Python）；sh、C 程式的寫入看不到（problems.md M-3）。
- 只記不擋。aos7-run 只在 AOS7_AUDIT 有值時把這個資料夾放進任務的 PYTHONPATH（aos7-run 自己不載入）。

對應 spec §4.5、§5.1、§5.5（S-10、S-23）；本版沿用、尚無專門測試（P2-17）。
由 aos7-run 啟用後讓 Python 自動載入；讀 birth.json 與路徑邊界標記，追加 writes.jsonl，換 run 由 tick 清掉。
"""
import fcntl
import json
import os
import sys


def _install():
    """無參數；依 AOS7_* 環境安裝寫入觀察 hook，回傳 None。缺啟用旗標或任務位置就不安裝（spec §4.5，P2-17）。"""
    e = os.environ
    task, node, root = e.get("AOS7_TASK"), e.get("AOS7_NODE"), e.get("AOS7_ROOT")
    if not (e.get("AOS7_AUDIT") and task and node and root):
        return
    rp = os.path.realpath
    root_r, node_r = rp(root), rp(node)

    def load_targets():
        """birth.json 的掛載點目標；執行中加掛（M-6）後 tick 會改 birth.json，所以判不過時重讀一次。

        目標取宣告的空間路徑 `to`（接空間根再 realpath），不看掛載點連結現在指去哪：任務自己改指連結不算數（astra-2 二-4）。

        無參數；讀閉包中的 task／root_r，回傳獲准目標清單；出生紀錄不可讀或不可解時採空表（spec §4.5）。
        """
        try:
            with open(os.path.join(task, "birth.json"), encoding="utf-8") as f:
                birth = json.load(f)
            mounts = birth.get("mounts") or {}
        except (OSError, ValueError, AttributeError):
            birth, mounts = {}, {}
        out = [rp(os.path.join(root_r, v["to"])) for v in mounts.values()
               if isinstance(v, dict) and "at" in v and isinstance(v.get("to"), str)]
        if isinstance(birth.get("subroot"), str):
            # 路一的子根整棵算這個任務的（子 daemon 與它的 tick／tock 繼承了這個任務的環境；probes/llmteam）
            out.append(rp(os.path.join(root_r, birth["subroot"])))
        return out
    targets = load_targets()
    log = os.path.join(task, "writes.jsonl")
    busy = []
    wflags = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC

    def under(p, base):
        """以完整路徑段比對 p 是否在 base 內，回傳 bool；純字串判定，不查檔案（spec §5.5）。"""
        return p == base or p.startswith(base + os.sep)

    def registered():
        """空間根 `.aosd/nodes.json` 登記的 node 實際路徑 set（spec §1：node＝登記的資料夾，W12 起不再靠 timeline.json 認）。
        讀不到回空 set（只影響紀錄的 ok）。"""
        try:
            with open(os.path.join(root_r, ".aosd", "nodes.json"), encoding="utf-8") as f:
                nodes = json.load(f).get("nodes") or {}
            return {root_r if k == "." else os.path.join(root_r, k) for k in nodes if isinstance(k, str)}
        except (OSError, ValueError, AttributeError):
            return set()
    others = registered() - {node_r}

    def nested(real):
        """real 與 node 之間有沒有別的已登記 node 或 daemon 根（.aosd/）。

        參數 real 是寫入的實際路徑，回傳是否碰到巢狀邊界（spec §5.5）。註解疑點 sitecustomize:63：
        以前靠 `.aos/timeline.json` 認 node，登記制（§1、W12）之後改看 nodes.json。只影響紀錄的 ok，不阻止寫入（P2-17）。
        """
        d = os.path.dirname(real)
        while d != node_r and under(d, node_r):
            if d in others or os.path.isdir(os.path.join(d, ".aosd")):
                return True
            d = os.path.dirname(d)
        return False

    def base_of(dir_fd):
        """相對路徑的起點：有 dir_fd 就是那個 fd 指的資料夾（/proc/self/fd），不然是 cwd（astra-2 二-4）。

        參數 dir_fd 是可省略的目錄描述符；回傳目錄路徑，fd 讀不到時退回 cwd（spec §4.5，P2-17）。
        """
        if isinstance(dir_fd, int) and dir_fd >= 0:
            try:
                return os.readlink("/proc/self/fd/%d" % dir_fd)
            except OSError:
                pass
        return os.getcwd()

    def record(op, path, dir_fd=None):
        """記錄 op 對 path 的寫入，dir_fd 可指定相對路徑基準；回傳 None（spec §4.5、§5.5）。
        非文字路徑、空間外與紀錄檔本身略過；讀寫例外交給 hook 忽略，以維持「只記不擋」。"""
        if not isinstance(path, (str, bytes)):
            return
        real = rp(os.path.join(base_of(dir_fd), os.fsdecode(path)))
        if not under(real, root_r) or real == rp(log):
            return
        ok = any(under(real, t) for t in targets) or (under(real, node_r) and not nested(real))
        if not ok:
            # spec §4.5：加掛由下一個 tick 更新 birth，快取未命中時重讀，避免把新授予的目標誤報。
            targets[:] = load_targets()
            ok = any(under(real, t) for t in targets)
        rec = {"op": op, "path": real, "ok": ok, "pid": os.getpid()}
        given = os.path.normpath(os.path.join(base_of(dir_fd), os.fsdecode(path)))
        if given != real:
            rec["via"] = given   # 經過掛載點（或別的連結）寫的：寫的時候用的路徑
        line = (json.dumps(rec, ensure_ascii=False) + "\n").encode()
        # 同共用的 append_jsonl：檔尾是沒寫完的半行（上次寫到一半被殺）就先補換行，新紀錄不跟半行黏成壞行（astra-7 H-03）。
        # 多個 Python 後代同時寫：看檔尾＋寫入期間對 log 拿 flock，一次 os.write 寫完。這裡的 open／flock 也會觸發
        # audit 事件，但 hook 的 busy 旗標擋住遞迴
        fd = os.open(log, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
            except OSError:
                pass
            end = os.fstat(fd).st_size
            if end and os.pread(fd, 1, end - 1) != b"\n":
                line = b"\n" + line
            os.write(fd, line)
        finally:
            os.close(fd)

    def hook(event, args):
        """接收 Python 的 event 與 args；挑寫入事件交 record，回傳 None（spec §4.5，P2-17）。
        紀錄失敗一律略過；busy 阻止記錄自身觸發遞迴，避免觀察工具中斷任務。"""
        if busy:
            return
        try:
            busy.append(1)
            if event == "open":
                path, mode, flags = (tuple(args) + (None, None))[:3]
                w = (isinstance(flags, int) and flags & wflags) or (isinstance(mode, str) and any(c in mode for c in "wax+"))
                if w:
                    record("open", path)
            elif event in ("os.rename", "os.replace"):   # (src, dst, src_dir_fd, dst_dir_fd)
                record(event, args[0], args[2] if len(args) > 2 else None)
                record(event, args[1], args[3] if len(args) > 3 else None)
            elif event in ("os.remove", "os.rmdir"):     # (path, dir_fd)
                record(event, args[0], args[1] if len(args) > 1 else None)
            elif event == "os.mkdir":                    # (path, mode, dir_fd)
                record(event, args[0], args[2] if len(args) > 2 else None)
            elif event in ("os.truncate", "shutil.rmtree"):
                record(event, args[0])
            elif event == "os.symlink":                  # (src, dst, dir_fd)
                record(event, args[1], args[2] if len(args) > 2 else None)
            elif event == "os.link":                     # (src, dst, src_dir_fd, dst_dir_fd)
                record(event, args[1], args[3] if len(args) > 3 else None)
        except Exception:
            # spec §4.5、§11：這是觀察紀錄，不是攔截器；紀錄失敗不能改變被觀察任務的行為（P2-17）。
            pass
        finally:
            busy.clear()

    sys.addaudithook(hook)


_install()
