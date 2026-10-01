"""aos-tick：跑一格（B-626 核心：照表跑、每項結束碼紀錄）。

一格的順序（B-620「一格怎麼走」，POC 版）：

    認資料夾（要有 .aos/inst.json）→ 看擋板檔 → 換紀錄 → 讀表 → 刪停格檔
    → 照表跑（每項後寫紀錄、查停格檔）→ 回結束碼

`run_tick()` 就是照這個順序寫的，從它讀起。紀錄在 aos_tick_record.py、任務表在
aos_tick_table.py、跑單項在 aos_tick_run.py。

結束碼照 aos 體系慣例（使用者 2026-10-01，notes/verdicts/11-tick-as-unit.md 篇末，待統一更新 spec）：
0＝正常結束、1＝錯誤結束、2＝正常中斷。aos-tick 的碼只講 tick 自己，任務怎麼結束只記進紀錄、不影響它。

- 0：照表跑完（不管任務成敗、回幾）；看到停格檔、剩下不跑也是 0。
- 2：有擋板檔不開格（不寫紀錄、不加 seq）。
- 1：tick 自己出錯——argv 用法錯、--node 不對、沒有 .aos/inst.json；tick 自用的檔讀不到／寫不進／
  格式壞就讓 Python 自然丟錯（traceback 進 stderr、回 1），不分發生時機、不補救。

擋板檔與停格檔的機制使用者之後會詳細設計，目前做法是暫定。

stderr 只印 tick 自己的 `代碼: 說明` 行（或 traceback），任務的輸出照 inst 走。

〔使用者方向 2026-10-01〕POC 默認一切正常：檔案寫得進、讀得懂、不斷電、沒有別人在跑、
任務表是對的、帳號是對的。所以不取鎖（不回 75）、不驗表、不看 `user`（不回 125）、
不做 `--firstdo-fsync`、不判上下層（B-628）。
"""
import os
import sys

import aos_tick_run
import aos_tick_table
from aos_tick_record import Record

__all__ = ["main", "run_tick", "node_dir_from_arg"]

USAGE = "用法：aos-tick [--node <node>]"
EXIT_OK, EXIT_ERROR, EXIT_INTERRUPTED = 0, 1, 2   # aos 結束碼慣例
EXIT_USAGE = EXIT_ERROR          # 慣例：argv 用法錯也算錯誤結束

INST = os.path.join(".aos", "inst.json")
BLOCKED = os.path.join(".aos", "tick-blocked")
STOP = os.path.join(".aos", "tick", "stop")


def say(code, msg):
    """P-203：tick 自己的 stderr 診斷行，一律 `代碼: 說明`。"""
    sys.stderr.write("%s: %s\n" % (code, msg))
    sys.stderr.flush()


def main(argv=None):
    """P-203 argv：`aos-tick [--node <node>]`；用法錯回 1（aos 結束碼慣例）。
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
    if not os.path.isfile(os.path.join(node, INST)):
        # 使用者 2026-10-01：--node 指的資料夾必須有 .aos/inst.json；沒有就回 1（不再交給 aos-exec）
        say("no_inst", "%s 底下沒有 %s" % (node, INST))
        return EXIT_ERROR
    os.chdir(node)

    reason = read_reason(BLOCKED)
    if reason is not None:
        say("blocked", reason or "（擋板檔沒寫原因）")
        return EXIT_INTERRUPTED

    record = Record(node)
    record.open()
    items, ids = aos_tick_table.read_table(node)

    remove_stop_file()
    stopped_after = None
    for index, (item, task_id) in enumerate(zip(items, ids)):
        kind, value = run_one(node, item, task_id, index, record)
        record.add_task(task_id, kind, value)       # 任務怎麼結束只記下，不影響 tick 的結束碼
        reason = read_reason(STOP)
        if reason is not None:
            # 停格檔不算中斷，回 0（暫定，擋板檔與停格檔的機制使用者之後會詳細設計）
            say("stopped", reason or "（停格檔沒寫原因，停在 %s 之後）" % task_id)
            stopped_after = task_id
            break

    record.finish(EXIT_OK, stopped_after)
    return EXIT_OK


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
