"""固定回歸矩陣（一）：讀不到＝不知道（A2-01 與檔案層的三態；spec 第 0 節、5.4、2.6）。

**AOS7_TEST_* 環境變數只給測試用**：這裡用 `AOS7_TEST_FAULT`（分號分隔的 `op:glob:ERRNO`，glob 用 fnmatch 比完整路徑）
在指定的讀取點丟 OSError，`AOS7_TEST_RUNNER_CRASH` 讓 aos7-run 在指定點 SIGKILL 自己。正常環境不設；tick 起任務時拿掉。

矩陣維度與判定：

1. **/proc 讀不到**：op ∈ {proc-list（`/proc`）、proc-stat、proc-environ、proc-cmdline（只打在這個任務／runner 的 pid 上）}
   × errno ∈ {EIO、ESTALE、EACCES} × 情境 ∈
   - `healthy`：keep 任務正常活著。判定：judge 是 LIVE（proc-stat 時帶 `unsure`）；tick 不起新 run（started＝[]、birth 的 run 不變）、
     不殺（pid 還活）、不寫 exit.json；tock 的 alive 列它，unsure 時 errors 有這個槽一筆（phase unsure／judge）。
     已知 pid／runner 活著的判定走捷徑、不一定讀到 proc-list／environ／cmdline（astra-2：12 案有 9 案命中 0 次），所以同樣的故障下
     再送一份 kill 控制（kill 一定要身分掃描）：命中 ≥1、任務沒被殺、回合總結的 ctl 紀錄 ok:false、ctl-done.json 的
     result.ok＝false 且訊息帶 unknown、ctl.json 消費掉。拿掉注入：同一個 pid 繼續活、tock 的 alive 列它、執行次數仍 1、
     那件 kill 不重做（已記在 ctl-seen.json）。
   - `orphan`：runner 在 pid.json 前被 SIGKILL、任務還活（疑似 lost，要身分掃描）。判定：注入時 UNKNOWN——不殺、不寫 lost、
     不起新 run、tock errors 有一筆；拿掉後才收掉孤兒、判 lost，而且 lost 只報一次，之後槽裡剛好一個活程序。12 組全跑。
   - `deadboth`（只有 proc-list、proc-environ 全部 pid；environ × EACCES 除外）：runner 與任務都被 SIGKILL、沒 exit.json。判定同 orphan。
   - **environ 的 EACCES＝不是可辨認的任務、略過**（任務要跟 daemon 同 uid、environ 可讀，spec §11）；cmdline 的 EACCES 一律是
     不知道。所以 orphan 的 environ × EACCES 不在矩陣裡（那是誤用，已刪）；`deadboth_skip`（environ 全部 EACCES、任務確實死了）
     照常判 lost 一次、重起一個。
   **每個注入都斷言命中 ≥1**（`_matrix.fault`／`run_prog` 經 AOS7_TEST_FAULT_HITS 命中紀錄檔，子程序也算）。
   另有 `kill_identity` 在掃描不完整時回 (False, 說明)、`env_procs` 丟 `aos7_fs.Unknown`。
2. **檔案讀不到**（open 注入）：檔 ∈ {birth.json、exit.json、pid.json} × errno → 槽 UNKNOWN：不起、不判 lost、不刪槽（名字拿掉也不刪）、
   tock errors 一筆；拿掉後恢復（lost 只報一次、重新起一個），回合不跳號。
   檔 ∈ {round.json（tick 3、tock 3，round.json 原樣）、last-round.json（tock 3）}、listdir `.aos/tasks`（tick 3、tock 3）× errno：
   什麼都沒寫；拿掉後恢復、回合連續。
   T8-05：last-round.json 第 2 次讀（寫後讀回）注入 U／BAD／同 round 異內容：不關回合、不收尾，解除後重播。
3. **daemon 看 node 的 stat 讀不到** × errno：時間線保留、不進 missing、不起 reaper，last_error 帶 errno 類型。
   另有一案真 daemon 用 `AOS7_TEST_FAULT=@規則檔` 中途開關（命中紀錄檔經環境傳給 daemon 子程序）。
"""
import os, sys  # noqa: E401
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # tests/：base、_matrix
import errno
import json
import os
import unittest
from unittest import mock

from _matrix import ERRNOS, DaemonCase, Fault, MatrixCase, alive, fault, gen, rec_argv
import aos7_daemon
import aos7_daemon_timeline
import aos7_fs
import aos7_mount
import aos7_proc
import aos7_task
import aos7_tock
from aos7_fs import read_json, write_json

PROC_OPS = ("proc-list", "proc-stat", "proc-environ", "proc-cmdline")


def proc_rules(op, pids, e):
    """只打在給的 pid 上（proc-list 打 `/proc` 本身）。"""
    if op == "proc-list":
        return "proc-list:/proc:%s" % e
    leaf = op.split("-", 1)[1]
    return ";".join("%s:/proc/%d/%s:%s" % (op, p, leaf, e) for p in pids if p)


def keep_item(name="k"):
    return {"name": name, "mode": "keep", "argv": rec_argv(name, keep=True)}


