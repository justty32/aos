"""aos-tick：跑一格（B-626 核心：照表跑、每項結束碼紀錄）。

一格的順序（B-620「一格怎麼走」，POC 版）：

    認工作資料夾與任務表（目標是資料夾要有 .aos/tasks.json；是檔就拿它當表）→ 取鎖 → 看擋板檔 → 讀表
    → 換紀錄 → 刪停格檔 → 照表跑（每項後寫紀錄、查停格檔）→ 回結束碼

`run_tick()` 就是照這個順序寫的，從它讀起。紀錄在 aos_tick_record.py、任務表在
aos_tick_table.py、跑單項在 aos_tick_run.py。

結束碼照 aos 體系慣例（使用者 2026-10-01 再改，notes/verdicts/11-tick-as-unit.md 篇末，待統一更新 spec）：
0＝預料之中（含正常中斷）、非 0＝要額外處理、1＝通用錯誤。aos-tick 的碼只講 tick 自己，任務怎麼結束只記進紀錄、不影響它。

- 0：照表跑完（不管任務成敗、回幾）；看到停格檔、剩下不跑；同資料夾上一格還沒跑完（拿不到 `.aos/tick.lock`，
  stderr `busy:`）；有擋板檔（stderr `blocked:`）。後兩種不開格（不寫紀錄、不加 seq）。
- 1：tick 自己出錯——argv 用法錯、目標指的東西不存在、資料夾底下沒有 .aos/tasks.json、
  任務表不合極簡檢查（aos_tick_table.check_table，stderr `bad_table:`；在換紀錄之前，不算開過一格）；tick 自用的檔讀不到／寫不進／
  格式壞就讓 Python 自然丟錯（traceback 進 stderr、回 1），不分發生時機、不補救。

擋板檔與停格檔的機制使用者之後會詳細設計，目前做法是暫定。

stderr 只印 tick 自己的 `代碼: 說明` 行（或 traceback），任務的輸出照 inst 走。

〔使用者方向 2026-10-01〕POC 默認一切正常：檔案寫得進、讀得懂、不斷電、帳號是對的。
所以表只做極簡檢查、不看 `user`（不回 125）、不做 `--firstdo-fsync`、不判上下層（B-628）。
同資料夾互斥同日加回最簡版（外層定期跑，上一格沒跑完下一格就來是正常使用）：拿不到鎖回 0，
不回 75、鎖 fd 不傳給任務、沒有 `AOS_TICK_LOCK_FD`；任務逾時、tick 被殺時清孩子不做（留給 daemon 段）。

〔使用者方向 2026-10-01，待統一更新 spec〕目標怎麼認（notes/verdicts/11 篇末）：
省略用 `./`；相對路徑轉絕對；資料夾要有 `.aos/tasks.json`（跟 inst.json 無關）；
是檔就拿這個檔當這一格的任務表、它所在的資料夾當工作資料夾（檔在 `.aos/` 裡時取 `.aos` 的上一層）。

〔使用者方向 2026-10-01，待統一更新 spec〕狀態資料夾的名字照環境變數 `AOS_DIRNAME`（沒設＝`.aos`；
空字串＝不用子資料夾，狀態檔直接在工作資料夾下；含 `/`、是 `.`、`..` 算用法錯回 1）。本檔與 aos_tick_record／aos_tick_table 說的 `.aos` 都是這個名字。
環境變數照常傳給任務，不另處理。

〔使用者 2026-10-01，待統一更新 spec〕「工作資料夾」＝這一格 aos-tick 的 cwd（run_tick 會 chdir 過去），
給任務的 `AOS_TICK_CWD` 就是它的絕對路徑（原 `AOS_NODE_DIR` 改名）；`AOS_TICK_RECORD` 拿掉，
任務要看紀錄就從 `$AOS_TICK_CWD/<狀態資料夾>/tick/current.json` 找。node 是之後 aos-tick 的 node 模組的事，
tick 這層不談。同日再改：參數 `--node` 改名 `--target`（不留舊名，跟 aos-daemon、aos-exec 一樣叫「目標」；
aos-exec 的目標是位置參數，這裡照使用者原話用 `--target`），`resolve_node()` 改 `resolve_target()`、
stderr `no_node:` 改 `no_target:`。同日三改：`--target` 旗標拿掉（不留），目標改成位置參數 `aos-tick [<目標>]`，
跟 aos-exec 一樣；語意不變、`no_target:` 保留。
"""
import fcntl
import os
import sys

