# wf/public/recipes-隊員 — 掛隊員、等隊員、收隊、給 sol 寫任務書（任務類型→做法）

← [wf/public](README.md)｜[recipes 總頁](recipes.md)

每列只寫一行做法與出處，細節在出處。投稿：只追加列；做法變了改那一列並在「驗過」欄換日期。狀態：**驗過**＝有人實際照做成功；**聽說**＝文件有寫、還沒人回報照做過。

| 要做的事 | 做法（一行） | 出處／細節 | 驗過 |
|---|---|---|---|
| 掛一隻 gpt 的 agent-fsm 隊員（活樹裡） | `agent_def new` 從 `agent-fsm` 複製 → 改 `llm.json` 為 `{"model":"sol-high"}`（或 `astra-high`）→ `subagent add`，`envs` 帶 `AOS_LLM_KERNEL=<活樹>/ws/.stack/procs/llm-gpt` | [skyrim-agentctl 03「實際的隊形」](../../proto8/thinking/2026-11/14/skyrim-agentctl/03-隊形心得.md) | 11-14 ok-skyrim |
| 隊員命名 | `<eca名>-<角色>-<編號>`，例 `ok-kf-sol-1` | [07「命名」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md) | 11-14 |
| 給 fsm 隊員設資源上限 | `subagent add`／`ctl add` 帶 `limits`：sol 預設 `{"mem_mb":1024,"files":256}`；`procs` 別設；對 eca 下 prlimit 傳不到隊員 | [07「rlimit」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)、[sol-crew「rlimit 實測」](sol-crew.md) | 11-14 ok-pilot |
| 讓 gpt 隊員一路做到完、不要只回「我會做」 | 定義掛 `goal` 工具；任務書寫「第一步 goal set；輸出檔寫完才可以用純文字回答」 | [skyrim-agentctl 03 摩擦 1](../../proto8/thinking/2026-11/14/skyrim-agentctl/03-隊形心得.md) | 11-14 ok-skyrim |
| 唯讀蒐集的隊員怎麼擋寫檔 | 工具不給 shell 與刪除包；`write`／`edit` 加一個 `before_tool` hook 只准寫指定夾（exit 10＝擋） | 同上「實際的隊形」 | 11-14 ok-skyrim |
| 等隊員做完 | `say` 交代完就結束這一輪，叫隊員做完 `mailbox_send` 給你；真的要當場等，用短迴圈看 `<隊員 stack>/stage.txt` 變 `idle`，每輪三分鐘內；Claude Code 隊長可背景跑 [tools/waitdone](tools/waitdone/README.md)（看 `history.jsonl` 末行是不帶 tool_calls 的 assistant）。**不要用 `subagent listen` 等超過 60 秒的事**（活樹換樹前仍會被砍） | 同上摩擦 2、[aos-teams 入口第 4 件「等隊員」](../workflows/dispatch/aos-teams.md)、[tools/waitdone](tools/waitdone/README.md)、踩過的樣子在 [等隊員與讀信](等隊員與讀信.md) | 11-14 ok-skyrim、ok-llmk2、ok-view、ok-misc |
| 看隊員是在寫、在等腦、還是停了 | 看三樣：`<stack>/stage.txt`（idle／think／wait／act）、`history.jsonl` 的修改時間、`llm-gpt/requests/cur` 與 `new` 有沒有它的信 | 同上摩擦 3 | 11-14 ok-skyrim |
| 看誰用了多少腦 | 讀 `<活樹>/ws/.stack/procs/llm-gpt/ledger.jsonl`，照 `sender` 加總 `usage` 與 `elapsed_ms` | 同上「數字」 | 11-14 ok-skyrim |
| 收隊 | `subagent rm <名>`（stack 留著）；自己開過 gate 就 `kernel_gate off`；核對當初記的 pid 都不在 | 同上 | 11-14 ok-skyrim |
| 給 sol 寫任務書 | 一張單一件事、寫明可改哪些檔；事實（唯讀 sol）與設計分開；寫「讀完必讀，同一回合就動手」；交回的碼隊長自己再讀 | [sol-crew「任務書」](sol-crew.md) | 11-14 ok-astra |
| **施工的** sol 隊員要不要給必讀清單 | system 放清單、要它末行自報讀了哪幾份；雜活在任務書寫免讀或略讀。蒐集員、審稿員不用給，看下面「派蒐集員或審稿員」那列的看包（使用者 11-14 裁按角色分） | [sol-crew「必讀清單」](sol-crew.md) | 11-14 ok-pilot |
| sol 被 [aos] guard 誤擋唯讀查詢（字面含 rm／kill／aos-） | 不叫它改寫字面繞；隊長代跑搜尋、結果寫成檔叫它讀；行程檢查隊長做 | [sol-crew「guard」](sol-crew.md) | 11-14 ok-misc |
| 派蒐集員或審稿員（fsm sol） | `agent_def new` 範本 agent-fsm，蓋上 `wf/workflows/dispatch/kits/gather/` 的 system、tools、llm、.env；工具 24 支，沒有 shell、改不了自己；任務書不用附必讀清單 | [kits](../workflows/dispatch/kits/README.md)、[card](../workflows/dispatch/kits/card.md) | 聽說（11-14 ok-onboard，agent_def check 過，還沒真跑） |
| sol 開工半小時幾乎沒動 | 看它的 history：只有十幾行、沒有改動就是在排隊（sol 名額全體共用）。小題隊長自己讀；大盤點、大施工經部長同意改派 Claude 子 agent，任務書照用 | [sol-排隊與額度](sol-排隊與額度.md) | 11-14 ok-sec、ok-devt、ok-kb、ok-kmsg |
| 派 Claude 子 agent 做超過幾分鐘的事 | 前景跑（`run_in_background: false`）；叫它邊做邊寫 `progress.md`；可寫路徑寫成唯一一個絕對路徑、寫明 /tmp 也不行；結果要它放在最後一則回答 | [claude子agent](claude子agent.md) | 11-14 ok-onboard、head-front、ok-board、ok-limits、ok-kb |
| 派 sol 在暫存複本施工 | 任務書寫死五句：只改暫存複本、別人的檔不碰、先跑改動前基準、證明新測試會紅、貼真實輸出尾巴 | [sol-排隊與額度「sol 施工員的任務書」](sol-排隊與額度.md) | 11-14 ok-kmsg |
