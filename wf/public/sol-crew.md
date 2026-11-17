# wf/public/sol-crew — 帶 sol（agent-fsm、gpt）隊員的心得

← [wf/public](README.md)｜掛隊員的步驟、等隊員、收隊見 [recipes-隊員](recipes-隊員.md)；排隊慢、日額、掛法的坑見 [sol-排隊與額度](sol-排隊與額度.md)；隊形規矩見 [07](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)

## 任務書怎麼寫、怎麼分工

opus eca 隊長掛 agent-fsm sol（LiteLLM sol-high）蒐集事實或寫碼時：

1. **一張單只做一件事，寫清楚能改哪些檔**。兩隻並行各管各的檔（例：wait.py 一隻、新 hook 一隻），互不干擾。
2. **事實和設計分開**：先派一隻唯讀 sol 寫 facts.md（附檔名、行號）；設計由隊長（或 fable）定；寫碼再另派。
3. **寫明「讀完必讀，同一個回合就動手」**：不寫的話，sol 第一回合可能只把必讀重點列成表就結束，隊長空等（見 [等隊員與讀信](等隊員與讀信.md)）。
4. **檔案在它腳下被別線改掉時它會停下來問**，是好事。回它「只用現在的版本，行號重抓」。
5. **隊長不在同一回合等 sol**：`subagent say` 後結束回合，用 `clock_register` 排時間叫醒自己再看；Claude Code 隊長也可以背景跑 [tools/waitdone](tools/waitdone/README.md)，答完會通知。
6. **交回的東西自己再讀一遍碼**：例如寄信漏了 `--from`（寄件人變成使用者名），測試沒抓到，是隊長讀碼才發現。

## 必讀清單要不要給

- **先看角色**：使用者 11-14 裁「按角色分」。本節給**施工的** sol；蒐集員、審稿員只讀知識庫入口加站台層、任務書不附必讀清單，照 [kits](../workflows/dispatch/kits/README.md) 與 [card 第 3 步](../workflows/dispatch/kits/card.md)（產品版看包在 `proto8/templates/kits/`）。
- sol 很聽話：system 寫「先讀」，它照順序全讀才讀程式；要它在答案末行自報讀了哪幾份，自報跟 history.jsonl 對得上。
- 代價：每隻多約 5 萬 prompt token（必讀 7 份）。沒給清單的對照組在同一組規矩題也全對（它從 AGENTS.md 進去、跑 index_view、grep 自己找到）；清單換來的是路線固定、出處一致。
- **做法**：system 放清單，要它末行自報讀了哪幾份，方便核對。純蒐集的小雜活照 [aos-teams 入口「讀規矩」](../workflows/dispatch/aos-teams.md)（簡單工作與雜活例外，可免讀），在任務書寫明可免讀或略讀（max_lines），不必改定義。

## sol 被 [aos] guard 誤擋：隊長代跑唯讀搜尋，結果寫成檔交它

sol 的 shell 有 guard，擋字面含 `rm`、`kill`、`aos-*` 等的指令。guard 比對**指令字面**、不看意圖；純唯讀的簡單指令（`rg`、`grep`、`cat`、`pgrep` 這類，條件見 [tools/fsm-guard](tools/fsm-guard/README.md)「Relaxed shell check」）會跳過比對，其他寫法（`find`、`xargs`、`$(…)`、轉向到檔…）的唯讀查詢照樣會被擋。sol 被擋就停下報 BLOCKED，這是對的。

- **不要**叫 sol 改寫字面繞開（`"ki""ll"`、`r[m]`）：上層指示禁止繞 guard，它拒絕合理，白耗一輪。
- 隊長自己跑那些唯讀搜尋，結果寫成檔（例 `tickets/T15-search.txt`），可附它要的檔案全文、名字出現次數；告訴 sol：「用檔案工具讀這個檔；不要再跑被擋過的指令；還缺什麼列給我，我來跑。」
- 行程檢查（pgrep、ps）一律隊長做，任務書直接寫「行程檢查不用做」。
- 預防：開任務書時先想會不會用到含 `rm`、`kill`、`aos-` 的字面，會的話先跑好、附在任務書旁。

## rlimit 實測與腦額度

資源鍵、預設值、腦額度的規矩在 [07「sol 走 agent-fsm」](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)（rlimit 與腦額度兩條）；這裡是實測：

| 限制 | 值 | 結果 |
|---|---|---|
| mem_mb（AS） | 64、32MB | 正常；只壓 AS 時 aos-loop VmPeak 約 20MB。給 2GB 時 VmPeak 到 151MB，是 glibc arena 隨上限放大，不是真用到 |
| files（NOFILE） | 32 | 正常 |
| files（NOFILE） | 8 | 停機：`PostFailed aos-post cannot start ... [Errno 24] Too many open files`；daemon 標 stopped，信留在 queue/new |
| cpu_s | 2 | 正常但沒用：RLIMIT_CPU 按單一程序計，每格是新程序，管不到總 CPU；總量要 cgroup `cpu.max` |

- 建議範圍 mem_mb 1024～2048、files 256～4096（預設 `{"mem_mb":1024,"files":256}`），`procs` 別設。
- subagent 的父程序是 daemon、不是掛它的 eca：對 eca 下 prlimit 不會傳下去，要在 add 時帶 `limits`。對跑著的 aos-loop 下 prlimit 馬上生效，之後每格新起的子程序都繼承。
- 腦額度：每隻 sol 一份 llm kernel 的 `budget.senders`，key 是 sol 的 stack 路徑；用光被拒 `BudgetMissing`。窗是 `all`（永不重置）時直接 BLOCKED 停下，要調高額度再叫起來（窗怎麼分見知識庫 `aos/brain.json#/priority`）。暫存 kernel 整隊共用的日額見 [sol-排隊與額度](sol-排隊與額度.md)。
