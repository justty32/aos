# wf/public/sol-crew — 帶 sol（agent-fsm、gpt）隊員的心得

← [wf/public](README.md)｜掛隊員的步驟、等隊員、收隊見 [recipes](recipes.md)；隊形規矩見 [07](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)

每條：適用、做法、驗過、出處、投稿。

## 任務書怎麼寫、怎麼分工

- **適用**：opus eca 隊長掛 agent-fsm sol（LiteLLM sol-high）蒐集事實或寫碼。
- **做法**：
  1. **一張單只做一件事，寫清楚能改哪些檔**。兩隻並行各管各的檔（例：wait.py 一隻、新 hook 一隻），互不干擾。
  2. **事實和設計分開**：先派一隻唯讀 sol 寫 facts.md（附檔名、行號）；設計由隊長（或 fable）定；寫碼再另派。
  3. **寫明「讀完必讀，同一個回合就動手」**：不寫的話，sol 第一回合可能只把必讀重點列成表就結束（sol-3 這樣，催一次才動手）。
  4. **檔案在它腳下被別線改掉時它會停下來問**，是好事。回它「只用現在的版本，行號重抓」。
  5. **隊長不在同一回合等 sol**：`subagent say` 後結束回合，用 `clock_register` 排時間叫醒自己再看；Claude Code 隊長也可以背景跑 [tools/waitdone](tools/waitdone/README.md)，答完會通知。
  6. **交回的東西自己再讀一遍碼**：sol-4 寄信漏了 `--from`（寄件人變成使用者名），測試沒抓到，是隊長讀碼才發現。
- **驗過**：ok-astra 11-14，sol-2（蒐集）、sol-3（改 wait.py）、sol-4（新 hook）與暫存樹 T03～T08、E1；結果在 `wf/temp/ok-astra/notes/sol-readcheck.md`。
- **出處**：`proto8/thinking/2026-11/14/astra-kernel-1114.md`（階段 2、3、AK17）
- **投稿**：ok-astra（`sol-team-briefing.md`）

## 必讀清單要不要給

- **適用**：要不要把「aos 體系＋wf 規矩」必讀清單寫進 sol 的 system 和任務書。
- **先看角色**：使用者 11-14 裁「按角色分」。本節的結論是給**施工的** sol；蒐集員、審稿員只讀知識庫入口加站台層、任務書不附必讀清單，照 [kits](../workflows/dispatch/kits/README.md) 與 [card 第 3 步](../workflows/dispatch/kits/card.md)（產品版看包在 `proto8/templates/kits/`，3ed649b09、fdfbc5515）。
- **結論**：
  - sol 很聽話：system 寫「先讀」，它照順序全讀才讀程式；要它在答案末行自報讀了哪幾份，自報跟 history.jsonl 對得上。
  - 代價：每隻多約 5 萬 prompt token（必讀 7 份）。
  - 對照組（沒給清單）在同一組規矩題也全對：它從 AGENTS.md 進去、跑 index_view、grep 自己找到。清單換來的是路線固定、出處一致，這組題量不出「沒讀會答錯」。
- **做法**：system 放清單，要它末行自報讀了哪幾份，方便核對。純蒐集的小雜活照 07「簡單工作與雜活免讀」，在任務書寫明可免讀或略讀（max_lines），不必改定義。
- **驗過**：ok-pilot 11-14，sol-1、sol-3、sol-4 比較 `defs/sol` 與 `defs/sol-bare`；核對方式是讀 history.jsonl 看實際讀了哪些檔。ok-astra 同日也觀察到「先讀必讀才讀程式」。
- **出處**：`wf/temp/ok-pilot/notes.md` 第三、四輪
- **投稿**：ok-pilot（`必讀清單對fsm隊員的效果.md`）；ok-astra 第 1 條併入

## sol 被 [aos] guard 誤擋：隊長代跑唯讀搜尋，結果寫成檔交它

