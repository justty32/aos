# wf/public/sol-crew — 帶 sol（agent-fsm、gpt）隊員：任務書、guard、資源、排隊與額度

← [wf/public](README.md)｜掛隊員的步驟、等隊員、收隊見 [recipes](recipes.md)；隊形規矩見 [07](../workflows/dispatch/aos-teams/07-預設流程與agent-fsm.md)

## 任務書怎麼寫、怎麼分工

opus eca 隊長掛 agent-fsm sol（LiteLLM 的 `sol`，`reasoning_effort` high）蒐集事實或寫碼時：

1. **一張單只做一件事，寫清楚能改哪些檔**。兩隻並行各管各的檔，互不干擾。
2. **事實和設計分開**：先派一隻唯讀 sol 寫 facts.md（附檔名、行號）；設計由隊長（或 fable）定；寫碼再另派。
3. **寫明「讀完必讀，同一個回合就動手」**：不寫的話，sol 第一回合可能只把必讀重點列成表就結束，隊長空等（[等隊員與讀信](等隊員與讀信.md)）。
4. **檔案在它腳下被別線改掉時它會停下來問**，是好事。回它「只用現在的版本，行號重抓」。
5. **隊長不在同一回合等 sol**：`subagent say` 後結束回合，用 `clock_register` 叫醒自己再看；Claude Code 隊長也可以背景跑 [tools/waitdone](tools/waitdone/README.md)。
6. **交回的東西自己再讀一遍碼**：例如寄信漏了 `--from`（寄件人變成使用者名），測試沒抓到，是隊長讀碼才發現。

## sol 施工員的任務書：五句寫死，驗收只要讀 diff、重跑新測試

派 sol 在暫存複本裡改程式、補測試時，寫死「只改暫存複本」「另一位在改哪些檔你不碰」「先跑改動前基準」「證明新測試會紅（暫時改回舊碼）」「貼真實輸出尾巴」。

## 必讀清單要不要給

- **先看角色**：使用者 11-14 裁「按角色分」。本節給**施工的** sol；蒐集員、審稿員只讀知識庫入口加站台層、任務書不附必讀清單，照 [kits](../workflows/dispatch/kits/README.md) 與 [card 第 3 步](../workflows/dispatch/kits/card.md)（產品版看包在 `proto8/templates/kits/`）。
- sol 很聽話：system 寫「先讀」，它照順序全讀才讀程式；要它在答案末行自報讀了哪幾份，自報跟 history.jsonl 對得上。
- 代價：每隻多約 5 萬 prompt token（必讀 7 份）。沒給清單的對照組在同一組規矩題也全對；清單換來的是路線固定、出處一致。
- **做法**：system 放清單，要它末行自報讀了哪幾份。純蒐集的小雜活照 [aos-teams 入口「讀規矩」](../workflows/dispatch/aos-teams.md)（簡單工作與雜活可免讀），在任務書寫明可免讀或略讀（max_lines），不必改定義。

## sol 被 [aos] guard 誤擋：隊長代跑唯讀搜尋，結果寫成檔交它

sol 的 shell 有 guard，擋字面含 `rm`、`kill`、`aos-*` 等的指令。guard 比對**指令字面**、不看意圖；純唯讀的簡單指令（`rg`、`grep`、`cat`、`pgrep` 這類，條件見 [tools/fsm-guard](tools/fsm-guard/README.md)「Relaxed shell check」）會跳過比對，其他寫法（`find`、`xargs`、`$(…)`、轉向到檔…）的唯讀查詢照樣會被擋。sol 被擋就停下報 BLOCKED，這是對的。

- **不要**叫 sol 改寫字面繞開（`"ki""ll"`、`r[m]`）：上層指示禁止繞 guard，它拒絕合理，白耗一輪。
- 隊長自己跑那些唯讀搜尋，結果寫成檔（例 `tickets/T15-search.txt`），可附它要的檔案全文、名字出現次數；告訴 sol：「用檔案工具讀這個檔；不要再跑被擋過的指令；還缺什麼列給我，我來跑。」看包的 sol 沒有 shell，量檔案大小這類事也由隊長代跑。
- 行程檢查（pgrep、ps）一律隊長做，任務書直接寫「行程檢查不用做」。
- 預防：開任務書時先想會不會用到含 `rm`、`kill`、`aos-` 的字面，會的話先跑好、附在任務書旁。