import aos_dirname
import aos_tick_run
import aos_tick_table
from aos_tick_record import Record

__all__ = ["main", "run_tick", "resolve_target"]

USAGE = "用法：aos-tick [<目標>]（目標＝資料夾或任務表檔；留空＝./）"
EXIT_OK, EXIT_ERROR = 0, 1     # aos 結束碼慣例：0＝預料之中（含正常中斷）、1＝通用錯誤
EXIT_USAGE = EXIT_ERROR          # 慣例：argv 用法錯也算通用錯誤

def state(*parts):
    """狀態資料夾裡的相對路徑（run_tick 已 chdir 到工作資料夾）：鎖、擋板、停格檔。"""
    return os.path.join(aos_dirname.name(), *parts)


def say(code, msg):
    """P-203：tick 自己的 stderr 診斷行，一律 `代碼: 說明`。"""
    sys.stderr.write("%s: %s\n" % (code, msg))
    sys.stderr.flush()


def main(argv=None):
    """P-203 argv：`aos-tick [<目標>]`，目標是位置參數（跟 aos-exec 一樣，使用者 2026-10-01）：資料夾或任務表檔，留空＝`./`。
    用法錯回 1（aos 結束碼慣例）：任何 `-` 開頭的旗標（`-h`／`--help` 除外）、多於一個目標。
    `--firstdo-fsync` POC 先不做（使用者方向 2026-10-01），給了算用法錯。"""
    args = sys.argv[1:] if argv is None else list(argv)
    target_arg = None
    for a in args:
        if a in ("-h", "--help"):
            print(USAGE)
            return EXIT_OK
        if a.startswith("-") or target_arg is not None:
            say("usage", "看不懂的參數 %r；%s" % (a, USAGE))
            return EXIT_USAGE
        target_arg = a
    bad = aos_dirname.error()
    if bad:
        say("usage", bad)
        return EXIT_USAGE
    found = resolve_target(target_arg)
    if found is None:
        return EXIT_ERROR
    return run_tick(*found)


def resolve_target(arg):
    """〔使用者方向 2026-10-01，待統一更新 spec；取代 B-602「認哪個資料夾」、P-203 的 `--node`；目標是位置參數〕
    回 (工作資料夾, 這一格的任務表)，都是絕對路徑；不合法回 None。

    - 省略目標：用 `./`。相對路徑一律轉成絕對（不往上層找）。
    - 資料夾：要有 `.aos/tasks.json`，表就是它；不看 `.aos/inst.json`。
    - 檔：這個檔就是這一格的表（跟資料夾模式同一套極簡檢查，見 aos_tick_table.check_table）；它所在的資料夾當工作資料夾，
      但那個資料夾若叫 `.aos`，取它的上一層（`aos-tick yyy/.aos/tasks.json` 跟 `aos-tick yyy` 一樣）。
    - 上面的 `.aos` 都是 aos_dirname.name()（環境變數 `AOS_DIRNAME`，預設 `.aos`）。
      設成空字串時狀態檔直接在工作資料夾下（資料夾要有 `tasks.json`），檔案模式「往上取一層」的特判不適用。
    - 都不是（不存在）：回 None。
    """
    path = os.path.abspath(arg if arg is not None else ".")
    if os.path.isdir(path):
        table = os.path.join(path, aos_dirname.name(), aos_tick_table.TABLE_NAME)
        if not os.path.isfile(table):
            say("no_tasks", "%s 底下沒有 %s" % (path, os.path.join(aos_dirname.name(), aos_tick_table.TABLE_NAME)))
            return None
        return path, table
    if os.path.isfile(path):
        cwd = os.path.dirname(path)
        if aos_dirname.name() and os.path.basename(cwd) == aos_dirname.name():
            cwd = os.path.dirname(cwd)
        return cwd, path
    say("no_target", "目標指的東西不存在：%s" % arg)
    return None


