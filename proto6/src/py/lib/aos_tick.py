"""aos-tick：跑一格（B-626 核心四件事：互斥鎖、照表跑、上下層判定、每項結束碼紀錄）。

一格的順序（B-620「一格怎麼走」）：

    認資料夾 → 取鎖 → 看擋板檔 → 換紀錄 → 讀表驗表 → 刪停格檔 → 照表跑（每項後寫紀錄、查停格檔）→ 回結束碼

`run_tick()` 就是照這個順序寫的，從它讀起。紀錄在 aos_tick_record.py、任務表在
aos_tick_table.py、跑單項在 aos_tick_run.py。

結束碼（P-203）：0 全部成功、1 有失敗／被停格檔停下／被擋板檔擋住、2 argv 或任務表不合法、75 鎖被占。
stderr 只印 tick 自己的 `代碼: 說明` 行，任務的輸出照 inst 走。
"""
import fcntl
import os
import sys

import aos_exec
import aos_inst
import aos_tick_run
import aos_tick_table
from aos_tick_record import Record

__all__ = ["main", "run_tick", "node_dir_from_arg", "default_parent"]

USAGE = "用法：aos-tick [--node <node>] [--firstdo-fsync]"
EXIT_OK, EXIT_FAILED, EXIT_INVALID, EXIT_LOCKED = 0, 1, 2, 75

LOCK = os.path.join(".aos", "tick.lock")
BLOCKED = os.path.join(".aos", "tick-blocked")
STOP = os.path.join(".aos", "tick", "stop")


def say(code, msg):
    """P-203：tick 自己的 stderr 診斷行，一律 `代碼: 說明`。"""
    sys.stderr.write("%s: %s\n" % (code, msg))
    sys.stderr.flush()


def main(argv=None):
    """P-203 argv：`aos-tick [--node <node>] [--firstdo-fsync]`；用法錯回 2。"""
    args = sys.argv[1:] if argv is None else list(argv)
    node_arg, fsync = None, os.environ.get("AOS_TICK_FIRSTDO_FSYNC") == "1"
    while args:
        a = args.pop(0)
        if a == "--firstdo-fsync":
            fsync = True
        elif a == "--node" and args:
            node_arg = args.pop(0)
        elif a.startswith("--node="):
            node_arg = a[len("--node="):]
        elif a in ("-h", "--help"):
            print(USAGE)
            return EXIT_OK
        else:
            say("usage", "看不懂的參數 %r；%s" % (a, USAGE))
            return EXIT_INVALID
    node = node_dir_from_arg(node_arg)
    if node is None:
        return EXIT_INVALID
    return run_tick(node, fsync)


def node_dir_from_arg(arg):
    """B-602「認哪個資料夾」、P-203：`--node` 可以是資料夾、`.aos/inst.json` 或 `inst.json`，
    一律正規化成 node 資料夾；省略用目前目錄。指定時要是絕對路徑，不往上層找。認不出回 None。"""
    if arg is None:
        return os.getcwd()
    if not os.path.isabs(arg):
        say("usage", "--node 要是絕對路徑（node id）：%r" % arg)
        return None
    path = os.path.normpath(arg)
    if not os.path.isdir(path) and os.path.basename(path) == "inst.json":
        path = os.path.dirname(path)
        if os.path.basename(path) == ".aos":
            path = os.path.dirname(path)
    if not os.path.isdir(path):
        say("usage", "--node 不是資料夾，也不是資料夾裡的 .aos/inst.json 或 inst.json：%s" % arg)
        return None
    return path


def run_tick(node, fsync=False):
    """B-620「一格怎麼走」：整格照這個順序，回整格結束碼。"""
    if not os.path.isdir(os.path.join(node, ".aos")):
        return run_bare_inst(node)
    os.chdir(node)

    lock_fd = take_lock()
    if lock_fd is None:
        return EXIT_LOCKED

    reason = read_reason(BLOCKED)
    if reason is not None:
        say("blocked", reason or "（擋板檔沒寫原因）")
        return EXIT_FAILED

    record = Record(node, say, fsync=fsync)
    record.open()

    try:
        items, ids = aos_tick_table.read_table(node)
    except aos_tick_table.TableError as e:
        say("config_invalid", str(e))
        record.finish(EXIT_INVALID)
        return EXIT_INVALID

    remove_stop_file()
    failed, stopped_after = False, None
    for index, (item, task_id) in enumerate(zip(items, ids)):
        kind, value = run_one(node, item, task_id, index, lock_fd, record)
        record.add_task(task_id, kind, value)
        if (kind, value) != ("exit", 0):
            failed = True
        reason = read_reason(STOP)
        if reason is not None:
            say("stopped", reason or "（停格檔沒寫原因，停在 %s 之後）" % task_id)
            stopped_after = task_id
            break

    code = EXIT_FAILED if failed or stopped_after is not None else EXIT_OK
    record.finish(code, stopped_after)
    return code


