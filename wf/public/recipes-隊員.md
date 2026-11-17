# wf/public/recipes-隊員 — 掛隊員、等隊員、收隊、給 sol 寫任務書（任務類型→做法）

← [wf/public](README.md)｜[recipes 總頁](recipes.md)

每列一行做法，細節在出處。標「聽說」的是文件有寫、還沒人回報照做過；其餘都有人照做成功。

<!-- wf-nav -->
| 要做的事 | 做法（一行） | 出處／細節 |
|---|---|---|
| 掛一隻 gpt 的 agent-fsm 隊員 | `agent_def new` 範本 agent-fsm（`llm.json` 是 `{"model":"sol-high"}`，`.env` 或 `envs` 帶 `AOS_LLM_KERNEL=<llm-gpt 的 stack>`）→ `subagent add` 帶 `limits` | [aos-teams 入口第 3 件](../workflows/dispatch/aos-teams.md)、[skyrim-agentctl 03「實際的隊形」](../../proto8/thinking/2026-11/14/skyrim-agentctl/03-隊形心得.md) |
| 派蒐集員或審稿員（fsm sol） | 範本 agent-fsm 蓋上 `wf/workflows/dispatch/kits/gather/` 的 system、tools、llm、.env；沒有 shell、改不了自己；任務書不附必讀清單（聽說） | [kits](../workflows/dispatch/kits/README.md)、[card](../workflows/dispatch/kits/card.md) |
| 隊員命名 | `<eca名>-<角色>-<編號>`，例 `ok-kf-sol-1` | [07「sol 走 agent-fsm」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md) |
| 給 fsm 隊員設資源上限 | add 時帶 `limits`：sol 預設 `{"mem_mb":1024,"files":256}`；`procs` 別設；對 eca 下 prlimit 傳不到隊員 | [07「sol 走 agent-fsm」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)、[sol-crew「rlimit 實測」](sol-crew.md#rlimit-實測與腦額度) |
| 讓 gpt 隊員一路做到完、不要只回「我會做」 | 定義掛 `goal` 工具；任務書寫「第一步 goal set；輸出檔寫完才可以用純文字回答」 | [skyrim-agentctl 03「摩擦」](../../proto8/thinking/2026-11/14/skyrim-agentctl/03-隊形心得.md) |
| 唯讀蒐集的隊員怎麼擋寫檔 | 工具不給 shell 與刪除包；`write`／`edit` 加一個 `before_tool` hook 只准寫指定夾（exit 10＝擋） | 同上「實際的隊形」 |
| 等隊員做完 | `say` 完就結束這一輪，叫隊員做完 `mailbox_send` 給你；要等就 clock 叫醒自己再 `listen` 帶 `last: 1`，或背景跑 [tools/waitdone](tools/waitdone/README.md)；`listen` 帶 `timeout_s` 60 以內 | [等隊員與讀信](等隊員與讀信.md)、[aos-teams 入口第 4 件](../workflows/dispatch/aos-teams.md) |
| 看隊員是在寫、在等腦、還是停了 | 看三樣：`<stack>/stage.txt`（idle／think／wait／act）、`history.jsonl` 的修改時間、`llm-gpt/requests/cur` 與 `new` 有沒有它的信 | [skyrim-agentctl 03「摩擦」](../../proto8/thinking/2026-11/14/skyrim-agentctl/03-隊形心得.md) |
| 看誰用了多少腦 | 讀 `<活樹>/ws/.stack/procs/llm-gpt/ledger.jsonl`，照 `sender` 加總 `usage` 與 `elapsed_ms` | 同上「數字」 |
| 收隊 | `subagent rm <名>`（stack 留著）；自己開過 gate 就 `kernel_gate off`；核對當初記的 pid 都不在 | 同上 |
| 給 sol 寫任務書 | 一張單一件事、寫明可改哪些檔；事實（唯讀 sol）與設計分開；寫「讀完必讀，同一回合就動手」；交回的碼隊長自己再讀 | [sol-crew「任務書」](sol-crew.md) |
| **施工的** sol 要不要給必讀清單 | system 放清單、要它末行自報讀了哪幾份；雜活寫免讀或略讀。蒐集員、審稿員不用給（使用者 11-14 裁按角色分） | [sol-crew「必讀清單」](sol-crew.md) |
| sol 被 guard 擋了唯讀查詢 | 不叫它改寫字面繞；隊長代跑搜尋、結果寫成檔叫它讀；行程檢查隊長做 | [sol-crew「guard」](sol-crew.md) |
| sol 開工半小時幾乎沒動 | 看 history：只有十幾行、沒有改動就是在排隊。小題隊長自己讀；大盤點、大施工經部長同意改派 Claude 子 agent | [sol-排隊與額度](sol-排隊與額度.md) |
| 派 sol 在暫存複本施工 | 任務書寫死五句：只改暫存複本、別人的檔不碰、先跑改動前基準、證明新測試會紅、貼真實輸出尾巴 | [sol-排隊與額度「施工員的任務書」](sol-排隊與額度.md) |
| 派 Claude 子 agent 做超過幾分鐘的事 | 前景跑；邊做邊寫 `progress.md`；可寫路徑寫成唯一一個絕對路徑、/tmp 也不行；結果放在最後一則回答 | [claude子agent](claude子agent.md) |
