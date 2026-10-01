"""aos-tick：跑一格（B-626 核心：照表跑、每項結束碼紀錄）。

一格的順序（B-620「一格怎麼走」，POC 版）：

    認 node 與任務表（--node 是資料夾要有 .aos/tasks.json；是檔就拿它當表）→ 看擋板檔 → 換紀錄 → 讀表 → 刪停格檔
    → 照表跑（每項後寫紀錄、查停格檔）→ 回結束碼

`run_tick()` 就是照這個順序寫的，從它讀起。紀錄在 aos_tick_record.py、任務表在
aos_tick_table.py、跑單項在 aos_tick_run.py。

結束碼照 aos 體系慣例（使用者 2026-10-01，notes/verdicts/11-tick-as-unit.md 篇末，待統一更新 spec）：
0＝正常結束、1＝錯誤結束、2＝正常中斷。aos-tick 的碼只講 tick 自己，任務怎麼結束只記進紀錄、不影響它。

- 0：照表跑完（不管任務成敗、回幾）；看到停格檔、剩下不跑也是 0。
- 2：有擋板檔不開格（不寫紀錄、不加 seq）。
- 1：tick 自己出錯——argv 用法錯、--node 指的東西不存在、資料夾底下沒有 .aos/tasks.json、
  任務表不合極簡檢查（aos_tick_table.check_table，stderr `bad_table:`）；tick 自用的檔讀不到／寫不進／
  格式壞就讓 Python 自然丟錯（traceback 進 stderr、回 1），不分發生時機、不補救。

擋板檔與停格檔的機制使用者之後會詳細設計，目前做法是暫定。

stderr 只印 tick 自己的 `代碼: 說明` 行（或 traceback），任務的輸出照 inst 走。

〔使用者方向 2026-10-01〕POC 默認一切正常：檔案寫得進、讀得懂、不斷電、沒有別人在跑、
帳號是對的。所以不取鎖（不回 75）、表只做極簡檢查、不看 `user`（不回 125）、
不做 `--firstdo-fsync`、不判上下層（B-628）。

〔使用者方向 2026-10-01，待統一更新 spec〕`--node` 怎麼認（notes/verdicts/11 篇末）：
省略用 `./`；相對路徑轉絕對；資料夾要有 `.aos/tasks.json`（跟 inst.json 無關）；
是檔就拿這個檔當這一格的任務表、它所在的資料夾當 node（檔在 `.aos/` 裡時 node 取 `.aos` 的上一層）。
"""
import os
import sys

import aos_tick_run
import aos_tick_table
from aos_tick_record import Record

__all__ = ["main", "run_tick", "resolve_node"]

USAGE = "用法：aos-tick [--node <node>]"
EXIT_OK, EXIT_ERROR, EXIT_INTERRUPTED = 0, 1, 2   # aos 結束碼慣例
EXIT_USAGE = EXIT_ERROR          # 慣例：argv 用法錯也算錯誤結束

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
    found = resolve_node(node_arg)
    if found is None:
        return EXIT_ERROR
    return run_tick(*found)


def resolve_node(arg):
    """〔使用者方向 2026-10-01，待統一更新 spec；取代 B-602「認哪個資料夾」、P-203 的 `--node`〕
    回 (node 資料夾, 這一格的任務表)，都是絕對路徑；不合法回 None。

    - 省略 `--node`：用 `./`。相對路徑一律轉成絕對（不往上層找）。
    - 資料夾：要有 `.aos/tasks.json`，表就是它；不看 `.aos/inst.json`。
    - 檔：這個檔就是這一格的表（跟資料夾模式同一套極簡檢查，見 aos_tick_table.check_table）；它所在的資料夾當 node，
      但那個資料夾若叫 `.aos`，node 取它的上一層（`--node yyy/.aos/tasks.json` 跟 `--node yyy` 一樣）。
    - 都不是（不存在）：回 None。
    """
    path = os.path.abspath(arg if arg is not None else ".")
    if os.path.isdir(path):
        table = os.path.join(path, aos_tick_table.TABLE)
        if not os.path.isfile(table):
            say("no_tasks", "%s 底下沒有 %s" % (path, aos_tick_table.TABLE))
            return None
        return path, table
    if os.path.isfile(path):
        node = os.path.dirname(path)
        if os.path.basename(node) == ".aos":
            node = os.path.dirname(node)
        return node, path
    say("no_node", "--node 指的東西不存在：%s" % arg)
    return None


def run_tick(node, table):
    """B-620「一格怎麼走」：整格照這個順序，回整格結束碼。node、table 由 resolve_node() 給（絕對路徑）。
    node 的 `.aos/`、`.aos/tick/` 不在時由 Record.open() 建（只建資料夾）。"""
    os.chdir(node)

    reason = read_reason(BLOCKED)
    if reason is not None:
        say("blocked", reason or "（擋板檔沒寫原因）")
        return EXIT_INTERRUPTED

    record = Record(node)
    record.open()
    try:
        items, ids = aos_tick_table.read_table(table, node)
    except aos_tick_table.TableInvalid as e:
        say("bad_table", str(e))          # 使用者 2026-10-01：表格式錯算 tick 自己的錯（紀錄停在 ended:false）
        return EXIT_ERROR

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
    # id 型別不查（極簡檢查），環境變數要字串就 str()
    task_vars = {"AOS_NODE_DIR": node, "AOS_TICK_RECORD": record.current,
                 "AOS_TASK_ID": str(task_id), "AOS_TASK_INDEX": str(index)}
    kind, value, note = aos_tick_run.run_item(inst, task_vars)
    if note:
        say("exec_failed", "%s: %s" % (task_id, note))
    return kind, value