def run_bare_inst(node):
    """plan 待問 5／6〔使用者方向 2026-09-30 晚〕：沒有 .aos/ 照 aos-exec 找檔。有 inst.json 就像
    aos-exec 把它跑一次（不取鎖、不寫紀錄，退出碼照 aos-exec）；兩個都沒有回 2、不自建 .aos/。"""
    if not os.path.isfile(os.path.join(node, "inst.json")):
        say("config_invalid", "%s 沒有 .aos/ 也沒有 inst.json（不自建）" % node)
        return EXIT_INVALID
    code, kind = aos_exec.run_target(node)
    return aos_exec.EXIT_AOS if kind == aos_exec.AOS else code


def take_lock():
    """B-602「取鎖」：對 `.aos/tick.lock` 取非阻塞獨占 flock，不存在就建立；拿不到回 None（回 75）。

    鎖 fd 預設不會傳給子程序，跑任務時用 pass_fds 明講（aos_tick_run）。
    """
    try:
        fd = os.open(LOCK, os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as e:
        say("lock_unavailable", "開不了鎖檔 %s：%s" % (LOCK, e))
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)                               # 鎖被占：什麼都不做、不印
        return None
    except OSError as e:
        os.close(fd)
        say("lock_unavailable", "取不到鎖 %s：%s" % (LOCK, e))
        return None
    return fd


def read_reason(path):
    """B-620、P-213 停格檔與擋板檔：檔在回第一行原因（可能是空字串），不在回 None。"""
    if not os.path.lexists(path):
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.readline().strip()
    except OSError:
        return ""


def remove_stop_file():
    """B-620：取鎖後、開第一項前刪掉上一格留下的停格檔。"""
    try:
        os.unlink(STOP)
    except FileNotFoundError:
        pass
    except OSError as e:
        say("stop_unremovable", "刪不掉上一格留下的停格檔 %s：%s" % (STOP, e))


def run_one(node, item, task_id, index, lock_fd, record):
    """B-620「跑每一項」「任務的帳號」：帳號不同回 125 不跑；否則重新展開再跑。回 (kind, value)。"""
    try:
        mismatch = aos_tick_table.check_user(item)
        if mismatch is not None:
            say("user_mismatch", "%s: %s" % (task_id, mismatch))
            return "exit", aos_tick_run.EXIT_NOT_RUN
        # 跑到時才重新展開（plan 待問 3），不重用開格驗過的結果
        inst = aos_tick_table.load_inst(item, node)
    except aos_inst.InstError as e:
        # 開格驗過、跑到時卻壞了：檔案在格中被改（待問 6 已裁定不特別設計），就當這一項沒跑成
        say("exec_failed", "%s: %s" % (task_id, e))
        return "exit", aos_tick_run.EXIT_NOT_RUN
    task_vars = {"AOS_NODE_DIR": node, "AOS_TICK_LOCK_FD": str(lock_fd),
                 "AOS_TASK_ID": task_id, "AOS_TASK_INDEX": str(index)}
    if record.path_for_task() is not None:
        task_vars["AOS_TICK_RECORD"] = record.path_for_task()
    kind, value, note = aos_tick_run.run_item(inst, task_vars, lock_fd)
    if note:
        say("exec_failed", "%s: %s" % (task_id, note))
    return kind, value


def default_parent(node_dir):
    """B-628 預設上層：從本資料夾往上找，最近一個有 `.aos/inst.json` 或 `inst.json` 的資料夾；
    找不到回 None。純路徑計算、逐段往上比、不展開 symlink、不看 daemon。只是函式，不另加輸出。"""
    here = os.path.normpath(node_dir)
    while True:
        up = os.path.dirname(here)
        if up == here:
            return None
        if any(os.path.isfile(os.path.join(up, rel)) for rel in (os.path.join(".aos", "inst.json"), "inst.json")):
            return up
        here = up