## 掛法的幾個坑

- **沒帶 `AOS_LLM_KERNEL`**：第一個 brain call 就 `LlmKernelMissing`。改成 `~/aos-home` 一套的機器（公司那台 11-23 起），這個值由上層 daemon 那一列傳下來，[kits/gather](../workflows/dispatch/kits/README.md) 的 `.env` 不用抄；還沒改的機器才要定義的 `.env` 帶它，或 `subagent add` 的 `envs` 帶 `{"AOS_LLM_KERNEL": "<llm kernel 的 stack>"}`（見 [03-換機](../workflows/dev-env/03-換機.md)）。
- **要開 headless Chrome 的隊員不能設 `mem_mb`**：AS 上限讓 Chrome 起不來，改用 `limits {"files":4096}`。
- **停下來的訊息措辭會改變行為**：hook 訊息寫 `Stop and report this as BLOCKED`，sol 就把整份工作丟掉。要接進流程的訊息，接線前拿真 sol 試一次。
- **借別線的假 agent 腳本先看信的格式**：例 `aos-agent say` 的信是 `{"body":{"role","content"}}`，照 `m["content"]` 讀會 `KeyError`。

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
- 腦額度：每隻 sol 一份 llm kernel 的 `budget.senders`，key 是 sol 的 stack 路徑；用光被拒 `BudgetMissing`。窗是 `all`（永不重置）時直接 BLOCKED 停下，要調高額度再叫起來（窗怎麼分見知識庫 `aos/brain.md#/Priority and budgets`）。
- **暫存 llm kernel 的日額會讓整隊一起停**：自己暫存樹起的 kernel，sol 那包端點（11-14 那時叫 sol-high）有每日 `max_calls`（例 600），幾隻 sol 同一天用完就全部 `BudgetMissing … reached in this window (day)`。kernel 每輪重讀 kernel.json，改了數字 `ctl start` 就能繼續，不用重起 kernel；正在答的那則會丟掉，要重新 say 一次。

## sol 排隊很慢：小題隊長自己讀，大盤點或大施工改派 Claude 子 agent

llm kernel 的 sol 名額全體共用（11-14 那時是舊樹 llm-gpt 的 sol-high，只有兩三個），十幾條線同時派 sol 時，開工半小時只寫幾百位元組、蒐集員近一小時沒交稿都會發生。

1. 先判斷是不是卡住：看 sol 的 history，只有十幾行、沒有改動，就是在排隊。
2. 小題目不必等蒐集：隊長自己讀關鍵六七個檔把設計寫出來，把蒐集員停掉、名額讓給施工員。
3. 大量對程式的盤點、大施工：經 eca-aos 同意改派 Claude 子 agent，任務書照用同一份（通常一小時內交回），也要守額度時段；sol 留給範圍小、路徑明確的題。原來的 sol 用 `subagent rm` 收（只是下表，stack 留著）。
4. 任務書也有責任：一張單塞八段題目、先要它讀六份必讀，會更慢（照上面「任務書」）。

## 縮工具清單之前先量它佔提示的幾成；快取命中低先看 session id

想省 sol 的額度時：

- 照問腦時實際送出的樣子量工具清單（`{type, function:{name, description, parameters}}` 的 JSON 字元數），跟帳本上後段的提示大小比。例：55 支約 2 萬 token，後段提示 7～15 萬，拿掉四成工具整體只省約一成。
- 帳本 `ledger.jsonl` 上 `cached_tokens/prompt_tokens` 只中一個固定的小數字、自己的對話一次都不中：是請求沒帶固定的 session id（pack 的 `session_key`）；帶了命中八成以上，不帶兩三成。
- 驗「請求開頭有沒有變」：對自己隊員的 `think/request.json` 隔一分鐘各取一次，只存各段的雜湊比對，不存內容、不讀別線的 history。對照實驗要兩隻同時跑、各做一樣大小的真工作。