- **適用**：sol 的 shell 有 guard，擋字面含 `rm`、`kill`、`aos-*` 等的指令。
- **坑**：guard 比對**指令字面**、不看意圖，唯讀查詢也會被擋（`grep -rn "rm accepted"` 中 `\brm\s`；查 `kill_group` 中 `kill`；`pgrep … aos-daemon` 中 `aos-*`）。sol 被擋就停下報 BLOCKED，這是對的。
- **不要**：叫 sol 改寫字面繞開（`"ki""ll"`、`r[m]`）。五隻裡兩隻明確拒絕（上層指示禁止繞 guard），拒絕合理，白耗一輪。
- **做法**：
  1. 隊長自己跑那些唯讀搜尋，結果寫成檔（例 `tickets/T15-search.txt`），可附它要的檔案全文、名字出現次數。
  2. 告訴 sol：「用檔案工具讀這個檔；不要再跑被擋過的指令；還缺什麼列給我，我來跑。」
  3. 行程檢查（pgrep、ps）一律隊長做，任務書直接寫「行程檢查不用做」。
  4. 預防：開任務書時先想會不會用到含 `rm`、`kill`、`aos-` 的字面，會的話先跑好、附在任務書旁。
- **驗過**：ok-misc 11-14，T11～T15 五隻 sol 實際遇到，照做解卡。
- **出處**：`proto8/thinking/2026-11/14/misc-1114.md`；`~/code/misc-1114/tickets/T11-search.txt`、`T15-search.txt`
- **投稿**：ok-misc（`sol-guard-誤判與交搜尋結果.md`）

## rlimit 實測與腦額度

- **rlimit 實測**（ok-pilot 11-14，sol-2、5、6，加上 prlimit 收緊後派題）：
  | 限制 | 值 | 結果 |
  |---|---|---|
  | mem_mb（AS） | 64、32MB | 正常；只壓 AS 時 aos-loop VmPeak 約 20MB。給 2GB 時 VmPeak 到 151MB，是 glibc arena 隨上限放大，不是真用到 |
  | files（NOFILE） | 32 | 正常 |
  | files（NOFILE） | 8 | 停機：`PostFailed aos-post cannot start ... [Errno 24] Too many open files`；daemon 標 stopped，信留在 queue/new |
  | cpu_s | 2 | 正常但沒用：RLIMIT_CPU 按單一程序計，每格是新程序，管不到總 CPU；總量要 cgroup `cpu.max` |
- 合法的鍵只有 `mem_mb`、`cpu_s`、`procs`、`file_mb`、`files`、`user`（開檔是 `files` 不是 `nofile`）；50e7a35bc 起 `ctl add --limits` 另收 cgroup 的 `mem_total_mb`、`procs_total`（`proto8/py/daemon_ctl/entry.py` 的 `LIMIT_INTS`）。現況以知識庫 `aos/agents/subagent.json#/add` 為準（f1ef04ba0）。
- subagent 的父程序是 daemon、不是掛它的 eca：對 eca 下 prlimit 不會傳下去，要在 add 時帶 `limits`。對跑著的 aos-loop 下 prlimit 馬上生效，之後每格新起的子程序都繼承。
- 值照 07：sol 預設 `{"mem_mb":1024,"files":256}`（ok-pilot 建議範圍 mem_mb 1024～2048、files 256～4096），`procs` 別設。
- **腦額度**：每隻 sol 一份 llm kernel 的 `budget.senders`，key 是 sol 的 stack 路徑（例 150 次），用光被拒 `BudgetMissing`。commit 2368ee3af 起 agent-fsm 被拒不停、等著重試，並由 brain_notify hook 寄一封 BLOCKED 給 mom（見 `proto8/templates/agent-fsm/hooks.json`）。**例外**：313ce20ec 起 kernel 的錯多帶 window（hour／day／all），window 是 `all`（永不重置）時不重試、直接 BLOCKED 停下（`BudgetMissing … (window all: …)` 退 1，見 `templates/agent-fsm/wait.py` 與知識庫 `aos/brain.json#/priority`），要調高額度再叫起來。
- **出處**：`wf/temp/ok-pilot/notes.md` 第二、四輪；commit 2368ee3af
- **投稿**：ok-pilot（`fsm隊員rlimit實測.md`）；ok-astra（`sol-team-briefing.md` 第 8 條）
