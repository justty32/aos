"""aos-tick 跑任務表的一項：照 inst 開串流、開子程序、等它，回 exit 或 signal（B-620「跑每一項」、P-203）。

照 inst 的規則（mkdir、串流預設 /dev/null、envs 疊加或清空、另開 session）跟從 proto5 複製來的
`aos_exec_run._execute_inst()` 一樣，只多兩件那裡沒有的事，所以這裡自己開程序、不改 lib：

- 三個 `AOS_*` 變數（`AOS_TICK_CWD`、`AOS_TASK_ID`、`AOS_TASK_INDEX`）蓋在繼承的環境上（`envs` 清空時一個都不放）；inst 的 `envs` 最後疊上去。
  〔使用者方向 2026-10-01〕鎖 fd 不傳給任務（`os.open` 預設不可繼承、Popen 預設 close_fds），沒有 `AOS_TICK_LOCK_FD`。
- 自己 wait，分出 `exit` 與 `signal`（`_execute_inst` 把訊號 N 折成 128+N）。

沒跑成（mkdir、cwd、重導向檔開不起來）照 aos-exec 算 125；找不到程式 127、沒執行權 126。
inst 的 `exit` 欄位照寫（被訊號 N 殺寫 128+N，跟 aos-exec 一樣）。
沒有逾時（P-008 延後）；核心不清後代（B-602）。
"""
import os
import subprocess

import aos_exec_run

__all__ = ["run_item", "EXIT_NOT_RUN"]

EXIT_NOT_RUN = 125


def _env(inst, task_vars):
    env = {} if inst["envs_clear"] else dict(os.environ, **task_vars)
    env.update(inst["envs"])
    return env


def run_item(inst, task_vars):
    """跑一項，回 (kind, value, note)：kind 是 "exit" 或 "signal"；note 是要印在 stderr 的說明或 None。"""
    to_make = [inst["cwd"]] if inst["cwd_mkdir"] else []
    for name in ("stdout", "stderr", "exit"):
        if inst[name]["mkdir"]:
            to_make.append(os.path.dirname(inst[name]["path"]) or ".")
    try:
        for d in to_make:
            os.makedirs(d, exist_ok=True)
    except OSError as e:
        return "exit", EXIT_NOT_RUN, "mkdir 建不起來：%s" % e
    exit_path = inst["exit"]["path"]
    if exit_path and not os.path.isdir(os.path.dirname(exit_path) or "."):
        return "exit", EXIT_NOT_RUN, "exit 檔的父目錄不存在（沒開 mkdir 不會幫你建）：%s" % exit_path
    if not os.path.isdir(inst["cwd"]):
        return "exit", EXIT_NOT_RUN, "cwd 不是資料夾：%s" % inst["cwd"]

    env = _env(inst, task_vars)
    opened = []
    note = None
    try:
        try:
            fin = None if inst["stdin"]["inherit"] else open(inst["stdin"]["path"] or os.devnull, "rb")
            opened.append(fin)
            fout = aos_exec_run._open_out(inst["stdout"])
            opened.append(fout)
            if inst["stderr"]["merge"]:
                ferr = subprocess.STDOUT
            else:
                ferr = aos_exec_run._open_out(inst["stderr"])
                opened.append(ferr)
        except OSError as e:
            return "exit", EXIT_NOT_RUN, "重導向的檔案開不起來：%s" % e
        try:
            p = subprocess.Popen(inst["argv"], cwd=inst["cwd"], env=env, start_new_session=True,
                                 stdin=fin, stdout=fout, stderr=ferr)
        except ValueError as e:
            return "exit", EXIT_NOT_RUN, "無法啟動子程式：%s" % e
        except PermissionError as e:
            kind, value, note = "exit", 126, "沒有執行權：%s（exit 126）" % e
        except (FileNotFoundError, NotADirectoryError) as e:
            kind, value, note = "exit", 127, "找不到程式：%s（exit 127）" % e
        except OSError as e:
            kind, value, note = "exit", 126, "起不了子行程：%s（exit 126）" % e
        else:
            p.wait()
            rc = p.returncode
            kind, value = ("signal", -rc) if rc < 0 else ("exit", rc)
    finally:
        for f in opened:
            if f is not None:
                f.close()

    if exit_path:
        status = value if kind == "exit" else 128 + value
        aos_exec_run._write_exit(exit_path, status, inst["exit"]["append"])   # 默認寫得進（使用者方向 2026-10-01）
    return kind, value, note
