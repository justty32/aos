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

## ok-kf 接手紀錄（11-14 家機）

### 批 5（ctl 接 AOS_KERNEL 查詢信）
- 施工：暫存樹 `~/code/kf-1114/fsm` 的 agent-fsm sol（sol-b5 接 b5-wip.patch 補完；sol-g1 蒐集畫面題事實），腦走 LiteLLM chatgpt-gpt-6.1-sol-high。ok-kf 審 diff。
- 守門：`guard.json` 的 `\baos-[a-z-]+` 會擋 `proto8/cmd/aos-agent` 路徑，`kill`／`curl` 會擋搜尋字串，兩條都拿掉（bwrap `--unshare-all` 已隔開 pid 與網路；`fsm/issues.md` K10、K11）。sol 每次被擋都停下報 BLOCKED，沒有繞路。
- 三支 fork／subagent 舊測試釘的是 11-12 小修線的契約（只設 AOS_KERNEL＝DaemonMissing），ok-kf 代定照圖紙改成 KernelFailed＋寄出查詢信。
- 驗收：main 51dc8b931＋本批乾淨複本全綠；py 那支 test_flags_anywhere.test_eca_screen_eca_after_subcommand 在 main 本來就紅（本批沒碰，已轉 xiaosi）。
- 畫面兩題（走 kernel 時 stop／rm 關不關畫面、run_entry 給畫面的環境與 watch 判走）：sol 蒐集 → ok-kf 匯總 → fable 設計 → ok-kf 細化 → Argon 審 → 採納表。批 5 只寫已知限制，實作留批 5b。計劃與審查在 `wf/temp/ok-kf/b5-design/`（plan.md 末尾的採納表：1a～1c、2a～2d 採，2e 不採）。另開題 C′（eca-claude 範本加 after_stop hook 自己收畫面，sleep 也會收）要交使用者裁。

### sol 有沒有讀必讀（使用者 11-14 要求）
- 讀清單放進 system text 與任務書開頭之前：兩隻都沒讀過任何必讀檔。
- 放進去之後：兩隻都讀了全部必讀（history 可證）。之後報告改用中文；看到工作區被別人改過會停下來問；測試和圖紙衝突時不自己選，而是列出兩邊請 ok-kf 裁；交件只寫事實、不夾設計。詳細在 `~/code/kf-1114/fsm/notes-must-read.md`。

### 對頂層加 AOS_KERNEL 的風險（已寄 xiaosi BLOCKED）
- 批 5 之後，設了 AOS_KERNEL 的查表指令（ctl ls／state／who、say、listen 等經 common.table() 的）都會先寄 `procs_state_path`，3 秒沒回信就 KernelFailed。
- kernel_gate 的 hold 每封都留；triage 把它判成「不認得」→ hold；框架站 lib/aos/kernel 沒有處理這種信。
- 所以 eca 帶 AOS_KERNEL 指 gate 要等批 6（站回答或放行查詢信，triage 也認得它）。

### 批 5b（走 kernel 時的畫面）
- 照 `wf/temp/ok-kf/b5-design/plan.md` 末尾的採納表施工（sol-b5），ok-kf 審 diff。
- `rm --purge` 走 kernel：讀列 → 寄 rm、等回信 ok → 關畫面 → 刪 stack；被拒什麼都不動；列缺 def 就印 warning、照常 purge。stop、不帶 purge 的 rm 照舊不關畫面（docs/02 寫了 stop 後 close、rm 前 close、已 rm 用 tmux kill-server）。
- `run_entry`：走 kernel 不覆寫 AOS_DAEMON；直連時拿掉 AOS_KERNEL。`state_path(fresh=True)`。`aos-eca-screen watch` 走 kernel 每 5 秒最多重問一次，照 Argon 四步判定。
- 圖紙 03「decl.py 不改」那列改成「改」並寫原因。
- C′（範本 after_stop hook 自己收畫面）已寄 xiaosi NEEDS-USER，等使用者裁。

### 批 11b（查詢信的條文、文件、知識庫）
- opus 子 agent 在 repo 外複本起稿，ok-kf 審、補 README 與 agent.json／me.json，24bc28e23 進 main。
- 子 agent 讀碼時發現疑似 bug：`ctl add --dotenv-override` 走 kernel 時沒傳下去，已轉 ok-misc（功能是它的）。

