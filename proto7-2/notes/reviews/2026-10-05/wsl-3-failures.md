# WSL 上 3 項穩定失敗：測試寫錯（對環境與時序的錯誤假設），不是產品 bug

[本日報告索引](README.md)｜[藍圖 loop7](../../blueprint-loop7.md)

**結論：三項都是 (a)＋(b)——測試對 `/bin/sh` 行為與「aos7-run 起得比恢復回合快」的假設在這台機器不成立；產品判定全部照 spec 5.4 走對了，與 R8-01／K-04／D1 無關，也不是最近的 commit 造成（10-04 的 97191272 上一樣紅）。已改測試、核心零改動。**

環境：Linux 6.6.114.1 WSL2、Ubuntu 24.04.4、Python 3.12.3、8 核；`/bin/sh -> dash 0.5.12-6ubuntu5`。

## 根因

| 測試 | 根因 | 類 |
|---|---|---|
| test_ctl `test_old_run_leftover_not_taken_as_new_run` | 任務 argv 是 `sh -c '…; fi; sleep 60'`。這台的 dash **不把 -c 的最後一個命令 exec 掉**、會 fork（連單獨一個 `sleep 3` 也 fork；bash 會 exec）。run 2 因此是 sh＋sleep 兩個程序，兩個都帶 `AOS7_RUN=2`，`env_procs` 照 spec 5.2 兩個都算是對的；斷言「只有主程序」錯。 | (a) 環境＋(b) |
| test_matrix_once `test_keep_runner_before_exit` | 兩個毛病輪流出：① `rec_argv(short_first=True)` 的 `…; sleep 0.2` 同上被 dash fork，同一個 run 1 有 sh＋sleep → 「雙開」誤報；② runner 點的 tick 不等 runner，恢復的 4 回合在行程內跑、整段約 15 ms，比 aos7-run 起 Python（這台約 18 ms）再跑任務 0.2 秒還快 → 回合都看到「runner 還在、當活」，runner 之後才自殺、已沒有回合去判 lost 重起 → 5 秒後 `[]`。 | (a)＋(b) |
| test_matrix_once `test_once_after_popen` | tick 在 Popen aos7-run 之後被殺；恢復 5 回合（約 13 ms）全部跑完時 runner 還沒起任務（判定正確地回 LIVE unsure「剛起」→「aos7-run 還在，當活」），`settle` 對 unsure 不等，結束時還沒跑 → 0 次。多等 1.5 秒再看，`ran-o.txt` 就是 `1`、程序全收。 | (b) 時序競態 |

同族的 `test_keep_runner_before_pid` 在這台約 10% 間歇紅（`'suspect' != 'live'`），也是 ②：恢復回合跑在 runner 自殺之前；它還暴露一個假綠——最後「剛好一個活程序」被前任殘留滿足、新 run 的任務其實還沒起來。

為什麼 astra-6 綠：同一套測試在那台三次全綠（[astra-6 回歸](../../play/2026-10-04-astra-6-infra.md)），推測是 `/bin/sh` 會 exec 最後一個命令、且恢復回合相對 Python 啟動較慢；那台的 sh 版本沒留紀錄，**未證實**。可證實的是：把測試的 `sh -c` 換成 `bash -c`，test_ctl 那項 3／3 綠、once_after_popen 3／3 綠、keep_runner_before_exit 4／5 綠（剩下那次是 ② 的時序）。

## 證據（摘要）

- 單跑紅：`nice -n 5 python3 proto7-2/tests/run_all.py -k test_old_run_leftover_not_taken_as_new_run` → `[549852, 549853] != [549852]`；`-k TestLaunchCrash` → 18 項 2 紅（就是題述兩項）。
- 不是近期 commit：`git archive 97191272 proto7-2` 解到 scratchpad 單跑，同樣紅（TestLaunchCrash 該次 3 紅，多一項 keep_runner_before_pid）；`git log 97191272..HEAD` 對 `_matrix.py`、兩個測試檔、`aos7_run／task／proc／tick／tock.py` 沒有任何 commit。
- dash 不 exec：`dash -c 'sleep 3'`、`dash -c 'true; sleep 3'`、`dash -c 'if …; fi; sleep 3'` 主程序都還是 dash、底下有 sleep 子程序；`bash -c` 五種寫法主程序都變成 sleep。
- 雙開誤報的兩個 pid：`550945 sh -c echo 1 >> …; touch …; sleep 0.2`（AOS7_RUN=1）與 `550947 sleep 0.2`（父＝550945、AOS7_RUN=1）——同一個 run 的父子，不是兩次起動。
- once_after_popen 的回合總結：5 回合全是 `alive: ["o#1"]`，errors 依序「剛起」×2、「疑似 lost…但這個 run 的 aos7-run 還在，當活」×3；測試結束瞬間 `env_procs(runners=True)` 只有 aos7-run 一個 python；1.5 秒後 `ran=['1']`、程序 `[]`。
- 啟動時間：`python3 bin/aos7-run`（走到用法錯就退）約 17～18 ms，`python3 -c pass` 約 11 ms。
- keep_runner_before_pid 間歇紅時：view 是 run 1 `suspect`（「沒有 pid.json，runner 已不在」），唯一的活程序是 run 1 的 `sleep 60`（AOS7_RUN=1）、tock.json round 5——回合都在 runner 自殺前跑完。

## 處理（只改測試，commit 在本分支）

- `tests/_matrix.py` `rec_argv`：`short_first` 的 `sleep 0.2` → `exec sleep 0.2`（docstring 記 dash 行為）。
- `tests/core/test_ctl.py`：`…; fi; sleep 60` → `exec sleep 60`。
- `tests/core/test_matrix_once.py`：
  - `interrupt_tick(point, node, slot)`：runner 點先等 birth 記的 runner（pid＋starttime）確定不在才開始恢復——確保測到的是中斷點本身。
  - `_once`：第一個 tock 照舊（保留「剛起」窗口的覆蓋），之後每回合 tick 前等這個槽的程序（含 aos7-run）全部不在。
  - `_keep` 收尾：先等**現在這個 run** 的 pid.json，再要求活程序**剛好是它的 pid**（原本只數「一個」，會被前任殘留滿足）。
- 驗證：修後 `-k test_matrix_once` 30／30 綠（另一批 20 次前修到一半時抓到 keep_runner_before_pid 間歇紅，才補了上兩條）、`-k test_ctl` 5／5 綠。拿掉 `resolve` 的「先收殘留」做變異（scratchpad 複本），修後的 `keep_runner_before_pid` 轉紅（`run 2 的 601108：[601106, 601108]`）；只數「一個」的寫法同變異仍綠——原本是假綠。
- 未跑全套（機器有別隊）。其他用 `sh -c '… ; 命令'` 又數程序個數的測試，這台全套只紅這 3 項，暫不動；寫新測試時最後的長睡請一律 `exec`。
- 跟藍圖的關係：不涉及 D1～D10。R8-01／K-04 是「kill 打在啟動交接窗口」，這裡沒有 kill、判定也沒誤判；這次加的「等 runner 真的死」與 T8 系列「先證明故障真的發生」同一原則，可併入 T1→T2 線參考。
