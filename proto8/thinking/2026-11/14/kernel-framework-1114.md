# 通用 kernel 框架 11-14（線框，家機）：批 5 接線做到一半、gpt 施工隊暫存樹步驟 1～6 驗過，交棒給 ok-kf；這次沒有程式進 main

← [2026-11-14](README.md)｜前情：[11-13 開工紀錄](../13/kernel-framework-開工.md)（§十二、§十四「還沒做」）｜圖紙 [kernel-framework](../12/kernel-framework/README.md)（[03 狀態查詢信](../12/kernel-framework/03-狀態查詢信.md)、[05 施工步驟](../12/kernel-framework/05-施工步驟.md)）｜[eca-as-kernel](../13/eca-as-kernel.md)｜gpt 隊前一輪 [gpt-fsm-team](../13/gpt-fsm-team.md)

## 使用者原話（11-14，頂層轉，依序）

- 「你列的這些都可以。開始推進吧」——範圍：家機重做批 5 接線、批 6、批 10（公司補丁 `~/code/kf2-1113` 不用；11-13「不，明天我們重做。」），之後真腦做 7b、11b、12、13、14。
- 「跑一整晚...我們現在就用本地litellm proxy，使用gpt」「作爲我們要的實作」——寫碼優先交給 agent-fsm（astra 指揮 sol，腦接 `http://127.0.0.1:4000`），撞到的問題照實記。
- 「然後每條線都讓opus作爲協調，要規劃就走正規規劃流程」
- 「蒐集資料和實作都可以試試看交給sol等」
- 「不要走codex」
- 「不要terra，盡量用sol，把sol作爲sonnet來用」
- 「然後有需要的，可以自己掛kernel或agent。」
- 「多掛幾隻opus eca，把各條線分給他們」——本線交棒給活樹裡的 opus eca `ok-kf`。

## 做了什麼

| 時間 | 事 | 結果 |
|---|---|---|
| 07:5x | 批 5 接線派 codex `gpt-6.1-sol`（工作複本 `~/code/kf-1114/b5`） | 使用者「不要走codex」→ 收掉（pid 146097、子 147095，cwd 核過在 `~/code/kf-1114`），它還沒改到任何檔 |
| 08:0x | 批 5 接線改由 Claude opus 隊員補位（gpt 隊還沒架好、這批擋著線星） | 交棒時停在半路，見下 |
| 08:0x | gpt 施工隊暫存樹（opus 隊員建，照 gpt-fsm-team 04） | 步驟 1～6 驗過，步驟 7 乾跑沒跑 |
| — | 批 10 圖紙（給 gpt 隊用） | 寫好：`~/code/kf-1114/blueprints/b10.md`，沒派 |

**沒有 commit 程式**。批 5 是半成品，照規矩不進 main（線星的階段 0 接線還要等它）。

## 真腦用量

- gpt（LiteLLM）：3 次呼叫、4920 token（暫存樹 kernel 三包各問一句 OK）。
- codex：一次，啟動不到幾分鐘就收掉，沒改檔；用量沒記到。
- Claude：隊長＋兩名 opus 隊員（不經 aos 帳）。

## 交棒給 ok-kf

### 做到哪

- **批 5 接線**：在 `~/code/kf-1114/b5`（`git archive 10133771b`＋impls bin、`git init`，base commit `3825d5a`）改了 11 檔、198＋／46−，全部 import 得起來；**`ctl/rm.py`、`ctl/set_def.py`、`cmd/aos-agent` 的 README／docs 還沒改；改後測試一條都沒跑**。改過的檔：`py/daemon_ctl/{__init__,table}.py`、`cmd/aos-agent/aos_agent/{common,hints}.py`、`ctl/{add,ls,phase,shared,state,where,who}.py`。整份 diff 存在 `~/code/kf-1114/b5/kf-check/b5-wip.patch`（對 base）。任務書 `~/code/kf-1114/task-b5.md`（原寫給 codex，驗收 7 條照用；「開 subagent」那句改讀成 Claude／gpt 隊）。隊員的交棒狀態（報告檔寫不進暫存夾，記在這裡）：
  - 已接：`daemon_ctl` 匯出 `state_path` 等、`table.state()`／`names_of()` 收 `TableFile`；`common.py` 的 `table_ref()`（沒走 kernel＝原樣 `find_daemon`）；`shared.py` 走 kernel 時跳過 `need_table`／`daemon_up`、寄 `AOS_KERNEL`、回信信箱 `kernel_reply_box()`；`ls`／`who`／`where`／`state` 加 `--timeout-s`；`add` 走 kernel 只看回信；`phase.py` 的 start／stop／sleep／wake 只看回信、pause／resume 經查詢信拿 stack。
  - 還沒做：`rm.py`（不帶 `--purge` 用 `ctl_wait(..., replied=True)`、stdout 含 `rm accepted for NAME`；`--purge` 照舊經 `find`；WAITER 參數是檔就 `dc.rows_at`）；`set_def.py`（`add_letter` 傳 `daemon=None`；`--restart` 用 `cmd_stop/cmd_start(..., look=True)`，否則 stop 一回信就 start 會被拒）；`listen.py:115` 的 warning 走 kernel 問不到會丟 `KernelFailed`；文件；index_gen。
  - base 測試（改前）：`test_kernel_state_path` 12 skipped；`py/tests` 全 OK；`cmd/aos-agent/tests` 只有 `test_tools_override.test_ls_default_is_brief` 紅（與本批無關）；`lib/agent` 各夾全綠。結果與腳本在 `/tmp/kf-b5-runs/`（`suites.sh <proto8根> <輸出夾>`，經 clean-env 跑），base 程式碼 `/tmp/kf-b5-base-bcegempj`。
  - 隊員的小選擇（可翻）：沒走 kernel 時舊路一字不變；走 kernel 時 `daemon_path()` 回表檔所在夾（同 `who --json` 的 `daemon` 欄）；`--envs` 目標寫絕對路徑；逾時訊息附 `AOS_KERNEL` 旁 `queue.json` 路徑；給了 `--daemon D` 又設 `AOS_KERNEL` 時信照舊寄 `AOS_KERNEL`（原本如此）。