### 批 6（lib 端＋gate 放行查詢信）
- lib 端（ok-kf-sol-1）：fork、subagent 以自己那列的 stack 為基準、放在自己 stack 隔壁、不帶 --daemon、subagents.json 存絕對路徑（舊帳的相對路徑不認，照圖紙 03 第 4 列）；on_clock 經 `ctl ls --json` 找鐘、記鐘檔、讀不到重查一次。批 5 代定的三支過渡測試改成「只設 AOS_KERNEL 也能掛子與分身」。
- gate（sol-g1）：kernel_gate 的 hold、triage 對只有 `procs_state_path: true` 的信直接放行，並寫時照其他鍵判。sol-g1 查證：框架站對這種信的規則結果是 pass，照 next 轉；reply_via_me 開或不開，回信都回得到原寄件人（附真 daemon 測試）。
- 合到 main 時 fork/_entry 和 ok-misc 的 timeout_s＝0 撞一處，手動合（兩邊都留）。
- 知識庫 kernel.json 的 gate 段、N-63 02「批 6 之後」那段跟著改。
- 頂層要等這批進 main，才讓 eca 帶 AOS_KERNEL（repo-aos 11-14 來信）。注意：活樹的 lib 是另一份，要換樹時重拷才生效。

### 批 10（問腦總機切 Python 版）
- ok-kf-sol-2 在 repo 外複本 b10tree 施工；ok-kf 在外面建 aos-llm（沒有舊夾也建得起來，19 例過）。
- 刪 `impls/aos-llm-kernel` 要頂層准（~/.local/bin/aos-llm-kernel 指向它），已寄 xiaosi 選甲／乙。

### 批 7b（鏈劇本第 3 段＋只設 AOS_KERNEL）
- ok-kf-sol-1 施工。鏈劇本裡 agent 的環境拿掉 AOS_DAEMON，只靠 AOS_KERNEL；第 3 段：站 A 的 before_reply hook 照原寄件人產刪減表（路徑轉絕對），agent 的 `ctl ls --json`／`ctl who --json` 只看得到自己和它帳上的子，看不到 other；查詢信每站各過一次、不被留。
- main 0a3ffe5c4＋本批連跑兩次 8/8。N-28 那句「鏈劇本那段還沒驗」改成驗過。
- 11-14 頂層裁乙：先交不刪的部分（範本換身體、標頭搬進 aos-llm、CMake／install／tree-swap 拿掉舊名、測試換叫 kernel_llm/_entry、兩支 live 測試搬進 kernel_llm/tests）。`impls/aos-llm-kernel` 舊夾與 `~/.local/bin/aos-llm-kernel` symlink 列進今晚換樹清單，刪檔要使用者點頭。活樹有自己一份範本，不直接讀 repo 的 kernel/llm-kernel。
- 驗 main 0a3ffe5c4 對 main＋本批：受影響的 7 夾＋image-move-check 結果相同，只有 agent-fsm 兩支紅，兩邊一樣。其中 test_fork 是批 6 漏改：details 改成絕對路徑後，範本測試還在比相對路徑（我批 6 驗收時漏跑 templates/tests/agent-fsm），本批一併改；test_hooks 那支 ok-misc 已在 77a822e1c 修好。

### 批 12（問腦條文、文件、知識庫跟上 kernel_llm）
- 65522efd8，44 檔。跟圖紙 04 不同、照程式寫：kernel_llm 照舊讀 AOS_KERNEL、沒有 next；04 說的 kernel/llm-kernel README 不存在。
- 留著沒改：生成的 _index.json（等佇列重生）、三處程式碼註解（llm_kernel.hpp 第 1 行、post.hpp、lib/base/llm_http/_entry），等換樹刪舊夾時一起。

### 批 14（家機：問腦 live 測試＋試驗場換身體）
- main 65522efd8 的乾淨複本（`~/code/kf-1114/verify-b14-65522efd8`，清掉 AOS_*）：`lib/aos/kernel_llm/tests` 的 test_batch8_live、test_nesting_live 共 9 例全過（真 daemon 兩層，端點是本機假程式）。
- 試驗場：整份 `cp -a ~/code/playground` 到 `~/code/kf-1114/pg-b14`，原件沒動。複本裡 lib／py／templates／knowledge 換成上面那份 main，總機 `llm_kernel/def/daemon.json` 從 `aos-llm-kernel kernel.json` 換成範本的 `aos-exec $AOS_HOME/lib/aos/kernel_llm kernel.json`，兩個 stack 移到 `.orig` 另起；只掛 fsm_ann，腦改 `sol`（LM Studio 沒開，`stupid-fast` 用不了）。fsm_ann 用工具查時間、答一句，兩次問腦都記進 ledger：欄位跟換之前的舊列逐鍵同序，sender 是 agent stack、endpoint sol、usage 有真 token。
- 沒做：LM Studio 兩個本機包的互斥與黏著（LM Studio 沒開）；對帳腳本照 letter → child 配對；可選的「領班加框架站」由批 13 代驗。

