"""aos-tick：跑一格（B-626 核心：照表跑、每項結束碼紀錄）。

一格的順序（B-620「一格怎麼走」，POC 版）：

    認資料夾 → 看擋板檔 → 換紀錄 → 讀表 → 刪停格檔 → 照表跑（每項後寫紀錄、查停格檔）→ 回結束碼

`run_tick()` 就是照這個順序寫的，從它讀起。紀錄在 aos_tick_record.py、任務表在
aos_tick_table.py、跑單項在 aos_tick_run.py。

結束碼：0 全部成功、1 有任務失敗／被停格檔停下／被擋板檔擋住／tick 自己出錯（traceback）；
argv 用法錯回 2。stderr 只印 tick 自己的 `代碼: 說明` 行，任務的輸出照 inst 走。

〔使用者方向 2026-10-01〕POC 默認一切正常：檔案寫得進、讀得懂、不斷電、沒有別人在跑、
任務表是對的、帳號是對的。所以不取鎖（不回 75）、不驗表（不回 2）、不看 `user`（不回 125）、
不做 `--firstdo-fsync`、不判上下層（B-628）。出事就讓 Python 自然丟錯（traceback、回 1）。
"""
import os
import sys

import aos_exec
import aos_tick_run
import aos_tick_table
from aos_tick_record import Record

__all__ = ["main", "run_tick", "node_dir_from_arg"]

USAGE = "用法：aos-tick [--node <node>]"
EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2

BLOCKED = os.path.join(".aos", "tick-blocked")
STOP = os.path.join(".aos", "tick", "stop")


def say(code, msg):
    """P-203：tick 自己的 stderr 診斷行，一律 `代碼: 說明`。"""
    sys.stderr.write("%s: %s\n" % (code, msg))
    sys.stderr.flush()


def main(argv=None):
    """P-203 argv：`aos-tick [--node <node>]`；用法錯回 2。
    `--firstdo-fsync` POC 先不做（使用者方向 2026-10-01），給了算用法錯。"""
    args = sys.argv[1:] if argv is None else list(argv)
    node_arg = None
    while args:
        a = args.pop(0)
        if a == "--node" and args:
            node_arg = args.pop(0)
        elif a.startswith("--node="):
            node_arg = a[len("--node="):]
        elif a in ("-h", "--help"):
            print(USAGE)
            return EXIT_OK
        else:
            say("usage", "看不懂的參數 %r；%s" % (a, USAGE))
            return EXIT_USAGE
    node = node_dir_from_arg(node_arg)
    if node is None:
        return EXIT_USAGE
    return run_tick(node)


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


def run_tick(node):
    """B-620「一格怎麼走」：整格照這個順序，回整格結束碼。"""
    if not os.path.isdir(os.path.join(node, ".aos")):
        # plan 待問 5／6：沒有 .aos/ 就整個交給 aos-exec 跑這個資料夾（不寫紀錄，退出碼照 aos-exec；
        # 連 inst.json 也沒有時是 aos-exec 的用法錯 2）
        code, kind = aos_exec.run_target(node)
        return aos_exec.EXIT_AOS if kind == aos_exec.AOS else code
    os.chdir(node)

    reason = read_reason(BLOCKED)
    if reason is not None:
        say("blocked", reason or "（擋板檔沒寫原因）")
        return EXIT_FAILED

    record = Record(node)
    record.open()
    items, ids = aos_tick_table.read_table(node)

    remove_stop_file()
    failed, stopped_after = False, None
    for index, (item, task_id) in enumerate(zip(items, ids)):
        kind, value = run_one(node, item, task_id, index, record)
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


def read_reason(path):
    """B-620、P-213 停格檔與擋板檔：檔在回第一行原因（可能是空字串），不在回 None。"""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.readline().strip()


def remove_stop_file():
    """B-620：開第一項前刪掉上一格留下的停格檔。"""
    if os.path.exists(STOP):
        os.unlink(STOP)


def run_one(node, item, task_id, index, record):
    """B-620「跑每一項」：跑到時才展開這一項（plan 待問 3）再跑。回 (kind, value)。"""
    inst = aos_tick_table.load_inst(item, node)
    task_vars = {"AOS_NODE_DIR": node, "AOS_TICK_RECORD": record.current,
                 "AOS_TASK_ID": task_id, "AOS_TASK_INDEX": str(index)}
    kind, value, note = aos_tick_run.run_item(inst, task_vars)
    if note:
        say("exec_failed", "%s: %s" % (task_id, note))
    return kind, value