- **批 5 停下的三個設計題**（圖紙沒寫到，照使用者「要規劃就走正規規劃流程」，接手的人別邊做邊定）：(1) 走 kernel 時 `stop`、`rm` 不關畫面（關畫面要讀表，圖紙說寄信指令不讀表）；(2) `common.table()` 改走查詢信後，`say`、`listen`、`tools`、`llm`、`history`、`hook`、`system`、`goal`、`chat`、`screen` 找對象也會先問、問不到報 `KernelFailed`——圖紙 03 第 1 列寫要改 `common.py` 的 table，但任務書只列 ctl，範圍待定；(3) `decl.run_entry` 給畫面入口的 `AOS_DAEMON` 走 kernel 時給什麼（刪減表檔名不叫 `procs_state.json` 時下游 watch 會讀錯）。
- **批 6、批 10**：沒動程式。批 10 圖紙已寫（上表）；批 6 要等批 5 進 main 再寫圖紙（圖紙 03 第 3～5 列＋開工紀錄代定 9）。
- **gpt 施工隊**：`~/code/kf-1114/fsm/`，現況、用法、權限、額度在哪改都在它的 `README.md`；問題清單 `issues.md`（K1～K9；K9＝活樹 08:22 多出 `ok-*` 幾列，就是這次交棒掛的 eca，不是問題）。

### 還在跑的程序（都在 `~/code/kf-1114/fsm/`，記在 `fsm/pids.txt`）

| pid | 是什麼 | 留不留 |
|---|---|---|
| 159076 | 暫存樹 daemon（stack `~/code/kf-1114/fsm/ws/.stack`） | 留（gpt 隊要用） |
| 158881 | tmux server（`-S ~/code/kf-1114/fsm/tmux.sock`） | 留（daemon 跑在裡面） |
| 159091 | `_clock`（daemon 子行程） | 留 |
| 163754 | `llm-gpt`（Python 問腦總機，auto_restart，pid 會變） | 留 |

已收：codex 146097／147095。gpt-lead、sol 從沒起過。收暫存樹的唯一做法：`echo ~/code/kf-1114/fsm/ws/.stack` 核路徑後 `~/code/kf-1114/fsm/bin/aosenv aos-daemon-ctl -d /home/lorkhan/code/kf-1114/fsm/ws/.stack shutdown`。活樹兩台 daemon（37179、37183）全程沒碰。

### 下一步（建議順序）

1. **批 5 最優先**（線星等著）：把 `b5-wip.patch` 補完 `rm.py`（`--purge` 經查詢信、不帶 `--purge` 只看回信）、`set_def.py`（經查詢信拿列）、文件；跑任務書驗收 7 條，關鍵是 `cmd/aos-agent/tests/test_kernel_state_path.py` 12 例實跑全過、沒設 `AOS_KERNEL` 的 30 步以上對照一致。過了再落到 repo（`cmd/`、`py/` 存檔即生效：先寫暫存檔再改名，存完立刻 import 驗一次），commit 訊息開頭「線框 批5」。
2. 批 5 進 main 後驗「只設 `AOS_KERNEL` 仍 `DaemonMissing`」（ctl 那半由批 5 解，fork／subagent 那半要批 6）。
3. gpt 隊：寫 `fsm/bin/cleanup`、跑步驟 7 乾跑（假圖紙先 commit 進 `work/repo`，不然 astra 會判 BLOCKED），通了再派批 10（`blueprints/b10.md`；C++ 由隊長在沙箱外建）。
4. 批 6 圖紙 → gpt 隊；之後 7b、11b、12、13、14。

### 已知的坑

- `~/code/kf-1114/fsm/work/repo` 與 `fsm/aos/` 是 `f8c4baf2` 的複本，批 5 的複本 `b5` 是 `10133771b`；兩邊基底不同，換到 gpt 隊做時先對齊到當時的 main。
- 我們的 shell 帶活樹的 `AOS_*`：任何 aos 指令與測試經 `~/code/kf-1114/clean-env.sh`（bash，清光再 exec）；暫存樹用 `fsm/bin/aosenv`。
- `~/.local/bin/aos-*` 與 user site 的 `.pth` 指向 `~/repo/aos`（fsm issues K3）：暫存樹照預設跑會用 repo 的程式，所以 fsm 另抄了一份 runtime。
- 子 agent 寫報告檔會被工具擋（批 5 隊員、隊長代存都撞到），報告直接寫進本檔或回報訊息。
- 批 5 隊員留了一份 base 抄本在 `/tmp/kf-b5-base-bcegempj`（對照用），可刪。
- 接線後凡是設了 `AOS_KERNEL` 的都要 daemon 會答查詢信：家機活樹的 `aos-daemon`（repo bin，11-13 23:20）已認 `procs_state_path`（`strings` 看得到），活樹 `env.sh` 不設 `AOS_KERNEL`，所以接線對活樹沒影響。