### 批 13（真腦 eca 經框架站生 subagent）
- 同一份試驗場複本：agent daemon 換成框架站（daemon.json 的身體是 `lib/aos/kernel`、自己的 AOS_KERNEL 指自己的 requests；kernel.json `max_running: 3`、`queue: true`、`reply_via_me: true`；_sweeper 也算一格）。eca_bob（claude haiku，tools 補 subagent 包）掛上時帶 `AOS_KERNEL=<框架站>/requests`。
- 叫它用 subagent 工具連 add 兩隻（def＝fsm_ann）：kid1 回 `added kid1 … subagents 1/4`、表上多一列；kid2（on_queued=ok）回 `queued kid2 at position 1 …`，框架站 queue.json 有它、表上沒有。腦收到的兩個工具結果都沒有報錯。ctl stop kid1 放一格後，kid2 一秒內出隊、running。再叫它 `subagent ls`（走查詢信）：kid1 stopped、kid2 running，subagents.json 的 kid2 從 queued_letter 換成 stack。
- codex（gpt-6-luna）那半照規則不跑。複本已 shutdown；`~/code/kf-1114/pg-b14` 留著當證據。

### C′（畫面延後關，A 包＝主體）
- 使用者規則：stop／sleep 後延後關畫面（預設 10 分鐘、可設、0＝立刻），延後期間又起來就不關，pause 不關，有人看也照關。
- 流程：sol-g1 盤點事實（kf-check/G-cprime-facts.md）→ fable 設計（G-cprime-design.md）→ ok-kf 修 → Argon 審（wf/temp/ok-kf/cprime/argon.md：抓到 reap 先拿鎖再讀單的順序漏洞與刪單 TOCTOU 等，提案六點全收）→ 定案 wf/temp/ok-kf/cprime/final.md → ok-kf-sol-1 施工（c1tree）。
- 做法：after_stop 的 `screen_linger_stop` 在小格原子寫到期單 `screen_close.json`（token、停下那支 loop 與畫面身分），用畫面自己那台 tmux 的 `run-shell -b -d` 排到期指令（背景化，kill-server 收不到它）；after_start 的 `screen_linger_start`（第一格）撤單。到期 reap：無鎖先驗 token → 拿小格 lock → 鎖內重驗 token、畫面身分、`state.json` 對 `/proc` 的 loop 身分 → 先 close 再按 token 刪單；鎖忙 30 秒重排、最多 10 次。秒數在定義夾 cli.json `screen_close_after_s`（預設 600），兩格 hook 設 null＝不自動關。不讀 daemon 表、不改 C++。
- 驗：main a964f0455 的三份乾淨複本（原樣／＋A／＋A＋B）跑 proto8 全部 tests 夾，逐夾狀態相同，只多了新測試（lib/agent 135→155、templates 20→21、aos-agent 116→119）；impls 四夾與 archive 原本就紅、三份一樣。真 tmux 劇本（kf-check/cprime_real_tmux.py，自有 socket、假 claude）20～28 全過：tmux 四個前提、stop 延後關、重起撤單、sleep／wake、pause 不關、走 kernel 的 rm 不帶 purge 延後關、0 當場關、有人 attach 照關、daemon shutdown 後照關。
- 合到 main 時 knowledge/aos/cli/eca.json 與 ok-misc 的改動衝突，按鍵合（只加 screen_linger 一鍵）。
- **B 包（ctl stop 拿掉立刻關、set-def --restart 自己關、docs/02 第 6 條、test_stop_linger、test_rm_keep）沒進**：等今晚換樹把活樹 lib／templates 換新、核對 ~/aos-home 各 eca 定義與現有 stack 的 hooks.json 都有兩格後才進，否則活樹直連 stop 會沒人關畫面。合好的 B 包檔照原路徑存在 wf/temp/ok-kf/cprime/B/（清單 FILES.txt），是對 main a964f0455 的整檔版本。
- 沒做：sweeper 後援（SIGKILL／OOM、停著才開的畫面不補排）。
- 自首：驗收時 ok-kf 誤 rm -rf 了兩份自己幾分鐘前建的 main 複本（verify-cprime-base／A-a964f0455），已報 xiaosi。
- **今晚換樹清單（頂層 11-14 准排入；換不換、何時換等使用者點頭）**：(1) 活樹 lib/agent 與 templates 換新；(2) ~/aos-home 各 eca 定義的 hooks.json 補 screen_linger_start、screen_linger_stop 兩格，並核對現有 stack 的 hooks.json 沒蓋掉；(3) 換完驗 A 包在活樹生效後，才交 B 包的 commit。