def run_tick(cwd, table):
    """B-620「一格怎麼走」：整格照這個順序，回整格結束碼。cwd（工作資料夾）、table 由 resolve_target() 給（絕對路徑）。
    工作資料夾的 `.aos/` 不在時由 take_lock() 建、`.aos/tick/` 由 Record.open() 建（只建資料夾）；`.aos` 是 aos_dirname.name()。"""
    os.chdir(cwd)

    lock_fd = take_lock()
    if lock_fd is None:
        say("busy", "這個資料夾上一格還沒跑完：%s" % cwd)
        return EXIT_OK             # 使用者 2026-10-01 再改：預料之中，回 0（原 2）
    try:
        return _run_locked(cwd, table)
    finally:
        os.close(lock_fd)          # 程序結束本來就會放；在同一個 Python 裡呼叫 run_tick 時也要放


def _run_locked(cwd, table):
    reason = read_reason(state("tick-blocked"))
    if reason is not None:
        say("blocked", reason or "（擋板檔沒寫原因）")
        return EXIT_OK             # 使用者 2026-10-01 再改：正常中斷也是 0（原 2）

    try:
        items, ids = aos_tick_table.read_table(table, cwd)
    except aos_tick_table.TableInvalid as e:
        say("bad_table", str(e))          # 使用者 2026-10-01：表壞算 tick 自己的錯，不算開過一格（紀錄、seq 都不動）
        return EXIT_ERROR

    record = Record(cwd, aos_dirname.name())
    record.open()
    remove_stop_file()
    stopped_after = None
    for index, (item, task_id) in enumerate(zip(items, ids)):
        kind, value = run_one(cwd, item, task_id, index)
        record.add_task(task_id, kind, value)       # 任務怎麼結束只記下，不影響 tick 的結束碼
        reason = read_reason(state("tick", "stop"))
        if reason is not None:
            # 停格檔不算中斷，回 0（暫定，擋板檔與停格檔的機制使用者之後會詳細設計）
            say("stopped", reason or "（停格檔沒寫原因，停在 %s 之後）" % task_id)
            stopped_after = task_id
            break

    record.finish(EXIT_OK, stopped_after)
    return EXIT_OK


def take_lock():
    """B-602 的最簡版（使用者 2026-10-01 加回）：對 `.aos/tick.lock` 取非阻塞獨占 flock（不存在就建）。
    拿到回 fd，拿不到回 None。`os.open` 開的 fd 預設不可繼承（PEP 446），子程序又是 close_fds，
    所以任務拿不到這把鎖；不設 `AOS_TICK_LOCK_FD`。"""
    if aos_dirname.name():         # 空字串＝工作資料夾本身，不用建
        os.makedirs(aos_dirname.name(), exist_ok=True)
    fd = os.open(state("tick.lock"), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def read_reason(path):
    """B-620、P-213 停格檔與擋板檔：檔在回第一行原因（可能是空字串），不在回 None。"""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.readline().strip()


def remove_stop_file():
    """B-620：開第一項前刪掉上一格留下的停格檔。"""
    stop = state("tick", "stop")
    if os.path.exists(stop):
        os.unlink(stop)


def run_one(cwd, item, task_id, index):
    """B-620「跑每一項」：跑到時才展開這一項（plan 待問 3）再跑。回 (kind, value)。
    cwd 是工作資料夾（絕對路徑），原樣給任務當 `AOS_TICK_CWD`（使用者 2026-10-01；沒有 `AOS_TICK_RECORD`）。"""
    inst = aos_tick_table.load_inst(item, cwd)
    # id 型別不查（極簡檢查），環境變數要字串就 str()
    task_vars = {"AOS_TICK_CWD": cwd, "AOS_TASK_ID": str(task_id), "AOS_TASK_INDEX": str(index)}
    kind, value, note = aos_tick_run.run_item(inst, task_vars)
    if note:
        say("exec_failed", "%s: %s" % (task_id, note))
    return kind, value
